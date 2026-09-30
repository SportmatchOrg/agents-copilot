#!/usr/bin/env python3
"""El loop del Security Agent.

Mismo esquema que el test agent (ReAct: el modelo elige una acción, el arnés la
ejecuta, la observación vuelve al historial) y mismo cliente de modelos, con su
cadena de fallback: `test-agent/models.py` se importa, no se copia.

La diferencia que importa: la evidencia NO es texto del modelo. Cada `http` lo
ejecuta el arnés y queda registrado en `calls.json` con request y respuesta
reales. Un hallazgo solo puede CITAR números de request; lo que se publica es
lo que el arnés vio, no lo que el modelo dice que vio.

Uso:  run-agent.py --ctx <dir> --repo <ruta> [--changed archivo1,archivo2]
Lee   $CTX/endpoints.json, $CTX/baseline.json
Deja  $CTX/calls.json, $CTX/agent-output.json, $CTX/agent-history.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# El orden importa: las dos carpetas tienen un `agent_prompt.py`. `test-agent`
# entra al path solo por `models.py`, y esta carpeta tiene que quedar PRIMERO o
# el modelo recibe las instrucciones del test agent (pasó en la primera corrida).
sys.path.insert(0, str(HERE.parent / "test-agent"))
sys.path.insert(0, str(HERE))
import agent_prompt  # noqa: E402
assert Path(agent_prompt.__file__).resolve().parent == HERE, "agent_prompt equivocado"
import models  # noqa: E402  (test-agent/models.py: cadena con fallback)
import target  # noqa: E402
from llm_client import LLMError  # noqa: E402

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")
MAX_ITERATIONS = agent_prompt.MAX_ITERATIONS
MAX_WALL_SECONDS = int(os.environ.get("SEC_MAX_WALL_SECONDS", "1500"))
MAX_READ = 40_000
MAX_FREE_RETRIES = 3
PRELOAD_SUFFIXES = (".controller.ts", ".service.ts", ".guard.ts", ".dto.ts")


# --- contexto precargado ------------------------------------------------------

def _source_block(repo: Path) -> str:
    src = repo / SERVICE_ROOT / "src"
    parts = []
    for path in sorted(src.rglob("*.ts")):
        if "generated" in path.parts or not path.name.endswith(PRELOAD_SUFFIXES):
            continue
        rel = path.relative_to(repo)
        parts.append(f"--- {rel} ---\n{path.read_text(encoding='utf-8')}")
    return "=== CÓDIGO (controllers, services, guards, DTOs) ===\n" + "\n\n".join(parts)


def _endpoints_block(endpoints: list[dict]) -> str:
    lines = [f"{e['method']:6} {e['path']:45} guards={','.join(e['guards']) or '-'}"
             f"{'  body=' + e['body']['type'] if e.get('body') else ''}" for e in endpoints]
    return "=== ENDPOINTS ===\n" + "\n".join(lines)


def _baseline_block(baseline: dict) -> str:
    findings = baseline.get("findings") or []
    head = (f"{len(baseline.get('probes') or [])} requests automáticos "
            f"(401 sin sesión, 400 con campo de más, guards, rutas pisadas, SQL crudo).")
    if not findings:
        return f"=== BASELINE ===\n{head} Sin hallazgos."
    rows = [f"- [{f['check']}] {f['title']} — {f['endpoint'] or f['location']}" for f in findings]
    return f"=== BASELINE ===\n{head} Ya reportados (no los repitas):\n" + "\n".join(rows)


def _focus(changed: list[str]) -> str:
    back = [c for c in changed if c.startswith(f"{SERVICE_ROOT}/src/")]
    if not back:
        return "Revisá toda la API."
    return ("Esta corrida es por una PR que toca estos archivos. Priorizá los "
            "endpoints que dependen de ellos, y después seguí con el resto:\n"
            + "\n".join(f"  - {c}" for c in back))


# --- herramientas -------------------------------------------------------------

def read_file(repo: Path, rel: str) -> tuple[bool, str]:
    rel = (rel or "").strip().lstrip("/")
    root = (repo / SERVICE_ROOT).resolve()
    try:
        path = (repo / rel).resolve()
        path.relative_to(root)
    except (ValueError, OSError):
        return False, f"ruta no permitida: {rel!r}. Solo archivos dentro de {SERVICE_ROOT}/."
    if not path.is_file():
        return False, f"no existe: {rel}"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_READ:
        text = text[:MAX_READ] + "\n[...recortado...]"
    return True, text


def do_http(args: dict, calls: list[dict]) -> tuple[bool, str]:
    who = args.get("as")
    who = None if who in (None, "", "null", "none", "anon") else str(who).upper()
    try:
        res = target.request(str(args.get("method", "")), str(args.get("path", "")),
                             body=args.get("body"), as_user=who)
    except ValueError as e:
        return False, str(e)
    res["n"] = len(calls) + 1
    calls.append(res)
    return True, f"#{res['n']} {res['request']['method']} {res['request']['path']} " \
                 f"como {who or 'sin sesión'}\n{target.render(res)}"


# --- cobertura ------------------------------------------------------------------

def _pattern_matches(pattern: str, path: str) -> bool:
    a = pattern.strip("/").split("/")
    b = path.split("?")[0].strip("/").split("/")
    return len(a) == len(b) and all(x.startswith(":") or x == y for x, y in zip(a, b))


def untested(endpoints: list[dict], calls: list[dict]) -> list[str]:
    """Endpoints a los que el agente todavía no le pegó. Se cuenta en código:
    en la primera corrida el modelo gastó 20 acciones en join-requests y nunca
    tocó notificaciones, ratings ni el perfil."""
    out = []
    for ep in endpoints:
        if (ep["method"], ep["path"]) in (("GET", "/"), ("GET", "/health")):
            continue
        hit = any(c["request"]["method"] == ep["method"]
                  and _pattern_matches(ep["path"], c["request"]["path"]) for c in calls)
        if not hit:
            out.append(f"{ep['method']} {ep['path']}")
    return out


# Si el presupuesto se agota sin `finish`, lo que el modelo vio se pierde. Pasó
# en la primera corrida: 20 acciones, 20 requests, `outcome=budget` y el reporte
# vacío por construcción. El cierre no es una decisión que necesite presupuesto:
# lo pide el arnés, en un turno aparte.
CIERRE = """\
Se terminaron las acciones. No hay más requests.

Respondé AHORA con `finish`, y solo con `finish`: el resumen de lo que probaste
y los hallazgos que encontraste en los requests #1 a #{n}. Si todo se comportó
como el código dice, `findings: []`."""


# --- loop ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--changed", default="")
    args = ap.parse_args()

    ctx, repo = Path(args.ctx), Path(args.repo).resolve()
    endpoints = json.loads((ctx / "endpoints.json").read_text(encoding="utf-8"))
    baseline = json.loads((ctx / "baseline.json").read_text(encoding="utf-8"))
    changed = [c.strip() for c in args.changed.split(",") if c.strip()]

    blocks = [_endpoints_block(endpoints), _baseline_block(baseline), _source_block(repo)]
    messages = [{"role": "system", "content": agent_prompt.SYSTEM},
                agent_prompt.first_turn(blocks, _focus(changed))]

    # La exploración arranca del mismo estado que el replay: base recién sembrada.
    target.reset()
    client = models.ChainClient()

    calls: list[dict] = []
    history: list[dict] = []
    outcome, finish_payload = "budget", {}
    started = time.monotonic()
    iteration = free_retries = 0
    last_signature = None

    while iteration < MAX_ITERATIONS:
        iteration += 1
        elapsed = time.monotonic() - started
        if elapsed > MAX_WALL_SECONDS:
            outcome = "timeout"
            print(f"[loop] corte por tiempo ({elapsed:.0f}s)", flush=True)
            break
        print(f"\n=== iteración {iteration}/{MAX_ITERATIONS} ({elapsed:.0f}s) ===", flush=True)

        try:
            reply, model_used = client.ask(messages, label=f"iter{iteration}")
        except LLMError as e:
            outcome = "llm_unavailable"
            print(f"[loop] sin modelo disponible: {e}", file=sys.stderr)
            break

        thought = str(reply.get("thought") or "")[:400]
        action = str(reply.get("action") or "")
        call_args = reply.get("args") if isinstance(reply.get("args"), dict) else {}
        print(f"[{model_used}] 💭 {thought}")
        print(f"[{model_used}] → {action} {json.dumps(call_args, ensure_ascii=False)[:200]}")
        entry = {"iteration": iteration, "model": model_used, "thought": thought,
                 "action": action, "args": call_args}

        if action == "finish":
            finish_payload = call_args
            outcome = "finished"
            history.append(entry)
            break

        signature = json.dumps([action, call_args], sort_keys=True)
        if signature == last_signature:
            ok, out = False, ("Es EXACTAMENTE la misma acción que la anterior; el resultado "
                              "sería el mismo. Probá otra cosa o cerrá con `finish`.")
        elif action == "http":
            ok, out = do_http(call_args, calls)
        elif action == "read_file":
            ok, out = read_file(repo, str(call_args.get("path", "")))
        else:
            ok, out = False, (f"acción desconocida: {action!r}. Las acciones son "
                              f"`http`, `read_file` y `finish`.")
        last_signature = signature

        # Un rechazo por entrada inválida no ejecutó nada: no se cobra, con tope.
        if not ok and free_retries < MAX_FREE_RETRIES:
            free_retries += 1
            iteration -= 1
            entry["free_retry"] = free_retries

        entry.update({"ok": ok, "output_head": out[:300]})
        history.append(entry)
        print(f"   {'✓' if ok else '✗'} {out.splitlines()[0][:160] if out else ''}")

        restantes = MAX_ITERATIONS - iteration
        aviso = ""
        if restantes <= 3:
            aviso = (f"\n\n(Te quedan {restantes} acciones. Cerrá con `finish` antes de "
                     f"quedarte sin ninguna.)")
        elif action == "http" and ok and len(calls) % 5 == 0:
            falta = untested(endpoints, calls)
            if falta:
                aviso = ("\n\n(Endpoints que todavía no probaste: "
                         + "; ".join(falta) + ")")
        messages.append({"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)})
        messages.append(agent_prompt.user_turn(
            f"[resultado de {action} — {'OK' if ok else 'ERROR'}]\n{out}{aviso}"))

    if outcome == "budget":
        print(f"[loop] se agotaron las {MAX_ITERATIONS} acciones", flush=True)

    if outcome in ("budget", "timeout") and calls:
        print("\n[loop] cierre forzado (no cuenta como acción)", flush=True)
        messages.append(agent_prompt.user_turn(CIERRE.format(n=len(calls))))
        try:
            reply, model_used = client.ask(messages, label="cierre")
            if reply.get("action") == "finish" and isinstance(reply.get("args"), dict):
                finish_payload = reply["args"]
                outcome += "+cierre"
                history.append({"iteration": None, "model": model_used, "forced": True,
                                "action": "finish", "args": finish_payload})
        except LLMError as e:
            print(f"[loop] el cierre forzado no volvió: {e}", file=sys.stderr)

    findings = finish_payload.get("findings")
    payload = {
        "outcome": outcome,
        "iterations": sum(1 for h in history if "free_retry" not in h),
        "modelsUsed": sorted({h["model"] for h in history if h.get("model")}),
        "requests": len(calls),
        "summary": str(finish_payload.get("summary") or "")[:2000],
        "findings": findings if isinstance(findings, list) else [],
    }
    for name, data in (("calls.json", calls), ("agent-output.json", payload),
                       ("agent-history.json", history)):
        (ctx / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
    print(f"\n[loop] outcome={outcome} · {payload['iterations']} acciones · "
          f"{len(calls)} requests · {len(payload['findings'])} hallazgos declarados")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LLMError as e:
        print(f"::warning title=Security agent sin correr::{e}")
        sys.exit(0)
