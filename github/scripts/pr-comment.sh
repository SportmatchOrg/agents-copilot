#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# pr-comment.sh — Comentario "sticky" por agente en un PR.
#
# Por qué no `gh pr comment --edit-last`: ese flag edita el último comentario
# del USUARIO ACTUAL, y todos los workflows comentan como el mismo
# `github-actions[bot]`. Con dos agentes comentando el mismo PR (DoD checker y
# traductor a negocio), cada uno terminaba editando el comentario del otro.
#
# Acá cada agente marca su comentario con un HTML comment invisible
# (`<!-- agente:dod-checker -->`) y actualiza SOLO el suyo. Sigue sin spamear
# un comentario nuevo por push, y sin pisar al otro agente ni a un humano.
#
# Uso:  GH_TOKEN=... bash pr-comment.sh <numero_pr> <marcador> <archivo_body.md>
# Ej.:  bash pr-comment.sh 42 agente:dod-checker body.md
# ---------------------------------------------------------------------------
set -uo pipefail

PR="${1:?uso: pr-comment.sh <pr> <marcador> <archivo_body>}"
MARKER="${2:?falta el marcador, ej. agente:dod-checker}"
BODY_FILE="${3:?falta el archivo con el body}"
REPO="${GITHUB_REPOSITORY:?falta GITHUB_REPOSITORY}"

TAG="<!-- $MARKER -->"

TMP="$(mktemp)"
{ cat -- "$BODY_FILE"; printf '\n\n%s\n' "$TAG"; } > "$TMP"

# --paginate + --jq aplica el filtro por página, así que puede imprimir un id
# por página: nos quedamos con el último (el comentario más reciente del agente).
EXISTING="$(gh api --paginate "repos/$REPO/issues/$PR/comments" \
  --jq ".[] | select(.body != null and (.body | contains(\"$TAG\"))) | .id" 2>/dev/null | tail -n1)"

if [ -n "$EXISTING" ]; then
  if gh api -X PATCH "repos/$REPO/issues/comments/$EXISTING" -F "body=@$TMP" --silent 2>/dev/null; then
    echo "pr-comment: actualizado el comentario existente de '$MARKER' (id $EXISTING)."
    exit 0
  fi
  echo "pr-comment: no se pudo editar el comentario $EXISTING, se crea uno nuevo." >&2
fi

if gh api -X POST "repos/$REPO/issues/$PR/comments" -F "body=@$TMP" --silent 2>/dev/null; then
  echo "pr-comment: comentario de '$MARKER' creado en el PR #$PR."
else
  echo "::error::pr-comment: no se pudo comentar el PR #$PR (¿permisos pull-requests: write?)."
  exit 1
fi
