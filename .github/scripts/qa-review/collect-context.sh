#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# collect-context.sh — Fase 3 del QA PR Review Agent.
#
# Junta todo lo que el agente necesita saber del PR y lo deja en un directorio
# fuera del workspace del repo revisado, para que el checkout quede intacto
# (el workflow después verifica `git status --porcelain` vacío, plan §5).
#
#   qa-context/
#   ├── meta.json               PR: número, título, body, ramas, SHAs, autor
#   ├── diff.patch              diff de la PR (merge-base .. head)
#   ├── files.json              archivos cambiados con additions/deletions
#   ├── repo-tree.txt           estructura del repo (para que el Scout sepa qué pedir)
#   └── linear-issue.json       ticket SPM-xx de la rama, o {} si no hay
#
# Uso:  collect-context.sh <repo-dir> <pr-number> <owner/repo> <out-dir>
# Env:  GH_TOKEN (obligatorio), LINEAR_API_KEY (opcional), LINEAR_SH (ruta a linear.sh)
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_DIR="${1:?uso: collect-context.sh <repo-dir> <pr-number> <owner/repo> <out-dir>}"
PR="${2:?falta el número de PR}"
SLUG="${3:?falta owner/repo}"
OUT="${4:?falta el directorio de salida}"
: "${GH_TOKEN:?falta GH_TOKEN}"

mkdir -p "$OUT"
REPO_DIR="$(cd "$REPO_DIR" && pwd)"

# --- 1. Metadata del PR ----------------------------------------------------
gh pr view "$PR" --repo "$SLUG" \
  --json number,title,body,url,isDraft,state,baseRefName,headRefName,headRefOid,author,additions,deletions,changedFiles,labels \
  > "$OUT/meta.json"

HEAD_SHA="$(jq -r .headRefOid "$OUT/meta.json")"
BASE_REF="$(jq -r .baseRefName "$OUT/meta.json")"
BRANCH="$(jq -r .headRefName "$OUT/meta.json")"

# --- 2. Merge-base ---------------------------------------------------------
# Se usa el merge-base y no el tip de la rama base: el diff de la PR es de tres
# puntos, y comparar contra el tip metería en el "diff" cambios de otras PRs ya
# mergeadas a dev. Requiere checkout con fetch-depth: 0.
# Se fuerza el refspec para que quede `origin/<base>` local: `git fetch origin dev`
# a secas deja solo FETCH_HEAD y el merge-base de abajo fallaría.
git -C "$REPO_DIR" fetch --quiet origin \
  "+refs/heads/$BASE_REF:refs/remotes/origin/$BASE_REF" 2>/dev/null || true
BASE_SHA="$(git -C "$REPO_DIR" merge-base "origin/$BASE_REF" "$HEAD_SHA" 2>/dev/null || true)"
if [ -z "$BASE_SHA" ]; then
  echo "⚠️  No se pudo calcular el merge-base contra origin/$BASE_REF; uso el SHA base del PR."
  BASE_SHA="$(gh pr view "$PR" --repo "$SLUG" --json baseRefOid -q .baseRefOid)"
fi

jq --arg base "$BASE_SHA" --arg slug "$SLUG" \
   '. + {baseRefOid:$base, repo:$slug}' "$OUT/meta.json" > "$OUT/meta.tmp" \
  && mv "$OUT/meta.tmp" "$OUT/meta.json"

# --- 3. Diff ---------------------------------------------------------------
if ! git -C "$REPO_DIR" diff --no-color "$BASE_SHA" "$HEAD_SHA" > "$OUT/diff.patch" 2>/dev/null; then
  echo "⚠️  git diff falló; caigo al diff de la API de GitHub."
  gh pr diff "$PR" --repo "$SLUG" > "$OUT/diff.patch"
fi

# --- 4. Archivos cambiados -------------------------------------------------
gh pr view "$PR" --repo "$SLUG" --json files -q '.files' > "$OUT/files.json"

# --- 5. Árbol del repo -----------------------------------------------------
# Solo rutas versionadas y revisables: es el mapa que mira el Scout para decidir
# qué pedir. Se acota para no gastar contexto en carpetas generadas.
git -C "$REPO_DIR" ls-files \
  | grep -vE '(^|/)(node_modules|dist|build|\.next|out|coverage|vendor|\.turbo)(/|$)' \
  | grep -vE '\.(png|jpe?g|gif|webp|ico|svg|mp4|webm|mov|pdf|zip|woff2?|ttf|otf)$' \
  | head -3000 > "$OUT/repo-tree.txt"

# --- 6. Ticket de Linear ---------------------------------------------------
# Misma convención que el DoD checker: el identificador sale del nombre de la
# rama que Linear genera (ej. "santos/spm-42-login").
IDENT="$(printf '%s' "$BRANCH" | grep -oiE '[a-z]+-[0-9]+' | head -1 | tr '[:lower:]' '[:upper:]' || true)"
echo '{}' > "$OUT/linear-issue.json"
if [ -n "$IDENT" ] && [ -n "${LINEAR_API_KEY:-}" ] && [ -n "${LINEAR_SH:-}" ] && [ -f "${LINEAR_SH}" ]; then
  if bash "$LINEAR_SH" issue-context "$IDENT" > "$OUT/linear.tmp" 2>/dev/null && [ -s "$OUT/linear.tmp" ]; then
    mv "$OUT/linear.tmp" "$OUT/linear-issue.json"
    echo "Linear: $IDENT encontrado (evidencia visual: $(jq -r .hasVisualEvidence "$OUT/linear-issue.json"))"
  else
    rm -f "$OUT/linear.tmp"
    echo "Linear: la rama referencia $IDENT pero no se pudo consultar el ticket (evidence unavailable)."
  fi
elif [ -n "$IDENT" ]; then
  echo "Linear: la rama referencia $IDENT pero falta LINEAR_API_KEY (evidence unavailable)."
else
  echo "Linear: la rama '$BRANCH' no referencia ningún ticket."
fi

# --- Resumen ---------------------------------------------------------------
{
  echo "PR:      #$PR ($SLUG)"
  echo "Rama:    $BRANCH -> $BASE_REF"
  echo "Base:    $BASE_SHA"
  echo "Head:    $HEAD_SHA"
  echo "Diff:    $(wc -l < "$OUT/diff.patch") líneas de patch"
  echo "Linear:  ${IDENT:-(ninguno)}"
} | tee "$OUT/summary.txt"
