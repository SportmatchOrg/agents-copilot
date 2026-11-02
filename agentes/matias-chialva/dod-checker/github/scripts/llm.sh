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
#   LLM_FALLBACK_MODELS (variable, opcional) -> modelos alternativos, separados por coma
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
#     LLM_MODEL=openrouter/free
#     LLM_FALLBACK_MODELS=openrouter/free
#   OpenAI:
#     LLM_BASE_URL=https://api.openai.com/v1/chat/completions
#     LLM_MODEL=gpt-4o-mini
#
# Fallbacks: prueba LLM_MODEL y luego LLM_FALLBACK_MODELS en orden. Cuando el
# endpoint es OpenRouter (o LLM_MODEL termina en :free), agrega openrouter/free
# automáticamente: así un modelo gratuito retirado no corta el agente. El
# router elige entre los modelos gratuitos disponibles sin usar créditos.
# En 429/503 hace un reintento por modelo antes de pasar al siguiente.
#
# Uso:  bash llm.sh <archivo_con_el_prompt>
# Imprime por stdout el texto de la respuesta, o el sentinel LLM_UNAVAILABLE.
# ---------------------------------------------------------------------------
set -uo pipefail

PROMPT_FILE="${1:?uso: llm.sh <archivo_prompt>}"
BASE_URL="${LLM_BASE_URL:-https://generativelanguage.googleapis.com/v1beta/openai/chat/completions}"
MODEL="${LLM_MODEL:-gemini-2.5-flash}"
: "${LLM_API_KEY:?falta el secret LLM_API_KEY}"

# Construir la cadena sin repetir modelos. Para OpenRouter el fallback seguro
# por defecto es su router gratuito estable, no otro slug :free efímero.
MODELS=("$MODEL")
fallbacks="${LLM_FALLBACK_MODELS:-}"
if [[ "$BASE_URL" == *openrouter.ai* || "$MODEL" == *:free ]]; then
  fallbacks="${fallbacks:+$fallbacks,}openrouter/free"
fi

IFS=',' read -r -a fallback_candidates <<< "$fallbacks"
for candidate in "${fallback_candidates[@]}"; do
  candidate="$(printf '%s' "$candidate" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$candidate" ] && continue
  duplicate=false
  for configured in "${MODELS[@]}"; do
    [ "$candidate" = "$configured" ] && duplicate=true && break
  done
  [ "$duplicate" = false ] && MODELS+=("$candidate")
done

# Algunos proveedores (Gemini incluido) devuelven el error envuelto en un
# array (`[{"error": {...}}]`) en vez de un objeto plano. Este filtro
# soporta ambas formas.
extract_error() {
  jq -r 'if type=="array" then (.[0].error.message // "error desconocido")
         elif has("error") then (.error.message // "error desconocido")
         else "error desconocido" end' 2>/dev/null
}

max_attempts=2   # 1 intento inicial + 1 reintento
http_code=""
body=""
last_model="$MODEL"

for current_model in "${MODELS[@]}"; do
  last_model="$current_model"
  payload="$(jq -n --arg model "$current_model" --rawfile content "$PROMPT_FILE" \
    '{model:$model, messages:[{role:"user", content:$content}], temperature:0.3}')"
  attempt=1

  while [ "$attempt" -le "$max_attempts" ]; do
    raw="$(curl -sS -w '\n%{http_code}' "$BASE_URL" \
      -H "Authorization: Bearer $LLM_API_KEY" \
      -H "Content-Type: application/json" \
      -d "$payload" 2>/dev/null)"
    http_code="$(printf '%s' "$raw" | tail -n1)"
    body="$(printf '%s' "$raw" | sed '$d')"

    if [ "$http_code" = "200" ]; then
      content="$(printf '%s' "$body" | jq -r '.choices[0].message.content // empty' 2>/dev/null)"
      if [ -n "$content" ]; then
        echo "$content"
        exit 0
      fi
      # Una respuesta vacía no mejora reintentando el mismo modelo.
      break
    fi

    if { [ "$http_code" = "429" ] || [ "$http_code" = "503" ]; } && [ "$attempt" -lt "$max_attempts" ]; then
      sleep 5
      attempt=$((attempt + 1))
      continue
    fi
    break
  done

  if [ "$current_model" != "${MODELS[${#MODELS[@]}-1]}" ]; then
    echo "LLM: $current_model no disponible (HTTP ${http_code:-desconocido}); probando fallback." >&2
  fi
done

err_msg="$(printf '%s' "$body" | extract_error)"
echo "LLM_UNAVAILABLE: todos los modelos fallaron; último=$last_model HTTP ${http_code:-desconocido} - $err_msg"
exit 0
