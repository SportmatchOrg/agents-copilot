#!/usr/bin/env bash
# Apaga el back y borra el Postgres descartable. Idempotente: se puede correr
# aunque el setup haya fallado a la mitad.
set -uo pipefail

SEC_DB_CONTAINER="${SEC_DB_CONTAINER:-sportmatch-security-db}"

# Sin CTX no se sabe el pid: se cae al patrón. Un teardown que aborta por una
# variable faltante deja el server vivo, que es justo lo que tiene que evitar.
if [ -n "${CTX:-}" ] && [ -f "$CTX/server.pid" ]; then
  kill "$(cat "$CTX/server.pid")" 2>/dev/null || true
  rm -f "$CTX/server.pid"
fi
# Red de contención: el pid puede no ser el de node (ya pasó una vez).
pkill -f "security-agent/boot-server.js" 2>/dev/null || true
docker rm -f "$SEC_DB_CONTAINER" >/dev/null 2>&1 || true
