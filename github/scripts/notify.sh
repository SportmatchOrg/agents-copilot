#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# notify.sh — Postea un mensaje en Discord vía webhook.
#
# Antes este bloque estaba copiado como un heredoc de Python en cada workflow
# (10 copias, con variantes). Al centralizarlo acá:
#   - el mensaje NUNCA se interpola dentro de código (se lee de un archivo),
#     así que la salida del LLM no puede romper ni inyectar nada;
#   - un webhook sin configurar deja un aviso en el log en vez de tirar el job;
#   - el truncado a 2000 chars (límite de Discord) se hace en un solo lugar.
#
# Uso:  DISCORD_WEBHOOK_URL=... bash notify.sh <archivo_con_el_mensaje>
#       ... | bash notify.sh -          (lee de stdin)
#
# Nunca falla el job: ante error de red devuelve exit 0 y loguea el motivo.
# ---------------------------------------------------------------------------
set -uo pipefail

SRC="${1:?uso: notify.sh <archivo|->}"

if [ -z "${DISCORD_WEBHOOK_URL:-}" ]; then
  echo "notify: DISCORD_WEBHOOK_URL vacío (¿falta el secret?), no se postea nada." >&2
  exit 0
fi

CONTENT="$(cat -- "$SRC")"
if [ -z "$CONTENT" ]; then
  echo "notify: mensaje vacío, no se postea nada." >&2
  exit 0
fi

# Discord corta en 2000 caracteres; dejamos margen y marcamos el truncado.
PAYLOAD="$(jq -n --arg c "$CONTENT" \
  '{content: (if ($c|length) > 1900 then ($c[0:1897] + "…") else $c end)}')"

attempt=1
while [ "$attempt" -le 2 ]; do
  code="$(curl -sS -o /tmp/notify_resp.txt -w '%{http_code}' --max-time 30 \
    "$DISCORD_WEBHOOK_URL" \
    -H 'Content-Type: application/json' \
    -H 'User-Agent: Mozilla/5.0 (compatible; SportMatchBot/1.0)' \
    -d "$PAYLOAD" 2>/dev/null)"

  case "$code" in
    2*) echo "notify: mensaje posteado (HTTP $code)."; exit 0 ;;
    429|5*)
      # Rate limit del webhook u error transitorio: un reintento y listo.
      if [ "$attempt" -eq 1 ]; then sleep 5; attempt=2; continue; fi
      ;;
  esac
  break
done

echo "notify: no se pudo postear en Discord (HTTP ${code:-sin-respuesta}): $(head -c 300 /tmp/notify_resp.txt 2>/dev/null)" >&2
exit 0
