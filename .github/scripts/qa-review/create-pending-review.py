#!/usr/bin/env python3
"""Fases 9 y 10 — Pending review + lifecycle.

Único punto del sistema que escribe en GitHub, y el único que ve el
`QA_GITHUB_TOKEN`. El modelo nunca llega hasta acá: lo que se publica es
exclusivamente `validated-review.json`.

Crea una Pull Request Review en estado PENDING (se logra omitiendo el campo
`event` en el POST). Una review pendiente solo la ve quien la creó, así que el
token tiene que ser el del QA: así GitHub la considera *su* borrador y puede
editarlo, borrar comentarios y hacer el submit desde la UI.

Lifecycle (plan §17):
  A. no hay pending del agente     → crear
  B. hay pending del agente        → borrarla y crear una nueva (findings frescos)
  C. hay pending SIN el marker     → NO TOCAR: es una review manual del QA
  D. review ya submiteada + push   → no está PENDING, así que se crea una nueva

Uso:
  create-pending-review.py --ctx qa-context --repo owner/name --pr 7 \
      --head-sha <sha> [--dry-run]
Env: QA_GITHUB_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
# El marker lleva una huella de lo que el agente escribió (head + cantidad de
# comentarios). Hace falta porque GitHub permite UNA sola pending review por
# usuario y por PR: cuando el QA edita el borrador del agente —que es el flujo
# previsto— su trabajo queda DENTRO de una review que lleva el marker. Sin la
# huella, la corrida del push siguiente borraría los comentarios del QA.
MARKER_BASE = "<!-- sportmatch-qa-agent"
AGENT_COMMENT_PREFIX = "**QA-"


def build_marker(head_sha: str, n_comments: int) -> str:
    return f"{MARKER_BASE} sha={head_sha[:8]} comments={n_comments} -->"


def parse_marker(body: str) -> dict | None:
    """Extrae la huella del marker, o None si el body no es del agente."""
    idx = (body or "").find(MARKER_BASE)
    if idx == -1:
        return None
    end = body.find("-->", idx)
    fields = {}
    for token in body[idx + len(MARKER_BASE):end if end != -1 else None].split():
        key, _, value = token.partition("=")
        if value:
            fields[key] = value
    return fields
SEVERITY_ORDER = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "NIT": 3}


class GitHubError(RuntimeError):
    pass


def request(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, object]:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "sportmatch-qa-review-agent",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"message": raw[:500]}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GitHubError(f"error de red hablando con GitHub: {e}") from None


def api_message(body: object) -> str:
    if isinstance(body, dict):
        msg = str(body.get("message", body))
        errors = body.get("errors")
        if errors:
            msg += f" — {json.dumps(errors, ensure_ascii=False)[:400]}"
        return msg
    return str(body)[:400]


def render_body(review: dict, linear: dict, marker: str) -> str:
    findings = review["findings"]
    globals_ = [f for f in findings if f["kind"] == "global"]
    inline = [f for f in findings if f["kind"] == "inline"]

    parts = ["## QA Review — Draft", "", review["summary"]]

    if review.get("positives"):
        parts += ["", "### Positivo", ""]
        parts += [f"- {p}" for p in review["positives"]]

    if globals_:
        parts += ["", "### Observaciones generales", ""]
        parts += [f"- **{f['criterion']} · {f['severity']}** — {f['message']}"
                  for f in globals_]

    if inline:
        parts += ["", "### Comentarios en el código", ""]
        parts += [f"- **{f['criterion']} · {f['severity']}** — `{f['path']}:{f['line']}`"
                  for f in inline]

    if not findings:
        parts += ["", "No encontré nada para marcar según los criterios de QA."]

    if linear.get("identifier"):
        parts += ["", f"Ticket: [{linear['identifier']}]({linear.get('url', '')}) — "
                      f"{linear.get('title', '')}"]

    parts += [
        "",
        "---",
        "",
        "Review preparada automáticamente por el QA PR Review Agent a partir de "
        "`pr-review/SKILL.md` y `qa-criteria.md`. Los comentarios son propuestas: "
        "editá, borrá lo que no aplique y agregá lo tuyo. **La decisión y el submit "
        "son humanos.**",
        "",
        marker,
    ]
    return "\n".join(parts)


def is_untouched(repo: str, pr: int, token: str, review: dict) -> tuple[bool, str]:
    """¿El borrador sigue siendo exactamente lo que escribió el agente?

    Solo se reemplaza un borrador intacto. Si el QA agregó, editó o borró
    comentarios, su trabajo se respeta y no se genera uno nuevo: perder el
    trabajo del humano es mucho peor que quedarse con findings de un commit
    anterior, que el QA ve igual al abrir el PR.
    """
    fields = parse_marker(review.get("body") or "")
    if fields is None:
        return False, "no tiene el marker del agente"

    status, comments = request(
        "GET", f"/repos/{repo}/pulls/{pr}/reviews/{review['id']}/comments", token)
    if status != 200 or not isinstance(comments, list):
        return False, f"no se pudieron leer sus comentarios (HTTP {status})"

    expected = fields.get("comments")
    if expected is not None and str(len(comments)) != expected:
        return False, (f"tiene {len(comments)} comentarios y el agente había dejado "
                       f"{expected}")

    for c in comments:
        if not (c.get("body") or "").startswith(AGENT_COMMENT_PREFIX):
            return False, "tiene al menos un comentario que no escribió el agente"

    return True, ""


def lifecycle_decision(repo: str, pr: int, token: str, login: str,
                       head_sha: str) -> tuple[bool, str, list[dict]]:
    """(seguir, motivo, borradores_a_reemplazar).

    Se llama dos veces: una al principio del workflow (`--preflight`), para no
    gastar llamadas al modelo cuando ya sabemos que no vamos a publicar, y otra
    justo antes de crear, porque entre medio pudo cambiar algo.
    """
    status, pr_now = request("GET", f"/repos/{repo}/pulls/{pr}", token)
    if status == 200 and isinstance(pr_now, dict):
        live_sha = (pr_now.get("head") or {}).get("sha", "")
        if live_sha and live_sha != head_sha:
            return False, (f"el PR avanzó ({head_sha[:8]} → {live_sha[:8]}); la corrida "
                           "del push nuevo genera el borrador actualizado"), []
        if pr_now.get("state") != "open":
            return False, f"el PR ya no está abierto (state={pr_now.get('state')})", []
    else:
        print(f"⚠️  No pude releer el PR (HTTP {status}: {api_message(pr_now)}); "
              "sigo con el head SHA del evento.", file=sys.stderr)

    pendings, listed = find_pending(repo, pr, token, login)
    if not listed:
        print("⚠️  No pude listar las reviews; puede quedar un borrador duplicado.")

    to_replace = []
    for r in pendings:
        fields = parse_marker(r.get("body") or "")
        if fields is None:
            return False, (f"el QA ya tiene una review pendiente propia (#{r['id']}); "
                           "no se toca"), []
        if fields.get("sha") == head_sha[:8]:
            return False, (f"ya existe un borrador del agente para este mismo commit "
                           f"(#{r['id']})"), []
        untouched, reason = is_untouched(repo, pr, token, r)
        if not untouched:
            return False, (f"el borrador #{r['id']} ya fue trabajado por el QA "
                           f"({reason}); sus comentarios se perderían"), []
        to_replace.append(r)

    return True, "", to_replace


def find_pending(repo: str, pr: int, token: str, login: str) -> tuple[list[dict], bool]:
    """Devuelve (pendings del usuario, se_pudo_listar)."""
    pendings, page = [], 1
    while page <= 10:
        status, body = request("GET", f"/repos/{repo}/pulls/{pr}/reviews?per_page=100&page={page}",
                               token)
        if status != 200 or not isinstance(body, list):
            print(f"⚠️  No se pudieron listar las reviews (HTTP {status}: "
                  f"{api_message(body)}). No puedo verificar el lifecycle.", file=sys.stderr)
            return [], False
        for r in body:
            if r.get("state") == "PENDING" and \
                    (r.get("user") or {}).get("login", "").lower() == login.lower():
                pendings.append(r)
        if len(body) < 100:
            break
        page += 1
    return pendings, True


def run_preflight(args) -> int:
    """Decide temprano si el workflow debe seguir, para no gastar llamadas al
    modelo en un PR cuyo borrador el QA ya está trabajando."""
    token = os.environ.get("QA_GITHUB_TOKEN", "").strip()
    if not token:
        print("❌ Falta QA_GITHUB_TOKEN.", file=sys.stderr)
        return 1
    status, me = request("GET", "/user", token)
    if status != 200 or not isinstance(me, dict):
        print(f"❌ El QA_GITHUB_TOKEN no es válido (HTTP {status}: {api_message(me)}).",
              file=sys.stderr)
        return 1

    proceed, reason, _ = lifecycle_decision(
        args.repo, args.pr, token, me["login"], args.head_sha)

    if proceed:
        print(f"✅ Sin borrador previo que preservar; se analiza el PR #{args.pr}.")
    else:
        print(f"⏭️  Se omite el análisis: {reason}.")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"proceed={'true' if proceed else 'false'}\n")
            fh.write(f"reason={reason}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and not proceed:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"\n### QA Review — omitida\n\n{reason}.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--head-sha", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preflight", action="store_true",
                    help="solo decide si vale la pena correr el agente; no publica nada")
    args = ap.parse_args()

    ctx = Path(args.ctx)

    if args.preflight:
        return run_preflight(args)

    review = json.loads((ctx / "validated-review.json").read_text(encoding="utf-8"))
    try:
        linear = json.loads((ctx / "linear-issue.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        linear = {}

    comments = [
        {"path": f["path"], "line": f["line"], "side": "RIGHT",
         "body": f"**{f['criterion']} · {f['severity']}** — {f['message']}"}
        for f in sorted(review["findings"],
                        key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
        if f["kind"] == "inline"
    ]

    body = render_body(review, linear, build_marker(args.head_sha, len(comments)))

    (ctx / "review-body.md").write_text(body + "\n", encoding="utf-8")
    (ctx / "review-comments.json").write_text(
        json.dumps(comments, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.dry_run:
        print("— dry run: no se toca GitHub —\n")
        print(body)
        print(f"\n{len(comments)} comentarios inline:")
        for c in comments:
            print(f"  {c['path']}:{c['line']} — {c['body'][:100]}")
        return 0

    token = os.environ.get("QA_GITHUB_TOKEN", "").strip()
    if not token:
        print("❌ Falta QA_GITHUB_TOKEN. Sin el PAT del QA la review pendiente "
              "quedaría a nombre del bot y el QA no podría verla. No se publica.",
              file=sys.stderr)
        return 1

    status, me = request("GET", "/user", token)
    if status != 200 or not isinstance(me, dict):
        print(f"❌ El QA_GITHUB_TOKEN no es válido (HTTP {status}: {api_message(me)}).",
              file=sys.stderr)
        return 1
    login = me["login"]
    print(f"Autenticado como @{login} — la review pendiente va a quedar a su nombre.")

    # --- Lifecycle ---------------------------------------------------------
    proceed, reason, to_replace = lifecycle_decision(
        args.repo, args.pr, token, login, args.head_sha)
    if not proceed:
        print(f"⏭️  No se crea la review: {reason}.")
        if "trabajado por el QA" in reason:
            print("   Para obtener un borrador actualizado, enviá o descartá ese "
                  "primero y volvé a disparar el workflow.")
        return 0

    for r in to_replace:
        st, rb = request("DELETE", f"/repos/{args.repo}/pulls/{args.pr}/reviews/{r['id']}",
                         token)
        if st in (200, 204):
            print(f"🗑️  Borrada la pending review anterior del agente (#{r['id']}), "
                  "que estaba intacta y era de un commit anterior.")
        else:
            print(f"❌ No se pudo borrar la pending review anterior #{r['id']} "
                  f"(HTTP {st}: {api_message(rb)}). Corto acá para no duplicar borradores.",
                  file=sys.stderr)
            return 1

    # --- Crear la pending review -------------------------------------------
    # Sin `event`: eso es exactamente lo que la deja en PENDING.
    payload = {"commit_id": args.head_sha, "body": body}
    if comments:
        payload["comments"] = comments

    status, created = request("POST", f"/repos/{args.repo}/pulls/{args.pr}/reviews",
                              token, payload)

    if status == 422 and comments:
        # Un solo comentario inline inválido tumba el POST entero. Antes que
        # perder la review, se publica sin inline y los findings van al body.
        print(f"⚠️  GitHub rechazó los comentarios inline ({api_message(created)}). "
              "Reintento con todo en el body.", file=sys.stderr)
        extra = "\n".join(
            f"- **{f['criterion']} · {f['severity']}** — `{f['path']}:{f['line']}`: "
            f"{f['message']}"
            for f in review["findings"] if f["kind"] == "inline")
        fallback = render_body(review, linear, build_marker(args.head_sha, 0)).replace(
            build_marker(args.head_sha, 0),
            "### Findings que no se pudieron anclar a una línea\n\n" + extra + "\n\n"
            + build_marker(args.head_sha, 0))
        status, created = request("POST", f"/repos/{args.repo}/pulls/{args.pr}/reviews",
                                  token, {"commit_id": args.head_sha, "body": fallback})
        comments = []

    if status not in (200, 201) or not isinstance(created, dict):
        print(f"❌ No se pudo crear la pending review (HTTP {status}: "
              f"{api_message(created)}).", file=sys.stderr)
        return 1

    state = created.get("state")
    print(f"✅ Pending review creada (#{created.get('id')}, estado {state}) con "
          f"{len(comments)} comentarios inline.")
    if state != "PENDING":
        print(f"⚠️  ATENCIÓN: quedó en estado {state} y no PENDING. Eso significa que "
              "es visible para el developer. Revisar el payload.", file=sys.stderr)
        return 1

    print(f"   El QA la ve en: https://github.com/{args.repo}/pull/{args.pr}/files")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        inline_n = len(comments)
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(
                f"\n### QA Review — pending review creada\n\n"
                f"| | |\n|---|---|\n"
                f"| PR | #{args.pr} |\n"
                f"| Head | `{args.head_sha[:8]}` |\n"
                f"| Autor de la review | @{login} |\n"
                f"| Findings | {len(review['findings'])} "
                f"({inline_n} inline, {len(review['findings']) - inline_n} globales) |\n"
                f"| Positivos | {len(review['positives'])} |\n"
                f"| Linear | {linear.get('identifier', '—')} |\n\n"
                "> Solo @" + login + " ve este borrador. El submit es humano.\n"
            )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GitHubError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
