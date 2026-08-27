#!/usr/bin/env python3
"""El loop del API Test Agent (plan §5).

Esto es lo único agéntico del paquete: el modelo elige qué herramienta invocar,
recibe el resultado real como input del turno siguiente, y decide cuándo
terminó. El número de iteraciones no se sabe de antemano — solo su techo.

Todo lo que rodea a este archivo (precarga, validación, PR) es determinístico.

Uso:  run-agent.py --ctx <dir> --repo <ruta> --ticket SPM-42
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_prompt  # noqa: E402
import models  # noqa: E402
import tools as tools_mod  # noqa: E402
from llm_client import LLMError  # noqa: E402

MAX_ITERATIONS = agent_prompt.MAX_ITERATIONS
MAX_TEST_RUNS = 3
MAX_WALL_SECONDS = int(600)

READ_ACTIONS = {"read_file", "list_dir", "search"}


def observation(name: str, result: tools_mod.ToolResult) -> str:
    status = "OK" if result.ok else "ERROR"
    return f"[resultado de {name} — {status}]\n{result.output}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ticket", required=True)
    args = ap.parse_args()

    ctx_dir = Path(args.ctx)
    context = json.loads((ctx_dir / "context.json").read_text(encoding="utf-8"))
    toolbox = tools_mod.Toolbox(Path(args.repo))
    client = models.ChainClient()

    messages = [
        {"role": "system", "content": agent_prompt.SYSTEM},
        agent_prompt.first_turn(context["blocks"], args.ticket),
    ]

    history: list[dict] = []
    started = time.monotonic()
    outcome = "partial"
    finish_payload: dict = {}
    # Snapshot de los tests marcados suspected_bug, por iteración. El validador
    # lo usa para verificar que ninguno fue reescrito después (plan §4, regla 2).
    failing_snapshots: list[dict] = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        elapsed = time.monotonic() - started
        if elapsed > MAX_WALL_SECONDS:
            print(f"[loop] corte por tiempo ({elapsed:.0f}s)", flush=True)
            outcome = "timeout"
            break

        print(f"\n=== iteración {iteration}/{MAX_ITERATIONS} "
              f"({elapsed:.0f}s) ===", flush=True)
        try:
            reply, model_used = client.ask(messages, label=f"iter{iteration}")
        except LLMError as e:
            print(f"[loop] sin modelo disponible: {e}", file=sys.stderr)
            outcome = "llm_unavailable"
            break

        thought = str(reply.get("thought") or "")[:400]
        action = str(reply.get("action") or "")
        raw_args = reply.get("args")
        call_args = raw_args if isinstance(raw_args, dict) else {}

        print(f"[{model_used}] 💭 {thought}")
        print(f"[{model_used}] → {action} {json.dumps(call_args, ensure_ascii=False)[:200]}")

        entry = {"iteration": iteration, "model": model_used, "thought": thought,
                 "action": action, "args_keys": sorted(call_args)}

        if action == "finish":
            finish_payload = call_args
            entry["result"] = "finish"
            history.append(entry)
            outcome = "finished"
            break

        # Detección de bucle: con 5 turnos, tolerar tres repeticiones ya te
        # consumió el presupuesto entero. Con dos idénticas seguidas alcanza.
        signature = json.dumps([action, call_args], sort_keys=True)
        entry["signature"] = signature
        if history and history[-1].get("signature") == signature:
            print("[loop] misma acción repetida; corte por bucle", flush=True)
            outcome = "loop"
            history.append(entry)
            break

        if action == "run_tests" and toolbox.test_runs >= MAX_TEST_RUNS:
            result = tools_mod.ToolResult(
                False, f"ya usaste las {MAX_TEST_RUNS} corridas de tests "
                       f"disponibles. Terminá con `finish`.")
        elif action == "read_file":
            result = toolbox.read_file(str(call_args.get("path", "")))
        elif action == "list_dir":
            result = toolbox.list_dir(str(call_args.get("path", "")))
        elif action == "search":
            result = toolbox.search(str(call_args.get("term", "")))
        elif action == "write_spec_file":
            result = toolbox.write_spec_file(
                str(call_args.get("path", "")), str(call_args.get("content", "")))
            if result.ok:
                failing_snapshots.append({
                    "iteration": iteration,
                    "path": call_args.get("path"),
                    "failing_blocks": _failing_blocks(str(call_args.get("content", ""))),
                })
        elif action == "run_tests":
            result = toolbox.run_tests(str(call_args.get("pattern", "")))
        else:
            result = tools_mod.ToolResult(
                False, f"acción desconocida: {action!r}. Usá read_file, list_dir, "
                       f"search, write_spec_file, run_tests o finish.")

        entry["ok"] = result.ok
        entry["output_head"] = result.output[:300]
        history.append(entry)
        print(f"   {'✓' if result.ok else '✗'} {result.output.splitlines()[0][:160] if result.output else ''}")

        messages.append({"role": "assistant",
                         "content": json.dumps(reply, ensure_ascii=False)})
        messages.append(agent_prompt.user_turn(observation(action, result)))
    else:
        outcome = "budget"
        print(f"[loop] se agotaron las {MAX_ITERATIONS} iteraciones", flush=True)

    payload = {
        "ticket": args.ticket,
        "rf": context.get("rf"),
        "outcome": outcome,
        "iterations": len(history),
        "modelsUsed": sorted({h["model"] for h in history if h.get("model")}),
        "specsWritten": toolbox.written,
        "testRuns": toolbox.test_runs,
        "summary": str(finish_payload.get("summary") or "")[:2000],
        "acCoverage": finish_payload.get("acCoverage") or [],
        "suspectedBugs": finish_payload.get("suspectedBugs") or [],
        "criteria": context.get("criteria") or [],
        "failingSnapshots": failing_snapshots,
    }
    (ctx_dir / "agent-output.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ctx_dir / "agent-history.json").write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n[loop] outcome={outcome} · {len(history)} iteraciones · "
          f"{len(toolbox.written)} specs · {toolbox.test_runs} corridas")

    # Sin specs no hay nada que entregar, pero tampoco es un error del job:
    # el paso de PR se apaga solo mirando este output.
    if outcome == "llm_unavailable":
        return 0
    return 0


FAILING_RE = re.compile(r"^\s*(?:it|test)\.failing\s*\(\s*(['\"`])(.+?)\1", re.M)


def _failing_blocks(content: str) -> list[str]:
    """Nombres de los `it.failing(...)` del archivo.

    Es el snapshot de la regla 2 de §4: un test marcado `suspected_bug` no se
    puede reescribir ni borrar en una iteración posterior, y como
    `write_spec_file` reemplaza el archivo entero, la única forma de detectarlo
    es comparar contra lo que había.
    """
    return [name for _, name in FAILING_RE.findall(content)]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LLMError as e:
        print(f"::warning title=Test agent sin correr::{e}")
        sys.exit(0)
