#!/usr/bin/env python3
"""Formato común de salida de todos los agentes.

Es la "interfaz" del paquete: cada agente produce un `report.json` con la forma
de abajo, y este módulo es el ÚNICO que sabe dibujarlo y publicarlo (comentario
de PR, issue, Discord, Linear, resumen del job). Así todos los agentes se leen
igual y las reglas de ruido viven en un solo lugar.

    {
      "agent":    "dod-checker",                 id kebab-case, va en el marker
      "title":    "Definition of Done",          nombre visible del agente
      "status":   "ok" | "warn" | "fail" | "unknown",
      "summary":  "Veredicto en una o dos líneas: lo primero que se lee.",
      "findings": [{"severity": "urgent" | "important" | "minor",
                    "title":  "Qué pasa, en una línea",
                    "ref":    "archivo:línea · SPO-123 · PR #4   (opcional)",
                    "detail": "markdown con la evidencia          (opcional)"}],
      "sections": [{"title": "...", "body": "markdown", "open": false}],
      "context":  "PR #12 · título                                 (opcional)",
      "link":     "url a donde está el detalle                     (opcional)",
      "ai":       true    si un modelo intervino (default); false = chequeo determinístico
    }

Reglas de render (iguales para todos):
  - Arriba, siempre: estado + título + summary.
  - A la vista: solo los findings `urgent` e `important`, en una línea cada uno.
  - Plegado: los `minor`, el detalle de cada finding y las sections que no
    pidan `open: true`.
  - Discord: solo el titular, hasta 3 findings importantes y el link. Nunca el
    texto entero.

Uso desde un workflow:
  agent_report.py contract                       imprime el formato para el prompt
  agent_report.py ask --prompt prompt.txt --agent A --title T --out report.json [--tries 3]
                                                 llama al modelo, parsea y reintenta si no se entiende
  agent_report.py from-llm --agent A --title T --in resp.txt --out report.json
  agent_report.py new --agent A --title T --status ok --summary S --out report.json
  agent_report.py render --report report.json --target github|discord|linear|summary
  agent_report.py publish --report report.json [--pr N | --issue-label L --issue-title T]
                          [--comment-policy always|not-ok-or-existing]
                          [--discord-policy never|always|not-ok|changed]
                          [--linear-issue-id ID --linear-policy never|always|not-ok|changed]
                          [--context TXT] [--link URL]

Solo usa la stdlib, `gh` (para GitHub) y `linear.sh` (para Linear).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

STATUSES = ("ok", "warn", "fail", "unknown")
SEVERITIES = ("urgent", "important", "minor")
STATUS_ICON = {"ok": "🟢", "warn": "🟡", "fail": "🔴", "unknown": "⚪"}
SEVERITY_ICON = {"urgent": "🚨", "important": "⚠️", "minor": "·"}
SEVERITY_LABEL = {"urgent": "Urgente", "important": "Importante", "minor": "Menores"}
POLICIES = ("never", "always", "not-ok", "changed")

MAX_FINDINGS = 15
# Topes de seguridad por si el modelo no respeta el contrato: el texto largo
# va en `detail` o en las sections, que se pliegan.
MAX_SUMMARY = 280
MAX_TITLE = 160
MAX_REF = 60
DISCORD_MAX_FINDINGS = 3
DISCORD_LIMIT = 1900          # el tope real de Discord es 2000
FOOTER_AI = "asistido por IA · la decisión es humana"
FOOTER_DET = "chequeo automático, sin IA · la decisión es humana"

LINEAR_SH = Path(__file__).resolve().parents[3] / "github" / "scripts" / "linear.sh"
LLM_SH = Path(__file__).resolve().parents[3] / "github" / "scripts" / "llm.sh"


# --------------------------------------------------------------------------
# Contrato
# --------------------------------------------------------------------------

CONTRACT = """\
FORMATO DE SALIDA (obligatorio; es el formato común de todos los agentes de SportMatch).
Respondé SOLO con un objeto JSON válido: sin texto antes ni después y sin ```.
{
  "status": "ok" | "warn" | "fail",
  "summary": "el veredicto en UNA oración de hasta 160 caracteres: es lo primero (y a veces lo único) que se lee",
  "findings": [
    {"severity": "urgent" | "important" | "minor",
     "title": "qué pasa, en una línea",
     "ref": "solo identificadores: SPO-123, PR #4, archivo:línea. Sin explicaciones (opcional)",
     "detail": "evidencia en markdown (opcional, se muestra plegado)"}
  ],
  "sections": [{"title": "...", "body": "markdown", "open": false}]
}
Reglas:
- urgent = hay que resolverlo antes de seguir; important = conviene resolverlo; minor = detalle.
  Ante la duda, bajá la severidad: lo urgente e importante lo ve todo el equipo, lo menor queda plegado.
- "findings": [] si no hay nada. No inventes hallazgos para llenar.
- "title" de cada finding: una línea corta. La explicación va en "detail", no en "title" ni en "ref".
- No repitas en "sections" lo que ya dijiste en "findings" o en "summary".
- Español, sin relleno.
"""


def normalize(raw: dict, agent: str | None = None, title: str | None = None) -> dict:
    """Lleva cualquier dict al contrato: completa defaults y descarta basura.

    Nunca falla: un campo inválido se corrige o se cae. Un reporte que no se
    puede leer es peor que uno incompleto.
    """
    if not isinstance(raw, dict):
        raw = {}
    status = str(raw.get("status", "unknown")).strip().lower()
    report = {
        "agent": agent or str(raw.get("agent") or "agente"),
        "title": title or str(raw.get("title") or raw.get("agent") or "Agente"),
        "status": status if status in STATUSES else "unknown",
        "summary": _clip(" ".join(str(raw.get("summary") or "").split()), MAX_SUMMARY),
        "findings": [],
        "sections": [],
        "ai": bool(raw.get("ai", True)),
    }
    for f in raw.get("findings") or []:
        if not isinstance(f, dict) or not str(f.get("title") or "").strip():
            continue
        sev = str(f.get("severity", "minor")).strip().lower()
        report["findings"].append({
            "severity": sev if sev in SEVERITIES else "minor",
            "title": _clip(" ".join(str(f["title"]).split()), MAX_TITLE),
            "ref": _clip(" ".join(str(f.get("ref") or "").split()), MAX_REF),
            "detail": str(f.get("detail") or "").strip(),
        })
    order = {s: i for i, s in enumerate(SEVERITIES)}
    report["findings"].sort(key=lambda f: order[f["severity"]])
    report["findings"] = report["findings"][:MAX_FINDINGS]
    for s in raw.get("sections") or []:
        if not isinstance(s, dict) or not str(s.get("body") or "").strip():
            continue
        report["sections"].append({
            "title": " ".join(str(s.get("title") or "Detalle").split()),
            "body": str(s["body"]).strip(),
            "open": bool(s.get("open", False)),
        })
    for key in ("context", "link"):
        if raw.get(key):
            report[key] = str(raw[key]).strip()
    return report


def from_llm(text: str, agent: str, title: str) -> dict:
    """Convierte la salida cruda de llm.sh en un reporte.

    Si el modelo no respondió o no devolvió JSON, el reporte queda `unknown`:
    los publishers no pisan nada con un `unknown`, así que un mal día del
    proveedor no borra el último veredicto bueno.
    """
    text = (text or "").strip()
    if not text or text.startswith("LLM_UNAVAILABLE"):
        reason = text.removeprefix("LLM_UNAVAILABLE:").strip() or "sin respuesta"
        return normalize({"status": "unknown",
                          "summary": f"El modelo no respondió en esta corrida ({reason[:200]})."},
                         agent, title)
    data = _extract_json(text)
    if data is None:
        return normalize({"status": "unknown",
                          "summary": "El modelo respondió en un formato inesperado; no se publica nada.",
                          "sections": [{"title": "Respuesta cruda", "body": text[:6000]}]},
                         agent, title)
    if "status" not in data:
        # Respondió el contenido pero no el estado: se deduce de los hallazgos.
        sevs = {str(f.get("severity", "")).lower() for f in data.get("findings") or [] if isinstance(f, dict)}
        data = dict(data, status="fail" if "urgent" in sevs else "warn" if sevs else "ok")
    report = normalize(data, agent, title)
    if report["status"] == "unknown" and not report["summary"]:
        report["summary"] = "El modelo no indicó un estado."
    return report


def _extract_json(text: str) -> dict | None:
    """Encuentra el reporte en lo que devolvió el modelo, aunque venga sucio.

    Los modelos gratis del router cambian sin aviso y no todos respetan el
    "solo JSON": algunos razonan en <think>…</think>, otros envuelven en ```,
    otros agregan texto antes o después, y otros devuelven solo la lista de
    findings. Se toma el primer objeto JSON que parezca un reporte.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    cleaned = re.sub(r"^```[a-zA-Z]*\s*$", "", cleaned, flags=re.M).strip()
    keys = {"status", "summary", "findings", "sections"}
    decoder = json.JSONDecoder()
    first_list = None
    for m in re.finditer(r"[{\[]", cleaned):
        try:
            obj, _ = decoder.raw_decode(cleaned, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and keys & obj.keys():
            return obj
        if (first_list is None and isinstance(obj, list) and obj
                and all(isinstance(x, dict) and "title" in x for x in obj)):
            first_list = obj
    return {"findings": first_list} if first_list is not None else None


def ask(prompt_file: str, agent: str, title: str, tries: int = 3,
        call=None) -> tuple[dict, str]:
    """Llama al modelo con llm.sh y devuelve (reporte, texto crudo).

    Si el modelo respondió pero no se entiende, pregunta de nuevo: con el router
    `openrouter/free` cada llamada puede caer en otro modelo, y algunos no son
    para esto (el 11/10 respondió un clasificador de seguridad: "User Safety:
    safe"). Si llm.sh ya agotó la cadena de modelos (LLM_UNAVAILABLE), no se
    reintenta: sería repetir lo mismo.
    """
    call = call or (lambda: subprocess.run(["bash", str(LLM_SH), prompt_file],
                                           capture_output=True, text=True).stdout)
    report, text = from_llm("", agent, title), ""
    for n in range(1, tries + 1):
        text = call() or ""
        report = from_llm(text, agent, title)
        if report["status"] != "unknown" or not text.strip() or text.startswith("LLM_UNAVAILABLE"):
            break
        print(f"::group::Intento {n}/{tries}: respuesta en formato inesperado")
        print(text[:6000])
        print("::endgroup::")
    return report, text


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def marker(report: dict) -> str:
    return f"<!-- agente:{report['agent']} status={report['status']} -->"


def parse_marker(body: str, agent: str) -> tuple[bool, str | None]:
    """(es de este agente, estado previo). Acepta el marker viejo sin estado."""
    m = re.match(rf"<!-- agente:{re.escape(agent)}(?: status=(\w+))? -->", body or "")
    if not m:
        return False, None
    return True, m.group(1)


def _finding_line(f: dict) -> str:
    ref = f" · `{f['ref']}`" if f["ref"] else ""
    return f"- {SEVERITY_ICON[f['severity']]} **{f['title']}**{ref}"


def _details(summary: str, body: str) -> list[str]:
    # Las líneas en blanco alrededor son obligatorias: sin ellas GitHub no
    # renderiza el markdown de adentro.
    return [f"<details><summary>{summary}</summary>", "", body.strip(), "", "</details>", ""]


def render_github(report: dict, with_marker: bool = True) -> str:
    st = report["status"]
    out = [marker(report)] if with_marker else []
    out += [f"### {STATUS_ICON[st]} {report['title']}", ""]
    if report["summary"]:
        out += [f"**{report['summary']}**", ""]

    visible = [f for f in report["findings"] if f["severity"] != "minor"]
    minor = [f for f in report["findings"] if f["severity"] == "minor"]
    if visible:
        out += [_finding_line(f) for f in visible] + [""]
    if minor:
        out += _details(f"Menores ({len(minor)})", "\n".join(_finding_line(f) for f in minor))

    with_detail = [f for f in report["findings"] if f["detail"]]
    if with_detail:
        body = "\n\n".join(f"**{SEVERITY_ICON[f['severity']]} {f['title']}**"
                           + (f" · `{f['ref']}`" if f["ref"] else "")
                           + f"\n\n{f['detail']}" for f in with_detail)
        out += _details("Detalle de los hallazgos", body)

    for s in report["sections"]:
        if s["open"]:
            out += [f"**{s['title']}**", "", s["body"], ""]
        else:
            out += _details(s["title"], s["body"])

    run = _run_url()
    tail = f" · [corrida]({run})" if run else ""
    footer = FOOTER_AI if report.get("ai", True) else FOOTER_DET
    out.append(f"<sub>🤖 {report['agent']} · {footer}{tail}</sub>")
    return "\n".join(out).rstrip() + "\n"


def render_discord(report: dict) -> str:
    st = report["status"]
    head = f"{STATUS_ICON[st]} **{report['title']}**"
    if report.get("context"):
        head += f" · {report['context']}"
    lines = [head]
    if report["summary"]:
        lines.append(_clip(report["summary"], 300))
    visible = [f for f in report["findings"] if f["severity"] != "minor"]
    for f in visible[:DISCORD_MAX_FINDINGS]:
        ref = f" (`{f['ref']}`)" if f["ref"] else ""
        lines.append(f"• {SEVERITY_ICON[f['severity']]} {_clip(f['title'], 160)}{ref}")
    if len(visible) > DISCORD_MAX_FINDINGS:
        lines.append(f"• … y {len(visible) - DISCORD_MAX_FINDINGS} más")
    if report.get("link"):
        lines.append(f"→ {report['link']}")
    return "\n".join(lines)[:DISCORD_LIMIT]


def render_linear(report: dict) -> str:
    st = report["status"]
    lines = [f"**{STATUS_ICON[st]} {report['title']}** — {report['summary']}".rstrip(" —"), ""]
    visible = [f for f in report["findings"] if f["severity"] != "minor"]
    lines += [_finding_line(f) for f in visible]
    if report.get("link"):
        lines += ["", f"Detalle: {report['link']}"]
    return "\n".join(lines).strip() + "\n"


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _run_url() -> str:
    server, repo, run = (os.environ.get(k) for k in
                         ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run}" if server and repo and run else ""


# --------------------------------------------------------------------------
# Políticas de ruido
# --------------------------------------------------------------------------

def should_send(policy: str, status: str, previous: str | None) -> bool:
    """¿Este canal recibe aviso?

    never     nunca
    always    siempre (reportes programados que alguien espera leer)
    not-ok    solo si hay algo para mirar (warn / fail)
    changed   solo si el estado cambió respecto al último publicado; la
              primera vez, solo si no está ok. Es la política de las PRs:
              cada push re-evalúa, pero solo se avisa cuando algo se mueve.
    `unknown` (el modelo no respondió) solo sale con `always`.
    """
    if policy == "always":
        return True
    if policy == "never" or status == "unknown":
        return False
    if policy == "not-ok":
        return status in ("warn", "fail")
    if policy == "changed":
        return status != "ok" if previous is None else status != previous
    raise ValueError(f"política desconocida: {policy}")


# --------------------------------------------------------------------------
# Publicación
# --------------------------------------------------------------------------

def _gh(*args: str, input_text: str | None = None) -> str:
    res = subprocess.run(["gh", *args], input=input_text, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}… falló: {res.stderr.strip()[:300]}")
    return res.stdout


def find_pr_comment(repo: str, pr: str, agent: str) -> tuple[str | None, str | None]:
    out = _gh("api", f"repos/{repo}/issues/{pr}/comments", "--paginate",
              "--jq", ".[] | {id, body} | @json")
    found: tuple[str | None, str | None] = (None, None)
    for line in out.splitlines():
        c = json.loads(json.loads(line)) if line.startswith('"') else json.loads(line)
        mine, prev = parse_marker(c["body"], agent)
        if mine:
            found = (str(c["id"]), prev)   # el último gana, como antes
    return found


def upsert_pr_comment(repo: str, pr: str, body: str, comment_id: str | None) -> None:
    payload = json.dumps({"body": body})
    if comment_id:
        _gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{comment_id}",
            "--input", "-", input_text=payload)
    else:
        _gh("api", f"repos/{repo}/issues/{pr}/comments", "--input", "-", input_text=payload)


def find_issue(repo: str, label: str, agent: str) -> tuple[dict | None, str | None]:
    out = _gh("issue", "list", "--repo", repo, "--state", "open", "--label", label,
              "--json", "number,body,url", "--limit", "1")
    issues = json.loads(out or "[]")
    if not issues:
        return None, None
    return issues[0], parse_marker(issues[0]["body"], agent)[1]


def upsert_issue(repo: str, label: str, title: str, body: str, existing: dict | None) -> str:
    if existing:
        # Se reemplaza el body, no se suman comentarios: el issue no crece con cada push.
        _gh("api", "-X", "PATCH", f"repos/{repo}/issues/{existing['number']}",
            "--input", "-", input_text=json.dumps({"body": body}))
        return existing["url"]
    subprocess.run(["gh", "label", "create", label, "--repo", repo, "--color", "5319e7",
                    "--description", "Generado por un agente (para dedup)"],
                   capture_output=True)
    return _gh("issue", "create", "--repo", repo, "--title", title,
               "--label", label, "--body-file", "-", input_text=body).strip()


def send_discord(webhook: str, content: str) -> None:
    data = json.dumps({
        "content": content,
        "allowed_mentions": {"parse": []},   # nunca @everyone por accidente
        "flags": 4,                          # SUPPRESS_EMBEDS: sin previews gigantes de links
    }).encode()
    req = urllib.request.Request(webhook, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; SportMatchBot/1.0)"})
    urllib.request.urlopen(req, timeout=20)


def comment_linear(issue_id: str, body: str) -> str:
    tmp = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"linear-{os.getpid()}.md"
    tmp.write_text(body, encoding="utf-8")
    res = subprocess.run(["bash", str(LINEAR_SH), "comment", issue_id, str(tmp)],
                         capture_output=True, text=True)
    return res.stdout.strip()


def _output(**kv: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in kv.items():
                fh.write(f"{k}={v}\n")


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def publish(report: dict, args: argparse.Namespace) -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    status = report["status"]
    previous: str | None = None
    existed = False

    _summary(render_github(report, with_marker=False))

    if status == "unknown":
        # No se pisa el último veredicto bueno con un "no sé".
        print(f"::warning title={report['title']}::{report['summary']}")
    elif args.pr:
        comment_id, previous = find_pr_comment(repo, args.pr, report["agent"])
        existed = comment_id is not None
        if args.comment_policy == "always" or status != "ok" or existed:
            upsert_pr_comment(repo, args.pr, render_github(report), comment_id)
            print(f"comentario {'actualizado' if existed else 'creado'} en PR #{args.pr}")
        else:
            print("todo ok y sin comentario previo: no se comenta (not-ok-or-existing)")
    elif args.issue_label:
        issue, previous = find_issue(repo, args.issue_label, report["agent"])
        existed = issue is not None
        if args.comment_policy == "always" or status != "ok" or existed:
            url = upsert_issue(repo, args.issue_label, args.issue_title or report["title"],
                               render_github(report), issue)
            report.setdefault("link", url)
            print(f"issue {'actualizado' if existed else 'creado'}: {url}")
        else:
            print("todo ok y sin issue abierto: no se abre ninguno (not-ok-or-existing)")

    changed = previous is None or previous != status
    _output(status=status, previous_status=previous or "",
            changed=str(changed).lower(), existed=str(existed).lower())
    print(f"estado: {status} (antes: {previous or '—'})")

    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if webhook and should_send(args.discord_policy, status, previous):
        send_discord(webhook, render_discord(report))
        print("Discord: enviado")
    else:
        print(f"Discord: no se envía (política {args.discord_policy})")

    if args.linear_issue_id and should_send(args.linear_policy, status, previous):
        url = comment_linear(args.linear_issue_id, render_linear(report))
        print(f"Linear: {url or 'no se pudo comentar (¿permisos de LINEAR_API_KEY?)'}")
    elif args.linear_issue_id:
        print(f"Linear: no se comenta (política {args.linear_policy})")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _load(path: str) -> dict:
    return normalize(json.loads(Path(path).read_text(encoding="utf-8")))


def _save(report: dict, path: str) -> None:
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _output(status=report["status"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("contract")

    p = sub.add_parser("ask")
    p.add_argument("--prompt", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tries", type=int, default=3)

    p = sub.add_parser("from-llm")
    p.add_argument("--agent", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("new")
    p.add_argument("--agent", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--status", choices=STATUSES, required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("render")
    p.add_argument("--report", required=True)
    p.add_argument("--target", choices=("github", "discord", "linear", "summary"), default="github")

    p = sub.add_parser("publish")
    p.add_argument("--report", required=True)
    p.add_argument("--pr")
    p.add_argument("--issue-label")
    p.add_argument("--issue-title")
    p.add_argument("--comment-policy", choices=("always", "not-ok-or-existing"), default="always")
    p.add_argument("--discord-policy", choices=POLICIES, default="changed")
    p.add_argument("--linear-issue-id")
    p.add_argument("--linear-policy", choices=POLICIES, default="changed")
    p.add_argument("--context")
    p.add_argument("--link")

    args = ap.parse_args(argv)

    if args.cmd == "contract":
        print(CONTRACT, end="")
    elif args.cmd == "ask":
        report, text = ask(args.prompt, args.agent, args.title, args.tries)
        Path(args.out).with_suffix(".raw.txt").write_text(text, encoding="utf-8")
        _save(report, args.out)
        print(f"{args.agent}: {report['status']} — {report['summary']}")
    elif args.cmd == "from-llm":
        text = Path(args.inp).read_text(encoding="utf-8") if Path(args.inp).exists() else ""
        report = from_llm(text, args.agent, args.title)
        if report["status"] == "unknown" and text and not text.startswith("LLM_UNAVAILABLE"):
            # Queda en el log para entender qué devolvió el modelo.
            print("::group::Respuesta cruda del modelo (formato inesperado)")
            print(text[:6000])
            print("::endgroup::")
        _save(report, args.out)
        print(f"{args.agent}: {report['status']} — {report['summary']}")
    elif args.cmd == "new":
        _save(normalize({"status": args.status, "summary": args.summary},
                        args.agent, args.title), args.out)
    elif args.cmd == "render":
        report = _load(args.report)
        print({"github": render_github,
               "discord": render_discord,
               "linear": render_linear,
               "summary": lambda r: render_github(r, with_marker=False)}[args.target](report), end="")
    elif args.cmd == "publish":
        report = _load(args.report)
        if args.context:
            report["context"] = args.context
        if args.link:
            report["link"] = args.link
        return publish(report, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
