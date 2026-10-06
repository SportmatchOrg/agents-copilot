"""Lógica pura del reporte diario de KPIs (ADR-001 de SportMatch).

Todo lo que se puede probar sin red vive acá: fechas, p95, mediana, filtro de
PRs, validación de la respuesta del back y armado del lote. `report.py` solo
hace I/O y llama a estas funciones.

La regla que atraviesa todo el módulo: **sin muestra no hay valor**. Un KPI sin
denominador queda `NO_DATA` con `value = None`, nunca `0`. Y la publicación es
atómica: si uno de los diez no está `READY`, no se publica ninguno.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")
WINDOW_DAYS = 30
HEALTH_SAMPLES = 20
HEALTH_TIMEOUT_MS = 10_000

READY = "READY"
NO_DATA = "NO_DATA"
ERROR = "ERROR"

CATALOG_PATH = Path(__file__).resolve().parent / "kpi-catalog.json"
# Columnas que acepta `kpi_catalog` en la plataforma de la cátedra. `origin` es
# nuestro (quién calcula el KPI) y PostgREST rechaza columnas desconocidas.
CATALOG_COLUMNS = ("id", "kind", "unit", "name", "description", "source", "aggregation", "justification")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


class InputError(ValueError):
    """Un input del workflow es inválido. El mensaje es seguro para loguear."""


# ── Catálogo ─────────────────────────────────────────────────────────────────

def load_catalog(path: Path = CATALOG_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_ids(catalog: list[dict], origin: str | None = None) -> list[str]:
    return [k["id"] for k in catalog if origin is None or k["origin"] == origin]


def catalog_rows(catalog: list[dict]) -> list[dict]:
    """Filas para `POST /rest/v1/kpi_catalog`, sin las columnas propias."""
    return [{col: k[col] for col in CATALOG_COLUMNS if col in k} for k in catalog]


# ── Fechas (siempre en hora de Buenos Aires) ────────────────────────────────

def today_ar(now: datetime) -> date:
    return now.astimezone(ARGENTINA).date()


def resolve_measurement_date(raw: str | None, now: datetime) -> date:
    """La fecha medida: la pedida, o ayer en Buenos Aires.

    Tiene que ser un día completo: hoy todavía no terminó y una fecha futura la
    rechaza el dashboard.
    """
    yesterday = today_ar(now) - timedelta(days=1)
    value = (raw or "").strip()
    if not value:
        return yesterday
    if not _DATE_RE.match(value):
        raise InputError(f"date debe tener formato YYYY-MM-DD (llegó {value!r})")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise InputError(f"date no es una fecha válida: {value!r}") from error
    if parsed > yesterday:
        raise InputError(f"date tiene que ser como máximo ayer ({yesterday.isoformat()})")
    return parsed


def window_bounds(measured: date) -> tuple[datetime, datetime]:
    """`[D-29 00:00, D+1 00:00)` en Buenos Aires, como datetimes con zona."""
    start = datetime.combine(measured - timedelta(days=WINDOW_DAYS - 1), time.min, ARGENTINA)
    end = datetime.combine(measured + timedelta(days=1), time.min, ARGENTINA)
    return start, end


def parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


# ── Estadística ──────────────────────────────────────────────────────────────

def percentile_nearest_rank(values: list[float], pct: float) -> float | None:
    """Percentil por rango más cercano: el valor que deja `pct` % por debajo.

    Con 20 muestras y p95 es el valor 19 de la lista ordenada. No interpola: el
    resultado siempre es una latencia que realmente se midió.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[max(rank, 1) - 1]


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def round2(value: float) -> float:
    return round(value, 2)


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# ── KPIs externos ────────────────────────────────────────────────────────────

def result(kpi_id: str, status: str, value: float | None = None, **detail) -> dict:
    return {"kpiId": kpi_id, "status": status, "value": value, "detail": detail}


def health_results(samples: list[dict]) -> list[dict]:
    """`health_latency_p95` y `api_reachable` a partir de las 20 llamadas.

    Cada muestra es `{"ms": float, "ok": bool, "status": int}`. Las fallidas
    cuentan con lo que tardaron (o el timeout): una caída sube el p95 en vez de
    esconderse.
    """
    durations = [s["ms"] for s in samples]
    p95 = percentile_nearest_rank(durations, 95)
    ok_count = sum(1 for s in samples if s["ok"])
    latency = (
        result("health_latency_p95", READY, round2(p95), samples=len(samples), ok=ok_count)
        if p95 is not None
        else result("health_latency_p95", NO_DATA, samples=0)
    )
    reachable = result("api_reachable", READY, 1 if ok_count else 0, samples=len(samples), ok=ok_count)
    return [latency, reachable]


def is_bot(pr: dict) -> bool:
    user = pr.get("user") or {}
    return user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]")


def merged_in_window(prs: list[dict], start: datetime, end: datetime) -> list[dict]:
    """PRs humanos mergeados dentro de la ventana. La base ya viene filtrada."""
    selected = []
    for pr in prs:
        if not pr.get("merged_at") or is_bot(pr):
            continue
        merged = parse_github_datetime(pr["merged_at"])
        if start <= merged < end:
            selected.append(pr)
    return selected


def pr_lead_time_result(prs: list[dict]) -> dict:
    hours = [
        (parse_github_datetime(pr["merged_at"]) - parse_github_datetime(pr["created_at"])).total_seconds() / 3600
        for pr in prs
    ]
    value = median(hours)
    if value is None:
        return result("pr_lead_time", NO_DATA, sample=0)
    return result("pr_lead_time", READY, round2(value), sample=len(hours), prs=sorted(pr["number"] for pr in prs))


def should_stop_paging(page: list[dict], start: datetime) -> bool:
    """La API devuelve los PRs por `updated_at` descendente.

    Un PR mergeado dentro de la ventana tiene `updated_at >= merged_at >= start`:
    en cuanto aparece uno actualizado antes de `start`, ninguno de los que
    siguen puede entrar.
    """
    return not page or parse_github_datetime(page[-1]["updated_at"]) < start


# ── Respuesta del back ───────────────────────────────────────────────────────

def parse_back_response(body: object, measured: date, expected_ids: list[str]) -> tuple[str, list[dict]]:
    """Valida `POST /kpis/snapshots` y devuelve `(runId, resultados)`.

    Si la forma no es la del contrato de SPO-277, levanta `ValueError` con un
    mensaje sin datos: el workflow lo trata como error del back.
    """
    if not isinstance(body, dict):
        raise ValueError("la respuesta no es un objeto JSON")
    run_id = body.get("runId")
    if not isinstance(run_id, str) or not _UUID_RE.match(run_id):
        raise ValueError("runId falta o no es un UUID")
    if body.get("date") != measured.isoformat():
        raise ValueError("la fecha de la respuesta no coincide con la pedida")
    raw = body.get("results")
    if not isinstance(raw, list):
        raise ValueError("results falta o no es una lista")

    by_id: dict[str, dict] = {}
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("kpiId"), str):
            by_id[item["kpiId"]] = item

    results = []
    for kpi_id in expected_ids:
        item = by_id.get(kpi_id)
        if item is None:
            results.append(result(kpi_id, ERROR, reason="MISSING_FROM_BACK"))
            continue
        status = item.get("status")
        value = item.get("value")
        detail = {k: item.get(k) for k in ("numerator", "denominator", "errorCode") if item.get(k) is not None}
        if status == READY and not is_finite_number(value):
            results.append(result(kpi_id, ERROR, reason="INVALID_VALUE", **detail))
        elif status in (READY, NO_DATA, ERROR):
            results.append(result(kpi_id, status, value if status == READY else None, **detail))
        else:
            results.append(result(kpi_id, ERROR, reason="UNKNOWN_STATUS", **detail))
    return run_id, results


# ── Lote ─────────────────────────────────────────────────────────────────────

def order_like_catalog(results: list[dict], catalog: list[dict]) -> list[dict]:
    """Los diez del catálogo en su orden. El que falte queda `ERROR`."""
    by_id = {r["kpiId"]: r for r in results}
    return [by_id.get(kpi_id) or result(kpi_id, ERROR, reason="NOT_MEASURED") for kpi_id in catalog_ids(catalog)]


def blocking(results: list[dict]) -> list[dict]:
    return [r for r in results if r["status"] != READY]


def measurement_rows(results: list[dict], measured: date, env: str, run_id: str) -> list[dict]:
    """Las filas de `POST /rest/v1/measurement`. Solo con los diez `READY`."""
    if blocking(results):
        raise ValueError("no se arma un lote con KPIs que no están READY")
    return [
        {"kpi_id": r["kpiId"], "date": measured.isoformat(), "env": env, "value": r["value"], "run_id": run_id}
        for r in results
    ]


# ── Salida ───────────────────────────────────────────────────────────────────

def summary_markdown(report: dict) -> str:
    icons = {READY: "✅", NO_DATA: "⚪", ERROR: "❌"}
    lines = [
        f"### Reporte de KPIs · `{report['env']}` · {report['date']} · {report['mode']}",
        "",
        f"**Resultado:** {report['outcome']}",
        "",
    ]
    if report.get("reason"):
        lines += [f"> {report['reason']}", ""]
    lines += ["| KPI | Estado | Valor | Detalle |", "|---|---|---|---|"]
    for r in report["results"]:
        value = "—" if r["value"] is None else r["value"]
        detail = ", ".join(f"{k}={v}" for k, v in r["detail"].items() if k != "prs")
        lines.append(f"| `{r['kpiId']}` | {icons.get(r['status'], '?')} {r['status']} | {value} | {detail} |")
    if report.get("runId"):
        lines += ["", f"`run_id`: `{report['runId']}`"]
    return "\n".join(lines) + "\n"


def discord_message(report: dict | None, run_url: str) -> str:
    if report is None:
        return f"🔴 **Reporte de KPIs falló** antes de generar el resultado.\nCorrida: {run_url}"
    lines = [f"🔴 **Reporte de KPIs falló** · `{report['env']}` · {report['date']} · {report['mode']}"]
    if report.get("reason"):
        lines.append(f"Motivo: {report['reason']}")
    for r in blocking(report.get("results", [])):
        extra = r["detail"].get("reason") or r["detail"].get("errorCode") or ""
        lines.append(f"• `{r['kpiId']}`: {r['status']}" + (f" ({extra})" if extra else ""))
    lines.append("No se publicó nada en el dashboard de la cátedra.")
    lines.append(f"Corrida: {run_url}")
    return "\n".join(lines)[:1900]
