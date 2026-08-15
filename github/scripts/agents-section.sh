#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# agents-section.sh — Imprime una sección de AGENTS.md por su número.
#
# AGENTS.md es la fuente de verdad del proyecto, pero los prompts de los
# workflows repetían su contenido a mano (los 6 criterios de DoD, la lista de
# RF-01..RF-06). Cambiar AGENTS.md obligaba a acordarse de editar 7 prompts.
# Con esto, el prompt inyecta la sección real del archivo: una sola fuente.
#
# Uso:  bash agents-section.sh <numero> [archivo]
# Ej.:  bash agents-section.sh 6            # "## 6. Convenciones" completa
#
# Si el archivo o la sección no existen, imprime un aviso y sale 0 (el
# workflow sigue: un prompt sin esa sección es peor pero no fatal).
# ---------------------------------------------------------------------------
set -uo pipefail

N="${1:?uso: agents-section.sh <numero> [archivo]}"
FILE="${2:-AGENTS.md}"

if [ ! -f "$FILE" ]; then
  echo "(no se encontró $FILE)"
  exit 0
fi

OUT="$(awk -v pat="^## ${N}\\." '
  $0 ~ pat        { f = 1; print; next }
  f && /^## [0-9]+\./ { exit }
  f               { print }
' "$FILE")"

if [ -z "$OUT" ]; then
  echo "(no se encontró la sección $N en $FILE)"
else
  printf '%s\n' "$OUT"
fi
