# Pendientes de administración de GitHub — centralización de workflows

> Para quien tiene permisos de owner/admin en `SportmatchOrg`. Referencia:
> [ISSUE-centralizar-workflows-reutilizables.md](ISSUE-centralizar-workflows-reutilizables.md).
> Nada de esto lo puede resolver una PR: son configuraciones de repo/org.

## Repo `agents-copilot`

- [ ] Branch protection en `main`: requerir PR + al menos 1 aprobación humana
      antes de mergear (un cambio acá afecta corridas nuevas de SportMatch sin
      aviso).
- [ ] Settings → Actions → General → **Access**: habilitar que los workflows
      sean accesibles desde repos de `SportmatchOrg` (o listar explícitamente
      `sportmatch` y `sportmatch-sandbox`). Sin esto, `workflow_call` cruzado
      entre repos privados falla.
- [ ] Exigir como status check obligatorio la validación YAML / prueba mínima
      de cada reusable (la Fase 1 del issue la agrega; falta marcarla como
      *required* en la protección de rama).
- [ ] Opcional: `CODEOWNERS` sobre `.github/workflows/*-reusable.yml` para que
      cambios a la lógica compartida pasen por alguien específico.

## Repo `sportmatch` (`dev` y `main`)

- [ ] Settings → Actions → General → **Workflow permissions**: confirmar que
      el default no cape por debajo de lo que cada wrapper declara.
      `repo-onboarding` necesita `contents: write` + `pull-requests: write`;
      `weekly-status` necesita `contents: write`.
- [ ] Settings → Actions → General → **"Allow GitHub Actions to create and
      approve pull requests"**: debe estar habilitado (lo usa
      `repo-onboarding` para abrir su PR).
- [ ] Los 7 wrappers + sus secrets/vars tienen que existir tanto en `dev` como
      en `main`: GitHub resuelve el workflow desde la rama base del evento,
      no alcanza con tenerlo solo en una.

## Secrets a crear (Settings → Secrets and variables → Actions)

| Secret | Lo usan |
|---|---|
| `LLM_API_KEY` | los 7 |
| `LINEAR_API_KEY` | `dod-checker`, `dor-readiness`, `sprint-health`, `weekly-status` |
| `DISCORD_WEBHOOK_PLANNING` | `context-curator`, `dor-readiness`, `repo-onboarding` |
| `DISCORD_WEBHOOK_QA` | `pr-business-translator`, `dod-checker` |
| `DISCORD_WEBHOOK_PROGRESS` | `sprint-health`, `weekly-status` |

- [ ] Crear los 5 de arriba.
- [ ] Decidir alcance: secret de repo (solo `sportmatch`) vs. secret de
      organización restringido a `{sportmatch, sportmatch-sandbox}` —
      recomendado el segundo, porque `sportmatch-sandbox` ya se usa como
      entorno de piloto.
- [ ] **No** crear ni pasar `GITHUB_TOKEN` a mano: GitHub se lo entrega al
      reusable automáticamente con los permisos que declara el job llamador.

## Vars a crear (mismo lugar, pestaña Variables)

- [ ] `LLM_BASE_URL`
- [ ] `LLM_MODEL`
- [ ] `LINEAR_TEAM_KEY`

## Políticas a confirmar (de la sección "Seguridad y gobierno" del issue)

- [ ] Ningún wrapper usa `secrets: inherit` — solo pasa los secretos
      declarados explícitamente.
- [ ] Ningún reusable eleva permisos por encima de los que declara el caller.
- [ ] `persist-credentials: false` en las automatizaciones de solo lectura.
- [ ] No aparecen secrets, prompts ni respuestas completas del LLM en logs.

## Aprobación de workflows en PRs abiertas por el bot

- [ ] Settings → Actions → General → **Fork pull request workflows from
      outside collaborators**: en `sportmatch-sandbox` está frenando las PRs
      que abre `github-actions[bot]` (ej. la del API Test Agent) — QA Review,
      DoD checker y el Traductor quedan en `action_required` y nunca corren.
      Confirmado el 03/09/2026 en la PR #21 (`bot/tests-spo-168`). Ajustar
      esta política (o aprobar a mano cada vez) antes de dar por probada la
      cadena agente → QA de punta a punta.

## Rollout

- [ ] Confirmar que `sportmatch-sandbox` sigue siendo el entorno aprobado
      para pilotear cada migración antes de tocar `sportmatch` real.
- [ ] Definir quién da la confirmación humana final de "la operación y las
      salidas no cambiaron" (último ítem de la Definition of Done).
