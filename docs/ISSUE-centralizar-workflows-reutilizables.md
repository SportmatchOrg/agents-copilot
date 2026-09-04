# Centralizar los workflows de agentes en `agents-copilot`

> Tipo sugerido: `chore` · Prioridad sugerida: alta · Alcance: RNF-05 Mantenibilidad + RNF-04 Resiliencia

---

## Problema

El QA PR Review Agent ya utiliza el modelo de ejecución que queremos para el paquete:

- el evento se dispara desde un wrapper pequeño en `SportmatchOrg/sportmatch`;
- la lógica, los prompts, los scripts y el workflow reusable viven en `SportmatchOrg/agents-copilot`;
- una mejora en `agents-copilot` se aplica a las corridas nuevas sin copiar el workflow completo ni abrir una PR de sincronización en SportMatch.

Los otros workflows automáticos de agentes todavía están copiados completos en SportMatch. Esto genera dos fuentes de verdad y drift entre repositorios. De hecho, las versiones instaladas en `sportmatch/dev` ya difieren de las versiones
corregidas que existen en la rama `chore/agentes-v2` de `agents-copilot`.

## Objetivo

Aplicar el patrón de reusable workflow usado por QA a los siete workflows automáticos restantes, dejando en SportMatch únicamente el trigger, los permisos y el contrato de secretos de cada automatización.

La arquitectura final debe ser:

```text
SportmatchOrg/sportmatch
  wrapper: evento + permisos + secretos
                     │
                     ▼
SportmatchOrg/agents-copilot
  workflow reusable + prompts + scripts + lógica
```



## Alcance

Migrar estos workflows:


| Workflow actual              | Trigger que queda en SportMatch | Reusable central esperado             |
| ---------------------------- | ------------------------------- | ------------------------------------- |
| `context-curator.yml`        | `push` a `dev`/`main` + manual  | `context-curator-reusable.yml`        |
| `pr-business-translator.yml` | eventos de `pull_request`       | `pr-business-translator-reusable.yml` |
| `dod-checker.yml`            | eventos de `pull_request`       | `dod-checker-reusable.yml`            |
| `dor-readiness.yml`          | cron semanal + manual           | `dor-readiness-reusable.yml`          |
| `repo-onboarding.yml`        | cron mensual + manual           | `repo-onboarding-reusable.yml`        |
| `sprint-health.yml`          | cron diario + manual            | `sprint-health-reusable.yml`          |
| `weekly-status.yml`          | cron semanal + manual           | `weekly-status-reusable.yml`          |


También se debe dejar documentado que el octavo agente original, el code review nativo de GitHub Copilot, **no es un GitHub Actions workflow** y por lo tanto no puede migrarse mediante `workflow_call`. Sus archivos descubribles
(`AGENTS.md`, `copilot-instructions.md` y la skill de review) deben seguir existiendo en SportMatch.

## Fuera de alcance

- No centralizar `.github/workflows/ci.yml` ni `cd-back.yml`: pertenecen al producto y dependen de su implementación y despliegue.
- No cambiar el comportamiento funcional, prompts ni formato de salida de los agentes durante la migración.
- No cambiar los horarios de los cron.
- No modificar código de frontend o backend.
- No convertir el code review nativo de Copilot en un workflow propio.
- No migrar el API Test Agent: ya fue diseñado como reusable y debe tratarse en su entrega independiente.



## Diseño propuesto

### En `agents-copilot`

1. Llevar a `main` las versiones corregidas de los siete workflows y de la infraestructura compartida que hoy están en `chore/agentes-v2`.
2. Crear un reusable por automatización bajo `.github/workflows/`, todos con `on.workflow_call`.
3. Declarar inputs solamente cuando el repositorio destino necesite configurar comportamiento real, por ejemplo `agents_ref`, rama base o límites.
4. Declarar explícitamente los secretos que consume cada reusable.
5. Hacer checkout del repositorio llamador como target de análisis.
6. Resolver los scripts y la action compartida desde `agents-copilot`, sin depender de copias instaladas en `.github/scripts/` del repositorio llamador.
7. Mantener los side effects actuales y sus guardarraíles: comentarios sticky, deduplicación de issues/PRs, Linear, Discord y commits automáticos donde ya están autorizados.



### En `sportmatch`

Reemplazar los archivos actuales por los siguientes wrappers **exactos**. Estos son los archivos que deben copiarse y pegarse en SportMatch; no son pseudocódigo ni ejemplos.

Los siete reusables centrales deben implementar exactamente los nombres de secret que aparecen abajo: `LLM_API_KEY`, `LINEAR_API_KEY` y`DISCORD_WEBHOOK`. `secrets.GITHUB_TOKEN` no se pasa: GitHub lo entrega automáticamente al reusable con los permisos declarados por el job llamador.

Las variables `LLM_BASE_URL`, `LLM_MODEL` y `LINEAR_TEAM_KEY` se leen mediante el contexto `vars` del repositorio llamador dentro del reusable, igual que ya hace QA.

### Archivo 1 — `.github/workflows/context-curator.yml`

```yaml
name: Curador de contexto (drift AGENTS.md)

on:
  push:
    branches: [dev, main]
  workflow_dispatch:

jobs:
  context-curator:
    permissions:
      contents: read
      issues: write
    uses: SportmatchOrg/agents-copilot/.github/workflows/context-curator-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_PLANNING }}
```



### Archivo 2 — `.github/workflows/pr-business-translator.yml`

```yaml
name: Traductor de PR a negocio

on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [dev, main]

jobs:
  pr-business-translator:
    permissions:
      contents: read
      pull-requests: write
    uses: SportmatchOrg/agents-copilot/.github/workflows/pr-business-translator-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_QA }}
```



### Archivo 3 — `.github/workflows/dod-checker.yml`

```yaml
name: DoD checker

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [dev, main]

jobs:
  dod-checker:
    permissions:
      contents: read
      pull-requests: write
      checks: read
    uses: SportmatchOrg/agents-copilot/.github/workflows/dod-checker-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_QA }}
```



### Archivo 4 — `.github/workflows/dor-readiness.yml`

```yaml
name: Definition of Ready — digest semanal

on:
  schedule:
    - cron: "0 12 * * 1"
  workflow_dispatch:

jobs:
  dor-readiness:
    permissions:
      contents: read
    uses: SportmatchOrg/agents-copilot/.github/workflows/dor-readiness-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_PLANNING }}
```



### Archivo 5 — `.github/workflows/repo-onboarding.yml`

```yaml
name: Onboarding (refresh mensual)

on:
  schedule:
    - cron: "0 13 1 * *"
  workflow_dispatch:

jobs:
  repo-onboarding:
    permissions:
      contents: write
      pull-requests: write
    uses: SportmatchOrg/agents-copilot/.github/workflows/repo-onboarding-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_PLANNING }}
```



### Archivo 6 — `.github/workflows/sprint-health.yml`

```yaml
name: Sprint Health diario

on:
  schedule:
    - cron: "0 12 * * 1-5"
  workflow_dispatch:

jobs:
  sprint-health:
    permissions:
      contents: read
      pull-requests: read
    uses: SportmatchOrg/agents-copilot/.github/workflows/sprint-health-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_PROGRESS }}
```



### Archivo 7 — `.github/workflows/weekly-status.yml`

```yaml
name: Status Report semanal

on:
  schedule:
    - cron: "0 20 * * 5"
  workflow_dispatch:

jobs:
  weekly-status:
    permissions:
      contents: write
      pull-requests: read
    uses: SportmatchOrg/agents-copilot/.github/workflows/weekly-status-reusable.yml@main
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
      DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_PROGRESS }}
```

Estos wrappers sólo deben copiarse después de que los siete archivos `*-reusable.yml` existan en `agents-copilot/main`. La PR que agrega los wrappers no se valida a sí misma: los eventos empiezan a usar cada wrapper una vez que el archivo está presente en la rama base del evento.

## Seguridad y gobierno

- No usar `secrets: inherit`: pasar únicamente los secretos requeridos por cada workflow.
- El reusable puede mantener o reducir los permisos del caller, nunca elevarlos; por eso el wrapper debe declarar sus permisos explícitamente.
- Proteger `main` de `agents-copilot` con PR obligatoria y revisión humana. Un cambio mergeado allí afectará las corridas nuevas de SportMatch.
- Mantener `persist-credentials: false` en automatizaciones de solo lectura.
- Separar el paso que recibe credenciales de escritura del paso que invoca al LLM, cuando aplique.
- No exponer secrets, prompts sensibles ni respuestas completas en logs.
- Conservar `concurrency` y `cancel-in-progress` con grupos que no provoquen que caller y reusable se cancelen entre sí.



## Plan de implementación

### Fase 1 — Base central

- [ ] Integrar selectivamente en `main` la infraestructura vigente de`chore/agentes-v2`.
- [ ] Definir una convención común de rutas, inputs, secretos y summaries.
- [ ] Adaptar la infraestructura compartida para ejecutarse desde el checkout de`agents-copilot`, no desde archivos copiados en SportMatch.
- [ ] Agregar validación YAML y una prueba mínima de cada reusable.



### Fase 2 — Migración por tipo de evento

- [ ] Migrar y validar `context-curator` (`push`).
- [ ] Migrar y validar `pr-business-translator` y `dod-checker`(`pull_request`).
- [ ] Migrar y validar `dor-readiness`, `repo-onboarding`, `sprint-health` `weekly-status` (`schedule` + `workflow_dispatch`).



### Fase 3 — Wrappers en SportMatch

- [ ] Reemplazar los siete workflows completos por wrappers mínimos.
- [ ] Mantener nombres, triggers, cron, concurrencia y permisos actuales.
- [ ] Mapear secretos individualmente.
- [ ] Asegurar que los wrappers existan en `dev` y `main`, porque GitHub resuelve
  ```
  los workflows desde la rama base correspondiente.
  ```



### Fase 4 — Limpieza

- [ ] Identificar qué scripts/action locales ya no consume ningún workflow.
- [ ] Proponer su eliminación en una PR separada; no eliminarlos antes de validar
  ```
  todos los wrappers.
  ```
- [ ] Actualizar `install.sh`, `README.md`, `TESTING.md` y la versión del paquete.
- [ ] Mantener la instalación local de chat modes, instrucciones y skills que
  ```
  GitHub/Copilot necesitan descubrir dentro del repositorio destino.
  ```



## Estrategia de rollout

Migrar primero una automatización de solo lectura y bajo impacto, recomendada: `sprint-health`. Ejecutarla manualmente desde SportMatch y comparar su resultado contra el workflow actual.

Después continuar en este orden:

1. `dor-readiness`;
2. `context-curator`;
3. `pr-business-translator`;
4. `dod-checker`;
5. `repo-onboarding`;
6. `weekly-status`.

Los dos últimos escriben ramas, PRs o commits y deben validarse después de las automatizaciones de lectura/comentario.

## Validación requerida

Para cada workflow:

- [ ] El wrapper aparece en la pestaña Actions de SportMatch.
- [ ] El evento automático original sigue disparándolo.
- [ ] `workflow_dispatch` funciona cuando estaba disponible previamente.
- [ ] La ejecución usa el código de `agents-copilot@main`.
- [ ] Los permisos efectivos son los mínimos necesarios.
- [ ] Sólo se reciben los secretos declarados.
- [ ] La salida coincide funcionalmente con la versión anterior.
- [ ] Linear y Discord degradan de forma segura si falta una credencial o falla el proveedor.
- [ ] No se duplican comentarios, issues, ramas, PRs ni reportes.
- [ ] Un fallo del proveedor LLM no marca como fallida una PR de producto cuando el comportamiento previo era degradar con warning.
- [ ] Los logs y summaries permiten diagnosticar la corrida sin revelar secretos.

Pruebas específicas:

- [ ] `context-curator`: abre o actualiza un único issue ante drift.
- [ ] `pr-business-translator`: actualiza sólo su comentario sticky.
- [ ] `dod-checker`: actualiza sólo su comentario y conserva la integración con el ticket correcto de Linear.

- [ ] `dor-readiness`: distingue backlog vacío de error de Linear.
- [ ] `repo-onboarding`: no duplica una PR ya abierta y detecta archivos nuevos.
- [ ] `sprint-health`: distingue ciclo vacío de error de Linear.
- [ ] `weekly-status`: distingue `no-changes`, push exitoso y push rechazado.



## Criterios de aceptación

- [ ] Los siete workflows automáticos tienen un reusable funcional en
  ```
  `agents-copilot/.github/workflows/`.
  ```
- [ ] SportMatch contiene solamente wrappers mínimos para esos siete workflows.
- [ ] Los wrappers conservan exactamente los triggers y cron previos.
- [ ] Cada wrapper declara permisos y secretos mínimos de forma explícita.
- [ ] Ningún reusable depende de `.github/actions/agent-run` o
  ```
  `.github/scripts/*` copiados en SportMatch.
  ```
- [ ] Los siete workflows fueron probados desde SportMatch, incluyendo al menos
  ```
  una ejecución real del trigger principal de cada uno.
  ```
- [ ] Los efectos observables existentes se conservan: comentarios, Linear,
  ```
  Discord, issues, PRs y reportes según corresponda.
  ```
- [ ] `ci.yml`, `cd-back.yml` y el code review nativo de Copilot permanecen fuera
  ```
  de la migración.
  ```
- [ ] La documentación e instalador explican qué queda local y qué se ejecuta de
  ```
  forma centralizada.
  ```
- [ ] No se modificó código de producto ni se agregó alcance funcional fuera del
  ```
  MVP.
  ```



## Definition of Done

- [ ] PR de infraestructura mergeada en `agents-copilot/main`.
- [ ] PR de wrappers mergeada en `sportmatch/dev` y propagada a `main`.
- [ ] Checks de YAML/sintaxis verdes.
- [ ] Matriz de pruebas de los siete workflows documentada y en verde.
- [ ] Documentación e instalador actualizados.
- [ ] Confirmación humana de que la operación y las salidas no cambiaron.



## Evidencia actual

- Patrón existente: `.github/workflows/qa-review-reusable.yml` en
`agents-copilot`.
- Baseline del piloto: `Sprint Health diario` ejecutado manualmente en
`SportmatchOrg/sportmatch-sandbox` el 27/08/2026. Run
`33125296854`: terminó en verde y completó correctamente la lectura de
Linear, la llamada al LLM y la publicación en Discord.
- Workflows completos actuales: `.github/workflows/` de la rama `dev` de
`SportmatchOrg/sportmatch`.
- Versiones corregidas del paquete: rama `chore/agentes-v2` de
`SportmatchOrg/agents-copilot`.



## Título de PR sugerido

En `agents-copilot`:

```text
chore(RNF-05): centralizar workflows reutilizables de agentes
```

En SportMatch:

```text
chore(RNF-05): reemplazar workflows de agentes por wrappers
```

