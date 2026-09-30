#!/usr/bin/env bash
# Levanta el blanco del Security Agent: Postgres descartable + back compilado
# con autenticación simulada, escuchando en 127.0.0.1:$SEC_PORT.
#
# No reusa el `setup-stack.sh` del test agent a propósito. Ese hace
# `docker compose up -d db` con el compose del repo, y el compose fija
# `name: sportmatch`: en la máquina de un dev que ya tiene el stack levantado,
# eso ENGANCHA SU contenedor y SU volumen, y el reset de este agente le trunca
# la base local. Acá el Postgres es un `docker run` con nombre y puerto propios,
# que se borra al terminar (`teardown.sh`).
#
# Uso:  setup-stack.sh <ruta-al-repo>
# Deja en $CTX: server.pid, server.log
set -euo pipefail

REPO="${1:?uso: setup-stack.sh <ruta-al-repo>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_ROOT="${SERVICE_ROOT:-back}"
SERVICE="$REPO/$SERVICE_ROOT"
CTX="${CTX:?falta CTX}"
SEC_PORT="${SEC_PORT:-3900}"
SEC_DB_PORT="${SEC_DB_PORT:-55432}"
SEC_DB_CONTAINER="${SEC_DB_CONTAINER:-sportmatch-security-db}"
export DATABASE_URL="postgresql://root:root@localhost:${SEC_DB_PORT}/sportmatch?schema=public"

mkdir -p "$CTX"

# Si algo ya escucha en el puerto, el health check de abajo le contestaría OK a
# ESE proceso y no al nuestro. Pasó: un boot-server de una corrida anterior
# quedó vivo, y la corrida nueva le habría pegado a un back con la base borrada.
if curl -s -o /dev/null "http://127.0.0.1:$SEC_PORT/" 2>/dev/null; then
  echo "❌ el puerto $SEC_PORT ya está ocupado. Si es una corrida anterior:"
  echo "   pkill -f security-agent/boot-server.js"
  exit 1
fi

echo "→ Postgres descartable ($SEC_DB_CONTAINER, puerto $SEC_DB_PORT)"
docker rm -f "$SEC_DB_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$SEC_DB_CONTAINER" \
  -e POSTGRES_USER=root -e POSTGRES_PASSWORD=root -e POSTGRES_DB=sportmatch \
  -p "127.0.0.1:${SEC_DB_PORT}:5432" postgres:18-alpine >/dev/null

for i in $(seq 1 60); do
  if docker exec "$SEC_DB_CONTAINER" pg_isready -U root -d sportmatch >/dev/null 2>&1; then
    echo "  db lista (${i}s)"
    break
  fi
  if [ "$i" = "60" ]; then
    echo "❌ Postgres no respondió en 60s."
    docker logs "$SEC_DB_CONTAINER" | tail -20
    exit 1
  fi
  sleep 1
done

echo "→ dependencias"
( cd "$SERVICE" && npm ci --no-audit --no-fund >/dev/null )

echo "→ cliente Prisma + migraciones"
( cd "$SERVICE" && npx prisma generate >/dev/null && npx prisma migrate deploy >/dev/null )

echo "→ build"
( cd "$SERVICE" && npm run build >/dev/null )

echo "→ arrancando el back en 127.0.0.1:$SEC_PORT"
# `;` y no `&&` después del cd: con `cd && node &`, el `&` manda al fondo la
# cadena entera y `$!` es el pid de una subshell, no el de node. Matar ese pid
# dejaba el back vivo, y la corrida siguiente chocaba con el puerto ocupado.
( cd "$SERVICE"; SEC_PORT="$SEC_PORT" nohup node "$HERE/boot-server.js" \
    > "$CTX/server.log" 2>&1 & echo $! > "$CTX/server.pid" )

for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$SEC_PORT/health" >/dev/null 2>&1; then
    echo "  back arriba (${i}s)"
    break
  fi
  if ! kill -0 "$(cat "$CTX/server.pid")" 2>/dev/null || [ "$i" = "60" ]; then
    echo "❌ el back no levantó:"
    tail -30 "$CTX/server.log"
    exit 1
  fi
  sleep 1
done

# Gate: el reset (truncate + seed) tiene que andar. Sin él no hay replay, y un
# hallazgo que no se reproduce desde cero no se publica.
echo "→ verificando el reset"
if ! curl -sf -X POST "http://127.0.0.1:$SEC_PORT/__sec/reset" >/dev/null; then
  echo "❌ el reset falló:"
  curl -s -X POST "http://127.0.0.1:$SEC_PORT/__sec/reset" || true
  exit 1
fi

# Gate: la autenticación simulada tiene que comportarse como la real.
anon=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$SEC_PORT/users/me")
auth=$(curl -s -o /dev/null -w '%{http_code}' -H 'x-sec-user: A' "http://127.0.0.1:$SEC_PORT/users/me")
if [ "$anon" != "401" ] || [ "$auth" != "200" ]; then
  echo "❌ la auth simulada no se comporta como la real: anónimo=$anon (esperado 401), A=$auth (esperado 200)"
  exit 1
fi

echo "✅ blanco listo"
