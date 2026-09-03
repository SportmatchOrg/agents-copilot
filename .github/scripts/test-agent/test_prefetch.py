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
