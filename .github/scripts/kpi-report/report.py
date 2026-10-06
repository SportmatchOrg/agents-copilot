#!/usr/bin/env python3
"""Reporte diario de KPIs de SportMatch al dashboard de la cátedra (ADR-001).

    report.py run      calcula, valida y (en modo report) publica
    report.py notify   avisa por Discord con el resultado de `run`

Modos (`KPI_MODE`):
  dry-run   mide los externos, llama al back y arma el lote, sin publicar.
  report    lo mismo y, si los diez están READY, un único POST al dashboard.
  catalog   da de alta los diez KPIs en `kpi_catalog`. Se corre una vez por
            ambiente; repetirlo no cambia nada (ignore-duplicates).

Nada de esto usa un modelo: es código determinístico, como exige el challenge.

Ningún secret llega a un log: los errores se reportan con códigos propios
(`BACK_HTTP_503`, `SUPABASE_HTTP_409`...) y, como mucho, el `message` que
devuelve el dashboard, que nunca contiene nuestras claves.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kpi_lib as lib  # noqa: E402

USER_AGENT = "sportmatch-kpi-report"
BACK_TIMEOUT_S = 90  # El primer request a Azure puede ser un arranque en frío.
HTTP_TIMEOUT_S = 30
PAGE_SIZE = 100
MAX_PR_PAGES = 20


class StepError(RuntimeError):
    """Un paso falló. El mensaje es un código seguro para logs y Discord."""


# ── Config ───────────────────────────────────────────────────────────────────

def env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise lib.InputError(f"falta {name}")
    return value


def out_dir() -> Path:
    path = Path(os.environ.get("KPI_OUT_DIR", "kpi-out"))
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── HTTP ─────────────────────────────────────────────────────────────────────

def request(method: str, url: str, *, headers: dict | None = None, body: object = None,
            timeout: float = HTTP_TIMEOUT_S) -> tuple[int, object, dict]:
    """Devuelve `(status, json o None, headers)`. Un error de red es status 0."""
    data = None if body is None else json.dumps(body).encode()
    all_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _json_or_none(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as error:
        return error.code, _json_or_none(error.read()), dict(error.headers or {})
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None, {}


def _json_or_none(raw: bytes) -> object:
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def supabase_message(body: object) -> str:
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"][:200]
    return ""


# ── Mediciones ───────────────────────────────────────────────────────────────

def measure_health(api_url: str) -> list[dict]:
    """20 llamadas secuenciales a `/health`, con 10 s de timeout cada una."""
    samples = []
    for _ in range(lib.HEALTH_SAMPLES):
        started = time.perf_counter()
        status, body, _ = request("GET", f"{api_url}/health", timeout=lib.HEALTH_TIMEOUT_MS / 1000)
        elapsed = (time.perf_counter() - started) * 1000
        ok = status == 200 and isinstance(body, dict) and body.get("ok") is True
        samples.append({"ms": round(elapsed if status else max(elapsed, lib.HEALTH_TIMEOUT_MS), 1),
                        "ok": ok, "status": status})
    return samples


def measure_pr_lead_time(repo: str, token: str, measured) -> dict:
    start, end = lib.window_bounds(measured)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    collected: list[dict] = []
    for page in range(1, MAX_PR_PAGES + 1):
        query = urllib.parse.urlencode({"state": "closed", "base": "dev", "sort": "updated",
                                        "direction": "desc", "per_page": PAGE_SIZE, "page": page})
        status, body, _ = request("GET", f"https://api.github.com/repos/{repo}/pulls?{query}", headers=headers)
        if status != 200 or not isinstance(body, list):
            return lib.result("pr_lead_time", lib.ERROR, reason=f"GITHUB_HTTP_{status}")
        collected.extend(body)
        if lib.should_stop_paging(body, start) or len(body) < PAGE_SIZE:
            break
    return lib.pr_lead_time_result(lib.merged_in_window(collected, start, end))


def call_back(api_url: str, api_key: str, measured, internal_ids: list[str]) -> tuple[str | None, list[dict], str]:
    """`POST /kpis/snapshots`. Devuelve `(runId, resultados, motivo de fallo)`."""
    status, body, _ = request("POST", f"{api_url}/kpis/snapshots",
                              headers={"X-Kpi-Key": api_key},
                              body={"date": measured.isoformat()}, timeout=BACK_TIMEOUT_S)
    if status != 200:
        reason = "BACK_UNREACHABLE" if status == 0 else f"BACK_HTTP_{status}"
        return None, [lib.result(k, lib.ERROR, reason=reason) for k in internal_ids], reason
    try:
        run_id, results = lib.parse_back_response(body, measured, internal_ids)
    except ValueError as error:
        reason = f"BACK_INVALID_RESPONSE: {error}"
        return None, [lib.result(k, lib.ERROR, reason="BACK_INVALID_RESPONSE") for k in internal_ids], reason
    return run_id, results, ""


# ── Dashboard de la cátedra (Supabase / PostgREST) ──────────────────────────

def supabase_headers(prefer: str) -> dict:
    return {
        "apikey": env("KPI_SUPABASE_PUBLISHABLE_KEY"),
        "X-Project-Key": env("KPI_PROJECT_KEY"),
        "Prefer": prefer,
    }


def publish(rows: list[dict]) -> None:
    url = f"{env('KPI_SUPABASE_URL')}/rest/v1/measurement?on_conflict=project_id,kpi_id,date,env"
    status, body, _ = request("POST", url, headers=supabase_headers("resolution=ignore-duplicates,return=minimal"),
                              body=rows)
    if status != 201:
        message = supabase_message(body)
        raise StepError(f"SUPABASE_HTTP_{status}" + (f": {message}" if message else ""))


def register_catalog(catalog: list[dict]) -> None:
    url = f"{env('KPI_SUPABASE_URL')}/rest/v1/kpi_catalog?on_conflict=project_id,id"
    status, body, _ = request("POST", url, headers=supabase_headers("resolution=ignore-duplicates,return=minimal"),
                              body=lib.catalog_rows(catalog))
    if status not in (200, 201):
        message = supabase_message(body)
        raise StepError(f"SUPABASE_HTTP_{status}" + (f": {message}" if message else ""))


# ── Comandos ─────────────────────────────────────────────────────────────────

def write_outputs(report: dict) -> Path:
    name = f"kpi-{report['env']}-{report['date']}-{report.get('runId') or 'sin-run'}.json"
    path = out_dir() / name
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir() / "last-report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(lib.summary_markdown(report))
    print(lib.summary_markdown(report))
    return path


def run() -> int:
    now = datetime.now(timezone.utc)
    catalog = lib.load_catalog()
    try:
        kpi_env = env("KPI_ENV")
        mode = env("KPI_MODE")
        if kpi_env not in ("dev", "prod"):
            raise lib.InputError("KPI_ENV debe ser dev o prod")
        if mode not in ("dry-run", "report", "catalog"):
            raise lib.InputError("KPI_MODE debe ser dry-run, report o catalog")
        measured = lib.resolve_measurement_date(os.environ.get("KPI_DATE"), now)
    except lib.InputError as error:
        print(f"::error title=Input inválido::{error}")
        return 1

    report = {"env": kpi_env, "mode": mode, "date": measured.isoformat(), "runId": None,
              "outcome": "", "reason": "", "results": [], "health_samples": []}

    if mode == "catalog":
        try:
            register_catalog(catalog)
            report["outcome"] = f"catálogo registrado ({len(catalog)} KPIs)"
            write_outputs(report)
            return 0
        except (StepError, lib.InputError) as error:
            report["outcome"], report["reason"] = "falló el alta del catálogo", str(error)
            write_outputs(report)
            print(f"::error title=Catálogo::{error}")
            return 1

    try:
        api_url = env("SPORTMATCH_API_URL").rstrip("/")
        api_key = env("KPI_API_KEY")
    except lib.InputError as error:
        print(f"::error title=Config::{error}")
        return 1

    # 1. Externos primero: si el back está caído, el summary igual muestra la salud.
    samples = measure_health(api_url)
    report["health_samples"] = samples
    external = lib.health_results(samples)
    external.append(measure_pr_lead_time(
        os.environ.get("SPORTMATCH_REPO", "SportmatchOrg/sportmatch"),
        os.environ.get("PR_READ_TOKEN", ""), measured))

    # 2. Los siete de negocio, calculados y guardados por el back.
    run_id, internal, back_reason = call_back(api_url, api_key, measured, lib.catalog_ids(catalog, "back"))
    report["runId"] = run_id
    report["results"] = lib.order_like_catalog(external + internal, catalog)

    # 3. Todo o nada.
    blocked = lib.blocking(report["results"])
    if blocked or not run_id:
        report["outcome"] = "bloqueado: no se publica nada"
        report["reason"] = back_reason or f"{len(blocked)} KPI sin READY"
        write_outputs(report)
        print(f"::error title=Lote bloqueado::{report['reason']}")
        return 1

    if mode == "dry-run":
        report["outcome"] = "listo para publicar (dry-run: no se publicó)"
        write_outputs(report)
        return 0

    # 4. Un único POST con las diez filas.
    try:
        publish(lib.measurement_rows(report["results"], measured, kpi_env, run_id))
    except (StepError, lib.InputError) as error:
        report["outcome"], report["reason"] = "falló la publicación: no se publicó nada", str(error)
        write_outputs(report)
        print(f"::error title=Publicación::{error}")
        return 1

    report["outcome"] = "publicado (10 KPIs)"
    write_outputs(report)
    return 0


def notify() -> int:
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        print("::warning title=Discord::sin DISCORD_WEBHOOK_PROGRESS, no se avisa")
        return 0
    last = out_dir() / "last-report.json"
    report = json.loads(last.read_text(encoding="utf-8")) if last.exists() else None
    run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
               f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}")
    status, _, _ = request("POST", webhook, body={"content": lib.discord_message(report, run_url)})
    if status not in (200, 204):
        # El job ya está fallado por el motivo original; esto solo deja rastro.
        print(f"::warning title=Discord::no se pudo avisar (HTTP {status})")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    sys.exit({"run": run, "notify": notify}.get(command, run)())
