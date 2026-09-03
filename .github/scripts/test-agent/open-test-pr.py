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
import os
import subprocess
import sys
from pathlib import Path

BOT_NAME = "sportmatch-test-agent[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"

# Muchas orgs prohíben que Actions abra PRs (Settings → Actions → General →
# "Allow GitHub Actions to create and approve pull requests"). No se puede
# habilitar por repo si la org lo bloquea.
#
# Es el precio del requerimiento de autoría (§7.2): con un PAT la PR figuraría
# como escrita por una persona, que es justo lo que no queremos. Preferimos que
# el autor sea el bot y que la PR la abra un humano de un click, antes que
# falsear la autoría.
#
# Cuando pasa, NO se pierde nada: la rama ya está pusheada con los commits del
# bot. Se deja el link de comparación y el reporte en el summary, y el job
# termina en verde: una política de la org no es un fallo del agente.
PR_FORBIDDEN = "not permitted to create or approve pull requests"


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
    marcados = data.get("failingMarcados") or []
    lines += ["", "## Posibles bugs encontrados", ""]
    FAILING_NOTA = (
        "Estos tests están marcados con `it.failing(...)`. **En Jest, un test "
        "marcado así pasa cuando falla**: por eso la suite queda verde. "
        "Cuando alguien arregle el bug, ese test va a empezar a fallar — esa "
        "es la señal de que ya se le puede sacar el `.failing`.")
    if not bugs and not marcados:
        lines.append("_Ninguno._")
    elif not bugs:
        # El loop no llegó a `finish`, así que no hay evidencia estructurada
        # (§4 regla 3), pero los bloques marcados existen. Decir "Ninguno" acá
        # sería enterrar el entregable de más valor de la corrida: en SPO-182
        # eran seis, sobre un ticket que resultó estar sin implementar.
        lines += [FAILING_NOTA, "",
                  "> ⚠️ El loop se quedó sin turnos antes de cerrar, así que no "
                  "dejó el detalle de request/esperado/obtenido. Los tests "
                  "marcados son estos y hay que revisarlos a mano:", ""]
        lines += [f"- `{n}`" for n in marcados]
    else:
        lines.append(FAILING_NOTA)
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
        f"| Iteraciones | {data.get('iterations')} / {data.get('maxIterations', 7)} |",
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
                    "--body-file", str(Path(args.ctx, "pr-body.md"))],
                   repo, check=False)
        if proc.returncode != 0:
            combined = proc.stdout + proc.stderr
            if PR_FORBIDDEN in combined:
                return degrade(args, branch, subject, pr_body)
            print(f"❌ gh pr create falló:\n{combined}", file=sys.stderr)
            return 1
        print(f"✅ PR draft creada: {proc.stdout.strip()}")
    return 0


def degrade(args, branch: str, subject: str, pr_body: str) -> int:
    """La rama está pusheada; solo falta que un humano abra la PR."""
    slug = os.environ.get("TARGET_REPO", "").strip()
    compare = (f"https://github.com/{slug}/compare/{args.base}...{branch}?expand=1"
               if slug else f"(rama `{branch}`)")

    print(f"::warning title=PR no creada::La organización no permite que "
          f"GitHub Actions abra pull requests. La rama {branch} está pusheada "
          f"con los tests; falta abrir la PR a mano.")
    print(f"⚠️  PR no creada por política de la organización.")
    print(f"    Rama pusheada: {branch}")
    print(f"    Abrila acá:    {compare}")

    summary = Path(args.ctx, "summary.md")
    extra = (
        f"\n---\n\n"
        f"### ⚠️ La PR no se creó\n\n"
        f"La organización no permite que GitHub Actions abra pull requests "
        f"(`Settings → Actions → General → Allow GitHub Actions to create and "
        f"approve pull requests`). No se usa un PAT a propósito: la PR figuraría "
        f"como escrita por una persona y el requerimiento es que el autor sea el "
        f"agente.\n\n"
        f"**Los tests ya están pusheados** en `{branch}`, con los commits "
        f"firmados por el bot.\n\n"
        f"👉 **[Abrir la PR]({compare})**\n\n"
        f"<details><summary>Cuerpo de la PR que se habría creado</summary>\n\n"
        f"{pr_body}\n\n</details>\n")
    with summary.open("a", encoding="utf-8") as fh:
        fh.write(extra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
