"""Herramientas del API Test Agent (plan §5.2).

Todo lo que el modelo puede hacer sobre el repo pasa por acá. El modelo no
ejecuta nada: emite una acción JSON y este módulo la resuelve.

Dos invariantes que se validan en código, no en el prompt:

  1. Escritura restringida a `<SERVICE_ROOT>/test/*.e2e-spec.ts`. El harness
     (setup-e2e.ts, fixtures.ts, jest-e2e.json, stubs/) queda fuera de alcance:
     si el agente pudiera tocarlo, podría "arreglar" un test deshabilitando la
     autenticación o el truncado de la base (plan §3.6).
  2. Ninguna ruta puede escaparse del repo (`..`, absolutas, symlinks).

`SERVICE_ROOT` es configurable (plan §3.7): hoy `back`, y la v1 del plan asumía
`backend` — esa suposición costó seis secciones mal. No hardcodearlo.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")
TEST_CMD = os.environ.get("TEST_CMD", "npm run test:e2e")

MAX_TEST_OUTPUT = 8_000
# Errores de lint que se le muestran. Con 20 ya tiene de sobra para una tanda de
# arreglos, y más solo gasta contexto en repetir la misma regla.
MAX_LINT_PROBLEMS = 20
TEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT_SECONDS", "600"))

# Tope de tamaño por spec (plan §5.6). `write_spec_file` manda el archivo
# entero: los modelos free capean la salida en 4–8k tokens, y un archivo largo
# se trunca, rompe el JSON y quema un turno de cinco.
#
# Los valores originales (200 líneas / 8192 bytes) estaban mal calibrados y se
# comieron una corrida entera: el agente convergió 312 → 272 → 269 → 239 → 208
# líneas y se quedó sin presupuesto a una iteración de entrar. El detalle que lo
# delata: desde la segunda iteración ya estaba por DEBAJO del límite de bytes
# (7822 < 8192) — o sea que el cap de líneas era el único que bloqueaba, y las
# líneas son un mal proxy del riesgo real, que es el truncado por max_tokens.
#
# Ahora manda el tamaño en bytes, holgado respecto de max_tokens=8000, y el cap
# de líneas queda solo como red de contención contra un archivo absurdo.
MAX_SPEC_LINES = 400
MAX_SPEC_BYTES = 12_000

SPEC_RE = re.compile(rf"^{re.escape(SERVICE_ROOT)}/test/[A-Za-z0-9._-]+\.e2e-spec\.ts$")

# El spec de ejemplo es la referencia de estilo escrita a mano (fase 0b) y la
# prueba de que el oráculo funciona. El agente no lo puede pisar.
PROTECTED = {f"{SERVICE_ROOT}/test/partidos.example.e2e-spec.ts"}


# "Tests: 0 total" (el filtro descartó todo) y "No tests found" (ningún suite).
NO_TESTS_RE = re.compile(r"Tests:\s+0 total|No tests found", re.I)


# Jest lista cada fallo como "● Describe › [AC-7] nombre del test".
FAILED_AC_RE = re.compile(r"●[^\n]*?\[(AC-\d+)[a-z]?\]")
# Un `it.failing` que PASA rompe la suite con este mensaje. Es la señal de que
# la marca estaba de más, y destildarla es la única forma de llegar a verde:
# el validador la necesita para no confundir esa corrección con encubrir un bug.
FAILING_PASSED_MSG = "Failing test passed"


def marcas_de_mas(salida: str) -> list[str]:
    """AC cuyo `it.failing` pasó, o sea que estaba mal marcado."""
    out = set()
    for chunk in salida.split("●")[1:]:
        if FAILING_PASSED_MSG in chunk:
            m = re.search(r"\[(AC-\d+)[a-z]?\]", chunk.split("\n")[0])
            if m:
                out.add(m.group(1))
    return sorted(out)
_IT_RE = re.compile(r"^\s*(?:it|test)(?:\.failing)?\s*\(", re.M)


def _slice_block(content: str, start: int) -> str:
    """Del arranque de un it() hasta el siguiente. `write_spec_file` reemplaza
    el archivo entero, así que comparar bloques es la única forma de ver qué
    cambió entre iteraciones."""
    rest = content[start:]
    nxt = _IT_RE.search(rest)
    return rest[:nxt.start()] if nxt else rest


def ac_block(content: str, ac_id: str) -> str:
    """TODOS los cuerpos de `it('[AC-n] ...')`, concatenados. Vacío si no hay.

    Devolver solo el primero era un falso positivo esperando: desde que se
    aceptan sub-etiquetas, un AC puede tener varios bloques. En SPO-182 el
    `[AC-7]` era un placeholder honesto —"el guard está mockeado, 401 no se
    puede observar"— y el `[AC-7b]` de al lado sí verificaba el 404. Mirando
    solo el primero, el AC figuraba sin verificar.

    Importa que sea exhaustivo porque de acá sale también el aborto de la
    prohibición 1: un falso positivo ahí mata una corrida buena.
    """
    bloques = [
        _slice_block(content, m.end())
        for m in re.finditer(
            rf"^\s*(?:it|test)(?:\.failing)?\s*\(\s*['\"`]\s*\[{ac_id}[a-z]?\]",
            content, re.M)
    ]
    return "\n".join(bloques)


def failing_blocks(content: str) -> list[dict]:
    """Nombre y huella de cada `it.failing(...)` (plan §4, regla 2).

    El plan pide guardar el bloque "verbatim"; el código guardaba solo el
    nombre, así que se podía conservar el `it.failing(...)` y vaciarle el
    cuerpo. La huella cierra eso.

    Se normalizan los espacios antes de hashear: un reindentado no cambia lo
    que el test afirma, y hacerlo abortar sería un falso positivo.
    """
    out = []
    for m in re.finditer(r"^\s*(?:it|test)\.failing\s*\(\s*(['\"`])(.+?)\1",
                         content, re.M):
        body = _slice_block(content, m.end())
        out.append({"name": m.group(2),
                    "sha": hashlib.sha1(" ".join(body.split()).encode()).hexdigest()[:12]})
    return out


@dataclass
class ToolResult:
    ok: bool
    output: str
    meta: dict | None = None


def safe_resolve(repo: Path, rel: str) -> Path | None:
    """Resuelve `rel` dentro de `repo`, o None si se escapa. Igual criterio que
    `resolve-context.py` del QA agent."""
    rel = (rel or "").strip().lstrip("/")
    if not rel or "\x00" in rel:
        return None
    try:
        target = (repo / rel).resolve()
        target.relative_to(repo.resolve())
    except (ValueError, OSError):
        return None
    return target


class Toolbox:
    def __init__(self, repo: Path) -> None:
        self.repo = repo.resolve()
        self.service = self.repo / SERVICE_ROOT
        self.written: list[str] = []
        self.test_runs = 0

    def write_spec_file(self, path: str, content: str) -> ToolResult:
        rel = (path or "").strip().lstrip("/")
        if not SPEC_RE.match(rel):
            return ToolResult(False, (
                f"ruta no permitida: {rel!r}. Solo se puede escribir "
                f"{SERVICE_ROOT}/test/<nombre>.e2e-spec.ts — el harness "
                f"(setup-e2e.ts, fixtures.ts, jest-e2e.json) no se toca."))
        if rel in PROTECTED:
            return ToolResult(False, (
                f"{rel} es el spec de ejemplo de referencia y no se modifica. "
                f"Escribí uno nuevo con otro nombre."))
        if content is None or not content.strip():
            return ToolResult(False, "contenido vacío")

        n_lines = content.count("\n") + 1
        n_bytes = len(content.encode("utf-8"))
        if n_lines > MAX_SPEC_LINES or n_bytes > MAX_SPEC_BYTES:
            return ToolResult(False, (
                f"el archivo es demasiado grande ({n_lines} líneas, {n_bytes} bytes; "
                f"máximo {MAX_SPEC_LINES} líneas / {MAX_SPEC_BYTES} bytes). "
                f"El tope que muerde es el de BYTES, no el de líneas: apuntá a "
                f"~300 líneas. Repartilo en dos specs por grupo de AC — uno por "
                f"endpoint anda bien, y cada uno se verifica solo."))

        target = safe_resolve(self.repo, rel)
        if target is None:
            return ToolResult(False, f"ruta inválida: {rel!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if rel not in self.written:
            self.written.append(rel)
        return ToolResult(True, f"escrito {rel} ({n_lines} líneas)")

    # --- oráculo -----------------------------------------------------------

    def run_tests(self, pattern: str = "") -> ToolResult:
        """El oráculo. Devuelve exit code + stdout recortado."""
        self.test_runs += 1
        cmd = TEST_CMD.split()
        if pattern:
            cmd += ["--", "-t", pattern] if TEST_CMD.startswith("npm") else ["-t", pattern]
        env = dict(os.environ)
        try:
            proc = subprocess.run(cmd, cwd=self.service, capture_output=True,
                                  text=True, timeout=TEST_TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"la suite superó {TEST_TIMEOUT}s y se abortó")
        except FileNotFoundError:
            return ToolResult(False, f"no se pudo ejecutar {TEST_CMD!r} en {self.service}")

        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # Se extrae ANTES del recorte: si el fallo quedó fuera de los últimos
        # 8 KB, igual sabemos que ese AC falló. Es el dato que le faltaba al
        # validador para exigir que un AC que falló no termine en verde con el
        # assert aflojado (§4, prohibición 1).
        failed_acs = sorted(set(FAILED_AC_RE.findall(combined)))
        # La cola de Jest es donde están los fallos y el resumen; el head es ruido.
        if len(combined) > MAX_TEST_OUTPUT:
            combined = "[...recortado...]\n" + combined[-MAX_TEST_OUTPUT:]
        # Jest sale 0 cuando el filtro no matchea NADA, y eso llegaba al agente
        # como "TODOS LOS TESTS PASARON". Es un oráculo mintiendo: en SPO-168 se
        # comió una de las corridas disponibles con un verde de cero tests.
        # `pattern` filtra por NOMBRE de test (-t), no por nombre de archivo.
        if proc.returncode == 0 and NO_TESTS_RE.search(combined):
            return ToolResult(False, (
                "no se ejecutó NINGÚN test: el filtro no matcheó nada, así que "
                "este verde no significa nada. `pattern` filtra por el NOMBRE "
                "del test (lo que va dentro de `it('...')`), no por el nombre "
                "del archivo. Corré sin `pattern` para la suite completa.\n\n"
                + combined.strip()))

        # El agente tiene que ver la MISMA vara que lo juzga. El validador corre
        # `tsc --noEmit` y aborta si no compila, pero ts-jest es más permisivo:
        # las corridas 5, 6 y la de SPO-182 en CI pasaron los tests y murieron
        # en el compile por algo que al agente nunca se le mostró — un
        # `possibly null`, un `prisma.$use` que ya no existe en Prisma 7.
        #
        # Antes esto corría SOLO con Jest en verde, para ahorrar los ~20s de tsc
        # cuando el agente ya tenía rojo que arreglar. SPO-197 mostró que ese
        # ahorro es el que cuesta la corrida: los tests estaban en rojo, ts-jest
        # reportó los imports rotos como fallos difusos de runtime, el agente
        # adivinó mal cuatro iteraciones seguidas y el validador lo mató con
        # cuatro TS2305/2307/2459 exactos que nunca vio. Los 20s se pagan
        # siempre: son más baratos que una iteración a ciegas.
        tsc = subprocess.run(
            ["npx", "tsc", "--noEmit", "-p", "tsconfig.json"],
            cwd=self.service, capture_output=True, text=True,
            timeout=TEST_TIMEOUT)
        compila = tsc.returncode == 0

        # Las DOS varas se corren y se informan JUNTAS, aunque el compile ya
        # haya fallado. Antes se cortaba en el tsc para no ensuciar con lint
        # type-aware sobre código roto — y eso mandó la corrida de SPO-197 a un
        # ping-pong de 15 iteraciones: el agente tipaba `res.body` para callar
        # al lint, eso destapaba TS18048 en `.find()`, destipaba para callar al
        # compile, y volvía el lint. Nunca vio los dos a la vez, así que nunca
        # pudo arreglar los dos a la vez. El ruido es un costo menor que el
        # bucle; para eso va la aclaración de abajo.
        lint = self._lint_specs()

        if not compila or lint:
            partes = []
            if not compila:
                partes.append("=== NO COMPILA (el validador aborta la entrega "
                              "si no compila) ===\n"
                              + (tsc.stdout + tsc.stderr).strip()[-2000:])
            if lint:
                partes.append("=== NO PASA EL LINT (el CI del repo corre "
                              "`npm run lint`; una PR que no lintea no se "
                              "mergea) ===\n" + lint)
            if not compila and lint:
                partes.append(
                    "Arreglá LAS DOS COSAS en la misma escritura. No alcanza "
                    "con una: si tipás el body para callar al lint y el acceso "
                    "queda `possibly undefined`, afirmá con `!` — volver a "
                    "`any` te devuelve el error de lint. Algunos errores de "
                    "lint pueden desaparecer solos al arreglar el compile.")
            cabecera = ("los tests pasan PERO" if proc.returncode == 0 else
                        f"exit code: {proc.returncode} — HAY TESTS FALLANDO, y además")
            cuerpo = "\n\n".join(partes)
            if proc.returncode != 0:
                cuerpo += f"\n\n--- salida de los tests ---\n{combined.strip()}"
            return ToolResult(False, f"{cabecera} el spec no pasa:\n\n{cuerpo}", {
                "exit_code": proc.returncode, "failed_acs": failed_acs,
                "tsc": compila, "eslint": not lint,
                "marcas_de_mas": marcas_de_mas(combined)})

        verdict = "TODOS LOS TESTS PASARON" if proc.returncode == 0 else "HAY TESTS FALLANDO"
        return ToolResult(
            proc.returncode == 0,
            f"exit code: {proc.returncode} — {verdict}\n\n{combined.strip()}",
            {"exit_code": proc.returncode, "failed_acs": failed_acs,
             "tsc": True, "eslint": True,
             "marcas_de_mas": marcas_de_mas(combined)},
        )

    def _lint_specs(self) -> str | None:
        """Los errores de ESLint en los specs del agente, o None si está limpio."""
        # `self.written` es relativo al repo; eslint corre con cwd=self.service.
        targets = []
        for rel in self.written:
            path = self.repo / rel
            if path.is_file():
                targets.append(str(path.relative_to(self.service)))
        if not targets:
            return None
        # `--fix` y no `--no-fix`. El `--no-fix` original cuidaba algo real —
        # `npm run lint` del repo corre con `--fix` sobre `src/`, que el agente
        # tiene PROHIBIDO tocar— pero ese riesgo no existe acá: los targets son
        # las rutas de `self.written`, que ya pasaron por `SPEC_RE`. eslint no
        # ve ningún archivo que el agente no tenga permitido escribir.
        #
        # Va con fix porque en SPO-197 lo único que separaba a la corrida del
        # verde eran errores `prettier/prettier`: formato puro, determinístico y
        # sin una sola decisión adentro. El modelo cerró con `finish` antes que
        # arreglarlos y el validador tiró el job. Pelear indentación a fuerza de
        # turnos de LLM —200s y una chance de JSON roto cada uno— es tirar el
        # presupuesto en lo único que la máquina hace mejor y gratis. Lo que
        # queda sin arreglar es lo que sí requiere criterio: los `any` sin tipar.
        try:
            proc = subprocess.run(
                ["npx", "eslint", *targets, "--quiet", "--fix",
                 "--format", "json"],
                cwd=self.service, capture_output=True, text=True,
                timeout=TEST_TIMEOUT)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Sin linter no se bloquea la entrega: el CI lo va a decir igual, y
            # un `npx` que no arranca no es culpa del spec.
            return None
        # 0 = limpio, 1 = hay errores de lint. Cualquier otra cosa (2 = config
        # rota, crash) es un problema de la herramienta, no del spec: bloquear
        # ahí dejaría al agente sin salida por algo que no puede arreglar.
        if proc.returncode != 1:
            return None
        # El formato por default (`stylish`) alinea en columnas con padding y va
        # precedido del path absoluto. Recortando por la COLA —que es lo que
        # hacía esto— al modelo le llegaba una línea cortada al medio y después
        # espacios: sin archivo, sin línea y sin regla. En la corrida 8 se colgó
        # reescribiendo lo mismo tres veces porque el error era ilegible, y murió
        # en la iteración 4 de 15. Se parsea el JSON y se rinde compacto, de
        # arriba hacia abajo: los primeros errores son los que hay que arreglar.
        try:
            reporte = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            return ("el lint falló y no se pudo leer su salida:\n\n"
                    + (proc.stdout + proc.stderr).strip()[:1500])

        lineas, total = [], 0
        for archivo in reporte:
            nombre = Path(archivo.get("filePath", "?")).name
            for m in archivo.get("messages") or []:
                total += 1
                if len(lineas) < MAX_LINT_PROBLEMS:
                    lineas.append(
                        f"  {nombre}:{m.get('line')}:{m.get('column')}  "
                        f"{m.get('ruleId')}  {m.get('message')}")
        if not lineas:
            return None
        cola = (f"\n  ... y {total - len(lineas)} más"
                if total > len(lineas) else "")
        return ("tipá el body de la respuesta; no lo esquives con `any`.\n\n"
                + "\n".join(lineas) + cola)
