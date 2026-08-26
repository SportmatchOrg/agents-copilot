"""Cliente LLM del QA PR Review Agent.

Por qué no reusa `github/scripts/llm.sh`: ese script está pensado para los
agentes que comentan un PR o Discord, y ante un fallo degrada en silencio
(imprime `LLM_UNAVAILABLE` y sale con 0) para no romper el job. El QA reviewer
necesita lo contrario (plan §29): si el runtime no está disponible, **no se
crea la review** y el job falla con un mensaje claro. Además necesita modo JSON
y un reintento con reprompt cuando el modelo devuelve JSON inválido.

Provider-agnostic, igual que llm.sh:
  LLM_API_KEY   (secret, obligatorio)
  LLM_BASE_URL  (default: OpenRouter chat/completions)
  LLM_MODEL     (default: minimax/minimax-m3:free)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "minimax/minimax-m3:free"

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class LLMError(RuntimeError):
    """Fallo definitivo del runtime del agente. El job debe fallar."""


def _config() -> tuple[str, str, str]:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "Falta la API key del modelo. Cargá QA_LLM_API_KEY (o LLM_API_KEY) en "
            "el repo. Sin runtime de agente no se crea la review."
        )
    return (
        key,
        os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL,
        os.environ.get("LLM_MODEL", "").strip() or DEFAULT_MODEL,
    )


def _post(url: str, key: str, payload: dict, timeout: int) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # OpenRouter usa estos headers para atribuir el tráfico; son opcionales.
            "HTTP-Referer": "https://github.com/SportmatchOrg/agents-copilot",
            "X-Title": "SportMatch QA PR Review Agent",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, json.dumps({"error": {"message": f"error de red: {e}"}})


def _error_message(body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body[:300].replace("\n", " ")
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message", err))[:300]
        if err:
            return str(err)[:300]
    return body[:300].replace("\n", " ")


def extract_json(text: str) -> dict:
    """Saca el objeto JSON de la respuesta del modelo.

    Tolera que venga envuelto en ```json ... ``` o con texto alrededor, pero NO
    intenta reparar JSON roto: el plan (§29) pide explícitamente no rescatar
    parcialmente una salida ambigua.
    """
    candidates = [text.strip()]
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])

    for c in candidates:
        try:
            parsed = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("la respuesta no contiene un objeto JSON válido")


def call_json(prompt: str, *, temperature: float = 0.2, timeout: int = 300,
              max_http_attempts: int = 3, label: str = "llm") -> dict:
    """Llama al modelo y devuelve un dict. Lanza LLMError si no se puede."""
    key, base_url, model = _config()
    messages = [{"role": "user", "content": prompt}]
    use_json_mode = True
    last_error = "desconocido"

    # Dos rondas: la segunda solo ocurre si el modelo devolvió JSON inválido y
    # se le repite el pedido señalándole el error.
    for round_no in (1, 2):
        body = None
        for attempt in range(1, max_http_attempts + 1):
            payload = {"model": model, "messages": messages,
                       "temperature": temperature}
            if use_json_mode:
                payload["response_format"] = {"type": "json_object"}

            status, body = _post(base_url, key, payload, timeout)
            if status == 200:
                break

            msg = _error_message(body)
            last_error = f"HTTP {status or 'sin respuesta'} — {msg}"
            # Algunos modelos de OpenRouter no soportan response_format: se reintenta sin él.
            if status == 400 and "response_format" in body and use_json_mode:
                print(f"[{label}] el modelo no soporta JSON mode; reintento sin él",
                      file=sys.stderr)
                use_json_mode = False
                continue
            if status in RETRYABLE_STATUS and attempt < max_http_attempts:
                delay = 5 * attempt
                print(f"[{label}] {last_error}; reintento en {delay}s "
                      f"({attempt}/{max_http_attempts})", file=sys.stderr)
                time.sleep(delay)
                continue
            raise LLMError(f"[{label}] el modelo no respondió: {last_error}")
        else:
            raise LLMError(f"[{label}] el modelo no respondió: {last_error}")

        try:
            content = json.loads(body)["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise LLMError(
                f"[{label}] respuesta 200 sin contenido utilizable: {body[:300]}"
            ) from None
        if not content or not content.strip():
            raise LLMError(f"[{label}] el modelo devolvió una respuesta vacía.")

        try:
            return extract_json(content)
        except ValueError as e:
            if round_no == 2:
                raise LLMError(
                    f"[{label}] el modelo devolvió JSON inválido dos veces ({e}). "
                    "No se crea la review: no se rescatan salidas ambiguas."
                ) from None
            print(f"[{label}] JSON inválido ({e}); repregunto una vez", file=sys.stderr)
            messages = messages + [
                {"role": "assistant", "content": content[:4000]},
                {"role": "user", "content":
                    "Tu respuesta anterior no era JSON válido. Respondé ÚNICAMENTE "
                    "el objeto JSON pedido, sin texto antes ni después, sin markdown "
                    "y sin backticks."},
            ]

    raise LLMError(f"[{label}] no se pudo obtener JSON del modelo.")  # pragma: no cover
