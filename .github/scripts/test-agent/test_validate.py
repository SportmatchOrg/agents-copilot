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
        self.assertFalse(v.asserts_lo_que_pide(ac, v.test_block(SPEC, "AC-7")))

    def test_deja_pasar_el_que_verifica_lo_pedido(self):
        ac = "En un partido que ya pasó devuelve **400**."
        self.assertTrue(v.asserts_lo_que_pide(ac, v.test_block(SPEC, "AC-4")))

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
        self.assertEqual(v.test_block(SPEC, "AC-99"), "")

    def test_el_bloque_no_se_come_el_test_siguiente(self):
        self.assertNotIn("AC-4", v.test_block(SPEC, "AC-7"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
