#!/usr/bin/env bash
# Levanta el oráculo (plan §3.2): SOLO Postgres, migraciones y cliente Prisma.
#
# No se buildea la imagen de Nest a propósito: los tests son in-process con
# supertest (`Test.createTestingModule`), así que el contenedor `back` no se usa.
# Eso saca el paso más lento del job y elimina la dependencia de `back/.env`.
#
# Uso:  setup-stack.sh <ruta-al-repo>
set -euo pipefail

REPO="${1:?uso: setup-stack.sh <ruta-al-repo>}"
SERVICE_ROOT="${SERVICE_ROOT:-back}"
SERVICE="$REPO/$SERVICE_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://root:root@localhost:5432/sportmatch?schema=public}"

# El compose declara `env_file: ./back/.env` para el servicio `back`. Aunque
# solo levantemos `db`, CUALQUIER comando de compose parsea el archivo entero y
# aborta si ese .env no existe — y está gitignoreado, así que en CI nunca está.
# Se crea desde el ejemplo: el contenedor `back` no se usa, pero compose necesita
# poder leerlo. Al estar en .gitignore, el validador no lo ve como cambio.
if [ ! -f "$SERVICE/.env" ]; then
  echo "→ creando $SERVICE_ROOT/.env (compose lo exige aunque no usemos el servicio back)"
  cp "$SERVICE/.env.example" "$SERVICE/.env" 2>/dev/null || : > "$SERVICE/.env"
fi

echo "→ levantando Postgres"
docker compose -f "$REPO/docker-compose.yml" up -d db

echo "→ esperando el healthcheck"
for i in $(seq 1 60); do
  cid=$(docker compose -f "$REPO/docker-compose.yml" ps -q db 2>/dev/null || true)
  if [ -z "$cid" ]; then
    echo "❌ no se pudo identificar el contenedor de Postgres:"
    docker compose -f "$REPO/docker-compose.yml" ps -q db || true
    exit 1
  fi
  status=$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)
  if [ "$status" = "healthy" ]; then
    echo "  db healthy (${i}s)"
    break
  fi
  if [ "$i" = "60" ]; then
    echo "❌ Postgres no llegó a healthy en 60s. El loop no arranca: gastar cuota"
    echo "   contra un stack que no levantó es tirar el día."
    docker compose -f "$REPO/docker-compose.yml" logs db | tail -30
    exit 1
  fi
  sleep 1
done

echo "→ dependencias"
( cd "$SERVICE" && npm ci --no-audit --no-fund >/dev/null )

echo "→ cliente Prisma"
( cd "$SERVICE" && npx prisma generate >/dev/null )

echo "→ migraciones"
( cd "$SERVICE" && npx prisma migrate deploy )

# Si el spec de verificación no pasa, el problema es el entorno y no el agente.
# Mejor descubrirlo acá que después de gastar iteraciones y cuota.
#
# Un repo puede no tener spec de ejemplo: `install-harness.sh` deja `test/` con
# solo configuración a propósito, para no dejar un test de ejemplo viviendo para
# siempre en el repo. En ese caso el gate usa el mismo spec de humo que el
# instalador — se escribe, corre y se borra.
HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/test-harness"
if ls "$SERVICE"/test/*example*.e2e-spec.ts >/dev/null 2>&1; then
  PATRON='example'; LIMPIAR=""
  echo "→ verificando el oráculo con el spec de ejemplo"
else
  PATRON='__smoke__'; LIMPIAR="$SERVICE/test/__smoke__.e2e-spec.ts"
  echo "→ verificando el oráculo con el spec de humo (temporal)"
  cp "$HARNESS_DIR/smoke.e2e-spec.ts" "$LIMPIAR"
fi

if ! ( cd "$SERVICE" && npm run test:e2e -- --testPathPatterns "$PATRON" >/dev/null 2>&1 ); then
  echo "❌ el spec de verificación no pasa. El oráculo no es confiable; se aborta."
  ( cd "$SERVICE" && npm run test:e2e -- --testPathPatterns "$PATRON" 2>&1 | tail -30 )
  [ -n "$LIMPIAR" ] && rm -f "$LIMPIAR"
  exit 1
fi
[ -n "$LIMPIAR" ] && rm -f "$LIMPIAR"

echo "✅ stack listo"
