#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install.sh — Instala el paquete de agentes de IA de SportMatch en un repo.
#
# Copia AGENTS.md a la raíz del repo destino y el contenido de github/ a
# .github/ (resolviendo el renombrado github -> .github) e imprime los
# próximos pasos (secrets, commit).
#
# Los workflows del paquete (github/workflows/*.yml) son wrappers finos: la
# lógica, los prompts y los scripts viven en SportmatchOrg/agents-copilot y
# se resuelven ahí en cada corrida vía `uses: .../*-reusable.yml@main`. Por
# eso NO hace falta copiar scripts al repo destino, y volver a correr este
# script sobre un repo ya instalado reemplaza cualquier workflow viejo
# (versión completa, pre-centralización) por su wrapper actual.
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
         "$TARGET/.github/workflows"

cp "$SCRIPT_DIR/github/copilot-instructions.md"     "$TARGET/.github/"
cp "$SCRIPT_DIR/github/chatmodes/"*.chatmode.md     "$TARGET/.github/chatmodes/"
cp "$SCRIPT_DIR/github/skills/pr-review/SKILL.md"   "$TARGET/.github/skills/pr-review/"
# qa-criteria.md NO se instala a propósito (plan §7). El QA PR Review Agent lo
# lee desde agents-copilot en runtime, así que acá no hace falta; y si viviera
# bajo .github/skills/ del repo de desarrollo, la review nativa de Copilot
# podría levantarlo y empezar a publicar comentarios QA sin aprobación humana,
# que es exactamente lo que este diseño evita.
# Wrappers: reemplazan sin preguntar cualquier .yml previo con el mismo
# nombre (incluida una versión completa pre-centralización).
cp "$SCRIPT_DIR/github/workflows/"*.yml             "$TARGET/.github/workflows/"

echo "✅ Archivos instalados."
echo ""
echo "Próximos pasos en el repo destino:"
echo "  1. Cargá los secrets (una vez, en el repo):"
echo "       gh secret set LLM_API_KEY              --repo <owner/repo>"
echo "       gh secret set LINEAR_API_KEY           --repo <owner/repo>"
echo "       gh secret set DISCORD_WEBHOOK_QA       --repo <owner/repo>"
echo "       gh secret set DISCORD_WEBHOOK_PLANNING --repo <owner/repo>"
echo "       gh secret set DISCORD_WEBHOOK_PROGRESS --repo <owner/repo>"
echo "     (opcional, para cambiar de proveedor de LLM — ver agents-copilot/.github/scripts/llm.sh):"
echo "       gh variable set LLM_BASE_URL --repo <owner/repo>"
echo "       gh variable set LLM_MODEL    --repo <owner/repo>"
echo "     (opcional: habilita que el DoD checker cree un ticket de Linear"
echo "      cuando un PR no referencia ninguno):"
echo "       gh variable set LINEAR_TEAM_KEY --repo <owner/repo>   # ej. SPM"
echo "  2. Commiteá a la rama base (dev/main) para que los workflows se activen:"
echo "       git add AGENTS.md .github && git commit -m 'chore: add AI agents' && git push"
echo "  3. (Copilot) activá el code review automático en Settings → Code review del repo."
echo "  4. QA PR Review Agent (qa-review.yml) — setup adicional, una vez:"
echo "     a. QA_GITHUB_TOKEN es un Fine-Grained PAT de la PERSONA que hace QA."
echo "        Una pending review solo la ve quien la creó: con el token del bot,"
echo "        el QA no vería su propio borrador."
echo "        Permisos — en este repo:      Contents: Read"
echo "                                      Pull requests: Read and write"
echo "                                      Metadata: Read"
echo "                  en agents-copilot:  Contents: Read, Metadata: Read"
echo "     b. En SportmatchOrg/agents-copilot → Settings → Actions → General →"
echo "        Access: permitir que los repos de la organización usen sus workflows."
echo "     c. Settings → General → Pull Requests → Automatically delete head"
echo "        branches (resuelve el criterio QA-08 sin gastar tokens)."
