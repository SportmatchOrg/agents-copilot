"""Cadena de modelos con fallback (plan §5.5).

Por qué no alcanza `llm_client.call_json`: ese cliente habla con UN modelo y
lanza `LLMError` cuando se agota. Este agente corre contra el tier gratis de
OpenRouter, donde la cuota diaria se termina, así que la elección no es un
modelo sino una cadena. Además el loop necesita conversación multi-turno, no un
prompt suelto.

Se reusa el transporte de `llm_client` (POST, backoff, extracción de JSON) y se
agrega encima: historial, avance de cadena, y registro de qué modelo produjo
cada iteración.

Reglas de avance:
  429 / 402  → siguiente modelo (cuota agotada: reintentar no ayuda)
  503 / 5xx  → backoff exponencial sobre el MISMO modelo y recién después avanzar
  JSON malo  → una repregunta; si vuelve a fallar, siguiente modelo
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qa-review"))
import llm_client  # noqa: E402
from llm_client import LLMError  # noqa: E402

# Default del 2026-08-27, verificado contra openrouter.ai/api/v1/models.
# Los modelos free aparecen y desaparecen: esto es un default, no una constante.
# Se pisa con LLM_MODEL_CHAIN (coma-separada).
DEFAULT_CHAIN = [
    "z-ai/glm-5.2:free",                        # structured_outputs + seed + reasoning_effort
    "minimax/minimax-m3:free",                  # ya probado en qa-review
    "nvidia/nemotron-3-super-120b-a12b:free",   # otro proveedor: cuotas independientes
    "openrouter/free",                          # router: último recurso, no determinístico
]

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

ADVANCE_NOW = {402, 429}          # cuota o crédito: cambiar de modelo ya
BACKOFF_FIRST = {500, 502, 503, 504, 408, 409}
MAX_BACKOFF_ATTEMPTS = 3


class ChainExhausted(LLMError):
    """Se acabaron los modelos de la cadena. No hay con qué seguir."""


class ChainClient:
    """Cliente multi-turno con cadena de fallback.

    Política sticky (plan §5.5): al cambiar de modelo se CONSERVA el historial y
    se sigue en la iteración donde estaba. Con 5 turnos no hay presupuesto para
    reiniciar el loop.
    """

    def __init__(self, *, chain: list[str] | None = None, temperature: float = 0.1,
                 max_tokens: int = 8000, timeout: int = 300) -> None:
        self.chain = chain or self._chain_from_env()
        self.index = 0
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.base_url = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
        self.key = os.environ.get("LLM_API_KEY", "").strip()
        if not self.key:
            raise LLMError("Falta LLM_API_KEY. Sin runtime no hay agente.")
        self.json_mode = True
        print(f"[models] cadena: {' → '.join(self.chain)}", flush=True)

    @staticmethod
    def _chain_from_env() -> list[str]:
        raw = os.environ.get("LLM_MODEL_CHAIN", "").strip()
        if raw:
            models = [m.strip() for m in raw.split(",") if m.strip()]
            if models:
                return models
        return list(DEFAULT_CHAIN)

    @property
    def model(self) -> str:
        return self.chain[self.index]

    def _advance(self, reason: str) -> None:
        previous = self.model
        self.index += 1
        if self.index >= len(self.chain):
            raise ChainExhausted(
                f"Cadena agotada tras {previous} ({reason}). "
                f"Modelos probados: {', '.join(self.chain)}."
            )
        # El json_mode se re-habilita: que un modelo no lo soporte no dice nada
        # del siguiente.
        self.json_mode = True
        print(f"[models] {previous} → {self.model}  (motivo: {reason})",
              file=sys.stderr, flush=True)

    def ask(self, messages: list[dict], *, label: str = "agent") -> tuple[dict, str]:
        """Devuelve (objeto JSON, modelo que lo produjo).

        Registrar el modelo por turno no es opcional: sin ese dato, un cambio de
        conducta a mitad de corrida es indepurable.
        """
        attempts_json = 0
        local_messages = list(messages)

        while True:
            body = None
            for attempt in range(1, MAX_BACKOFF_ATTEMPTS + 1):
                payload = {
                    "model": self.model,
                    "messages": local_messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                if self.json_mode:
                    payload["response_format"] = {"type": "json_object"}

                status, body = llm_client._post(
                    self.base_url, self.key, payload, self.timeout)

                if status == 200:
                    break

                msg = llm_client._error_message(body)
                if status == 400 and "response_format" in (body or "") and self.json_mode:
                    print(f"[{label}] {self.model} no soporta JSON mode; sin él",
                          file=sys.stderr)
                    self.json_mode = False
                    continue
                if status in ADVANCE_NOW:
                    self._advance(f"HTTP {status} — {msg}")
                    break
                if status in BACKOFF_FIRST and attempt < MAX_BACKOFF_ATTEMPTS:
                    delay = llm_client._backoff(attempt)
                    print(f"[{label}] HTTP {status} en {self.model}; reintento en "
                          f"{delay}s ({attempt}/{MAX_BACKOFF_ATTEMPTS})",
                          file=sys.stderr, flush=True)
                    time.sleep(delay)
                    continue
                self._advance(f"HTTP {status} — {msg}")
                break
            else:
                self._advance("sin respuesta tras los reintentos")
                continue

            if body is None:
                continue
            try:
                parsed_body = json.loads(body)
                content = parsed_body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                # Puede ser el cuerpo de error de un status != 200 que ya avanzó.
                continue
            if not content or not content.strip():
                self._advance("respuesta vacía")
                continue

            try:
                return llm_client.extract_json(content), self.model
            except ValueError as e:
                attempts_json += 1
                if attempts_json >= 2:
                    self._advance(f"JSON inválido dos veces ({e})")
                    attempts_json = 0
                    local_messages = list(messages)
                    continue
                print(f"[{label}] JSON inválido ({e}); repregunto una vez",
                      file=sys.stderr)
                local_messages = local_messages + [
                    {"role": "assistant", "content": content[:2000]},
                    {"role": "user", "content":
                        "Tu respuesta anterior no era JSON válido. Respondé "
                        "ÚNICAMENTE el objeto JSON pedido, sin texto alrededor, "
                        "sin markdown y sin backticks."},
                ]
