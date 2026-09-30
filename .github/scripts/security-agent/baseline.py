#!/usr/bin/env python3
"""Chequeos de seguridad que NO necesitan modelo.

Todo lo que se puede verificar con una regla fija va acá y no en el loop: es
gratis, no alucina y corre igual con la cuota de OpenRouter agotada. El agente
recibe este resultado precargado y se concentra en lo que sí requiere criterio
(autorización entre usuarios, reglas de negocio, datos que se filtran).

Chequeos:
  BL-01  estático  endpoint sin FirebaseAuthGuard (fuera de la allowlist pública)
  BL-02  dinámico  request anónimo a un endpoint protegido no devuelve 401
  BL-03  dinámico  body con un campo de más no devuelve 400 (el DTO no valida)
  BL-04  estático  ruta estática declarada después de una con parámetro que la pisa
  BL-05  estático  SQL crudo con `$queryRawUnsafe` / `$executeRawUnsafe` en src/

Uso:  baseline.py --repo <ruta> --ctx <dir>     (el blanco tiene que estar arriba)
Lee  $CTX/endpoints.json.  Escribe  $CTX/baseline.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target  # noqa: E402

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")

# Endpoints que son públicos a propósito. Cualquier otro sin guard es hallazgo.
PUBLIC_OK = {("GET", "/"), ("GET", "/health")}
AUTH_GUARD = "FirebaseAuthGuard"

# Un id con forma de cuid que no existe: alcanza para llegar al guard y al pipe.
FAKE_ID = "cm0000000000000000secagent"
PARAM_RE = re.compile(r":\w+")


def concrete(path: str) -> str:
    return PARAM_RE.sub(FAKE_ID, path)


def finding(check: str, severity: str, title: str, ep: dict | None, detail: str,
            evidence: dict | None = None) -> dict:
    return {
        "source": "baseline",
        "check": check,
        "severity": severity,
        "title": title,
        "endpoint": f"{ep['method']} {ep['path']}" if ep else None,
        "location": f"{ep['file']}:{ep['line']}" if ep else None,
        "detail": detail,
        "evidence": evidence or {},
    }


def bl01_sin_guard(endpoints: list[dict]) -> list[dict]:
    out = []
    for ep in endpoints:
        if AUTH_GUARD in ep["guards"] or (ep["method"], ep["path"]) in PUBLIC_OK:
            continue
        out.append(finding(
            "BL-01", "alta", "Endpoint sin autenticación", ep,
            f"`{ep['handler']}` no tiene `@UseGuards({AUTH_GUARD})` ni a nivel de "
            f"método ni de controller. Cualquiera sin sesión puede llamarlo."))
    return out


def bl02_anonimo(endpoints: list[dict]) -> tuple[list[dict], list[dict]]:
    out, log = [], []
    for ep in endpoints:
        if AUTH_GUARD not in ep["guards"]:
            continue
        body = {} if ep["method"] in ("POST", "PUT", "PATCH") else None
        res = target.request(ep["method"], concrete(ep["path"]), body=body, as_user=None)
        log.append({"check": "BL-02", "endpoint": f"{ep['method']} {ep['path']}",
                    "status": res["status"]})
        if res["status"] != 401:
            out.append(finding(
                "BL-02", "alta", "Endpoint protegido responde sin sesión", ep,
                f"Sin usuario respondió {res['status']} en vez de 401.",
                {"request": res["request"], "status": res["status"], "body": res["body"]}))
    return out, log


# Tipos de body que el ValidationPipe no puede validar: no son una clase.
LOOSE_BODY_RE = re.compile(r"^(any|object|unknown|Record<.*>|\{.*\})$")


def bl03_campo_extra(endpoints: list[dict]) -> tuple[list[dict], list[dict]]:
    """Un campo de más tiene que dar 400.

    Los guards corren ANTES que los pipes: un 401/403/404 no dice nada sobre la
    validación, solo que algo cortó antes (primer falso positivo del agente, en
    `PATCH /users/:id`, donde `OwnAccountGuard` devolvía 403). Por eso solo es
    hallazgo si el handler ACEPTÓ el campo (2xx), y si un guard corta se
    reintenta con el id propio de A, que es el caso que pasa el guard de cuenta.
    """
    out, log = [], []
    me = target.request("GET", "/users/me", as_user="A")
    my_id = (me["body"] or {}).get("id") if isinstance(me["body"], dict) else None

    for ep in endpoints:
        if not ep.get("body") or AUTH_GUARD not in ep["guards"]:
            continue
        paths = [concrete(ep["path"])]
        if my_id and ":" in ep["path"]:
            paths.append(PARAM_RE.sub(my_id, ep["path"]))

        verdict, res = "no_concluyente", None
        for path in paths:
            res = target.request(ep["method"], path, body={"__secAgentExtra": True}, as_user="A")
            if res["status"] == 400:
                verdict = "ok"
                break
            if 200 <= res["status"] < 300:
                verdict = "acepta_extra"
                break
        log.append({"check": "BL-03", "endpoint": f"{ep['method']} {ep['path']}",
                    "status": res["status"], "verdict": verdict})

        if verdict == "acepta_extra":
            out.append(finding(
                "BL-03", "media", "El body no se valida contra el DTO", ep,
                f"Con un campo que no existe en `{ep['body']['type']}` respondió "
                f"{res['status']}: el handler aceptó el body. El `ValidationPipe` con "
                f"`forbidNonWhitelisted` no está actuando.",
                {"request": res["request"], "status": res["status"], "body": res["body"]}))
        elif LOOSE_BODY_RE.match(ep["body"]["type"]):
            out.append(finding(
                "BL-03", "media", "El body no se valida contra el DTO", ep,
                f"El `@Body()` está tipado como `{ep['body']['type']}`, que no es una "
                f"clase: el `ValidationPipe` no tiene contra qué validar."))
    return out, log


def _matches(param_path: str, static_path: str) -> bool:
    a, b = param_path.strip("/").split("/"), static_path.strip("/").split("/")
    return len(a) == len(b) and all(x.startswith(":") or x == y for x, y in zip(a, b))


def bl04_rutas_pisadas(endpoints: list[dict]) -> list[dict]:
    out = []
    by_file: dict[str, list[dict]] = {}
    for ep in endpoints:
        by_file.setdefault(ep["file"], []).append(ep)
    for eps in by_file.values():
        for i, first in enumerate(eps):
            if ":" not in first["path"]:
                continue
            for later in eps[i + 1:]:
                if (later["method"] == first["method"] and later["path"] != first["path"]
                        and _matches(first["path"], later["path"])):
                    out.append(finding(
                        "BL-04", "media", "Ruta inalcanzable (la pisa otra)", later,
                        f"`{first['method']} {first['path']}` está declarada antes "
                        f"(línea {first['line']}) y captura también "
                        f"`{later['path']}`, así que `{later['handler']}` nunca se ejecuta."))
    return out


UNSAFE_RE = re.compile(r"\$(queryRawUnsafe|executeRawUnsafe)\s*\(")


def bl05_sql_crudo(repo: Path) -> list[dict]:
    out = []
    src = repo / SERVICE_ROOT / "src"
    for path in sorted(src.rglob("*.ts")):
        if "generated" in path.parts:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if UNSAFE_RE.search(line):
                rel = str(path.relative_to(repo))
                out.append({
                    "source": "baseline", "check": "BL-05", "severity": "media",
                    "title": "SQL crudo sin parametrizar", "endpoint": None,
                    "location": f"{rel}:{n}",
                    "detail": "`$queryRawUnsafe`/`$executeRawUnsafe` no escapa lo que se "
                              "interpola. Si algo del request llega a ese string, es "
                              "inyección SQL. Usar `$queryRaw` con template tag.",
                    "evidence": {"line": line.strip()[:200]},
                })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ctx", required=True)
    args = ap.parse_args()
    ctx, repo = Path(args.ctx), Path(args.repo)
    endpoints = json.loads((ctx / "endpoints.json").read_text(encoding="utf-8"))

    target.reset()
    findings = bl01_sin_guard(endpoints)
    f2, log2 = bl02_anonimo(endpoints)
    f3, log3 = bl03_campo_extra(endpoints)
    findings += f2 + f3 + bl04_rutas_pisadas(endpoints) + bl05_sql_crudo(repo)

    (ctx / "baseline.json").write_text(json.dumps(
        {"findings": findings, "probes": log2 + log3}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"baseline: {len(log2) + len(log3)} requests · {len(findings)} hallazgos")
    for f in findings:
        print(f"  [{f['check']}] {f['severity']:5} {f['title']} — {f['endpoint'] or f['location']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
