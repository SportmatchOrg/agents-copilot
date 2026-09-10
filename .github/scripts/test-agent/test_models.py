#!/usr/bin/env python3
"""Test de la cadena de modelos (plan §5.5).

Cubre la rama que falló en la corrida de SPO-168: el modelo devolvió `{}` —
JSON válido, pero no una acción — y como `extract_json` no fallaba, la cadena
nunca avanzaba. Dos turnos quemados con tres modelos de respaldo sin estrenar.

Uso:  python3 -m unittest discover -s .github/scripts/test-agent -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("LLM_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import llm_client  # noqa: E402


def reply(content: str, model: str = "servido/por-el-router") -> tuple[int, str]:
    return 200, json.dumps({"model": model,
                            "choices": [{"message": {"content": content}}]})


ACTION = '{"thought": "escribo", "action": "write_spec_file", "args": {}}'


class ChainAdvanceTest(unittest.TestCase):
    def setUp(self):
        self._post = llm_client._post
        self.calls: list[str] = []

    def tearDown(self):
        llm_client._post = self._post

    def fake_post(self, bodies: list[tuple[int, str]]):
        def _fake(url, key, payload, timeout):
            self.calls.append(payload["model"])
            return bodies[len(self.calls) - 1]
        llm_client._post = _fake

    def test_json_sin_action_avanza_de_modelo(self):
        # `{}` dos veces sobre el primero: una repregunta, después la cadena avanza.
        self.fake_post([reply("{}"), reply("{}"), reply(ACTION)])
        client = models.ChainClient(chain=["modelo-a", "modelo-b"])
        out, used = client.ask([{"role": "user", "content": "x"}])
        self.assertEqual(out["action"], "write_spec_file")
        self.assertEqual(self.calls, ["modelo-a", "modelo-a", "modelo-b"])
        self.assertEqual(used, "servido/por-el-router")

    def test_una_accion_valida_no_repregunta(self):
        self.fake_post([reply(ACTION)])
        client = models.ChainClient(chain=["modelo-a"])
        out, _ = client.ask([{"role": "user", "content": "x"}])
        self.assertEqual(out["action"], "write_spec_file")
        self.assertEqual(self.calls, ["modelo-a"])

    def test_sin_action_agota_la_cadena_en_vez_de_devolver_basura(self):
        self.fake_post([reply("{}")] * 6)
        client = models.ChainClient(chain=["modelo-a", "modelo-b"])
        with self.assertRaises(models.ChainExhausted):
            client.ask([{"role": "user", "content": "x"}])

    def test_registra_el_modelo_real_no_la_entrada_de_la_cadena(self):
        """Con `openrouter/free` el router elige: queremos saber quién contestó."""
        self.fake_post([reply(ACTION, model="nvidia/nemotron-3-super-120b-a12b:free")])
        client = models.ChainClient(chain=["openrouter/free"])
        _, used = client.ask([{"role": "user", "content": "x"}])
        self.assertEqual(used, "nvidia/nemotron-3-super-120b-a12b:free")


if __name__ == "__main__":
    unittest.main(verbosity=2)


QUOTA = (429, json.dumps({"error": {"message": "Rate limit exceeded: free-models-per-day"}}))


class SegundaKeyTest(unittest.TestCase):
    """SPO-197: `free-models-per-day` es por CUENTA, no por modelo. Los cuatro
    modelos de la cadena devolvieron 429 en ~300ms y la corrida murió en la
    iteración 5 de 15. El fallback de modelos no puede nada contra eso: hace
    falta otra cuenta."""

    def setUp(self):
        self._post = llm_client._post
        self._env = {k: os.environ.get(k)
                     for k in ("LLM_API_KEY", "LLM_API_KEY_FALLBACK")}
        self.calls: list[tuple[str, str]] = []

    def tearDown(self):
        llm_client._post = self._post
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def fake_post(self, bodies):
        def _fake(url, key, payload, timeout):
            self.calls.append((key, payload["model"]))
            return bodies[len(self.calls) - 1]
        llm_client._post = _fake

    def test_cuota_agotada_pasa_a_la_segunda_key_y_reinicia_la_cadena(self):
        os.environ["LLM_API_KEY"] = "key-1"
        os.environ["LLM_API_KEY_FALLBACK"] = "key-2"
        self.fake_post([QUOTA, QUOTA, reply(ACTION)])
        client = models.ChainClient(chain=["modelo-a", "modelo-b"])
        out, _ = client.ask([{"role": "user", "content": "x"}])
        self.assertEqual(out["action"], "write_spec_file")
        # La cadena arranca de cero en la segunda cuenta, no sigue en modelo-b.
        self.assertEqual(self.calls, [("key-1", "modelo-a"),
                                      ("key-1", "modelo-b"),
                                      ("key-2", "modelo-a")])

    def test_sin_segunda_key_la_cadena_se_agota(self):
        os.environ["LLM_API_KEY"] = "key-1"
        os.environ.pop("LLM_API_KEY_FALLBACK", None)
        self.fake_post([QUOTA, QUOTA])
        client = models.ChainClient(chain=["modelo-a", "modelo-b"])
        with self.assertRaises(models.ChainExhausted):
            client.ask([{"role": "user", "content": "x"}])

    def test_json_roto_no_gasta_la_segunda_key(self):
        """Otra cuenta produce el mismo JSON roto: rotar ahí es pagar cuatro
        modelos más de latencia para llegar al mismo lugar."""
        os.environ["LLM_API_KEY"] = "key-1"
        os.environ["LLM_API_KEY_FALLBACK"] = "key-2"
        self.fake_post([reply("{}")] * 4)
        client = models.ChainClient(chain=["modelo-a", "modelo-b"])
        with self.assertRaises(models.ChainExhausted):
            client.ask([{"role": "user", "content": "x"}])
        self.assertNotIn("key-2", [k for k, _ in self.calls])


class DiagnosticoTest(unittest.TestCase):
    """SPO-197: nemotron falló cuatro veces con las dos keys y el log decía
    solo "JSON inválido". Truncado por max_tokens, razonamiento suelto y basura
    del proveedor se ven iguales desde afuera y se arreglan distinto."""

    def test_truncado_se_reconoce_por_finish_reason(self):
        body = {"choices": [{"finish_reason": "length",
                             "message": {"content": '{"action": "wri'}}],
                "usage": {"completion_tokens": 8000, "total_tokens": 17000}}
        out = models.ChainClient._porque(body, '{"action": "wri')
        self.assertIn("finish_reason='length'", out)
        self.assertIn("8000/17000", out)
        self.assertIn("action", out)

    def test_razonamiento_sin_content_se_distingue_de_vacio(self):
        body = {"choices": [{"finish_reason": "stop",
                             "message": {"content": "", "reasoning": "x" * 4000}}]}
        self.assertIn("reasoning=4000 chars", models.ChainClient._porque(body))
        self.assertIn("content vacío", models.ChainClient._porque(body))

    def test_no_vuelca_respuestas_enormes_al_log(self):
        """El log de Actions es público y esto es salida cruda del modelo."""
        out = models.ChainClient._porque({}, "y" * 50_000)
        self.assertLess(len(out), 400)

    def test_body_deforme_no_explota(self):
        for body in ({}, {"choices": []}, {"choices": [None]}, {"choices": "raro"}):
            self.assertIsInstance(models.ChainClient._porque(body, "x"), str)


def truncado(content: str) -> tuple[int, str]:
    return 200, json.dumps({"model": "m", "choices": [
        {"finish_reason": "length", "message": {"content": content}}]})


class RazonamientoYTopeTest(unittest.TestCase):
    """SPO-197: nemotron gastó los 8000 tokens razonando (19428 chars) y lo
    cortaron a mitad del JSON — cuatro veces, con las dos keys, 0 iteraciones."""

    def setUp(self):
        self._post = llm_client._post
        self.payloads: list[dict] = []

    def tearDown(self):
        llm_client._post = self._post

    def fake(self, bodies):
        def _fake(url, key, payload, timeout):
            self.payloads.append(payload)
            return bodies[len(self.payloads) - 1]
        llm_client._post = _fake

    def test_pide_razonamiento_bajo_y_deja_techo_para_el_spec(self):
        self.fake([reply(ACTION)])
        models.ChainClient(chain=["m"]).ask([{"role": "user", "content": "x"}])
        self.assertEqual(self.payloads[0]["reasoning"], {"effort": "low"})
        self.assertGreaterEqual(self.payloads[0]["max_tokens"], 16000)

    def test_si_el_modelo_rechaza_reasoning_sigue_sin_el(self):
        rechazo = (400, json.dumps({"error": {"message": "unknown field reasoning"}}))
        self.fake([rechazo, reply(ACTION)])
        client = models.ChainClient(chain=["m"])
        out, _ = client.ask([{"role": "user", "content": "x"}])
        self.assertEqual(out["action"], "write_spec_file")
        self.assertNotIn("reasoning", self.payloads[1])   # reintenta sin el campo
        self.assertEqual(client.index, 0)                 # y sin quemar el modelo

    def test_una_respuesta_cortada_pide_escribir_menos(self):
        """Repreguntar "respondé solo JSON" a algo que se cortó por tope lo
        vuelve a cortar en el mismo lugar."""
        self.fake([truncado('{"action": "write_spec_file", "args": {"cont'),
                   reply(ACTION)])
        models.ChainClient(chain=["m"]).ask([{"role": "user", "content": "x"}])
        reclamo = self.payloads[1]["messages"][-1]["content"]
        self.assertIn("CORTÓ por largo", reclamo)
        self.assertIn("menos", reclamo)

    def test_json_roto_sin_truncar_mantiene_el_reclamo_de_siempre(self):
        self.fake([reply("no soy json"), reply(ACTION)])
        models.ChainClient(chain=["m"]).ask([{"role": "user", "content": "x"}])
        reclamo = self.payloads[1]["messages"][-1]["content"]
        self.assertIn("ÚNICAMENTE el objeto JSON", reclamo)
        self.assertNotIn("CORTÓ", reclamo)
