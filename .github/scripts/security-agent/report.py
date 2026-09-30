#!/usr/bin/env python3
"""Arma el reporte en markdown: lo que va como comentario en la PR y al resumen
del job. Solo publica hallazgos del baseline y del agente CONFIRMADOS por el
replay; los descartados figuran como conteo, para que se vea que existieron.

Uso:  report.py --ctx <dir>        Deja  $CTX/report.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MARKER = "<!-- agente:security-agent -->"
ORDER = {"alta": 0, "media": 1, "baja": 2}
ICON = {"alta": "🔴", "media": "🟠", "baja": "🟡"}


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

    findings = sorted(baseline["findings"] + validated["confirmed"],
                      key=lambda f: ORDER.get(f["severity"], 9))

    out = [MARKER, "## 🔒 Security Agent", ""]
    if findings:
        out.append(f"**{len(findings)} hallazgo(s)** sobre {len(endpoints)} endpoints.")
    else:
        out.append(f"Sin hallazgos sobre {len(endpoints)} endpoints.")
    out.append("")

    for f in findings:
        where = f.get("endpoint") or f.get("location") or ""
        tag = f.get("check") or "agente"
        out += [f"### {ICON.get(f['severity'], '⚪')} {f['title']}",
                f"`{where}` · {tag} · severidad **{f['severity']}**", ""]
        if f.get("location") and f.get("endpoint"):
            out.append(f"Código: `{f['location']}`")
        if f.get("detail"):
            out.append(f["detail"])
        if f.get("expected"):
            out.append(f"\n**Esperado:** {f['expected']}")
        ev = f.get("evidence")
        if isinstance(ev, list) and ev:
            out += ["", "**Reproducción** (verificada desde una base limpia):"] + [_call(c) for c in ev]
        elif isinstance(ev, dict) and ev.get("request"):
            out += ["", "**Evidencia:**", _call(ev)]
        out.append("")

    probes = len(baseline.get("probes") or [])
    out += ["<details><summary>Cómo se obtuvo</summary>", "",
            f"- Chequeos automáticos: {probes} requests (401 sin sesión, 400 con campo de más, "
            f"guards, rutas pisadas, SQL crudo).",
            f"- Agente: {agent.get('outcome', 'no corrió')} · {agent.get('iterations', 0)} acciones · "
            f"{agent.get('requests', 0)} requests · modelos: {', '.join(agent.get('modelsUsed') or []) or '—'}.",
            f"- Hallazgos del agente descartados por no reproducirse: {len(validated['discarded'])}.",
            "- Corre contra una copia local del back con base descartable y autenticación "
            "simulada. No prueba la verificación de tokens de Firebase.",
            ""]
    if agent.get("summary"):
        out += [f"Resumen del agente: {agent['summary']}", ""]
    out.append("</details>")

    (ctx / "report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"reporte: {len(findings)} hallazgos → {ctx / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
