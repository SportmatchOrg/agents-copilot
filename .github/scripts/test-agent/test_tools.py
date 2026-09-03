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

    # --- lectura -----------------------------------------------------------

    def test_lee_dentro_del_repo(self):
        r = self.box.read_file("back/src/partidos/svc.ts")
        self.assertTrue(r.ok)
        self.assertIn("export const x", r.output)

    def test_no_lee_fuera_del_repo(self):
        self.assertFalse(self.box.read_file("../../../etc/hosts").ok)
        self.assertFalse(self.box.read_file("/etc/hosts").ok)

    def test_recorta_archivos_grandes(self):
        big = self.repo / "back" / "grande.ts"
        big.write_text("a" * (tools.MAX_FILE_BYTES + 5000))
        r = self.box.read_file("back/grande.ts")
        self.assertTrue(r.ok)
        self.assertIn("recortado", r.output)

    def test_list_dir_oculta_node_modules(self):
        (self.repo / "back" / "node_modules").mkdir()
        r = self.box.list_dir("back")
        self.assertTrue(r.ok)
        self.assertNotIn("node_modules", r.output)

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

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name) / "back").mkdir()
        self.box = tools.Toolbox(Path(self.tmp.name))
        self.real = tools.subprocess.run
        self.cmds = []

    def tearDown(self):
        tools.subprocess.run = self.real
        self.tmp.cleanup()

    def fake(self, jest_rc, tsc_rc, tsc_out="x.ts(1,1): error TS2339: nope"):
        def _run(cmd, **kw):
            self.cmds.append(cmd[0])
            if cmd[0] == "npx":
                return self.Fake(tsc_rc, tsc_out)
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

    def test_con_jest_rojo_no_se_paga_el_tsc(self):
        self.fake(jest_rc=1, tsc_rc=0)
        self.assertFalse(self.box.run_tests().ok)
        self.assertNotIn("npx", self.cmds)


class SearchSinRipgrepTest(unittest.TestCase):
    """Los runners de GitHub no traen `rg`: en CI esta herramienta estuvo muerta
    desde el día uno y en SPO-171 mató una corrida por bucle."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repo = Path(self.tmp.name)
        (repo / "back" / "src").mkdir(parents=True)
        (repo / "back" / "src" / "a.ts").write_text("export const findById = 1;\n")
        (repo / "back" / "node_modules").mkdir()
        (repo / "back" / "node_modules" / "b.ts").write_text("findById ruido\n")
        self.box = tools.Toolbox(repo)
        self._which = tools.shutil.which
        tools.shutil.which = lambda n: None if n == "rg" else self._which(n)

    def tearDown(self):
        tools.shutil.which = self._which
        self.tmp.cleanup()

    def test_encuentra_con_grep(self):
        r = self.box.search("findById")
        self.assertTrue(r.ok, r.output)
        self.assertIn("back/src/a.ts", r.output)

    def test_grep_respeta_las_exclusiones(self):
        self.assertNotIn("node_modules", self.box.search("findById").output)

    def test_sin_coincidencias_no_es_error(self):
        r = self.box.search("noExisteEnNingunLado")
        self.assertTrue(r.ok)
        self.assertIn("Sin coincidencias", r.output)


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
