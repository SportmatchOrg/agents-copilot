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
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SERVICE_ROOT = os.environ.get("SERVICE_ROOT", "back").strip("/")
TEST_CMD = os.environ.get("TEST_CMD", "npm run test:e2e")

MAX_FILE_BYTES = 40_000
MAX_MATCHES = 40
MAX_TEST_OUTPUT = 8_000
SEARCH_TIMEOUT = 30
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

EXCLUDE_DIRS = {"node_modules", "dist", ".git", ".next", "coverage", "generated"}

# "Tests: 0 total" (el filtro descartó todo) y "No tests found" (ningún suite).
NO_TESTS_RE = re.compile(r"Tests:\s+0 total|No tests found", re.I)


# Jest lista cada fallo como "● Describe › [AC-7] nombre del test".
FAILED_AC_RE = re.compile(r"●[^\n]*?\[(AC-\d+)\]")
# Un `it.failing` que PASA rompe la suite con este mensaje. Es la señal de que
# la marca estaba de más, y destildarla es la única forma de llegar a verde:
# el validador la necesita para no confundir esa corrección con encubrir un bug.
FAILING_PASSED_MSG = "Failing test passed"


def marcas_de_mas(salida: str) -> list[str]:
    """AC cuyo `it.failing` pasó, o sea que estaba mal marcado."""
    out = set()
    for chunk in salida.split("●")[1:]:
        if FAILING_PASSED_MSG in chunk:
            m = re.search(r"\[(AC-\d+)\]", chunk.split("\n")[0])
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
    """El cuerpo del `it('[AC-n] ...')`, vacío si no está."""
    m = re.search(rf"^\s*(?:it|test)(?:\.failing)?\s*\(\s*['\"`]\s*\[{ac_id}\]",
                  content, re.M)
    return _slice_block(content, m.end()) if m else ""


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

    # --- lectura -----------------------------------------------------------

    def list_dir(self, path: str = "") -> ToolResult:
        target = safe_resolve(self.repo, path or SERVICE_ROOT)
        if target is None or not target.is_dir():
            return ToolResult(False, f"{path!r} no es un directorio del repo")
        entries = []
        for item in sorted(target.iterdir()):
            if item.name in EXCLUDE_DIRS or item.name.startswith("."):
                continue
            entries.append(f"{item.name}/" if item.is_dir() else item.name)
        return ToolResult(True, "\n".join(entries) or "(vacío)")

    def read_file(self, path: str) -> ToolResult:
        target = safe_resolve(self.repo, path)
        if target is None or not target.is_file():
            return ToolResult(False, f"{path!r} no existe o queda fuera del repo")
        raw = target.read_bytes()[:MAX_FILE_BYTES]
        text = raw.decode("utf-8", "replace")
        suffix = "\n[...recortado a 40 KB]" if target.stat().st_size > MAX_FILE_BYTES else ""
        return ToolResult(True, text + suffix)

    def search(self, term: str) -> ToolResult:
        if not (term or "").strip():
            return ToolResult(False, "término vacío")
        # Los runners de GitHub NO traen ripgrep, así que en CI esta herramienta
        # estuvo muerta desde el día uno: en SPO-171 el agente la llamó, recibió
        # "no disponible", repitió la misma acción y el detector de bucle mató la
        # corrida. Nunca se vio antes porque en local `rg` sí está.
        # grep está en todos lados y hace lo mismo que necesitamos acá.
        if shutil.which("rg"):
            cmd = ["rg", "--line-number", "--no-heading", "--max-count", "5",
                   "--max-columns", "200"]
            for d in EXCLUDE_DIRS:
                cmd += ["-g", f"!{d}/**"]
            cmd += ["--", term, str(self.service)]
        else:
            cmd = ["grep", "-rnI", "--max-count=5"]
            for d in EXCLUDE_DIRS:
                cmd += [f"--exclude-dir={d}"]
            cmd += ["-e", term, str(self.service)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=SEARCH_TIMEOUT)
        except subprocess.TimeoutExpired:
            return ToolResult(False, "la búsqueda tardó demasiado")
        lines = proc.stdout.splitlines()
        if not lines:
            return ToolResult(True, "Sin coincidencias.")
        shown = [ln.replace(str(self.repo) + "/", "")[:200]
                 for ln in lines[:MAX_MATCHES]]
        extra = f"\n[...{len(lines) - MAX_MATCHES} coincidencias más]" if len(lines) > MAX_MATCHES else ""
        return ToolResult(True, "\n".join(shown) + extra)

    # --- escritura ---------------------------------------------------------

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
                f"Escribí menos casos, o repartilos en otro spec."))

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
        # Solo si Jest pasó: con tests en rojo el agente ya tiene qué arreglar,
        # y tsc cuesta ~20s que no vale la pena pagar ahí.
        if proc.returncode == 0:
            tsc = subprocess.run(
                ["npx", "tsc", "--noEmit", "-p", "tsconfig.json"],
                cwd=self.service, capture_output=True, text=True,
                timeout=TEST_TIMEOUT)
            if tsc.returncode != 0:
                errores = (tsc.stdout + tsc.stderr).strip()[-2000:]
                return ToolResult(False, (
                    "los tests pasan PERO el spec no compila, y el validador "
                    "aborta la entrega si no compila. Arreglá esto:\n\n"
                    + errores), {"exit_code": 0, "failed_acs": failed_acs,
                                 "tsc": False})

        verdict = "TODOS LOS TESTS PASARON" if proc.returncode == 0 else "HAY TESTS FALLANDO"
        return ToolResult(
            proc.returncode == 0,
            f"exit code: {proc.returncode} — {verdict}\n\n{combined.strip()}",
            {"exit_code": proc.returncode, "failed_acs": failed_acs,
             "marcas_de_mas": marcas_de_mas(combined)},
        )
