#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# linear.sh — Helpers de la API GraphQL de Linear para los workflows de agentes.
#
# Requiere el secret LINEAR_API_KEY (Settings → API → Personal API key, o una
# API key de workspace con permiso de lectura/escritura de issues).
#
# Subcomandos:
#   linear.sh find-by-identifier <IDENT>
#     Busca un issue por su identificador humano (ej. "SPM-42"). Linear
#     acepta el identificador o el UUID en el mismo campo `id`. Imprime el
#     JSON del issue (id, identifier, title, description, url, state) o
#     nada si no existe.
#
#   linear.sh team-id <TEAM_KEY>
#     Resuelve el UUID interno de un equipo a partir de su key (ej. "SPM").
#     Necesario para crear issues nuevos. Imprime el UUID o nada.
#
#   linear.sh comment <ISSUE_ID> <archivo_body.md>
#     Agrega un comentario a un issue existente (por UUID). Imprime la URL
#     del comentario creado.
#
#   linear.sh create-issue <TEAM_ID> <title> <archivo_body.md>
#     Crea un issue nuevo en el equipo dado. Imprime "<identifier> <url>".
#
# Ante cualquier error de red/API, estos comandos no rompen el script que
# los llama: devuelven salida vacía (exit 0) y el workflow decide cómo
# degradar (loggear y seguir, no bloquear el resto del job).
# ---------------------------------------------------------------------------
set -uo pipefail

: "${LINEAR_API_KEY:?falta el secret LINEAR_API_KEY}"
API="https://api.linear.app/graphql"

gql() { # $1 = payload JSON completo (query/mutation + variables)
  curl -sS "$API" \
    -H "Authorization: $LINEAR_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$1" 2>/dev/null
}

cmd="${1:?uso: linear.sh <find-by-identifier|team-id|comment|create-issue> ...}"
shift

case "$cmd" in
  find-by-identifier)
    IDENT="${1:?falta el identificador, ej. SPM-42}"
    PAYLOAD=$(jq -n --arg id "$IDENT" \
      '{query:"query($id:String!){ issue(id:$id){ id identifier title description url state{name} } }", variables:{id:$id}}')
    gql "$PAYLOAD" | jq -c '.data.issue // empty' 2>/dev/null
    ;;

  team-id)
    KEY="${1:?falta el team key, ej. SPM}"
    PAYLOAD=$(jq -n --arg k "$KEY" \
      '{query:"query($k:String!){ teams(filter:{key:{eq:$k}}){ nodes { id key } } }", variables:{k:$k}}')
    gql "$PAYLOAD" | jq -r '.data.teams.nodes[0].id // empty' 2>/dev/null
    ;;

  comment)
    ISSUE_ID="${1:?falta el ISSUE_ID (uuid)}"
    BODY_FILE="${2:?falta el archivo con el body del comentario}"
    PAYLOAD=$(jq -n --arg id "$ISSUE_ID" --rawfile body "$BODY_FILE" \
      '{query:"mutation($id:String!,$body:String!){ commentCreate(input:{issueId:$id, body:$body}){ success comment{ url } } }", variables:{id:$id, body:$body}}')
    gql "$PAYLOAD" | jq -r '.data.commentCreate.comment.url // empty' 2>/dev/null
    ;;

  create-issue)
    TEAM_ID="${1:?falta el TEAM_ID (uuid)}"
    TITLE="${2:?falta el título}"
    BODY_FILE="${3:?falta el archivo con la descripción}"
    PAYLOAD=$(jq -n --arg tid "$TEAM_ID" --arg title "$TITLE" --rawfile body "$BODY_FILE" \
      '{query:"mutation($tid:String!,$title:String!,$body:String!){ issueCreate(input:{teamId:$tid, title:$title, description:$body}){ success issue{ identifier url } } }", variables:{tid:$tid, title:$title, body:$body}}')
    gql "$PAYLOAD" | jq -r 'if .data.issueCreate.success then "\(.data.issueCreate.issue.identifier) \(.data.issueCreate.issue.url)" else empty end' 2>/dev/null
    ;;

  *)
    echo "comando desconocido: $cmd" >&2
    exit 1
    ;;
esac
