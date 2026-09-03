#!/usr/bin/env bash
# Instala el harness de tests e2e en un repo, y lo verifica.
#
# El repo destino queda con `back/test/` LIMPIO: solo configuración, ningún
# test. La verificación usa un spec de humo que se escribe, corre y se borra —
# así no dejamos un test de ejemplo viviendo para siempre en el repo, pero
# tampoco instalamos a ciegas.
#
# Un `back/test/` vacío con `--passWithNoTests` daría verde sin probar nada, y
# ese es justo el falso verde que este proyecto viene evitando.
#
# Uso:  bash install-harness.sh <ruta-al-repo>
set -euo pipefail

REPO="${1:?uso: install-harness.sh <ruta-al-repo>}"
SERVICE_ROOT="${SERVICE_ROOT:-back}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SRC="$HERE/test-harness"
SERVICE="$REPO/$SERVICE_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://root:root@localhost:5432/sportmatch?schema=public}"

[ -d "$SERVICE" ] || { echo "❌ no existe $SERVICE — ¿es la ruta correcta?"; exit 1; }
[ -f "$SERVICE/package.json" ] || { echo "❌ falta $SERVICE_ROOT/package.json"; exit 1; }

echo "→ copiando el harness a $SERVICE_ROOT/test/"
mkdir -p "$SERVICE/test/stubs"
cp "$SRC/back/test/"*.ts "$SRC/back/test/"*.json "$SERVICE/test/"
cp "$SRC/back/test/stubs/"*.ts "$SERVICE/test/stubs/"

echo "→ ajustando el script test:e2e"
python3 - "$SERVICE/package.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
# Prisma 7 carga su query compiler WASM con un import() dinámico: sin esto,
# Jest lo rechaza en runtime CJS.
d.setdefault("scripts", {})["test:e2e"] = (
    "NODE_OPTIONS=--experimental-vm-modules jest --config ./test/jest-e2e.json")
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
open(p, "a").write("\n")
print("   test:e2e = NODE_OPTIONS=--experimental-vm-modules jest --config ./test/jest-e2e.json")
PY

echo "→ levantando Postgres"
docker compose -f "$REPO/docker-compose.yml" up -d db >/dev/null
for i in $(seq 1 60); do
  cid=$(docker compose -f "$REPO/docker-compose.yml" ps -q db 2>/dev/null || true)
  [ -n "$cid" ] || { echo "❌ no se pudo identificar el contenedor de Postgres"; exit 1; }
  [ "$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)" = healthy ] && break
  [ "$i" = 60 ] && { echo "❌ Postgres no llegó a healthy en 60s"; exit 1; }
  sleep 1
done

echo "→ dependencias y migraciones"
( cd "$SERVICE" && npm ci --no-audit --no-fund >/dev/null && npx prisma generate >/dev/null && npx prisma migrate deploy >/dev/null )

echo "→ verificando con un spec de humo (temporal)"
SMOKE="$SERVICE/test/__smoke__.e2e-spec.ts"
cp "$SRC/smoke.e2e-spec.ts" "$SMOKE"
trap 'rm -f "$SMOKE"' EXIT
if ! ( cd "$SERVICE" && npm run test:e2e -- --testPathPatterns '__smoke__' 2>&1 | tail -25 ); then
  echo
  echo "❌ el harness NO funciona en este repo. No se borra nada: revisá la salida de arriba."
  exit 1
fi
rm -f "$SMOKE"; trap - EXIT

echo
echo "✅ harness instalado y verificado. Contenido de $SERVICE_ROOT/test/:"
( cd "$SERVICE" && find test -type f | sort | sed 's/^/   /' )
echo
echo "   Sin tests: el agente los escribe. Commiteá esto y listo."
