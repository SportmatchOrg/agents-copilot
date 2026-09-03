# Reemplazar 4 workflows rotos en sportmatch/dev por sus wrappers validados

> Prioridad: alta (P0) — corrige una regresión activa de 5+ días, no es
> trabajo nuevo de centralización.

## Problema

`context-curator.yml`, `dod-checker.yml`, `pr-business-translator.yml` y
`qa-review.yml` en `SportmatchOrg/sportmatch` (rama `dev`) tienen
`on: workflow_call:` como único trigger. No es un evento real: sin un `uses:`
externo que los invoque, no disparan nunca, para ningún push ni PR.

Última corrida en verde de los tres primeros: **29/08/2026**. Desde entonces
hubo PRs reales (ej. `feature/SPO-179`, 03/09) que no los dispararon. Llevan
**5+ días apagados** sin que nadie lo note, porque un trigger inválido no
genera ningún error visible. `qa-review.yml` tiene el mismo problema, y
además usa `secrets: inherit` (contradice la política de secretos mínimos).

`dor-readiness.yml`, `repo-onboarding.yml`, `sprint-health.yml` y
`weekly-status.yml` están bien — no tocar.

## Alcance

Reemplazar los 4 archivos completos por sus wrappers, tal cual están en
`agents-copilot@main` una vez mergeada la PR:

- `github/workflows/context-curator.yml`
- `github/workflows/dod-checker.yml`
- `github/workflows/pr-business-translator.yml`
- `github/workflows/qa-review.yml`

Cada uno pasa de ~100-170 líneas de lógica completa a ~15-20 líneas de
wrapper (trigger + permisos + `uses:` + secrets explícitos). El wrapper de
`qa-review.yml` además deja de usar `secrets: inherit`.

No hace falta cargar secrets nuevos: `QA_GITHUB_TOKEN`, `LLM_API_KEY` y
`LINEAR_API_KEY` ya existen como org secrets visibles para `sportmatch`.

**Forma más simple de aplicarlo**: correr `install.sh` de `agents-copilot`
contra el clon local de `sportmatch` — copia los wrappers de los 8 workflows
de una sola vez (los 4 de acá + los 4 que ya estaban bien) y no requiere
tocar nada a mano. Confirmado en sandbox: reemplaza toda la lógica vieja por
los wrappers en un solo commit.

## Validación

- [ ] Push a `dev` dispara `Curador de contexto`.
- [ ] Un PR nuevo dispara `DoD checker`, `Traductor de PR a negocio` y `QA Review`.
- [ ] `DoD checker` y `Traductor` dejan comentarios separados en el PR (no se pisan).
- [ ] `QA Review` crea la pending review a nombre del QA (no autosubmit).
- [ ] `gh run list --repo SportmatchOrg/sportmatch` muestra los 4 en verde tras el fix.

## Fuera de alcance

- El API Test Agent va por separado: su wrapper es `workflow_dispatch` a mano
y no es parte de esta regresión.
- ~~No tocar `dor-readiness`, `repo-onboarding`, `sprint-health`,
`weekly-status` — sus reusables todavía no existen.~~ **Ya existen** (`c34bb02`),
así que `install.sh` puede reemplazar los 8 de una. Ojo igual: los 4 nuevos
solo se probaron con `sprint-health`; los otros tres se validan con la
checklist de abajo.
- No aplicar en `main` hasta confirmar que `dev` quedó verde.

