#!/usr/bin/env python3
"""Arma el reporte con el formato común de los agentes
(.github/scripts/common/agent_report.py): un `report.json` que después publica
`agent_report.py publish` en la PR y en el resumen del job.

Solo entran hallazgos del baseline y del agente CONFIRMADOS por el replay; los
descartados figuran como conteo, para que se vea que existieron.

Uso:  report.py --ctx <dir>        Deja  $CTX/report.json  (y $CTX/report.md, para correr local)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import agent_report as ar  # noqa: E402

# Severidad propia del agente → severidad del formato común.
SEVERITY = {"alta": "urgent", "media": "important", "baja": "minor"}


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _call(c: dict) -> str:
    req = c["request"]
    body = f" `{json.dumps(req['body'], ensure_ascii=False)[:200]}`" if req.get("body") else ""
    resp = json.dumps(c["body"], ensure_ascii=False) if c.get("body") is not None else ""
    if len(resp) > 300:
        resp = resp[:300] + "…"
    return (f"- `{req['method']} {req['path']}` como **{req['as'] or 'sin sesión'}**{body}"
            f" → **{c['status']}** `{resp}`")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ctx = Path(ap.parse_args().ctx)

    baseline = _load(ctx / "baseline.json", {"findings": [], "probes": []})
    validated = _load(ctx / "validated.json", {"confirmed": [], "discarded": []})
    agent = _load(ctx / "agent-output.json", {})
    endpoints = _load(ctx / "endpoints.json", [])

    findings = baseline["findings"] + validated["confirmed"]
    common = []
    for f in findings:
        detail = []
        if f.get("location") and f.get("endpoint"):
            detail.append(f"Código: `{f['location']}`")
        if f.get("detail"):
            detail.append(f["detail"])
        if f.get("expected"):
            detail.append(f"**Esperado:** {f['expected']}")
        ev = f.get("evidence")
        if isinstance(ev, list) and ev:
            detail.append("\n".join(["**Reproducción** (verificada desde una base limpia):"] + [_call(c) for c in ev]))
        elif isinstance(ev, dict) and ev.get("request"):
            detail.append("**Evidencia:**\n" + _call(ev))
        common.append({
            "severity": SEVERITY.get(f["severity"], "minor"),
            "title": f"{f['title']} ({f.get('check') or 'agente'})",
            "ref": f.get("endpoint") or f.get("location") or "",
            "detail": "\n\n".join(detail),
        })

    sevs = {f["severity"] for f in common}
    status = "fail" if "urgent" in sevs else "warn" if "important" in sevs else "ok"
    n = len(endpoints)
    if common:
        counts = ", ".join(f"{len([f for f in common if f['severity'] == s])} {ar.SEVERITY_LABEL[s].lower()}"
                           for s in ar.SEVERITIES if any(f["severity"] == s for f in common))
        summary = f"{len(common)} hallazgo(s) sobre {n} endpoints: {counts}."
    else:
        summary = f"Sin hallazgos sobre {n} endpoints."

    probes = len(baseline.get("probes") or [])
    how = [f"- Chequeos automáticos: {probes} requests (401 sin sesión, 400 con campo de más, "
           f"guards, rutas pisadas, SQL crudo).",
           f"- Agente: {agent.get('outcome', 'no corrió')} · {agent.get('iterations', 0)} acciones · "
           f"{agent.get('requests', 0)} requests · modelos: {', '.join(agent.get('modelsUsed') or []) or '—'}.",
           f"- Hallazgos del agente descartados por no reproducirse: {len(validated['discarded'])}.",
           "- Corre contra una copia local del back con base descartable y autenticación "
           "simulada. No prueba la verificación de tokens de Firebase."]
    if agent.get("summary"):
        how += ["", f"Resumen del agente: {agent['summary']}"]

    report = ar.normalize({"status": status, "summary": summary, "findings": common,
                           "sections": [{"title": "Cómo se obtuvo", "body": "\n".join(how)}],
                           "ai": bool(agent)},
                          "security-agent", "Security Agent")
    (ctx / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ctx / "report.md").write_text(ar.render_github(report), encoding="utf-8")
    print(f"reporte: {status} · {len(common)} hallazgos → {ctx / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
