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
