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
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_prompt  # noqa: E402
import models  # noqa: E402
import tools as tools_mod  # noqa: E402
from llm_client import LLMError  # noqa: E402

MAX_ITERATIONS = agent_prompt.MAX_ITERATIONS
# Con MAX_ITERATIONS=7 el camino ideal es write/test/fix/test/fix/test/finish:
# tres corridas justas. Quedaba en 3 desde que el techo era 5, así que la
# corrida de SPO-168 llegó a la iteración 7 queriendo verificar —justo lo que
# le pedimos— y se la rechazamos. Una de slack, porque una corrida se puede
# perder en un pattern que no matchea nada.
MAX_TEST_RUNS = 4
MAX_WALL_SECONDS = int(600)

# Un rechazo por VALIDACIÓN DE ENTRADA (archivo muy grande, ruta no permitida)
# no ejecutó nada: no tiene sentido que cueste lo mismo que una corrida de tests.
# Con 5 iteraciones, castigar un error de formato es lo que hizo que una corrida
# entera terminara con cero specs. Se regalan unos pocos reintentos, con tope
# para que no se vuelva un loop infinito por la puerta de atrás.
MAX_FREE_RETRIES = 2

READ_ACTIONS = {"read_file", "list_dir", "search"}


# La política de §4 está en el SYSTEM, pero cuando el modelo la necesita quedó
# 6000 tokens atrás y gana la inercia de "arreglar el test". En SPO-168 el agente
# dedujo solo que al endpoint le faltaba el `@Body()` con DTO — un suspected_bug
# de manual — y siguió reescribiendo igual. Cinco corridas sin que la vía se
# active. Esto la pone delante de él en el momento exacto de la decisión.
CLASIFICA = """

─── SEGUNDA CORRIDA EN ROJO: CLASIFICÁ ANTES DE REESCRIBIR ───

Ya reescribiste el spec y sigue fallando. Antes de tocar otra línea, clasificá
cada test que falla:

  test_error     el test está mal (payload, fixture, ruta) → corregilo
  suspected_bug  el test es correcto y el CÓDIGO no cumple el AC
                 → marcalo `it.failing(...)`, no lo toques más, y reportalo en
                   `suspectedBugs` con ac / request / expected / actual
  blocked        el endpoint no existe o el AC es ambiguo → reportalo

Si ya viste que el código no hace lo que pide el AC — un DTO que falta, una
validación que no está, un status que no coincide — eso es `suspected_bug` y NO
un test para arreglar. Reescribirlo para que pase sería debilitar el assert, que
está prohibido. Un suspected_bug legítimo vale más que diez tests verdes.

Un `it.failing` PASA cuando falla: la suite queda en verde y el bug queda en el
reporte. Es la forma de cerrar, no un fracaso."""


def observation(name: str, result: tools_mod.ToolResult, nudge: str = "") -> str:
    status = "OK" if result.ok else "ERROR"
    return f"[resultado de {name} — {status}]\n{result.output}{nudge}"


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
    # Los AC que fallaron en ALGUNA corrida. El validador exige que cada uno
    # termine o marcado `it.failing`, o siguiendo verificando lo que pide el AC:
    # que falle y después pase en verde con el assert aflojado es la prohibición
    # 1 de §4, que hasta ahora no tenía ningún mecanismo detrás.
    failed_acs: set[str] = set()

    iteration = 0
    free_retries = 0
    failed_runs = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1
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
                    "failing_blocks": tools_mod.failing_blocks(
                        str(call_args.get("content", ""))),
                })
        elif action == "run_tests":
            result = toolbox.run_tests(str(call_args.get("pattern", "")))
            failed_acs |= set((result.meta or {}).get("failed_acs") or [])
        else:
            result = tools_mod.ToolResult(
                False, f"acción desconocida: {action!r}. Usá read_file, list_dir, "
                       f"search, write_spec_file, run_tests o finish.")

        entry["ok"] = result.ok
        entry["output_head"] = result.output[:300]

        # Rechazo por validación de entrada: no se ejecutó nada, no se cobra.
        if (not result.ok and action == "write_spec_file"
                and free_retries < MAX_FREE_RETRIES):
            free_retries += 1
            iteration -= 1
            entry["free_retry"] = free_retries
            print(f"   ↩︎  no cuenta como iteración "
                  f"({free_retries}/{MAX_FREE_RETRIES} libres)")
        history.append(entry)
        print(f"   {'✓' if result.ok else '✗'} {result.output.splitlines()[0][:160] if result.output else ''}")

        messages.append({"role": "assistant",
                         "content": json.dumps(reply, ensure_ascii=False)})
        if action == "run_tests" and not result.ok:
            failed_runs += 1
        nudge = CLASIFICA if (action == "run_tests" and not result.ok
                              and failed_runs >= 2) else ""
        messages.append(agent_prompt.user_turn(
            observation(action, result, nudge)))
    else:
        outcome = "budget"
        print(f"[loop] se agotaron las {MAX_ITERATIONS} iteraciones", flush=True)

    # --- verificación final, fuera del presupuesto del modelo ---------------
    # SPO-168, SPO-171 y SPO-182 murieron las tres igual: el último turno se fue
    # en un `write_spec_file` y el spec quedó sin correr. En SPO-182 eso descartó
    # seis `it.failing` legítimos —el primer hallazgo real del agente— por una
    # sola acción.
    #
    # Subir el techo no lo arregla: no es un problema de cantidad de turnos sino
    # de en qué se gasta el último. Y pedirlo en el prompt ya se probó y no
    # alcanzó. Correr el oráculo no es una decisión que necesite al modelo, así
    # que la toma el arnés y no le cuesta una iteración.
    if (not _spec_verified(history) and toolbox.written
            and toolbox.test_runs < MAX_TEST_RUNS):
        print("\n[loop] verificación final (no cuenta como iteración)", flush=True)
        final = toolbox.run_tests()
        failed_acs |= set((final.meta or {}).get("failed_acs") or [])
        history.append({"iteration": None, "model": None, "forced": True,
                        "thought": "verificación final forzada por el arnés",
                        "action": "run_tests", "ok": final.ok,
                        "output_head": final.output[:300]})
        print(f"   {'✓' if final.ok else '✗'} "
              f"{final.output.splitlines()[0][:160] if final.output else ''}")

    payload = {
        "ticket": args.ticket,
        "maxIterations": MAX_ITERATIONS,
        "specVerified": _spec_verified(history),
        "rf": context.get("rf"),
        "outcome": outcome,
        "iterations": sum(1 for h in history if not h.get("forced")),
        "modelsUsed": sorted({h["model"] for h in history if h.get("model")}),
        "specsWritten": toolbox.written,
        "testRuns": toolbox.test_runs,
        "summary": str(finish_payload.get("summary") or "")[:2000],
        "acCoverage": finish_payload.get("acCoverage") or [],
        "suspectedBugs": finish_payload.get("suspectedBugs") or [],
        "criteria": context.get("criteria") or [],
        "failingSnapshots": failing_snapshots,
        "failedAcs": sorted(failed_acs),
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


def _spec_verified(history: list[dict]) -> bool:
    """¿El spec que se entrega pasó por el oráculo?

    Un `outcome=budget` que corta justo después de un `write_spec_file` deja un
    archivo que NUNCA se ejecutó. Pasó en las corridas de SPM-42 y SPO-168: job
    verde, rama pusheada, "9/12 AC cubiertos" — sobre un spec sin verificar.

    Verificado = después del último write exitoso hubo un `run_tests` en verde.
    Un `it.failing` bien usado deja la suite en verde, así que un suspected_bug
    legítimo sigue contando como verificado.
    """
    last_write = max(
        (i for i, e in enumerate(history)
         if e.get("action") == "write_spec_file" and e.get("ok")),
        default=None)
    if last_write is None:
        return False
    return any(e.get("action") == "run_tests" and e.get("ok")
               for e in history[last_write + 1:])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LLMError as e:
        print(f"::warning title=Test agent sin correr::{e}")
        sys.exit(0)
