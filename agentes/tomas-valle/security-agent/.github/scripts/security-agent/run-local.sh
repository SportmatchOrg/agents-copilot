#!/usr/bin/env bash
# Corre el Security Agent entero en local, sin GitHub Actions.
#
# Uso:  run-local.sh <ruta-a-un-clon-de-sportmatch> [archivos,cambiados]
#       SEC_SKIP_AGENT=1 run-local.sh ...   solo la parte determinística
#
# La key se lee de `agents-copilot/.env` (SECURITY_LLM_API_KEY=... o
# LLM_API_KEY=...), que está en el .gitignore. Apuntalo a un CLON, no a tu carpeta de trabajo: el setup corre
# `npm ci` y `npm run build` adentro.
set -euo pipefail

REPO="$(cd "${1:?uso: run-local.sh <ruta-al-clon> [archivos,cambiados]}" && pwd)"
CHANGED="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/../../../.env"
export CTX="${CTX:-/tmp/security-agent-ctx}"
export SERVICE_ROOT="${SERVICE_ROOT:-back}"
# Sin esto, redirigido a un archivo, el log del loop sale todo junto al final.
export PYTHONUNBUFFERED=1

if [ -f "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; fi
# Misma prioridad que el workflow: la key propia del agente primero.
if [ -n "${SECURITY_LLM_API_KEY:-}" ]; then export LLM_API_KEY="$SECURITY_LLM_API_KEY"; fi
rm -rf "$CTX"; mkdir -p "$CTX"
trap 'bash "$HERE/teardown.sh"' EXIT

bash "$HERE/setup-stack.sh" "$REPO"
python3 "$HERE/endpoints.py" --repo "$REPO" --out "$CTX/endpoints.json"
python3 "$HERE/baseline.py"  --repo "$REPO" --ctx "$CTX"
if [ -z "${SEC_SKIP_AGENT:-}" ]; then
  python3 "$HERE/run-agent.py" --ctx "$CTX" --repo "$REPO" --changed "$CHANGED"
  python3 "$HERE/replay.py"    --ctx "$CTX"
fi
python3 "$HERE/report.py"    --ctx "$CTX"

echo
echo "── contexto en $CTX ──"
ls -1 "$CTX"
