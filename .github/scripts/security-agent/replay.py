#!/usr/bin/env python3
"""Validador determinístico de los hallazgos del agente.

Un hallazgo se publica solo si:
  1. cita requests que existen en `calls.json` (evidencia real, no texto), y
  2. desde una base recién sembrada, re-ejecutar la exploración hasta el último
     request citado devuelve el MISMO status en cada request citado.

Por qué se re-ejecuta todo el prefijo y no solo los citados: el escenario lo
arman requests que el modelo puede no haber citado (el que creó el partido, el
que se unió). Re-ejecutar el prefijo entero garantiza el mismo estado; son
requests locales de milisegundos.

Los ids cambian entre corridas (cuid). Se traducen: al re-ejecutar el request i,
se recorren en paralelo la respuesta original y la nueva, y cada id viejo queda
mapeado al nuevo para reemplazarlo en los requests siguientes.

Uso:  replay.py --ctx <dir>
Lee   $CTX/calls.json, $CTX/agent-output.json
Deja  $CTX/validated.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target  # noqa: E402

ID_RE = re.compile(r"^c[a-z0-9]{20,32}$")
SEVERITIES = ("alta", "media", "baja")


def _align(old, new, mapping: dict[str, str]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for k in old.keys() & new.keys():
            _align(old[k], new[k], mapping)
    elif isinstance(old, list) and isinstance(new, list):
        for a, b in zip(old, new):
            _align(a, b, mapping)
    elif isinstance(old, str) and isinstance(new, str):
        if old != new and ID_RE.match(old) and ID_RE.match(new):
            mapping.setdefault(old, new)


def _rewrite(value, mapping: dict[str, str]):
    if isinstance(value, str):
        for old, new in mapping.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_rewrite(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: _rewrite(v, mapping) for k, v in value.items()}
    return value


def replay(calls: list[dict], upto: int) -> list[dict]:
    target.reset()
    mapping: dict[str, str] = {}
    out = []
    for call in calls[:upto]:
        req = call["request"]
        res = target.request(req["method"], _rewrite(req["path"], mapping),
                             body=_rewrite(req["body"], mapping), as_user=req["as"])
        _align(call["body"], res["body"], mapping)
        out.append(res)
    return out


def validate(finding: dict, calls: list[dict]) -> tuple[bool, str, list[dict]]:
    cited = finding.get("calls")
    if not isinstance(cited, list) or not cited:
        return False, "no cita ningún request", []
    try:
        cited = sorted({int(n) for n in cited})
    except (TypeError, ValueError):
        return False, f"`calls` inválido: {finding.get('calls')!r}", []
    if cited[0] < 1 or cited[-1] > len(calls):
        return False, f"cita requests que no existen (hay {len(calls)})", []

    again = replay(calls, cited[-1])
    diffs = [f"#{n}: {calls[n - 1]['status']} → {again[n - 1]['status']}"
             for n in cited if calls[n - 1]["status"] != again[n - 1]["status"]]
    if diffs:
        return False, "no se reproduce desde una base limpia (" + ", ".join(diffs) + ")", []
    return True, "reproducido", [calls[n - 1] for n in cited]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    args = ap.parse_args()
    ctx = Path(args.ctx)
    # Si el loop no corrió (sin key, sin modelo disponible) no hay nada que
    # validar, y eso no es un error del job: el baseline igual se publica.
    if not (ctx / "calls.json").exists() or not (ctx / "agent-output.json").exists():
        print("replay: el loop no dejó salida; nada que validar")
        return 0
    calls = json.loads((ctx / "calls.json").read_text(encoding="utf-8"))
    output = json.loads((ctx / "agent-output.json").read_text(encoding="utf-8"))

    confirmed, discarded = [], []
    for f in output.get("findings") or []:
        if not isinstance(f, dict):
            continue
        ok, reason, evidence = validate(f, calls)
        item = {
            "source": "agent",
            "severity": f.get("severity") if f.get("severity") in SEVERITIES else "media",
            "title": str(f.get("title") or "(sin título)")[:200],
            "endpoint": str(f.get("endpoint") or "")[:120],
            "expected": str(f.get("expected") or "")[:400],
            "detail": str(f.get("why") or "")[:1200],
            "evidence": evidence,
            "replay": reason,
        }
        (confirmed if ok else discarded).append(item)
        print(f"  {'✓' if ok else '✗'} {item['title']} — {reason}")

    (ctx / "validated.json").write_text(json.dumps(
        {"confirmed": confirmed, "discarded": discarded}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"replay: {len(confirmed)} confirmados · {len(discarded)} descartados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
