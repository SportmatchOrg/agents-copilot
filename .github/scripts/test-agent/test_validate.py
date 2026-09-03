#!/usr/bin/env python3
"""Test de la guarda anti-assert-debilitado (§4, prohibición 1).

Nace de SPO-168: el agente bajó `.expect(400)` a `.expect(201)` y renombró el
test para que describiera lo que hace el código en vez de lo que pide el AC.
La regla 2 de §4 no lo agarra —el snapshot solo cubre bloques ya marcados
`it.failing`— así que el AC se contaba como cubierto.

Uso:  python3 -m unittest discover -s .github/scripts/test-agent -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools  # noqa: E402

_s = importlib.util.spec_from_file_location(
    "validate_output", Path(__file__).resolve().parent / "validate-output.py")
v = importlib.util.module_from_spec(_s)
_s.loader.exec_module(v)

SPEC = """
  it('[AC-7] enviar usuarioId en el body no cambia quién se une (se ignora)', async () => {
    await request(server).post(`/partidos/${id}/participantes`)
      .send({ usuarioId: 'x' }).expect(201);
  });

  it('[AC-4] en un partido que ya pasó devuelve 400', async () => {
    await request(server).post(`/partidos/${id}/participantes`).expect(400);
  });
"""


class AssertDebilitadoTest(unittest.TestCase):
    def test_marca_el_assert_aflojado(self):
        ac = "Mandar un `usuarioId` en el body no cambia quién se anota "\
             "(devuelve **400** por la whitelist)."
        self.assertFalse(v.asserts_lo_que_pide(ac, tools.ac_block(SPEC, "AC-7")))

    def test_deja_pasar_el_que_verifica_lo_pedido(self):
        ac = "En un partido que ya pasó devuelve **400**."
        self.assertTrue(v.asserts_lo_que_pide(ac, tools.ac_block(SPEC, "AC-4")))

    def test_alcanza_con_uno_de_los_status_del_criterio(self):
        # AC-6 pide 404 y 401; el 401 es intesteable con el guard overrideado.
        ac = "Un id de partido inexistente devuelve **404**; sin token, **401**."
        self.assertTrue(v.asserts_lo_que_pide(ac, "await x.expect(404);"))

    def test_un_ac_sin_status_no_se_cruza(self):
        ac = "Las queries viven en el repository; las excepciones, en el service."
        self.assertTrue(v.asserts_lo_que_pide(ac, "expect(res.body).toHaveLength(1);"))

    def test_ignora_numeros_que_no_son_status(self):
        self.assertTrue(v.asserts_lo_que_pide("El cupo máximo es 30.", "expect(a).toBe(1)"))

    def test_bloque_de_un_ac_inexistente_queda_vacio(self):
        self.assertEqual(tools.ac_block(SPEC, "AC-99"), "")

    def test_el_bloque_no_se_come_el_test_siguiente(self):
        self.assertNotIn("AC-4", tools.ac_block(SPEC, "AC-7"))


class ReglaDosVerbatimTest(unittest.TestCase):
    """El plan pide el bloque verbatim; el código guardaba solo el nombre."""

    MARCADO = """
  it.failing('[AC-7] devuelve 400 por whitelist', async () => {
    await request(server).post('/x').send({ usuarioId: 'y' }).expect(400);
  });
"""
    VACIADO = """
  it.failing('[AC-7] devuelve 400 por whitelist', async () => {
    expect(true).toBe(true);
  });
"""

    def test_mismo_nombre_y_cuerpo_da_la_misma_huella(self):
        otro = self.MARCADO.replace("  it.failing", "    it.failing")
        self.assertEqual(tools.failing_blocks(self.MARCADO)[0]["sha"],
                         tools.failing_blocks(otro)[0]["sha"])

    def test_vaciar_el_cuerpo_cambia_la_huella(self):
        a = tools.failing_blocks(self.MARCADO)[0]
        b = tools.failing_blocks(self.VACIADO)[0]
        self.assertEqual(a["name"], b["name"])
        self.assertNotEqual(a["sha"], b["sha"])


class FailedAcParseTest(unittest.TestCase):
    def test_saca_los_ac_de_la_salida_de_jest(self):
        salida = ("  \u25cf Participantes (SPO-168) \u203a [AC-7] enviar usuarioId\n"
                  "  \u25cf Participantes (SPO-168) \u203a [AC-3] cupo lleno\n")
        self.assertEqual(sorted(set(tools.FAILED_AC_RE.findall(salida))),
                         ["AC-3", "AC-7"])

    def test_una_suite_verde_no_reporta_ninguno(self):
        self.assertEqual(tools.FAILED_AC_RE.findall("Tests: 16 passed, 16 total"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
