#!/usr/bin/env python3
"""Tests de las herramientas del agente (plan, fase 1).

No gastan un solo token. Son los que importan: la mitad de los errores de un
agente son errores de sus herramientas, no del modelo — y acá viven los
guardarraíles que impiden que el modelo toque el harness o se escape del repo.

Uso:  python3 -m unittest discover -s .github/scripts/test-agent -p 'test_*.py'
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SERVICE_ROOT", "back")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools  # noqa: E402


class ToolboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "back" / "test").mkdir(parents=True)
        (self.repo / "back" / "src" / "partidos").mkdir(parents=True)
        (self.repo / "back" / "test" / "setup-e2e.ts").write_text("harness")
        (self.repo / "back" / "test" / "partidos.example.e2e-spec.ts").write_text("ejemplo")
        (self.repo / "back" / "src" / "partidos" / "svc.ts").write_text("export const x = 1;")
        (self.repo / "secreto.txt").write_text("no me toques")
        self.box = tools.Toolbox(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # --- escritura: el guardarraíl que protege el harness ------------------

    def test_escribe_un_spec_valido(self):
        r = self.box.write_spec_file("back/test/partidos.e2e-spec.ts", "const a = 1;\n")
        self.assertTrue(r.ok, r.output)
        self.assertIn("back/test/partidos.e2e-spec.ts", self.box.written)

    def test_rechaza_escribir_el_harness(self):
        for path in ("back/test/setup-e2e.ts", "back/test/fixtures.ts",
                     "back/test/jest-e2e.json", "back/test/stubs/x.ts"):
            r = self.box.write_spec_file(path, "malicioso")
            self.assertFalse(r.ok, f"{path} NO debería poder escribirse")
        self.assertEqual((self.repo / "back/test/setup-e2e.ts").read_text(), "harness")

    def test_rechaza_pisar_el_spec_de_ejemplo(self):
        r = self.box.write_spec_file(
            "back/test/partidos.example.e2e-spec.ts", "otra cosa")
        self.assertFalse(r.ok)
        self.assertEqual(
            (self.repo / "back/test/partidos.example.e2e-spec.ts").read_text(), "ejemplo")

    def test_rechaza_escribir_codigo_de_aplicacion(self):
        r = self.box.write_spec_file("back/src/partidos/svc.ts", "hackeado")
        self.assertFalse(r.ok)
        self.assertEqual(
            (self.repo / "back/src/partidos/svc.ts").read_text(), "export const x = 1;")

    def test_rechaza_path_traversal(self):
        for path in ("../../../etc/passwd", "/etc/passwd",
                     "back/test/../../../x.e2e-spec.ts"):
            self.assertFalse(self.box.write_spec_file(path, "x").ok, path)

    def test_rechaza_specs_con_demasiadas_lineas(self):
        r = self.box.write_spec_file(
            "back/test/gigante.e2e-spec.ts",
            "\n".join(["x"] * (tools.MAX_SPEC_LINES + 10)))
        self.assertFalse(r.ok)
        self.assertIn("demasiado grande", r.output)

    def test_rechaza_specs_con_demasiados_bytes(self):
        """El límite que realmente protege contra el truncado por max_tokens.

        Una corrida entera terminó con cero specs porque el cap de LÍNEAS
        bloqueaba archivos que ya estaban por debajo del de bytes. Las líneas
        son la red de contención; los bytes son el límite real.
        """
        r = self.box.write_spec_file(
            "back/test/pesado.e2e-spec.ts", "x" * (tools.MAX_SPEC_BYTES + 100))
        self.assertFalse(r.ok)
        self.assertIn("demasiado grande", r.output)

    def test_acepta_un_spec_de_tamano_realista(self):
        """~210 líneas es el tamaño natural de un spec de 12 casos. Rechazarlo
        fue el bug que se comió una corrida."""
        linea = "  // comentario de relleno para simular un spec real\n"
        r = self.box.write_spec_file("back/test/realista.e2e-spec.ts", linea * 210)
        self.assertTrue(r.ok, r.output)

    def test_rechaza_contenido_vacio(self):
        self.assertFalse(self.box.write_spec_file("back/test/a.e2e-spec.ts", "  ").ok)

    def test_no_escribe_fuera_del_repo(self):
        """`safe_resolve` es la frontera de confianza y sigue viva aunque las
        acciones de lectura se hayan ido: el path lo elige el modelo."""
        for ruta in ("../../../etc/cron.d/x.e2e-spec.ts",
                     "/etc/cron.d/x.e2e-spec.ts",
                     "back/test/../../../x.e2e-spec.ts"):
            self.assertFalse(
                self.box.write_spec_file(ruta, "it('[AC-1] x', () => {});").ok,
                f"dejó escribir en {ruta!r}")

    # --- oráculo -----------------------------------------------------------

    def test_run_tests_cuenta_las_corridas(self):
        self.box.run_tests()   # falla: no hay npm project, pero debe contar
        self.assertEqual(self.box.test_runs, 1)


class OraculoCompilaTest(unittest.TestCase):
    """El agente tiene que ver la misma vara que lo juzga: ts-jest es más
    permisivo que `tsc --noEmit`, y tres corridas pasaron los tests y murieron
    en el compile del validador por algo que nunca se les mostró."""

    class Fake:
        def __init__(self, rc, out=""):
            self.returncode, self.stdout, self.stderr = rc, out, ""

    SPEC = "back/test/join-requests.e2e-spec.ts"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name) / "back" / "test").mkdir(parents=True)
        (Path(self.tmp.name) / self.SPEC).write_text("it('[AC-1] x', () => {});")
        self.box = tools.Toolbox(Path(self.tmp.name))
        self.box.written.append(self.SPEC)
        self.real = tools.subprocess.run
        self.cmds = []

    def tearDown(self):
        tools.subprocess.run = self.real
        self.tmp.cleanup()

    def fake(self, jest_rc, tsc_rc, tsc_out="x.ts(1,1): error TS2339: nope",
             lint_rc=0, lint_out="x.ts:1:1  error  Unsafe member access .id"):
        def _run(cmd, **kw):
            self.cmds.append(cmd[0] if cmd[0] != "npx" else f"npx {cmd[1]}")
            if cmd[:2] == ["npx", "tsc"]:
                return self.Fake(tsc_rc, tsc_out)
            if cmd[:2] == ["npx", "eslint"]:
                return self.Fake(lint_rc, lint_out)
            return self.Fake(jest_rc, "Tests: 3 passed, 3 total")
        tools.subprocess.run = _run

    def test_jest_verde_y_tsc_rojo_no_es_verde(self):
        self.fake(jest_rc=0, tsc_rc=1)
        r = self.box.run_tests()
        self.assertFalse(r.ok)
        self.assertIn("no compila", r.output)
        self.assertIn("TS2339", r.output)

    def test_jest_verde_y_tsc_verde_si_es_verde(self):
        self.fake(jest_rc=0, tsc_rc=0)
        self.assertTrue(self.box.run_tests().ok)

    def test_compile_y_lint_se_informan_JUNTOS(self):
        """SPO-197: cortar en el tsc mandó la corrida a un ping-pong de 15
        iteraciones — tipaba el body para callar al lint, eso destapaba
        TS18048, destipaba, y volvía el lint. Nunca vio los dos a la vez."""
        self.fake(jest_rc=0, tsc_rc=1, lint_rc=1)
        r = self.box.run_tests()
        self.assertFalse(r.ok)
        self.assertIn("NO COMPILA", r.output)
        self.assertIn("NO PASA EL LINT", r.output)
        self.assertIn("LAS DOS COSAS", r.output)
        self.assertIn("npx tsc", self.cmds)
        self.assertIn("npx eslint", self.cmds)

    def test_con_jest_rojo_igual_se_muestran_los_errores_de_compile(self):
        """SPO-197: el tsc corría solo con Jest en verde. Los tests estaban en
        rojo, el agente nunca vio los TS2305/2307 de sus imports rotos, adivinó
        mal cuatro iteraciones y el validador lo mató con esos mismos errores."""
        self.fake(jest_rc=1, tsc_rc=1)
        r = self.box.run_tests()
        self.assertFalse(r.ok)
        self.assertIn("npx tsc", self.cmds)
        self.assertIn("NO COMPILA", r.output)
        self.assertIn("TS2339", r.output)
        # El rojo de Jest sigue estando: el compile va primero, no en lugar de.
        self.assertIn("3 passed", r.output)
        self.assertFalse(r.meta["tsc"])

    def test_con_jest_rojo_y_tsc_verde_solo_se_reporta_el_rojo(self):
        self.fake(jest_rc=1, tsc_rc=0)
        r = self.box.run_tests()
        self.assertFalse(r.ok)
        self.assertNotIn("NO COMPILA", r.output)
        self.assertTrue(r.meta["tsc"])


class NoTestsRegexTest(unittest.TestCase):
    """Un verde de cero tests es un oráculo mintiendo (SPO-168)."""

    def test_detecta_filtro_que_no_matcheo_nada(self):
        self.assertTrue(tools.NO_TESTS_RE.search(
            "Test Suites: 1 passed, 1 total\nTests:       0 total\n"))

    def test_detecta_ningun_suite(self):
        self.assertTrue(tools.NO_TESTS_RE.search(
            "No tests found, exiting with code 0"))

    def test_no_dispara_con_una_corrida_real(self):
        self.assertIsNone(tools.NO_TESTS_RE.search(
            "Test Suites: 2 passed, 2 total\nTests:       11 passed, 11 total\n"))


class SpecRegexTest(unittest.TestCase):
    def test_solo_matchea_specs_e2e(self):
        self.assertTrue(tools.SPEC_RE.match("back/test/partidos.e2e-spec.ts"))
        for bad in ("back/test/setup-e2e.ts", "back/test/a.spec.ts",
                    "back/src/a.e2e-spec.ts", "back/test/sub/a.e2e-spec.ts",
                    "test/a.e2e-spec.ts"):
            self.assertIsNone(tools.SPEC_RE.match(bad), bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class OraculoLinteaTest(unittest.TestCase):
    """SPO-197 / PR #61: el spec compiló, pasó los tests, se entregó — y
    `npm run lint` del CI la volteó con 8 errores de `res.body` sin tipar.
    Tercera vara que el agente no veía."""

    class Fake:
        def __init__(self, rc, out=""):
            self.returncode, self.stdout, self.stderr = rc, out, ""

    SPEC = "back/test/join-requests.e2e-spec.ts"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "back" / "test").mkdir(parents=True)
        (root / self.SPEC).write_text("it('[AC-1] x', () => {});")
        self.box = tools.Toolbox(root)
        self.box.written.append(self.SPEC)
        self.real = tools.subprocess.run
        self.cmds = []

    def tearDown(self):
        tools.subprocess.run = self.real
        self.tmp.cleanup()

    def fake(self, lint_rc, lint_out="1:1  error  Unsafe member access .id"):
        def _run(cmd, **kw):
            self.cmds.append(cmd)
            if cmd[:2] == ["npx", "eslint"]:
                return self.Fake(lint_rc, lint_out)
            return self.Fake(0, "Tests: 3 passed, 3 total")
        tools.subprocess.run = _run

    def test_lint_rojo_no_es_verde(self):
        self.fake(lint_rc=1)
        r = self.box.run_tests()
        self.assertFalse(r.ok)
        self.assertIn("NO PASA EL LINT", r.output)
        self.assertIn("Unsafe member access", r.output)
        # El encabezado de sección no se duplica con el del helper.
        self.assertEqual(r.output.count("NO PASA EL LINT"), 1)
        self.assertFalse(r.meta["eslint"])

    def test_lint_verde_si_es_verde(self):
        self.fake(lint_rc=0)
        r = self.box.run_tests()
        self.assertTrue(r.ok)
        self.assertTrue(r.meta["eslint"])

    def test_solo_lintea_los_specs_del_agente_y_sin_fix(self):
        """`npm run lint` del repo lleva --fix sobre src/, que el agente tiene
        prohibido tocar. Se invoca eslint derecho y acotado."""
        self.fake(lint_rc=0)
        self.box.run_tests()
        eslint = [c for c in self.cmds if c[:2] == ["npx", "eslint"]][0]
        self.assertIn("test/join-requests.e2e-spec.ts", eslint)
        self.assertIn("--no-fix", eslint)
        self.assertNotIn("--fix", eslint[2:])
        self.assertFalse([a for a in eslint if a.startswith("src")])

    def test_eslint_roto_no_bloquea_al_agente(self):
        """exit 2 es config rota o crash del linter, no un spec malo. El agente
        no puede arreglar eso, así que no se lo cuelga."""
        self.fake(lint_rc=2, lint_out="Error: Cannot find config")
        r = self.box.run_tests()
        self.assertTrue(r.ok)
        self.assertNotIn("NO PASA EL LINT", r.output)

    def test_sin_specs_escritos_no_lintea(self):
        self.box.written.clear()
        self.fake(lint_rc=1)
        self.assertTrue(self.box.run_tests().ok)
