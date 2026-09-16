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
# El presupuesto de corridas lo declara `agent_prompt`, que es donde también se
# le promete al modelo. Con MAX_ITERATIONS=15 el patrón alterna write/test, así
# que hacen falta ~7: dejarlo en 4 volvía decorativo el techo de iteraciones.
# Es el error que ya cometimos al subir 5→7 sin tocar este número.
MAX_TEST_RUNS = agent_prompt.MAX_TEST_RUNS
# 15 iteraciones a 40-100s cada una, más las corridas de tests (que ahora
# incluyen `tsc`). Con 600s el reloj cortaba cerca de la iteración 10 y el
# techo nuevo no se llegaba a usar nunca.
MAX_WALL_SECONDS = int(1800)

# Un rechazo por VALIDACIÓN DE ENTRADA (archivo muy grande, ruta no permitida)
# no ejecutó nada: no tiene sentido que cueste lo mismo que una corrida de tests.
# Con 5 iteraciones, castigar un error de formato es lo que hizo que una corrida
# entera terminara con cero specs. Se regalan unos pocos reintentos, con tope
# para que no se vuelva un loop infinito por la puerta de atrás.
MAX_FREE_RETRIES = 2



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


# Un `finish` con el oráculo en rojo no cierra nada: el validador exige un
# `run_tests` en verde detrás del último write (§8) y aborta el job entero. En
# SPO-197 el modelo cerró en la iteración 7 de 15 con los tests YA en verde y
# solo el lint en rojo —formato de Prettier— y la corrida murió con el spec a
# dos arreglos de estar lista y ocho iteraciones sin usar.
#
# Pedirlo en el prompt no alcanza (ya está pedido). Devolverle el veredicto
# cuesta un turno de quince; no hacerlo cuesta la corrida.
NO_CIERRES = """\
NO cerraste: el spec que estás entregando NO está en verde, y el validador
aborta el job si el último `write_spec_file` no tiene un `run_tests` en verde
detrás. Cerrar así tira la corrida entera — no se publica nada, ni siquiera lo
que ya funciona.

Arreglá lo que falta y volvé a escribir. Si lo que falla es un AC que el código
no cumple, marcalo `it.failing(...)`: eso deja la suite en verde y el bug en el
reporte, y ahí sí podés cerrar.

Este es el veredicto que estás por ignorar:

"""


def _finish_prematuro(history: list[dict], written: list[str],
                      ya_rechazado: bool) -> bool:
    """¿Este `finish` entrega un spec que el oráculo nunca aprobó?

    Se rechaza UNA sola vez. La segunda se respeta: el modelo puede tener razón
    en que no hay más que hacer —un AC intesteable, un endpoint que no existe—
    y un rechazo en bucle le comería el presupuesto para terminar igual en rojo.
    """
    return bool(written) and not ya_rechazado and not _spec_verified(history)


def _repite(history: list[dict], signature: str) -> bool:
    """¿El turno anterior DEL MODELO fue idéntico a este?

    Mira el último turno no-`forced`, no el último del historial. Desde que el
    arnés corre el oráculo solo, entre dos escrituras del modelo queda siempre
    una entrada `forced` de por medio — y esa no tiene `signature`, así que
    comparar contra `history[-1]` dejaba la detección de bucle muerta. La
    corrida 5 terminó justo así, reescribiendo el mismo archivo de 311 líneas.
    """
    previo = next((e for e in reversed(history) if not e.get("forced")), None)
    return bool(previo) and previo.get("signature") == signature


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
    # AC cuyo `it.failing` PASÓ: la marca estaba de más y destildarla es
    # legítimo, no encubrir un bug (§4 regla 2).
    marcas_de_mas: set[str] = set()

    iteration = 0
    repeticiones = 0
    free_retries = 0
    failed_runs = 0
    finish_rechazado = False
    # El veredicto completo del último oráculo. El historial guarda solo 300
    # caracteres —alcanza para depurar, no para que el modelo arregle nada— y
    # cuando se le rechaza un `finish` hay que devolvérselo entero.
    ultimo_veredicto = ""
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
            if _finish_prematuro(history, toolbox.written, finish_rechazado):
                finish_rechazado = True
                entry["result"] = "finish_rechazado"
                history.append(entry)
                print("   ✗ `finish` con el oráculo en rojo: se le devuelve el "
                      "veredicto y sigue")
                messages.append({"role": "assistant",
                                 "content": json.dumps(reply, ensure_ascii=False)})
                messages.append(agent_prompt.user_turn(
                    NO_CIERRES + ultimo_veredicto))
                continue
            finish_payload = call_args
            entry["result"] = "finish"
            history.append(entry)
            outcome = "finished"
            break

        # Detección de bucle. El umbral estaba en "una repetición y corto",
        # calibrado para 5 turnos donde cada ronda costaba dos. Ahora hay 15 de
        # un turno cada uno y las escrituras quedaron adyacentes, así que corta
        # mucho antes: la corrida 8 murió en la iteración 4 de 15 por una
        # repetición que venía de un error de lint ilegible, no de tozudez. La
        # primera se avisa y cuesta el turno; la segunda corta.
        signature = json.dumps([action, call_args], sort_keys=True)
        entry["signature"] = signature
        repetida = _repite(history, signature)
        if repetida:
            repeticiones += 1
        else:
            repeticiones = 0
        if repeticiones >= 2:
            print("[loop] misma acción repetida dos veces; corte por bucle",
                  flush=True)
            outcome = "loop"
            history.append(entry)
            break

        # Corrida automática del oráculo. El modelo NO la pide: medido sobre
        # las corridas 5 y 6, el 45% de los turnos eran un `run_tests` y NINGUNO
        # vino después de algo que no fuera un write. No era una decisión, era
        # un reflejo que costaba una llamada entera —con su deadline de 200s y
        # su chance de volver con JSON roto. En el free tier cada turno es un
        # billete de lotería a que el proveedor falle: sacar la mitad de los
        # turnos saca la mitad de la exposición sin pedirle al modelo nada
        # distinto de lo que ya hace bien. Mismo criterio que la verificación
        # final, que ya lo hacía por esta razón.
        auto = None
        if repetida:
            result = tools_mod.ToolResult(False, (
                "escribiste EXACTAMENTE lo mismo que en el turno anterior, así "
                "que el resultado sería idéntico y no se ejecutó. Cambiá el "
                "enfoque: si el error no te queda claro, arreglá UNA sola cosa "
                "y volvé a escribir. Si lo repetís otra vez, se corta la "
                "corrida."))
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
                auto = toolbox.run_tests()
                failed_acs |= set((auto.meta or {}).get("failed_acs") or [])
                marcas_de_mas |= set((auto.meta or {}).get("marcas_de_mas") or [])
        else:
            # read_file, list_dir y search se fueron: cero usos en 31 turnos con
            # historial. El prefetch de 8 bloques los volvió redundantes, y cada
            # una era una forma más de quemar un turno.
            result = tools_mod.ToolResult(
                False, f"acción desconocida: {action!r}. Las únicas acciones son "
                       f"`write_spec_file` y `finish`. Los tests se corren solos "
                       f"después de cada escritura: no hay nada que pedir.")

        entry["ok"] = result.ok
        entry["output_head"] = result.output[:300]

        # Rechazo por validación de entrada: no se ejecutó nada, no se cobra.
        if (not result.ok and not repetida and action == "write_spec_file"
                and free_retries < MAX_FREE_RETRIES):
            free_retries += 1
            iteration -= 1
            entry["free_retry"] = free_retries
            print(f"   ↩︎  no cuenta como iteración "
                  f"({free_retries}/{MAX_FREE_RETRIES} libres)")
        history.append(entry)
        print(f"   {'✓' if result.ok else '✗'} {result.output.splitlines()[0][:160] if result.output else ''}")

        # La corrida automática va al historial como turno `forced`, igual que
        # la verificación final: así no gasta iteración y `_spec_verified` y el
        # validador siguen leyendo lo mismo que antes.
        if auto is not None:
            ultimo_veredicto = auto.output
            history.append({
                "iteration": None, "model": None, "forced": True,
                "thought": "el arnés corre el oráculo después de cada escritura",
                "action": "run_tests", "ok": auto.ok,
                "output_head": auto.output[:300]})
            print(f"   {'✓' if auto.ok else '✗'} "
                  f"{auto.output.splitlines()[0][:160] if auto.output else ''}")
            if not auto.ok:
                failed_runs += 1

        messages.append({"role": "assistant",
                         "content": json.dumps(reply, ensure_ascii=False)})
        # El modelo ve la escritura Y el veredicto del oráculo en una sola
        # observación: es lo que antes le costaba dos turnos enterarse.
        vista = result if auto is None else tools_mod.ToolResult(
            auto.ok, f"{result.output}\n\n{auto.output}", auto.meta)
        nudge = CLASIFICA if (auto is not None and not auto.ok
                              and failed_runs >= 2) else ""
        messages.append(agent_prompt.user_turn(
            observation(action, vista, nudge)))
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
        marcas_de_mas |= set((final.meta or {}).get("marcas_de_mas") or [])
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
        "marcasDeMas": sorted(marcas_de_mas),
    }
    (ctx_dir / "agent-output.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ctx_dir / "agent-history.json").write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # El mismo conteo que el payload: la verificación forzada no es una
    # iteración del modelo. El log decía 8 y `validated.json` decía 7.
    print(f"\n[loop] outcome={outcome} · {payload['iterations']} iteraciones · "
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
