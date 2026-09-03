#!/usr/bin/env python3
"""Test de la extracción de AC (plan §8, "cómo se mide la cobertura").

El parser es el que decide qué se considera un criterio, y de ahí sale la
métrica principal de §11. Si se cuela un paso de implementación como si fuera
un AC, la cobertura mide otra cosa y nadie se entera.

Uso:  python3 -m unittest discover -s .github/scripts/test-agent -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "prefetch_context", Path(__file__).resolve().parent / "prefetch-context.py")
prefetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prefetch)

# Forma real de los tickets de SportMatch: una guía de implementación numerada
# ANTES de la sección de AC. Sin recortar a la sección, la guía se colaba y en
# SPO-168 no entraba un solo criterio real.
TICKET = """Contexto del ticket.

## Implementación

1. En `back/prisma/schema.prisma`, agregar el modelo.
2. Migrar y sumar al seed dos anotados.
3. Las reglas van en el service, en este orden:

**Criterios de aceptación**

- [ ] `POST /partidos/:id/participantes` devuelve **201**.
- [ ] Anotarse dos veces devuelve **409**.
- [x] Con el cupo lleno devuelve **409**.
"""


class AcceptanceCriteriaTest(unittest.TestCase):
    def test_ignora_los_pasos_de_implementacion(self):
        ac = prefetch.acceptance_criteria(TICKET)
        self.assertEqual(len(ac), 3)
        for paso in ("schema.prisma", "Migrar", "en este orden"):
            self.assertFalse([c for c in ac if paso in c], paso)

    def test_saca_el_checkbox(self):
        ac = prefetch.acceptance_criteria(TICKET)
        self.assertTrue(ac[0].startswith("`POST"), ac[0])
        self.assertTrue(ac[2].startswith("Con el cupo"), ac[2])

    def test_sin_seccion_cae_al_barrido_completo(self):
        """Comportamiento documentado para tickets sin sección de AC."""
        ac = prefetch.acceptance_criteria("- primer bullet suelto\n- segundo bullet")
        self.assertEqual(ac, ["primer bullet suelto", "segundo bullet"])

    def test_prosa_sin_vinetas_no_inventa_nada(self):
        self.assertEqual(prefetch.acceptance_criteria("Todo en prosa, sin listas."), [])
        self.assertEqual(prefetch.acceptance_criteria(""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
