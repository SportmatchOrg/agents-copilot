#!/usr/bin/env python3
"""Validador determinístico (plan §8).

Nada de lo que produce el modelo llega a GitHub sin pasar por acá. La política
de §4 vive en el prompt Y acá: un prompt no es un mecanismo de control.

Aborta el job:
  - archivos modificados fuera de `<SERVICE_ROOT>/test/*.e2e-spec.ts`
  - un test marcado `suspected_bug` fue reescrito o borrado (§4, regla 2)
  - los specs no compilan
  - el repo destino no está en la allowlist (§3.7)
  - aparece un Co-authored-by con mail humano (§7.2)

Degrada sin abortar:
  - suspectedBugs sin evidencia completa → se caen del reporte
  - AC declarado cubierto sin un it() que lo referencie → no cubierto

Uso:  validate-output.py --ctx <dir> --repo <ruta> [--target-repo owner/name]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools  # noqa: E402

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")

# El único hardcode permitido (plan §3.7): el guardarraíl inverso. Agregar el
# segundo elemento es la decisión explícita de apuntar a producción.
ALLOWED_REPOS = {"SportmatchOrg/sportmatch-sandbox"}

SPEC_RE = re.compile(rf"^{re.escape(SERVICE_ROOT)}/test/[A-Za-z0-9._-]+\.e2e-spec\.ts$")
AC_RE = re.compile(r"^\s*(?:it|test)(?:\.failing)?\s*\(\s*['\"`]\s*\[(AC-\d+)\]", re.M)
FAILING_RE = re.compile(r"^\s*(?:it|test)\.failing\s*\(\s*(['\"`])(.+?)\1", re.M)
BUG_FIELDS = ("ac", "request", "expected", "actual")

# Códigos HTTP que nombra el texto de un AC ("devuelve **400**", "→ 409").
STATUS_IN_AC_RE = re.compile(r"\b([1-5]\d\d)\b")
# Códigos que un test verifica de verdad: supertest o assert sobre .status.
STATUS_IN_TEST_RE = re.compile(
    r"\.expect\(\s*(\d{3})\s*\)|\.status\s*\)?\s*\.toBe\(\s*(\d{3})\s*\)")


def _es_failing(content: str, ac_id: str) -> bool:
    """¿El `[AC-n]` quedó marcado `it.failing`? Entonces el agente lo reportó
    como bug en vez de taparlo, que es justo lo que queremos."""
    return bool(re.search(
        rf"^\s*(?:it|test)\.failing\s*\(\s*['\"`]\s*\[{ac_id}\]", content, re.M))


def asserts_lo_que_pide(ac_text: str, block: str) -> bool:
    """¿El test verifica alguno de los status que nombra el criterio?

    Nace de SPO-168, donde el agente bajó un `.expect(400)` a `.expect(201)` y
    le cambió el nombre al test para que describiera lo que hace el código en
    vez de lo que pide el AC. La regla 2 de §4 no lo agarra: el snapshot solo
    protege bloques ya marcados `it.failing`, y este nunca lo estuvo.

    Se ancla al TEXTO DEL AC, no a lo que el modelo escribió antes: el criterio
    es la fuente de verdad, su primer intento no.

    Si el AC no nombra ningún status, no hay nada que cruzar y se deja pasar.
    """
    quiere = {c for c in STATUS_IN_AC_RE.findall(ac_text) if 200 <= int(c) < 600}
    if not quiere:
        return True
    verifica = {a or b for a, b in STATUS_IN_TEST_RE.findall(block)}
    return bool(quiere & verifica)


def fail(message: str) -> None:
    print(f"::error title=Validación del test agent::{message}")
    print(f"❌ {message}", file=sys.stderr)
    sys.exit(1)


def changed_files(repo: Path) -> list[str]:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                          capture_output=True, text=True)
    out = []
    for line in proc.stdout.splitlines():
        path = line[3:].strip()
        if "->" in path:            # renombrados
            path = path.split("->")[-1].strip()
        if path:
            out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--target-repo", default=os.environ.get("TARGET_REPO", ""))
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    ctx_dir = Path(args.ctx)

    # --- guardarraíl de repo ------------------------------------------------
    target = (args.target_repo or "").strip()
    if target and target not in ALLOWED_REPOS:
        fail(f"repo destino {target!r} no está en la allowlist "
             f"({', '.join(sorted(ALLOWED_REPOS))}). Este agente solo escribe "
             f"en el sandbox.")

    output = json.loads((ctx_dir / "agent-output.json").read_text(encoding="utf-8"))

    # --- nada fuera de los specs -------------------------------------------
    touched = changed_files(repo)
    intrusos = [p for p in touched if not SPEC_RE.match(p)]
    if intrusos:
        fail("el agente modificó archivos fuera de los specs: "
             + ", ".join(intrusos[:10]))

    specs = [p for p in touched if SPEC_RE.match(p)]
    if not specs:
        # Un job VERDE que no produjo tests es peor que uno rojo: entrena a la
        # gente a ignorar el check. Se pidieron tests y no hay tests — eso es un
        # fallo de la corrida, aunque la infraestructura haya funcionado.
        outcome = output.get("outcome")
        print(f"::error title=El agente no produjo tests::Terminó con "
              f"outcome={outcome} tras {output.get('iterations')} iteraciones "
              f"y no dejó ningún spec. Revisá el historial en los artifacts.")
        print("❌ el agente no dejó ningún spec; no hay nada que entregar",
              file=sys.stderr)
        empty = {**output, "specs": [], "publish": False, "coverage": [],
                 "coveredCount": 0, "totalAc": len(output.get("criteria") or [])}
        (ctx_dir / "validated.json").write_text(
            json.dumps(empty, indent=2, ensure_ascii=False), encoding="utf-8")
        write_summary(ctx_dir, empty)
        with (ctx_dir / "summary.md").open("a", encoding="utf-8") as fh:
            fh.write(
                "\n### ❌ El agente no produjo tests\n\n"
                f"Terminó con `outcome={empty.get('outcome')}` tras "
                f"{empty.get('iterations')} iteraciones sin dejar ningún spec. "
                "El historial completo de cada turno está en los artifacts del "
                "job: ahí se ve qué acción intentó y qué le respondió cada "
                "herramienta.\n")
        return 1

    # --- regla 2 de §4: ningún suspected_bug desapareció --------------------
    final_failing: dict[str, str] = {}
    for rel in specs:
        content = (repo / rel).read_text(encoding="utf-8", errors="replace")
        for blk in tools.failing_blocks(content):
            final_failing[blk["name"]] = blk["sha"]

    for snap in output.get("failingSnapshots") or []:
        for blk in snap.get("failing_blocks") or []:
            # Las corridas viejas guardaban solo el nombre (una string).
            name = blk["name"] if isinstance(blk, dict) else blk
            sha = blk.get("sha") if isinstance(blk, dict) else None
            if name not in final_failing:
                fail(f"el test marcado como suspected_bug {name!r} "
                     f"(iteración {snap.get('iteration')}) ya no está en el "
                     f"archivo final. §4 regla 2: no se reescriben ni se borran.")
            if sha and final_failing[name] != sha:
                fail(f"el test marcado como suspected_bug {name!r} "
                     f"(iteración {snap.get('iteration')}) sigue estando pero le "
                     f"cambió el cuerpo. §4 regla 2 pide el bloque verbatim: "
                     f"conservar el nombre y vaciar el test es la misma "
                     f"maniobra que borrarlo.")

    # --- los specs compilan -------------------------------------------------
    service = repo / SERVICE_ROOT
    tsc = subprocess.run(
        ["npx", "tsc", "--noEmit", "-p", "tsconfig.json"],
        cwd=service, capture_output=True, text=True)
    if tsc.returncode != 0:
        tail = (tsc.stdout + tsc.stderr)[-1500:]
        fail(f"los tests no compilan:\n{tail}")

    # --- el spec entregado pasó por el oráculo ------------------------------
    # Mismo criterio que el bloque de "no produjo tests": un verde sobre un spec
    # que nunca se ejecutó entrena a ignorar el check. Un `outcome=budget` que
    # corta justo después de un write deja exactamente eso, y la cobertura mide
    # que exista un `it('[AC-n]...')`, no que pase — así que sin esta guarda el
    # summary informa "9/12 cubiertos" sobre un archivo sin correr.
    if not output.get("specVerified", True):
        fail(f"el spec entregado nunca se ejecutó: la corrida terminó con "
             f"outcome={output.get('outcome')} justo después de escribirlo, sin "
             f"un run_tests en verde detrás. La cobertura mide nombres de it(), "
             f"no resultados: publicarlo sería informar un número sin respaldo.")

    # --- cobertura medida, no declarada (§8) --------------------------------
    covered: set[str] = set()
    for rel in specs:
        covered |= set(AC_RE.findall(
            (repo / rel).read_text(encoding="utf-8", errors="replace")))

    all_specs = "\n".join(
        (repo / rel).read_text(encoding="utf-8", errors="replace") for rel in specs)

    # --- §4 prohibición 1: no aflojar un assert para llegar al verde ---------
    # Hasta acá esta prohibición vivía SOLO en el prompt, y en SPO-168 el modelo
    # la leyó y la violó igual: bajó un `.expect(400)` a `.expect(201)` y le
    # cambió el nombre al test para que describiera al código en vez de al AC.
    #
    # El dato que lo delata es que ese AC FALLÓ antes: sabemos que el agente
    # chocó contra esa pared y que después la pared no estaba. Un AC intesteable
    # (el 401 con el guard overrideado) nunca falla y después pasa, así que no
    # necesita excepción escrita a mano: queda afuera solo.
    criteria_txt = output.get("criteria") or []
    for ac_id in output.get("failedAcs") or []:
        idx = int(ac_id.split("-")[1])
        if idx > len(criteria_txt):
            continue
        if _es_failing(all_specs, ac_id):
            continue          # lo reportó como bug: es lo que queremos
        block = tools.ac_block(all_specs, ac_id)
        if not block:
            continue          # no hay test: ya se cuenta como no cubierto
        if not asserts_lo_que_pide(criteria_txt[idx - 1], block):
            fail(f"{ac_id} falló en una corrida y terminó en verde sin verificar "
                 f"el status que pide el criterio. §4 prohibición 1: si el código "
                 f"no cumple, es suspected_bug (`it.failing`), no un assert para "
                 f"aflojar.\n    AC: {criteria_txt[idx - 1][:160]}")

    criteria = output.get("criteria") or []
    total_ac = len(criteria) or len(covered)
    coverage = []
    debilitados = []
    for i in range(1, (len(criteria) or len(covered)) + 1):
        ac_id = f"AC-{i}"
        text = criteria[i - 1] if i <= len(criteria) else ""
        hit = ac_id in covered
        motivo = ""
        if hit and text and not asserts_lo_que_pide(text, tools.ac_block(all_specs, ac_id)):
            hit, motivo = False, "el test no verifica el status que pide el criterio"
            debilitados.append(ac_id)
        coverage.append({"ac": ac_id, "text": text, "covered": hit,
                         **({"motivo": motivo} if motivo else {})})
    if debilitados:
        print(f"⚠️  {', '.join(debilitados)}: hay un it() con ese identificador "
              f"pero no verifica el status que pide el AC; no se cuentan como "
              f"cubiertos (§4: si el código no cumple, es suspected_bug, no un "
              f"assert para aflojar)")
    n_covered = sum(1 for c in coverage if c["covered"])

    declared = {c.get("ac") for c in (output.get("acCoverage") or [])
                if isinstance(c, dict) and c.get("covered")}
    inflado = sorted(declared - covered)
    if inflado:
        print(f"⚠️  el agente declaró cubiertos {inflado} sin un it() que los "
              f"referencie; se cuentan como NO cubiertos")

    # --- suspected bugs con evidencia --------------------------------------
    bugs, descartados = [], 0
    for bug in output.get("suspectedBugs") or []:
        if isinstance(bug, dict) and all(str(bug.get(f) or "").strip() for f in BUG_FIELDS):
            bugs.append(bug)
        else:
            descartados += 1
    if descartados:
        print(f"⚠️  {descartados} suspected_bug sin evidencia completa "
              f"({', '.join(BUG_FIELDS)}); se descartan")

    # Si el loop se quedó sin turnos antes de `finish`, `suspectedBugs` viene
    # vacío aunque el agente HAYA marcado bugs con `it.failing`. Pasó en SPO-182:
    # seis bloques marcados, cero reportados. Sin esto quedan invisibles para
    # quien lee el resumen, que es donde se decide si la PR vale.
    marcados = sorted(final_failing)
    if marcados and not bugs:
        print(f"⚠️  {len(marcados)} test(s) marcados `it.failing` sin entrada en "
              f"suspectedBugs: el loop no llegó a `finish`. Van al resumen igual "
              f"— son el entregable de más valor (§4), no se pierden por un turno.")

    validated = {
        **output,
        "specs": specs,
        "failingMarcados": marcados,
        "coverage": coverage,
        "coveredCount": n_covered,
        "totalAc": total_ac,
        "suspectedBugs": bugs,
        "publish": True,
    }
    (ctx_dir / "validated.json").write_text(
        json.dumps(validated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_summary(ctx_dir, validated)
    print(f"✅ validado: {len(specs)} spec(s), {n_covered}/{total_ac} AC cubiertos, "
          f"{len(bugs)} suspected_bug con evidencia")
    return 0


def write_summary(ctx_dir: Path, data: dict) -> None:
    """Resumen para el step summary del job.

    Se genera acá y no en el YAML a propósito: un heredoc de Python dentro de un
    bloque `run: |` rompe el escalar de YAML y GitHub rechaza el workflow entero
    sin crear ningún job.
    """
    rows = [
        ("Resultado", f"`{data.get('outcome')}`"),
        ("Iteraciones", f"{data.get('iterations')} / {data.get('maxIterations', 5)}"),
        ("AC cubiertos", f"{data.get('coveredCount')} / {data.get('totalAc')}"),
        ("Tests marcados `it.failing`", str(len(data.get("failingMarcados") or []))),
        ("Posibles bugs", str(len(data.get("suspectedBugs") or []))),
        ("Corridas de tests", str(data.get("testRuns"))),
        ("Modelos", ", ".join(data.get("modelsUsed") or []) or "—"),
        ("Specs", ", ".join(f"`{s}`" for s in data.get("specs") or []) or "—"),
    ]
    lines = ["| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows]
    for c in data.get("coverage") or []:
        mark = "✅" if c.get("covered") else "⬜"
        lines.append(f"- {mark} `{c['ac']}` {c.get('text', '')}".rstrip())
    marcados = data.get("failingMarcados") or []
    if marcados and not (data.get("suspectedBugs") or []):
        # El loop no llegó a `finish`, así que no hay evidencia estructurada
        # (§4 regla 3). Los bloques marcados existen igual y son lo más valioso
        # que produjo la corrida: se listan, con la salvedad dicha.
        lines += ["", "### Marcados como `suspected_bug`, sin reporte estructurado",
                  "", "El loop se quedó sin turnos antes de `finish`. Estos tests "
                  "quedaron marcados `it.failing` — pasan porque fallan, y "
                  "documentan un incumplimiento del AC:", ""]
        lines += [f"- `{n}`" for n in marcados]
    (ctx_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
