#!/usr/bin/env python3
"""Test de la guarda del oráculo (plan §8).

`_spec_verified` decide si la corrida se publica. Se equivoca en un sentido y
entregás un spec que nunca corrió — pasó dos veces, con job verde y todo.

`run-agent.py` tiene guión, así que no se importa como módulo normal.

Uso:  python3 -m unittest discover -s .github/scripts/test-agent -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path

os.environ.setdefault("LLM_API_KEY", "test-key")
_spec = importlib.util.spec_from_file_location(
    "run_agent", Path(__file__).resolve().parent / "run-agent.py")
run_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_agent)


def w(ok=True):
    return {"action": "write_spec_file", "ok": ok}


def t(ok):
    return {"action": "run_tests", "ok": ok}


class SpecVerifiedTest(unittest.TestCase):
    def test_write_seguido_de_tests_verdes(self):
        self.assertTrue(run_agent._spec_verified([w(), t(True)]))

    def test_corte_por_budget_justo_despues_de_escribir(self):
        # La corrida de SPO-168: write → test ✗ → write → test ✗ → write → fin.
        self.assertFalse(run_agent._spec_verified(
            [w(), t(False), w(), t(False), w()]))

    def test_ultima_corrida_en_rojo_no_alcanza(self):
        self.assertFalse(run_agent._spec_verified([w(), t(True), w(), t(False)]))

    def test_tests_verdes_previos_al_ultimo_write_no_cuentan(self):
        self.assertFalse(run_agent._spec_verified([w(), t(True), w()]))

    def test_sin_specs_no_hay_nada_verificado(self):
        self.assertFalse(run_agent._spec_verified([t(True)]))
        self.assertFalse(run_agent._spec_verified([]))

    def test_un_write_rechazado_no_cuenta_como_el_ultimo(self):
        # El write de la iteración 3 falló por validación de entrada: el spec
        # vigente sigue siendo el de la 1, y ese sí se corrió en verde.
        self.assertTrue(run_agent._spec_verified([w(), t(True), w(ok=False)]))


class ObservationNudgeTest(unittest.TestCase):
    """El recordatorio de §4 solo aparece cuando hace falta.

    En cada turno, no: sumar 1.5 KB a cada observación empuja el contexto y
    convierte el aviso en ruido que el modelo aprende a saltear.
    """

    def obs(self, ok, nudge):
        r = run_agent.tools_mod.ToolResult(ok, "salida")
        return run_agent.observation("run_tests", r, nudge)

    def test_lleva_la_clasificacion_cuando_se_la_pasan(self):
        self.assertIn("CLASIFICÁ ANTES DE REESCRIBIR",
                      self.obs(False, run_agent.CLASIFICA))

    def test_sin_nudge_la_observacion_queda_limpia(self):
        out = self.obs(False, "")
        self.assertNotIn("CLASIFICÁ", out)
        self.assertTrue(out.endswith("salida"))

    def test_nombra_las_tres_categorias_de_seccion_4(self):
        for cat in ("test_error", "suspected_bug", "blocked", "it.failing"):
            self.assertIn(cat, run_agent.CLASIFICA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
