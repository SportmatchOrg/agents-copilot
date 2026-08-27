#!/usr/bin/env python3
"""Entrega: rama, commit y PR draft (plan §3.4, §7.2).

Único side effect del agente sobre GitHub, y lo ejecuta código — no el modelo.

Autoría (§7.2, requerimiento explícito): los cambios figuran como del agente,
nunca como de una persona. Por eso el PR se crea con el GITHUB_TOKEN (autor
`github-actions[bot]`) y no con un PAT, y los commits llevan identidad de bot.
Efecto lateral buscado: una PR creada con GITHUB_TOKEN no dispara otros
workflows, así que el QA agent no se auto-dispara sobre esta PR.

Uso:  open-test-pr.py --ctx <dir> --repo <ruta> --ticket SPM-42 --base dev
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BOT_NAME = "sportmatch-test-agent[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        print(f"❌ {' '.join(cmd)}\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        sys.exit(1)
    return proc


def body(data: dict, ticket: str) -> str:
    covered = [c for c in data.get("coverage", []) if c.get("covered")]
    lines = [
        f"> Generado por el **API Test Agent** para `{ticket}`. "
        f"Nadie escribió esto a mano.",
        "",
        data.get("summary") or "_(el agente no dejó resumen)_",
        "",
        "## Cobertura de criterios de aceptación",
        "",
        f"**{data.get('coveredCount', 0)}/{data.get('totalAc', 0)}** cubiertos. "
        f"Medido por el validador cruzando los `[AC-n]` de los tests contra el "
        f"ticket, no autodeclarado por el modelo.",
        "",
    ]
    for c in data.get("coverage", []):
        mark = "✅" if c.get("covered") else "⬜"
        text = f" — {c['text']}" if c.get("text") else ""
        lines.append(f"- {mark} `{c['ac']}`{text}")

    bugs = data.get("suspectedBugs") or []
    lines += ["", "## Posibles bugs encontrados", ""]
    if not bugs:
        lines.append("_Ninguno._")
    else:
        lines.append(
            "Estos tests están marcados con `it.failing(...)`. **En Jest, un test "
            "marcado así pasa cuando falla**: por eso la suite queda verde. "
            "Cuando alguien arregle el bug, ese test va a empezar a fallar — esa "
            "es la señal de que ya se le puede sacar el `.failing`.")
        lines.append("")
        for bug in bugs:
            lines += [
                f"### `{bug.get('ac')}` — {bug.get('request')}",
                f"- **Esperado:** {bug.get('expected')}",
                f"- **Obtenido:** {bug.get('actual')}",
                f"- **Evidencia:** {bug.get('evidence') or '—'}",
                "",
            ]

    lines += [
        "## Cómo corrió",
        "",
        f"| | |",
        f"|---|---|",
        f"| Iteraciones | {data.get('iterations')} / 5 |",
        f"| Corridas de tests | {data.get('testRuns')} |",
        f"| Modelos usados | {', '.join(data.get('modelsUsed') or []) or '—'} |",
        f"| Fin | `{data.get('outcome')}` |",
        "",
        "El agente solo puede escribir `test/*.e2e-spec.ts`. El harness "
        "(`setup-e2e.ts`, `fixtures.ts`) está fuera de su alcance a propósito.",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--base", default="dev")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    data = json.loads(Path(args.ctx, "validated.json").read_text(encoding="utf-8"))

    if not data.get("publish"):
        print("nada que publicar")
        return 0

    branch = f"bot/tests-{args.ticket.lower()}"
    run(["git", "config", "user.name", BOT_NAME], repo)
    run(["git", "config", "user.email", BOT_EMAIL], repo)
    run(["git", "checkout", "-B", branch], repo)
    run(["git", "add"] + data["specs"], repo)

    n_bugs = len(data.get("suspectedBugs") or [])
    subject = f"test({args.ticket}): tests e2e generados por el API Test Agent"
    detail = (f"{data.get('coveredCount')}/{data.get('totalAc')} criterios de "
              f"aceptación cubiertos.")
    if n_bugs:
        detail += f" {n_bugs} posible(s) bug(s) marcados con it.failing."
    # Sin Co-authored-by: el requerimiento es que el autor sea el agente (§7.2).
    run(["git", "commit", "-m", subject, "-m", detail], repo)
    run(["git", "push", "-u", "origin", branch, "--force-with-lease"], repo)

    pr_body = body(data, args.ticket)
    Path(args.ctx, "pr-body.md").write_text(pr_body, encoding="utf-8")

    existing = run(["gh", "pr", "list", "--head", branch, "--json", "number",
                    "-q", ".[0].number"], repo, check=False).stdout.strip()
    if existing:
        run(["gh", "pr", "edit", existing, "--body-file",
             str(Path(args.ctx, "pr-body.md"))], repo)
        print(f"✅ PR #{existing} actualizada")
    else:
        proc = run(["gh", "pr", "create", "--draft", "--base", args.base,
                    "--head", branch, "--title", subject,
                    "--body-file", str(Path(args.ctx, "pr-body.md"))], repo)
        print(f"✅ PR draft creada: {proc.stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
