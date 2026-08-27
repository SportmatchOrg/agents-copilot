#!/usr/bin/env bash
# Corre el agente entero en local, sin GitHub Actions.
#
# No es opcional: depurar un loop agéntico a través de la UI de Actions es
# insoportable, y con cuota diaria de modelos free cada corrida desperdiciada
# cuesta un día.
#
# Uso:  LLM_API_KEY=... run-local.sh <ruta-al-sandbox> <TICKET> [RF-03]
set -euo pipefail

REPO="${1:?uso: run-local.sh <ruta-al-sandbox> <TICKET> [RF]}"
TICKET="${2:?falta el identifier del ticket, ej. SPM-42}"
RF="${3:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CTX="${CTX:-/tmp/test-agent-ctx}"

export SERVICE_ROOT="${SERVICE_ROOT:-back}"
export DATABASE_URL="${DATABASE_URL:-postgresql://root:root@localhost:5432/sportmatch?schema=public}"
mkdir -p "$CTX"

# Sin LINEAR_API_KEY se puede correr igual dejando un linear.json a mano en $CTX.
if [ -n "${LINEAR_API_KEY:-}" ] && [ ! -f "$CTX/linear.json" ]; then
  curl -s https://api.linear.app/graphql \
    -H "Authorization: ${LINEAR_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"query\":\"{ issue(id: \\\"$TICKET\\\") { identifier title description } }\"}" \
    | python3 -c 'import json,sys; print(json.dumps((json.load(sys.stdin).get("data") or {}).get("issue") or {}))' \
    > "$CTX/linear.json"
fi
[ -f "$CTX/linear.json" ] || echo '{}' > "$CTX/linear.json"

bash "$HERE/setup-stack.sh" "$REPO"
python3 "$HERE/prefetch-context.py" --ctx "$CTX" --repo "$REPO" --ticket "$TICKET" --rf "$RF"
python3 "$HERE/run-agent.py"        --ctx "$CTX" --repo "$REPO" --ticket "$TICKET"
python3 "$HERE/validate-output.py"  --ctx "$CTX" --repo "$REPO"

echo
echo "── contexto en $CTX ──"
ls -1 "$CTX"
echo
echo "No se abre PR en modo local. Para publicarla:"
echo "  python3 $HERE/open-test-pr.py --ctx $CTX --repo $REPO --ticket $TICKET"
