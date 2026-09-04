# Reemplazar los workflows de agentes en `sportmatch` por sus wrappers

> **P0** — corrige una regresión activa de 5+ días.
> **Depende de:** `ISSUE-harness-e2e-sportmatch.md`. Hacer ese primero.

## Problema

`context-curator.yml`, `dod-checker.yml`, `pr-business-translator.yml` y `qa-review.yml` en `SportmatchOrg/sportmatch@dev` tienen `on: workflow_call:` como único trigger. No es un evento real: sin un `uses:` externo que los invoque, no disparan nunca, para ningún push ni PR.

Última corrida en verde: **29/08/2026**. Desde entonces hubo PRs reales (ej. `feature/SPO-179`, 03/09) que no los dispararon. **5+ días apagados sin que nadie lo note**, porque un trigger inválido no genera ningún error visible.

`qa-review.yml` además usa `secrets: inherit`, contra la política de secretos mínimos.

## Qué correr

```bash
git clone https://github.com/SportmatchOrg/agents-copilot.git
cd agents-copilot
bash install.sh ../sportmatch
```

Reemplaza los 9 workflows del paquete por wrappers de ~15 líneas (trigger + permisos + `uses:` + secrets explícitos). La lógica queda en `agents-copilot`, así que mejorarla no vuelve a requerir tocar `sportmatch`.

No hacen falta secrets nuevos: `QA_GITHUB_TOKEN`, `LLM_API_KEY` y `LINEAR_API_KEY` son org secrets, y los workflows de `sportmatch` ya corrían con ellos hasta el 29/08. Si alguno saliera vacío en la primera corrida, es que la org restringió su visibilidad para este repo.

## El noveno: API Test Agent

`install.sh` instala también `test-agent.yml`. Es `workflow_dispatch` puro no se dispara solo, no toca ningún PR, y no participa de esta regresión. Queda instalado y listo para el primer uso a mano.

Por eso este issue depende del harness: sin `back/test/`, ese agente no tiene contra qué correr. El resto de los workflows no lo necesitan.

## Validación

- [ ] Push a `dev` dispara `Curador de contexto`.
- [ ] Un PR nuevo dispara `DoD checker`, `Traductor de PR a negocio` y `QA Review`.
- [ ] `DoD checker` y `Traductor` dejan comentarios separados (no se pisan).
- [ ] `QA Review` crea la pending review a nombre del QA (no autosubmit).
- [ ] Los 4 que ya andaban (`dor-readiness`, `repo-onboarding`, `sprint-health`,
  ```
  `weekly-status`) siguen verdes tras el reemplazo.
  ```
- [ ] `Actions → API Test Agent → Run workflow` con un ticket real deja una PR
  ```
  en draft con tests.
  ```



## Fuera de alcance

- No aplicar en `main` hasta confirmar que `dev` quedó verde.

