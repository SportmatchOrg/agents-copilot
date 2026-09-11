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
  cadena agotada por cuota → siguiente API key, y la cadena vuelve a empezar
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

# Default del 2026-09-11, verificado contra openrouter.ai/api/v1/models.
# Los modelos free aparecen y desaparecen: esto es un default, no una constante.
# Se pisa con LLM_MODEL_CHAIN (coma-separada).
#
# Una entrada muerta no es gratis: en SPO-197 glm-5.2:free y minimax-m3:free ya
# no existían, así que el 404 del primero encadenó los dos y cayó al router en
# una sola iteración. Un fallback que no existe convierte un mal turno del
# primario en fin de corrida.
#
# Reordenada con datos de TRES corridas (§11), no con el papel. nex-n2.5-pro y
# dots-3-note-preview entraron por declarar `structured_outputs`, y eso resultó
# ser el criterio equivocado: son patológicamente razonadores. Miden bien y
# producen nada — 62093 y 59274 caracteres de `reasoning` para devolver
# `content` vacío, quemando los 16000 tokens enteros y 600s de reloj por turno.
# Entre las dos se comieron la mayor parte de los 1896s de la corrida 6 y son
# la razón de que las tres últimas terminaran en timeout. `effort: low` no las
# frena: dots-3 no declara `reasoning_effort` y nex la ignora.
#
# Los dos nemotron son los únicos que produjeron trabajo útil: el super escribió
# los specs (68s las dos primeras iteraciones) y el lightning contestó rápido
# cuando el router cayó en él. El lightning no declara `response_format`, pero
# el 400 ya está manejado: se reintenta sin JSON mode sobre el mismo modelo.
DEFAULT_CHAIN = [
    "nvidia/nemotron-3-super-120b-a12b:free",   # el único que produjo specs válidos
    "nvidia/nemotron-3.5-lightning:free",       # rápido; sin JSON mode, se degrada solo
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
                 max_tokens: int = 16000, timeout: int = 300) -> None:
        self.chain = chain or self._chain_from_env()
        self.index = 0
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.base_url = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
        self.keys = self._keys_from_env()
        if not self.keys:
            raise LLMError("Falta LLM_API_KEY. Sin runtime no hay agente.")
        self.key_index = 0
        # `free-models-per-day` de OpenRouter se cobra por CUENTA, no por modelo:
        # cuando pega, los cuatro modelos de la cadena devuelven 429 en ~300ms y
        # el fallback de modelos no sirve para nada. Pasó en SPO-197, iteración 5
        # de 15. Lo único que salva esa corrida es otra cuenta.
        self.quota_hit = False
        self.json_mode = True
        # Los modelos de la cadena razonan, y el razonamiento se cobra contra
        # `max_tokens`. En SPO-197 nemotron gastó los 8000 tokens pensando
        # (19428 chars de `reasoning`) y lo cortaron a mitad del JSON:
        # `finish_reason='length'` cuatro veces seguidas, con las dos keys, sin
        # producir una sola acción. Se ataca por los dos lados —menos
        # razonamiento y más techo— porque bajar el esfuerzo solo no alcanza:
        # un spec de 300 líneas escapado dentro de un string JSON son varios
        # miles de tokens por sí solo.
        #
        # `reasoning` es la forma portable: los cuatro modelos de la cadena la
        # declaran, `reasoning_effort` no.
        self.reasoning = True
        print(f"[models] cadena: {' → '.join(self.chain)}", flush=True)
        if len(self.keys) > 1:
            print(f"[models] {len(self.keys)} API keys disponibles", flush=True)

    @staticmethod
    def _chain_from_env() -> list[str]:
        raw = os.environ.get("LLM_MODEL_CHAIN", "").strip()
        if raw:
            models = [m.strip() for m in raw.split(",") if m.strip()]
            if models:
                return models
        return list(DEFAULT_CHAIN)

    @staticmethod
    def _keys_from_env() -> list[str]:
        """Las keys en orden de uso. La segunda es opcional y suele ser otra
        cuenta de OpenRouter: el tope free es por cuenta, así que una key de
        respaldo del MISMO dueño no compra nada."""
        keys = [os.environ.get(name, "").strip()
                for name in ("LLM_API_KEY", "LLM_API_KEY_FALLBACK")]
        return [k for k in keys if k]

    @property
    def key(self) -> str:
        return self.keys[self.key_index]

    @property
    def model(self) -> str:
        return self.chain[self.index]

    def _advance(self, reason: str) -> None:
        previous = self.model
        self.index += 1
        if self.index >= len(self.chain):
            if not self._rotate_key(reason):
                raise ChainExhausted(
                    f"Cadena agotada tras {previous} ({reason}). "
                    f"Modelos probados: {', '.join(self.chain)}."
                )
        # Se re-habilitan: que un modelo no los soporte no dice nada del
        # siguiente.
        self.json_mode = True
        self.reasoning = True
        print(f"[models] {previous} → {self.model}  (motivo: {reason})",
              file=sys.stderr, flush=True)

    def _rotate_key(self, reason: str) -> bool:
        """Pasa a la key siguiente y reinicia la cadena. Devuelve False si no
        hay a dónde ir.

        Solo si en el camino hubo un 402/429: si la cadena murió porque los
        modelos devuelven JSON roto, otra key produce el mismo JSON roto y se
        pagan cuatro modelos más de latencia para llegar al mismo lugar.
        """
        if not self.quota_hit or self.key_index + 1 >= len(self.keys):
            return False
        self.key_index += 1
        self.index = 0
        self.quota_hit = False
        self.json_mode = True
        # Nunca la key: esto va a un log público de Actions.
        print(f"[models] cuota agotada ({reason}); paso a la API key "
              f"#{self.key_index + 1} y reinicio la cadena en {self.model}",
              file=sys.stderr, flush=True)
        return True

    @staticmethod
    def _porque(parsed_body: dict, content: str = "") -> str:
        """Por qué la respuesta no sirvió, con lo que mandó el proveedor.

        Antes se logueaba solo el motivo ("JSON inválido", "respuesta vacía") y
        eso no alcanza para decidir nada: JSON cortado por `max_tokens`, texto
        de razonamiento suelto y basura del proveedor se ven idénticos desde
        afuera, y cada uno se arregla distinto. En SPO-197 nemotron falló así
        cuatro veces seguidas con las dos keys y no hubo con qué diagnosticarlo.

        `finish_reason=length` es truncado; `reasoning` con `content` vacío es
        un modelo que se gastó el presupuesto pensando.
        """
        try:
            choice = (parsed_body.get("choices") or [{}])[0]
            message = choice.get("message") or {}
        except (AttributeError, IndexError, TypeError):
            choice, message = {}, {}
        usage = parsed_body.get("usage") or {}
        partes = [f"finish_reason={choice.get('finish_reason')!r}"]
        if usage:
            partes.append(f"tokens={usage.get('completion_tokens')}"
                          f"/{usage.get('total_tokens')}")
        razonamiento = message.get("reasoning") or ""
        if razonamiento:
            partes.append(f"reasoning={len(razonamiento)} chars")
        # Acotado: el log de Actions es público y esto es salida del modelo.
        partes.append(f"content={content[:300]!r}" if content else "content vacío")
        return " · ".join(partes)

    @staticmethod
    def _truncada(parsed_body: dict) -> bool:
        """`finish_reason='length'`: la respuesta llegó al tope de tokens."""
        try:
            return (parsed_body.get("choices") or [{}])[0].get(
                "finish_reason") == "length"
        except (AttributeError, IndexError, TypeError):
            return False

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
                if self.reasoning:
                    payload["reasoning"] = {"effort": "low"}

                status, body = llm_client._post(
                    self.base_url, self.key, payload, self.timeout)

                if status == 200:
                    break

                msg = llm_client._error_message(body)
                if status == 400 and "reasoning" in (body or "") and self.reasoning:
                    print(f"[{label}] {self.model} no acepta `reasoning`; sin él",
                          file=sys.stderr)
                    self.reasoning = False
                    continue
                if status == 400 and "response_format" in (body or "") and self.json_mode:
                    print(f"[{label}] {self.model} no soporta JSON mode; sin él",
                          file=sys.stderr)
                    self.json_mode = False
                    continue
                if status in ADVANCE_NOW:
                    self.quota_hit = True
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
                self._advance(f"respuesta vacía — {self._porque(parsed_body)}")
                continue

            try:
                # El modelo REAL, no la entrada de la cadena: con `openrouter/free`
                # el router elige por nosotros y `self.model` sería la string literal.
                # Justo la corrida donde más importa saber quién contestó es la única
                # que no lo diría, y `modelsUsed` alimenta las métricas de §11.
                reply = llm_client.extract_json(content)
                # Que sea JSON no alcanza: tiene que ser una ACCIÓN. Un `{}` es
                # JSON válido, así que `extract_json` no falla, la cadena nunca
                # avanza y el loop consume turnos con `action: ''` hasta que el
                # detector de bucle lo mata. Pasó en SPO-168: dos turnos
                # quemados con glm-5.2, minimax y el router sin estrenar.
                # Se valida acá para caer en la MISMA rama que un JSON roto:
                # repreguntar una vez, y recién después cambiar de modelo.
                if not isinstance(reply, dict) or not str(
                        reply.get("action") or "").strip():
                    raise ValueError("el JSON no trae `action`")
                return reply, parsed_body.get("model") or self.model
            except ValueError as e:
                attempts_json += 1
                detalle = self._porque(parsed_body, content)
                truncada = self._truncada(parsed_body)
                if attempts_json >= 2:
                    self._advance(f"JSON inválido dos veces ({e}) — {detalle}")
                    attempts_json = 0
                    local_messages = list(messages)
                    continue
                print(f"[{label}] JSON inválido ({e}); repregunto una vez "
                      f"— {detalle}", file=sys.stderr)
                if truncada:
                    # Repreguntar lo mismo la vuelve a cortar en el mismo lugar.
                    reclamo = (
                        "Tu respuesta anterior se CORTÓ por largo: llegaste al "
                        "tope de tokens antes de cerrar el JSON. Pensá menos y "
                        "escribí menos: si estás mandando un spec, mandá menos "
                        "casos en esta escritura y agregá el resto después. "
                        "Respondé ÚNICAMENTE el objeto JSON, completo y cerrado.")
                else:
                    reclamo = (
                        f"Tu respuesta anterior no sirve: {e}. Respondé "
                        f"ÚNICAMENTE el objeto JSON pedido, con `action` en "
                        f"read_file, list_dir, search, write_spec_file, "
                        f"run_tests o finish — sin texto alrededor, sin "
                        f"markdown y sin backticks.")
                local_messages = local_messages + [
                    {"role": "assistant", "content": content[:2000]},
                    {"role": "user", "content": reclamo},
                ]
