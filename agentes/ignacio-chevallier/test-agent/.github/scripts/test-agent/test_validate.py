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


class SubEtiquetasTest(unittest.TestCase):
    """Un AC del ticket puede empaquetar varias afirmaciones —"inexistente →
    404. Ya jugado → 400. Sin token → 401"— y el agente lo parte en `[AC-4a]` y
    `[AC-4b]`. Sin el sufijo, esos tests no matcheaban ninguna regex y el
    trabajo no contaba para nada."""

    SPEC = """
  it('[AC-4a] inexistente devuelve 404', async () => { await x.expect(404); });
  it.failing('[AC-4b] ya jugado devuelve 400', async () => { await x.expect(400); });
  it('[AC-5] otro caso', async () => { await x.expect(200); });
"""

    def test_la_cobertura_cuenta_el_ac_base(self):
        self.assertEqual(sorted(set(v.AC_RE.findall(self.SPEC))), ["AC-4", "AC-5"])

    def test_el_bloque_se_encuentra_por_el_ac_base(self):
        b = tools.ac_block(self.SPEC, "AC-4")
        self.assertIn("expect(404)", b)
        self.assertNotIn("AC-5", b)

    def test_junta_TODOS_los_bloques_del_mismo_ac(self):
        # Caso real de SPO-182: `[AC-7]` era un placeholder honesto sobre el
        # límite del harness y `[AC-7b]` verificaba el 404. Mirando solo el
        # primero, el AC figuraba sin verificar y la guarda lo marcaba mal.
        spec = """
  it('[AC-7] sin token devuelve 401', async () => { expect(true).toBe(true); });
  it('[AC-7b] id inexistente devuelve 404', async () => { await x.expect(404); });
  it('[AC-8] otra cosa', async () => { await x.expect(200); });
"""
        b = tools.ac_block(spec, "AC-7")
        self.assertIn("expect(404)", b)
        self.assertNotIn("AC-8", b)
        self.assertTrue(v.asserts_lo_que_pide(
            "Sin token, **401**. Id inexistente, **404**.", b))

    def test_es_failing_ve_la_sub_etiqueta(self):
        self.assertTrue(v._es_failing(self.SPEC, "AC-4"))

    def test_un_ac_sin_sufijo_sigue_andando(self):
        self.assertIn("expect(200)", tools.ac_block(self.SPEC, "AC-5"))

    def test_jest_reporta_el_ac_base(self):
        self.assertEqual(tools.FAILED_AC_RE.findall("● S › [AC-4b] ya jugado"), ["AC-4"])


class ReglaDosVeredictoTest(unittest.TestCase):
    """La regla 2 estuvo mal dos veces: primero floja (comparaba solo nombres,
    así que vaciar el cuerpo pasaba) y después estricta de más (bloqueaba al
    agente corrigiendo una marca que Jest le dijo que sobraba)."""

    FINAL = {"[AC-4] ya jugado devuelve 400": "aaa"}

    def test_intacto(self):
        self.assertEqual(v.r2_veredicto(
            "[AC-4] ya jugado devuelve 400", "aaa", self.FINAL, set()), "sigue")

    def test_cuerpo_distinto_se_permite(self):
        self.assertEqual(v.r2_veredicto(
            "[AC-4] ya jugado devuelve 400", "bbb", self.FINAL, set()), "cuerpo")

    def test_desaparecido_aborta(self):
        self.assertEqual(v.r2_veredicto(
            "[AC-9] otro test", "zzz", self.FINAL, set()), "falta")

    def test_desaparecido_pero_jest_dijo_que_sobraba(self):
        self.assertEqual(v.r2_veredicto(
            "[AC-9] otro test", "zzz", self.FINAL, {"AC-9"}), "destildado")

    def test_la_excusa_es_por_ac_no_general(self):
        # Que AC-7 sobrara no habilita borrar el de AC-9.
        self.assertEqual(v.r2_veredicto(
            "[AC-9] otro test", "zzz", self.FINAL, {"AC-7"}), "falta")

    def test_corrida_vieja_sin_sha_no_rompe(self):
        self.assertEqual(v.r2_veredicto(
            "[AC-4] ya jugado devuelve 400", None, self.FINAL, set()), "sigue")


class MarcasDeMasParseTest(unittest.TestCase):
    def test_detecta_el_aviso_de_jest(self):
        salida = ("  \u25cf Partidos \u203a [AC-7] no se puede bajar a otro\n"
                  "    Failing test passed even though it was supposed to fail.\n"
                  "  \u25cf Partidos \u203a [AC-3] otro que falla de verdad\n"
                  "    expected 404 got 500\n")
        self.assertEqual(tools.marcas_de_mas(salida), ["AC-7"])

    def test_una_suite_normal_no_reporta_nada(self):
        self.assertEqual(tools.marcas_de_mas("Tests: 9 passed, 9 total"), [])


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
