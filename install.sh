#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install.sh — Instala el paquete de agentes de IA de SportMatch en un repo.
#
# Copia AGENTS.md a la raíz del repo destino y el contenido de github/ a
# .github/ (resolviendo el renombrado github -> .github). Deja llm.sh
# ejecutable e imprime los próximos pasos (secrets, commit).
#
# Uso:  bash install.sh <ruta-al-repo-destino>
# Ej.:  bash install.sh ../sportmatch-onboarding
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:?uso: bash install.sh <ruta-al-repo-destino>}"

# --- Validaciones ----------------------------------------------------------
[ -d "$TARGET" ]            || { echo "❌ No existe la ruta destino: $TARGET"; exit 1; }
[ -d "$TARGET/.git" ]       || { echo "❌ $TARGET no es un repo git (falta .git/). Cloná el repo primero."; exit 1; }
[ -f "$SCRIPT_DIR/AGENTS.md" ] || { echo "❌ No encuentro AGENTS.md junto al script. Corré install.sh desde la raíz del paquete."; exit 1; }
[ -d "$SCRIPT_DIR/github" ] || { echo "❌ No encuentro la carpeta github/ junto al script."; exit 1; }

echo "→ Instalando agentes en: $TARGET"

# --- 1. AGENTS.md a la raíz ------------------------------------------------
if [ -f "$TARGET/AGENTS.md" ]; then
  echo "⚠️  Ya existe AGENTS.md en el destino. Lo copio como AGENTS.agents.md para que lo mergees a mano."
  cp "$SCRIPT_DIR/AGENTS.md" "$TARGET/AGENTS.agents.md"
else
  cp "$SCRIPT_DIR/AGENTS.md" "$TARGET/AGENTS.md"
fi

# --- 2. github/ -> .github/ (el renombrado clave) --------------------------
mkdir -p "$TARGET/.github/chatmodes" \
         "$TARGET/.github/skills/pr-review" \
         "$TARGET/.github/workflows" \
         "$TARGET/.github/scripts"

cp "$SCRIPT_DIR/github/copilot-instructions.md"     "$TARGET/.github/"
cp "$SCRIPT_DIR/github/chatmodes/"*.chatmode.md     "$TARGET/.github/chatmodes/"
cp "$SCRIPT_DIR/github/skills/pr-review/SKILL.md"   "$TARGET/.github/skills/pr-review/"
cp "$SCRIPT_DIR/github/workflows/"*.yml             "$TARGET/.github/workflows/"
cp "$SCRIPT_DIR/github/scripts/llm.sh"              "$TARGET/.github/scripts/"
cp "$SCRIPT_DIR/github/scripts/linear.sh"           "$TARGET/.github/scripts/"
chmod +x "$TARGET/.github/scripts/llm.sh" "$TARGET/.github/scripts/linear.sh"

echo "✅ Archivos instalados."
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
echo "     (opcional: habilita que el DoD checker cree un ticket de Linear"
echo "      cuando un PR no referencia ninguno — ver linear.sh):"
echo "       gh variable set LINEAR_TEAM_KEY --repo <owner/repo>   # ej. SPM"
echo "  2. Commiteá a la rama base (dev/main) para que los workflows se activen:"
echo "       git add AGENTS.md .github && git commit -m 'chore: add AI agents' && git push"
echo "  3. (Copilot) activá el code review automático en Settings → Code review del repo."
