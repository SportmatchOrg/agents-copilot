#!/usr/bin/env python3
"""Test del parseo de criterios de aceptación (plan §8, §11).

La cobertura es la métrica principal del piloto, así que el DENOMINADOR importa
tanto como el numerador. En SPO-182 la lista arrancaba bien pero no terminaba
nunca: se comía la sección `**Notas**` y dos bullets de justificación entraban
como AC-11 y AC-12.

Uso:  python3 -m unittest discover -s .github/scripts/test-agent -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_s = importlib.util.spec_from_file_location(
    "prefetch", Path(__file__).resolve().parent / "prefetch-context.py")
pf = importlib.util.module_from_spec(_s)
_s.loader.exec_module(pf)

TICKET = """**Referencia:** RF-05 · WBS 6.1.2

**Descripción**

La pantalla muestra quién juega.

**Pasos**

1. En el repository, agregar los participantes al detalle.
2. En el service, aplanar la respuesta.

**Criterios de aceptación**

- [ ] `GET /partidos/:id` devuelve `participantes`, ordenados por antigüedad.
- [ ] La respuesta **no** expone `email` ni `firebaseUid`.
- [ ] `npm run lint` y `npm run build` pasan.

**Notas**

* Se agrega solo al detalle a propósito.
* Este endpoint permite construir la pantalla 05 completa.
"""


class CriteriosTest(unittest.TestCase):
    def test_arranca_en_los_criterios_y_no_en_los_pasos(self):
        c = pf.acceptance_criteria(TICKET)
        self.assertTrue(c[0].startswith("`GET /partidos/:id`"), c[0])
        self.assertFalse(any("repository" in x for x in c))

    def test_corta_antes_de_las_notas(self):
        c = pf.acceptance_criteria(TICKET)
        self.assertEqual(len(c), 3)
        self.assertFalse(any("a propósito" in x for x in c))
        self.assertFalse(any("pantalla 05" in x for x in c))

    def test_el_checkbox_no_es_parte_del_criterio(self):
        self.assertFalse(pf.acceptance_criteria(TICKET)[0].startswith("["))

    def test_sin_encabezado_no_inventa_criterios(self):
        self.assertEqual(pf.acceptance_criteria("Un ticket en prosa, sin listas."), [])

    def test_ticket_vacio(self):
        self.assertEqual(pf.acceptance_criteria(""), [])
        self.assertEqual(pf.acceptance_criteria(None), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ContratoDeImportsTest(unittest.TestCase):
    """SPO-197: el harness completo YA iba en el contexto y no alcanzó. El
    agente importó TEST_USER y OTHER_USER de `setup-e2e` — viven en `fixtures`
    — y murió con TS2459/TS2305 en las dos corridas. `setup-e2e.ts` importa
    TEST_USER, así que el símbolo aparece ahí: la frontera hay que decirla."""

    SETUP = """import { TEST_USER } from './fixtures';
let currentUser: FirebaseUser = TEST_USER;
export function setAuthUser(user: FirebaseUser): void {}
export interface TestContext {}
export async function createTestApp(): Promise<TestContext> {}
"""
    FIXTURES = """export const TEST_USER: FirebaseUser = {};
export const OTHER_USER: FirebaseUser = {};
export async function seedBaseline(prisma: PrismaService) {}
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        test_dir = self.repo / pf.SERVICE_ROOT / "test"
        test_dir.mkdir(parents=True)
        (test_dir / "setup-e2e.ts").write_text(self.SETUP)
        (test_dir / "fixtures.ts").write_text(self.FIXTURES)

    def tearDown(self):
        self.tmp.cleanup()

    def test_atribuye_cada_simbolo_a_su_archivo(self):
        out = pf.import_contract(self.repo)
        setup, fixtures = out.split("de './fixtures':")
        # Lo que mató las dos corridas: TEST_USER/OTHER_USER van en fixtures.
        self.assertIn("TEST_USER", fixtures)
        self.assertIn("OTHER_USER", fixtures)
        self.assertNotIn("TEST_USER", setup.split("de './setup-e2e':")[1])
        self.assertIn("createTestApp", setup)

    def test_avisa_la_profundidad_del_import_de_src(self):
        self.assertIn("'../src/...'", pf.import_contract(self.repo))

    def test_sin_harness_no_inventa_el_bloque(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertIsNone(pf.import_contract(Path(empty)))
