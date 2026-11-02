# Origen: qa-review

- **Tipo:** agente
- **Repo:** SportmatchOrg/agents-copilot @ 0587e23
- **Archivos de la pieza** (definen la autoría): `.github/workflows/qa-review-reusable.yml`, `github/workflows/qa-review.yml`, `.github/scripts/qa-review`, `docs/SPORTMATCH_QA_REVIEW_AGENT_PLAN.md`, `docs/Runbook v2 — QA PR Review Agent con OpenRouter.md`
- **Archivos de apoyo** (compartidos con otras piezas, copiados para que sea autocontenida): `github/scripts/linear.sh`
- **Prompt:** `qa-review.md` (extraído sin cambios)
- **Commits por integrante** (sobre los archivos de la pieza): Ignacio Chevallier 13, Tomás Valle 2, Matías Chialva 1
- **Autor:** Ignacio Chevallier
- **Colaboradores:** Tomás Valle, Matías Chialva

## Notas
- Scout y Reviewer son dos fases del mismo pipeline (no se usan por separado): una sola pieza.
- El Reviewer carga además la skill pr-review (SKILL.md + references/qa-criteria.md). No se copia acá: es la pieza `pr-review` de Matías y copiarla la duplicaría en el catálogo. Al instalar, tiene que estar en `github/skills/pr-review/` del repo de agentes.
