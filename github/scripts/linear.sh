#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# linear.sh — Helpers de la API GraphQL de Linear para los workflows de agentes.
#
# Requiere el secret LINEAR_API_KEY (Settings → API → Personal API key, o una
# API key de workspace con permiso de lectura/escritura de issues). Si falta,
# los comandos de lectura devuelven status="error" y los de escritura salida
# vacía: el workflow degrada, no se cae.
#
# Subcomandos de LECTURA (imprimen SIEMPRE un JSON normalizado
# `{status, message, nodes}` con status ∈ ok | empty | error):
#
#   linear.sh active-issues
#     Issues del ciclo/sprint activo (agentes 9 Sprint Health y 10 Status).
#
#   linear.sh backlog-unscheduled
#     Issues de backlog todavía sin ciclo asignado (agente 5.1 DoR).
#
# Por qué normalizado: antes cada workflow hacía su propio `curl` y clasificaba
# la respuesta con `jq -e '.errors, .error'`, que toma el exit code del ÚLTIMO
# output — con `{"errors":[...]}` daba "no hay error" y un token vencido se
# reportaba como "no hay ciclo activo". La clasificación vive acá, una vez.
#
# Subcomandos de ESCRITURA / lookup puntual:
#
#   linear.sh find-by-identifier <IDENT>   → JSON del issue (o vacío)
#   linear.sh team-id <TEAM_KEY>           → UUID del equipo (o vacío)
#   linear.sh comment <ISSUE_ID> <file.md> → URL del comentario creado
#   linear.sh create-issue <TEAM_ID> <title> <file.md> → "<identifier> <url>"
#
# Ante error de red/API estos últimos devuelven salida vacía (exit 0) y el
# workflow decide cómo degradar (loggear y seguir, no bloquear el job).
# ---------------------------------------------------------------------------
set -uo pipefail

API="https://api.linear.app/graphql"
API_KEY="${LINEAR_API_KEY:-}"

gql() { # $1 = payload JSON completo (query/mutation + variables)
  [ -n "$API_KEY" ] || return 0
  curl -sS --max-time 60 "$API" \
    -H "Authorization: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$1" 2>/dev/null
}

# Ejecuta una query de listado y normaliza la respuesta a {status,message,nodes}.
fetch_issues() { # $1 = query GraphQL
  if [ -z "$API_KEY" ]; then
    jq -n '{status:"error", message:"falta el secret LINEAR_API_KEY", nodes:[]}'
    return 0
  fi

  local payload resp msg nodes
  payload="$(jq -n --arg q "$1" '{query:$q}')"
  resp="$(gql "$payload")"

  if [ -z "$resp" ]; then
    jq -n '{status:"error", message:"la API de Linear no respondió (red/timeout)", nodes:[]}'
    return 0
  fi

  # `has("errors") or has("error")` en vez de `.errors, .error`: un solo output,
  # así el exit code de jq -e refleja de verdad si hubo error.
  if printf '%s' "$resp" | jq -e 'has("errors") or has("error")' >/dev/null 2>&1; then
    msg="$(printf '%s' "$resp" | jq -r '(.errors[0].message // .error // "error desconocido")' 2>/dev/null)"
    jq -n --arg m "$msg" '{status:"error", message:$m, nodes:[]}'
    return 0
  fi

  nodes="$(printf '%s' "$resp" | jq -c '.data.issues.nodes // empty' 2>/dev/null)"
  if [ -z "$nodes" ]; then
    jq -n '{status:"error", message:"respuesta inesperada de Linear (sin data.issues)", nodes:[]}'
  elif [ "$(printf '%s' "$nodes" | jq 'length')" = "0" ]; then
    jq -n --argjson n "$nodes" '{status:"empty", message:"", nodes:$n}'
  else
    jq -n --argjson n "$nodes" '{status:"ok", message:"", nodes:$n}'
  fi
}

cmd="${1:?uso: linear.sh <active-issues|backlog-unscheduled|find-by-identifier|team-id|comment|create-issue> ...}"
shift

case "$cmd" in
  active-issues)
    fetch_issues '{ issues(filter:{cycle:{isActive:{eq:true}}}, first:100) { nodes { identifier title state{name} assignee{name} estimate updatedAt completedAt url } } }'
    ;;

  backlog-unscheduled)
    fetch_issues '{ issues(filter:{cycle:{null:true}, state:{type:{in:["backlog","unstarted"]}}}, first:25) { nodes { identifier title description estimate state{name} labels{nodes{name}} url } } }'
    ;;

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
