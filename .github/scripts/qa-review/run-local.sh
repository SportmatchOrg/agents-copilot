#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run-local.sh — Corre el pipeline completo del QA PR Review Agent desde tu
# máquina, contra una PR real, sin necesidad de GitHub Actions.
#
# Es la herramienta del pilot (Fase 13/14): permite iterar sobre `qa-criteria.md`
# y ver el efecto en findings reales sin esperar a que corra un workflow.
#
# Por defecto NO publica nada: imprime el borrador que crearía. Para crear la
# pending review de verdad hay que pasar --publish y tener QA_GITHUB_TOKEN.
#
# Uso:
#   run-local.sh <owner/repo> <pr-number> [--publish] [--keep]
#
# Env (se lee .env de la raíz de agents-copilot si existe):
#   LLM_API_KEY      obligatorio
#   LLM_BASE_URL     opcional
#   LLM_MODEL        opcional
#   LINEAR_API_KEY   opcional
#   QA_GITHUB_TOKEN  solo para --publish
#
# Ejemplo:
#   .github/scripts/qa-review/run-local.sh SportmatchOrg/sportmatch 42
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS="$(cd "$SCRIPTS/../../.." && pwd)"

SLUG="${1:?uso: run-local.sh <owner/repo> <pr-number> [--publish] [--keep]}"
PR="${2:?falta el número de PR}"
shift 2

PUBLISH=0
KEEP=0
for arg in "$@"; do
  case "$arg" in
    --publish) PUBLISH=1 ;;
    --keep)    KEEP=1 ;;
    *) echo "argumento desconocido: $arg" >&2; exit 1 ;;
  esac
done

# Config del LLM desde .env, sin pisar lo que ya esté en el entorno.
if [ -f "$AGENTS/.env" ]; then
  # `|| [ -n "$k" ]` rescata la última línea cuando el archivo no termina en \n.
  while IFS='=' read -r k v || [ -n "$k" ]; do
    case "$k" in ''|\#*) continue ;; esac
    if [ -z "${!k:-}" ]; then export "$k=$v"; fi
  done < "$AGENTS/.env"
fi

: "${LLM_API_KEY:?falta LLM_API_KEY (poné un .env en la raíz de agents-copilot)}"
command -v gh  >/dev/null || { echo "falta el CLI gh"; exit 1; }
command -v jq  >/dev/null || { echo "falta jq"; exit 1; }

WORK="$(mktemp -d)"
cleanup() { [ "$KEEP" = "1" ] && echo "Contexto en: $WORK" || rm -rf "$WORK"; }
trap cleanup EXIT

TARGET="$WORK/target"
CTX="$WORK/qa-context"
export GH_TOKEN="${GH_TOKEN:-$(gh auth token)}"

HEAD_SHA="$(gh pr view "$PR" --repo "$SLUG" --json headRefOid -q .headRefOid)"
BASE_REF="$(gh pr view "$PR" --repo "$SLUG" --json baseRefName -q .baseRefName)"

echo "▸ Clonando $SLUG en el head de la PR #$PR ($HEAD_SHA)…"
git clone --quiet "https://github.com/$SLUG.git" "$TARGET"
git -C "$TARGET" fetch --quiet origin "+refs/pull/$PR/head:refs/qa/pr" \
  "+refs/heads/$BASE_REF:refs/remotes/origin/$BASE_REF"
git -C "$TARGET" checkout --quiet --detach "$HEAD_SHA"

# Mismo preflight que el workflow: si el QA ya trabajó su borrador, no gastamos
# llamadas al modelo. Solo aplica con --publish; en dry run siempre se analiza.
if [ "$PUBLISH" = "1" ]; then
  : "${QA_GITHUB_TOKEN:?--publish necesita QA_GITHUB_TOKEN (el PAT del QA)}"
  echo "▸ Preflight…"
  out="$(python3 "$SCRIPTS/create-pending-review.py" --preflight \
          --ctx "$CTX" --repo "$SLUG" --pr "$PR" --head-sha "$HEAD_SHA")"
  echo "$out"
  case "$out" in *"Se omite el análisis"*) exit 0 ;; esac
fi

echo "▸ Contexto…"
LINEAR_SH="$AGENTS/github/scripts/linear.sh" \
  bash "$SCRIPTS/collect-context.sh" "$TARGET" "$PR" "$SLUG" "$CTX"

echo "▸ Checks determinísticos…"
python3 "$SCRIPTS/deterministic-checks.py" \
  --patch "$CTX/diff.patch" --repo "$TARGET" \
  --base-sha "$(jq -r .baseRefOid "$CTX/meta.json")" --head-sha "$HEAD_SHA" \
  --out "$CTX/deterministic-facts.json"

if [ "$(jq -r .nothingToReview "$CTX/deterministic-facts.json")" = "true" ]; then
  echo "⏭️  Nada que revisar (diff vacío o todo no revisable). No se llama al modelo."
  exit 0
fi

echo "▸ Scout…"
python3 "$SCRIPTS/run-scout.py" --ctx "$CTX" --agents-repo "$AGENTS" --target-repo "$TARGET"

echo "▸ Resolviendo contexto…"
python3 "$SCRIPTS/resolve-context.py" --ctx "$CTX" --target-repo "$TARGET"

echo "▸ Reviewer…"
python3 "$SCRIPTS/run-reviewer.py" --ctx "$CTX" --agents-repo "$AGENTS" --target-repo "$TARGET"

echo "▸ Validando…"
python3 "$SCRIPTS/validate-review.py" --ctx "$CTX" --target-repo "$TARGET" --head-sha "$HEAD_SHA"

echo "▸ Pending review…"
if [ "$PUBLISH" = "1" ]; then
  : "${QA_GITHUB_TOKEN:?--publish necesita QA_GITHUB_TOKEN (el PAT del QA)}"
  python3 "$SCRIPTS/create-pending-review.py" \
    --ctx "$CTX" --repo "$SLUG" --pr "$PR" --head-sha "$HEAD_SHA"
else
  python3 "$SCRIPTS/create-pending-review.py" \
    --ctx "$CTX" --repo "$SLUG" --pr "$PR" --head-sha "$HEAD_SHA" --dry-run
  echo ""
  echo "(dry run: no se creó nada en GitHub. Agregá --publish para crearla de verdad.)"
fi

[ "$KEEP" = "1" ] || echo "(agregá --keep para conservar prompts y salidas en un temp dir)"
