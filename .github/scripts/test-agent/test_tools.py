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

    def test_rechaza_specs_demasiado_largos(self):
        r = self.box.write_spec_file(
            "back/test/gigante.e2e-spec.ts", "\n".join(["x"] * 300))
        self.assertFalse(r.ok)
        self.assertIn("demasiado grande", r.output)

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


class SpecRegexTest(unittest.TestCase):
    def test_solo_matchea_specs_e2e(self):
        self.assertTrue(tools.SPEC_RE.match("back/test/partidos.e2e-spec.ts"))
        for bad in ("back/test/setup-e2e.ts", "back/test/a.spec.ts",
                    "back/src/a.e2e-spec.ts", "back/test/sub/a.e2e-spec.ts",
                    "test/a.e2e-spec.ts"):
            self.assertIsNone(tools.SPEC_RE.match(bad), bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
