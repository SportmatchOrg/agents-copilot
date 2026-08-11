#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# llm.sh — Llamada a un LLM vía endpoint compatible con OpenAI (chat completions)
#
# Provider-agnostic: se configura con variables de entorno. Por defecto usa
# el free tier de Google Gemini (AI Studio), que expone un endpoint
# compatible con OpenAI. Para cambiar de proveedor NO hace falta tocar los
# workflows: basta con setear estas variables/secret en el repo.
#
#   LLM_API_KEY   (secret, obligatorio)  -> tu API key del proveedor
#   LLM_BASE_URL  (variable, opcional)   -> URL del endpoint chat/completions
#   LLM_MODEL     (variable, opcional)   -> nombre del modelo
#
# Ejemplos de configuración por proveedor:
#   Gemini (default):
#     LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
#     LLM_MODEL=gemini-2.5-flash
#   Groq:
#     LLM_BASE_URL=https://api.groq.com/openai/v1/chat/completions
#     LLM_MODEL=llama-3.3-70b-versatile
#   OpenRouter:
#     LLM_BASE_URL=https://openrouter.ai/api/v1/chat/completions
#     LLM_MODEL=qwen/qwen3-coder:free
#   OpenAI:
#     LLM_BASE_URL=https://api.openai.com/v1/chat/completions
#     LLM_MODEL=gpt-4o-mini
#
# Reintentos: en 429 (rate limit) o 503 (overload, común en free tier) hace
# UN reintento tras una pausa corta. Si vuelve a fallar, en vez de romper el
# script imprime un sentinel "LLM_UNAVAILABLE: <motivo>" y sale con éxito
# (exit 0) para que el workflow que lo llama decida cómo degradar (avisar por
# Discord/PR sin action normal, en vez de fallar el job entero).
#
# Uso:  bash llm.sh <archivo_con_el_prompt>
# Imprime por stdout el texto de la respuesta, o el sentinel LLM_UNAVAILABLE.
# ---------------------------------------------------------------------------
set -uo pipefail

PROMPT_FILE="${1:?uso: llm.sh <archivo_prompt>}"
BASE_URL="${LLM_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai/chat/completions}"
MODEL="${LLM_MODEL:-gemini-2.5-flash}"
: "${LLM_API_KEY:?falta el secret LLM_API_KEY}"

# Armar el payload de forma segura (el prompt puede tener comillas y saltos).
PAYLOAD="$(jq -n --arg model "$MODEL" --rawfile content "$PROMPT_FILE" \
  '{model:$model, messages:[{role:"user", content:$content}], temperature:0.3}')"

# Algunos proveedores (Gemini incluido) devuelven el error envuelto en un
# array (`[{"error": {...}}]`) en vez de un objeto plano. Este filtro
# soporta ambas formas.
extract_error() {
  jq -r 'if type=="array" then (.[0].error.message // "error desconocido")
         elif has("error") then (.error.message // "error desconocido")
         else "error desconocido" end' 2>/dev/null
}

attempt=1
max_attempts=2   # 1 intento inicial + 1 reintento
http_code=""
body=""

while [ "$attempt" -le "$max_attempts" ]; do
  raw="$(curl -sS -w '\n%{http_code}' "$BASE_URL" \
    -H "Authorization: Bearer $LLM_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>/dev/null)"
  http_code="$(printf '%s' "$raw" | tail -n1)"
  body="$(printf '%s' "$raw" | sed '$d')"

  if [ "$http_code" = "200" ]; then
    content="$(printf '%s' "$body" | jq -r '.choices[0].message.content // empty' 2>/dev/null)"
    if [ -n "$content" ]; then
      echo "$content"
      exit 0
    fi
    # 200 pero sin el campo esperado: tratar como error, sin reintento (no es transitorio).
    break
  fi

  # Solo 429 (rate limit) y 503 (overload/free-tier) ameritan reintento.
  if { [ "$http_code" = "429" ] || [ "$http_code" = "503" ]; } && [ "$attempt" -lt "$max_attempts" ]; then
    sleep 5
    attempt=$((attempt + 1))
    continue
  fi
  break
done

err_msg="$(printf '%s' "$body" | extract_error)"
echo "LLM_UNAVAILABLE: HTTP ${http_code:-desconocido} - $err_msg"
exit 0
