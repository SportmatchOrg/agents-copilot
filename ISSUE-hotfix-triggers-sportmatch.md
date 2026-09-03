# Reemplazar los 8 workflows de agentes en `sportmatch` por sus wrappers

> P0 — corrige una regresión activa de 5+ días.
> **Alcance: los 8 agentes de workflow. NO incluye el API Test Agent**, que
> necesita trabajo aparte (ver `ISSUE-test-agent-a-produccion.md`).

## Problema

`context-curator.yml`, `dod-checker.yml`, `pr-business-translator.yml` y
`qa-review.yml` en `SportmatchOrg/sportmatch@dev` tienen `on: workflow_call:`
como único trigger. No es un evento real: sin un `uses:` externo que los
invoque, no disparan nunca.

Última corrida en verde: **29/08/2026**. Desde entonces hubo PRs reales (ej.
`feature/SPO-179`, 03/09) que no los dispararon. **5+ días apagados sin que
nadie lo note**, porque un trigger inválido no genera ningún error visible.

`qa-review.yml` además usa `secrets: inherit`, contra la política de secretos
mínimos.

## Solución

```bash
bash install.sh ../sportmatch     # desde el clon de agents-copilot@main
```

Reemplaza los 8 workflows por wrappers de ~15 líneas (trigger + permisos +
`uses:` + secrets explícitos). La lógica queda en `agents-copilot`, así que
mejorarla no vuelve a requerir tocar `sportmatch`.

No hacen falta secrets nuevos: `QA_GITHUB_TOKEN`, `LLM_API_KEY` y
`LINEAR_API_KEY` ya existen como org secrets visibles para `sportmatch`.

**Ojo:** `install.sh` pisa sin preguntar cualquier `.yml` con el mismo nombre.
Es lo que queremos con los 4 rotos, pero también toca los 4 que hoy andan.

## Estado de los reusables

Los 8 están en `agents-copilot@main` y **los 8 se probaron con corridas reales
en el sandbox**, no solo por inspección:

| Reusable | Verificado |
|---|---|
| `context-curator`, `dod-checker`, `pr-business-translator`, `qa-review` | PR #2, en uso desde el 03/09 |
| `sprint-health`, `dor-readiness` | corrida verde: Linear → LLM → Discord |
| `weekly-status` | corrida verde + **commiteó el reporte** como `sportmatch-bot` |
| `repo-onboarding` | corrida verde; se abstuvo de abrir PR por no haber cambios (guarda correcta) |

## Validación en `sportmatch`

- [ ] Push a `dev` dispara `Curador de contexto`.
- [ ] Un PR nuevo dispara `DoD checker`, `Traductor de PR a negocio` y `QA Review`.
- [ ] `DoD checker` y `Traductor` dejan comentarios separados (no se pisan).
- [ ] `QA Review` crea la pending review a nombre del QA (no autosubmit).
- [ ] `gh run list --repo SportmatchOrg/sportmatch` muestra los workflows en verde.

## Fuera de alcance

- **El API Test Agent.** Su wrapper es `workflow_dispatch` a mano y no es parte
  de esta regresión. Lo suyo va en `ISSUE-test-agent-a-produccion.md`.
- No aplicar en `main` hasta confirmar que `dev` quedó verde.
