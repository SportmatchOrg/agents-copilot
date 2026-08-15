#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install.sh — Instala/actualiza el paquete de agentes de IA de SportMatch.
#
# Copia AGENTS.md a la raíz del repo destino y el contenido de github/ a
# .github/ (resolviendo el renombrado github -> .github). Deja los scripts
# ejecutables, escribe .github/agents-version e imprime los próximos pasos.
#
# Es idempotente y seguro de re-correr: los archivos que el repo destino
# modificó a mano NO se pisan en silencio. Se listan al final y se copian
# como `<archivo>.nuevo` para comparar, salvo que se pase --force.
#
# Uso:  bash install.sh <ruta-al-repo-destino> [--force] [--dry-run]
# Ej.:  bash install.sh ../sportmatch-sandbox
#       bash install.sh ../sportmatch-sandbox --force   # pisa todo
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET=""
FORCE=0
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -*)        echo "❌ Opción desconocida: $arg"; exit 1 ;;
    *)         TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || { echo "uso: bash install.sh <ruta-al-repo-destino> [--force] [--dry-run]"; exit 1; }

# --- Validaciones ----------------------------------------------------------
[ -d "$TARGET" ]               || { echo "❌ No existe la ruta destino: $TARGET"; exit 1; }
[ -d "$TARGET/.git" ]          || { echo "❌ $TARGET no es un repo git (falta .git/). Cloná el repo primero."; exit 1; }
[ -f "$SCRIPT_DIR/AGENTS.md" ] || { echo "❌ No encuentro AGENTS.md junto al script. Corré install.sh desde la raíz del paquete."; exit 1; }
[ -d "$SCRIPT_DIR/github" ]    || { echo "❌ No encuentro la carpeta github/ junto al script."; exit 1; }

VERSION="$(cat "$SCRIPT_DIR/github/VERSION" 2>/dev/null || echo "desconocida")"
INSTALLED="$(cat "$TARGET/.github/agents-version" 2>/dev/null || echo "")"

echo "→ Instalando agentes v$VERSION en: $TARGET"
[ -n "$INSTALLED" ] && echo "  (versión instalada actualmente: $INSTALLED)"
[ "$DRY_RUN" = "1" ] && echo "  (--dry-run: no se escribe nada)"

# Lista de archivos divergentes, como texto (no array: bash 3.2 de macOS falla
# con `${#arr[@]}` sobre un array vacío bajo `set -u`).
DIVERGENTES=""

# copiar <origen> <destino>
# Copia salvo que el destino exista y difiera: en ese caso deja <destino>.nuevo
# y lo anota, para que un cambio local hecho a propósito no se pierda solo.
copiar() {
  src="$1"; dst="$2"
  if [ -f "$dst" ] && ! diff -q "$src" "$dst" >/dev/null 2>&1 && [ "$FORCE" = "0" ]; then
    DIVERGENTES="${DIVERGENTES}${dst}
"
    [ "$DRY_RUN" = "1" ] || cp "$src" "$dst.nuevo"
    return
  fi
  [ "$DRY_RUN" = "1" ] || cp "$src" "$dst"
}

# --- 1. AGENTS.md a la raíz ------------------------------------------------
copiar "$SCRIPT_DIR/AGENTS.md" "$TARGET/AGENTS.md"

# --- 2. github/ -> .github/ (el renombrado clave) --------------------------
if [ "$DRY_RUN" = "0" ]; then
  mkdir -p "$TARGET/.github/chatmodes" \
           "$TARGET/.github/skills/pr-review" \
           "$TARGET/.github/workflows" \
           "$TARGET/.github/scripts" \
           "$TARGET/.github/actions/agent-run"
fi

copiar "$SCRIPT_DIR/github/copilot-instructions.md"        "$TARGET/.github/copilot-instructions.md"
copiar "$SCRIPT_DIR/github/skills/pr-review/SKILL.md"      "$TARGET/.github/skills/pr-review/SKILL.md"
copiar "$SCRIPT_DIR/github/actions/agent-run/action.yml"   "$TARGET/.github/actions/agent-run/action.yml"

for f in "$SCRIPT_DIR/github/chatmodes/"*.chatmode.md; do
  copiar "$f" "$TARGET/.github/chatmodes/$(basename "$f")"
done
for f in "$SCRIPT_DIR/github/workflows/"*.yml; do
  copiar "$f" "$TARGET/.github/workflows/$(basename "$f")"
done
for f in "$SCRIPT_DIR/github/scripts/"*.sh; do
  copiar "$f" "$TARGET/.github/scripts/$(basename "$f")"
done

if [ "$DRY_RUN" = "0" ]; then
  chmod +x "$TARGET/.github/scripts/"*.sh
  printf '%s\n' "$VERSION" > "$TARGET/.github/agents-version"
fi

echo "✅ Archivos instalados (v$VERSION)."

if [ -n "$DIVERGENTES" ]; then
  echo ""
  echo "⚠️  Estos archivos ya estaban modificados en el destino y NO se pisaron."
  echo "   Se copió la versión nueva al lado, con sufijo .nuevo, para que compares:"
  printf '%s' "$DIVERGENTES" | while IFS= read -r d; do
    [ -n "$d" ] && echo "     diff \"$d\" \"$d.nuevo\""
  done
  echo "   Cuando resuelvas cada uno, borrá el .nuevo. (O reinstalá con --force"
  echo "   si querés que la plantilla gane siempre.)"
fi

echo ""
echo "Próximos pasos en el repo destino:"
echo "  1. Cargá los secrets (una vez, en el repo):"
echo "       gh secret set LLM_API_KEY              --repo <owner/repo>"
echo "       gh secret set LINEAR_API_KEY           --repo <owner/repo>"
echo "       gh secret set DISCORD_WEBHOOK_QA       --repo <owner/repo>"
echo "       gh secret set DISCORD_WEBHOOK_PLANNING --repo <owner/repo>"
echo "       gh secret set DISCORD_WEBHOOK_PROGRESS --repo <owner/repo>"
echo "     (opcional, para cambiar de proveedor de LLM — ver llm.sh):"
echo "       gh variable set LLM_BASE_URL --repo <owner/repo>"
echo "       gh variable set LLM_MODEL    --repo <owner/repo>"
echo "     (recomendado: el prefijo del team de Linear, ej. SPM. Habilita crear"
echo "      un ticket cuando un PR no referencia ninguno, y hace más preciso el"
echo "      matcheo del identificador en el nombre de la rama):"
echo "       gh variable set LINEAR_TEAM_KEY --repo <owner/repo>"
echo "  2. Commiteá a la rama base (dev/main) para que los workflows se activen:"
echo "       git add AGENTS.md .github && git commit -m 'chore: add AI agents' && git push"
echo "  3. (Copilot) activá el code review automático en Settings → Code review del repo."
