# Agentes de IA — SportMatch (versión GitHub Copilot)

Paquete de agentes para el repo de desarrollo, en formato **nativo de GitHub Copilot** (gratis con el plan **Copilot Student** del GitHub Student Developer Pack). Basado en el *Catálogo de Agentes de IA — Laboratorio IV*.

> **"Lab4 no codifica".** Los agentes revisan, verifican y reportan; no mergean código solos. Cuando detectan algo, dejan un comentario/sugerencia en el PR o proponen una tarjeta para Linear. La decisión final es humana.

## Cómo se mapean los 8 agentes a Copilot

Copilot no usa "subagentes" como Claude; usa **chat modes**, **custom instructions**, **agent skills** y **workflows**. Cada agente se implementa con la pieza nativa que corresponde:

| # | Agente | Pieza de Copilot | Cómo se usa |
|---|--------|------------------|-------------|
| 1 | Curador de contexto | Chat mode **+ workflow** | Manual en Chat, **y** automático en `push` a dev/main (abre/actualiza issue si hay drift) |
| 2 | Code reviewer | **Copilot code review** + agent skill + `copilot-instructions.md` | Automático en cada PR |
| 3 | Traductor a negocio | Chat mode **+ workflow** | Manual en Chat, **y** automático al abrir un PR (comenta el PR) |
| 4 | Onboarding de repo | Chat mode **+ workflow** | Manual en Chat, **y** automático el 1° de cada mes (abre PR con `docs/ONBOARDING.md` actualizado) |
| 5.1 | DoR checker | Chat mode **+ workflow** | Manual en Chat (un ticket puntual), **y** automático semanal (digest del backlog sin ciclo asignado) |
| 7 | DoD checker | Chat mode **+ workflow** | Manual en Chat, **y** automático en el PR (deja el veredicto DoD, y lo postea en el ticket real de Linear si el PR lo referencia) |
| 2.1 | **QA PR Review Agent** | **Reusable workflow + agent skill + criterios QA** | **Automático en cada PR a dev/main: prepara una review PENDING a nombre del QA** |
| 9 | Sprint Health | Workflow (cron + LLM) | Automático, diario → Discord |
| 10 | Status Reporter | Workflow (cron + LLM) | Automático, semanal → Discord |

Además: **`AGENTS.md`** en la raíz — Copilot code review **ya lo lee automáticamente** como contexto. Es el archivo más importante; completalo primero (tiene `TODO`s para el stack).

### Modo dual: chat mode vs. workflow

Los agentes 1, 3, 4, 5.1 y 7 vienen en **dos formas** que no se pisan:

- **Workflow automático** (`.yml`) — corre solo ante el evento de git (push o PR) como baseline. Deja el resultado en GitHub (comentario en el PR o issue) **y** avisa por Discord.
- **Chat mode** (`.chatmode.md`) — para cuando querés profundizar a mano desde VS Code.

Qué evento dispara cada workflow:

| Workflow | Evento | Salida |
|----------|--------|--------|
| `pr-business-translator.yml` | Al abrir/actualizar un PR | Comentario en el PR (se edita in-place en cada push) + Discord |
| `dod-checker.yml` | PR abierto / listo para revisión | Veredicto DoD como comentario (se edita in-place) + comentario en el ticket de Linear real (o se crea uno si el PR no referencia ninguno) + Discord |
| `context-curator.yml` | `push` a dev/main | Issue si detecta drift de AGENTS.md (actualiza el existente si ya había uno abierto, no duplica) + Discord |
| `repo-onboarding.yml` | Cron mensual (día 1) | PR con `docs/ONBOARDING.md` actualizado, para revisión humana + Discord |
| `dor-readiness.yml` | Cron semanal (lunes) | Digest de tickets del backlog sin AC/estimación/RF → Discord |
| `qa-review.yml` | PR abierta / actualizada / lista para revisión | **Pending review** (borrador visible solo para el QA) con resumen, positivos y hasta 5 findings |
| `pr-review` (nativo) | Cada PR | Comentarios inline de Copilot |
| `sprint-health.yml` | Cron diario | Discord |
| `weekly-status.yml` | Cron semanal | Commit del reporte + Discord |

## Estructura y dónde va cada cosa

```
agentes-copilot/
├── AGENTS.md                                → RAÍZ del repo
├── github/                                  → renombrar a .github/ al instalar
│   ├── copilot-instructions.md              → .github/copilot-instructions.md
│   ├── chatmodes/*.chatmode.md              → .github/chatmodes/
│   ├── skills/pr-review/
│   │   ├── SKILL.md                         → .github/skills/pr-review/SKILL.md
│   │   └── references/qa-criteria.md        → criterios QA-01…QA-10
│   ├── scripts/{llm.sh,linear.sh}           → .github/scripts/
│   └── workflows/*.yml                      → .github/workflows/
│
└── .github/                                 → NO se copia: es la config real de ESTE repo
    ├── workflows/qa-review-reusable.yml      lógica central del QA PR Review Agent
    └── scripts/qa-review/*                   sus scripts (contexto, checks, agente, validador)
```

> **`github/` vs `.github/`.** `github/` es el paquete que se instala en el repo de desarrollo.
> `.github/` es la configuración real de `agents-copilot`: ahí vive la lógica del QA PR Review
> Agent, que **no** se copia a ningún lado. El repo de desarrollo solo recibe un wrapper de 10
> líneas (`qa-review.yml`) que la invoca como *reusable workflow*.

> La carpeta va sin punto (`github/`) por una limitación de la herramienta que la generó. **Al instalar hay que renombrarla a `.github/`.**

## Instalación

Desde la raíz del repo de SportMatch:

```bash
cp ruta/agentes-copilot/AGENTS.md ./AGENTS.md
mkdir -p .github/chatmodes .github/skills/pr-review .github/workflows .github/scripts
cp ruta/agentes-copilot/github/copilot-instructions.md      .github/
cp ruta/agentes-copilot/github/chatmodes/*.chatmode.md      .github/chatmodes/
cp ruta/agentes-copilot/github/skills/pr-review/SKILL.md    .github/skills/pr-review/
cp ruta/agentes-copilot/github/workflows/*.yml              .github/workflows/
cp ruta/agentes-copilot/github/scripts/*.sh                 .github/scripts/
chmod +x .github/scripts/*.sh
git add AGENTS.md .github && git commit -m "chore: agentes de IA (Copilot)"
```

(O simplemente `bash install.sh <ruta-al-repo-destino>`, que hace exactamente esto.)

## Puesta en marcha

**Chat modes (agentes 1, 3, 4, 5.1, 7)** — se usan en **VS Code con Copilot**. En el chat, abrí el selector de modo y elegí, por ejemplo, *"repo-onboarding"* o *"dod-checker"*. Requiere Copilot activo (plan Student).

**Code review automático (agente 2)** — activá **Copilot code review automático** en el repo: *Settings → Code review → Automatic reviews* (o vía ruleset). A partir de ahí revisa cada PR usando `AGENTS.md`, `copilot-instructions.md` y la skill `pr-review`. Ojo: desde el 1/6/2026 el code review **consume minutos de GitHub Actions**.

**Todos los workflows (agentes 1, 3, 4, 5.1, 7, 9, 10)** — corren con un **LLM vía endpoint compatible con OpenAI**, llamado desde `.github/scripts/llm.sh`. Por defecto usan el **free tier de Google Gemini** (gratis, sin tarjeta). Configurá estos secrets en *Settings → Secrets and variables → Actions*:

| Secret | Para qué | Dónde |
|--------|----------|-------|
| `LLM_API_KEY` | Inferencia (genera los textos) | Google AI Studio → Get API key (gratis) |
| `LINEAR_API_KEY` | Leer el ciclo/sprint activo (agentes 9 y 10) **y** comentar/crear tickets desde el DoD checker (agente 7) | Linear → Settings → API → Personal API key |
| `DISCORD_WEBHOOK_QA` | Canal de QA/preview: DoD checker y traductor a negocio | Discord → canal → Integraciones → Webhooks |
| `DISCORD_WEBHOOK_PLANNING` | Canal de planning: curador de contexto | Discord → canal → Integraciones → Webhooks |
| `DISCORD_WEBHOOK_PROGRESS` | Canal de progreso: sprint health y status semanal | Discord → canal → Integraciones → Webhooks |

Las notificaciones van enrutadas por canal, así que son **tres** webhooks distintos. Si querés todo en un solo canal, poné la misma URL en los tres.

`GITHUB_TOKEN` ya viene incluido.

### Integración con Linear (agente 7 — DoD checker)

Con `LINEAR_API_KEY` configurado, `.github/scripts/linear.sh` hace más que leer:

- Al abrirse/actualizarse un PR, el DoD checker extrae el identificador de Linear del **nombre de la rama** (la convención que Linear genera solo al copiar "Branch name" desde un issue, ej. `santos/spm-42-login`), busca ese ticket por API y usa su `description` real como fuente de verdad de los criterios de aceptación — en vez de que el LLM adivine el RF desde el título del PR.
- El veredicto del DoD se postea como **comentario en ese ticket de Linear** (además del comentario en el PR), no solo como texto sugerido.
- Si el PR **no** referencia ningún ticket, es un problema de trazabilidad (AGENTS.md §8.5). Si además configurás la variable `LINEAR_TEAM_KEY` (el prefijo del equipo, ej. `SPM`), el DoD checker **crea** un ticket nuevo señalándolo, en vez de solo mencionarlo en el comentario del PR.
- Sin `LINEAR_API_KEY`, este paso se omite solo (el resto del chequeo de DoD sigue funcionando igual).

Esto depende de que la integración nativa GitHub↔Linear esté conectada en el workspace (Linear → Settings → Integrations → GitHub) para que las ramas/PRs usen esa convención de nombres.

> **Decisión de diseño:** el traductor a negocio (agente 3) también detecta cuando un PR "no mapea a ningún RF", pero **no** crea un ticket de seguimiento en Linear — esa responsabilidad es exclusiva del DoD checker (arriba). Ambos workflows disparan con los mismos eventos de PR; si los dos crearan tickets, un mismo PR huérfano generaría dos tickets duplicados. El traductor se queda solo con el comentario de advertencia en el PR.

### Agente 5.1 — Definition of Ready (`dor-readiness.yml` + chat mode)

Corre semanalmente (lunes) y lee del backlog de Linear los tickets que **todavía no tienen ciclo asignado** (`cycle: null`, estado `backlog`/`unstarted`), evaluando si cada uno tiene AC claros, RF asociado y estimación. Postea un digest en Discord con solo los tickets problemáticos — así el PM los arregla antes de que arranque el sprint, no a mitad de camino. Asume los tipos de estado por defecto de Linear; si el equipo los renombró, ajustar el filtro `state.type` en `dor-readiness.yml`.

> **Cambiar de proveedor de LLM sin tocar los workflows:** el script `llm.sh` es *provider-agnostic*. Para usar Groq, OpenRouter, OpenAI, etc., seteá dos **variables** de repo (*Settings → Secrets and variables → Actions → Variables*): `LLM_BASE_URL` y `LLM_MODEL`, y poné la key de ese proveedor en el secret `LLM_API_KEY`. Los valores por proveedor están documentados en la cabecera de `.github/scripts/llm.sh`.

> **⚠️ GitHub Models fue retirado el 30/07/2026.** Por eso NO usamos `actions/ai-inference`: esa API ya no existe. Este paquete llama directo a un proveedor externo.

> **Sobre el "cron":** el horario lo pone GitHub Actions con la línea `cron:` de cada workflow (en UTC; ya ajustado a hora Argentina en los comentarios).

### Agente 2.1 — QA PR Review Agent (`qa-review.yml` → reusable workflow)

Es el único agente cuya lógica **no** se copia al repo de desarrollo: vive en
`agents-copilot/.github/` y se invoca como *reusable workflow*. El repo destino recibe 10
líneas. Así los criterios se actualizan en un solo lugar y todos los repos los toman al toque.

**Qué produce.** Una **GitHub Review en estado `PENDING`** — un borrador que **solo ve el QA**.
El developer no ve nada hasta que el QA hace Submit. El agente analiza, propone y prepara; no
aprueba, no pide cambios, no mergea y no toca código.

```
PR → contexto + checks determinísticos + Linear
   → Scout (¿qué necesito mirar del repo?) → lectura de esos archivos
   → Reviewer → review.json → validador determinístico → Pending Review
   → el QA edita, borra falsos positivos, agrega lo suyo y hace Submit
```

**Por qué dos pasos de LLM.** El Scout decide qué archivos y búsquedas necesita; nuestro código
los resuelve (solo lectura, sin acceso al filesystem desde el modelo) y recién ahí el Reviewer
razona. Da comportamiento agentic sin mandar el repo entero al modelo y sin depender de tool
calling, LangGraph, MCP ni un servidor.

**Criterios.** `github/skills/pr-review/SKILL.md` (bugs, seguridad, RF) **más**
`references/qa-criteria.md` (QA-01…QA-10: scope y tamaño, comentarios, dependencias, debugging,
evidencia visual, hardcoding, assets, componentización/márgenes, idioma). Máximo **5 findings**
por review, con positivos reales. QA-08 (borrar branches) no lo revisa el agente: se resuelve
con *Automatically delete head branches*.

**Setup (una vez).**

| Qué | Dónde |
|---|---|
| Secret `QA_GITHUB_TOKEN` | Repo de desarrollo. Fine-grained PAT **de la persona que hace QA** — una pending review solo la ve quien la creó. Permisos: en el repo de desarrollo `Contents: Read`, `Pull requests: Read and write`, `Metadata: Read`; en `agents-copilot` `Contents: Read`, `Metadata: Read`. |
| Secret `LLM_API_KEY` | Repo de desarrollo. Key de OpenRouter (o del proveedor que se configure). |
| Secret `LINEAR_API_KEY` | Opcional. Sin ella el agente **omite** QA-05 y no compara scope contra el ticket, en vez de inventar. |
| Acceso a los workflows | `agents-copilot` → Settings → Actions → General → Access: permitir que los repos de la organización usen sus workflows. Sin esto el `uses:` del wrapper falla. |
| Auto-delete de branches | Repo de desarrollo → Settings → General → Pull Requests. Resuelve QA-08. |

**Modelo.** Se pasa como input del workflow (`llm_model`), nunca hardcodeado. Default:
`minimax/minimax-m3:free` vía OpenRouter. Cambiarlo es editar una línea del wrapper.

> ⚠️ La cuenta **free** de OpenRouter tiene un tope de ~50 requests/día en modelos `:free`, y
> cada PR consume 2 (Scout + Reviewer): unas 25 PRs por día. Con USD 10 de crédito el tope sube
> a 1000/día.

**Probarlo sin GitHub Actions.** El pipeline completo corre local contra una PR real:

```bash
.github/scripts/qa-review/run-local.sh SportmatchOrg/sportmatch 18          # dry run
.github/scripts/qa-review/run-local.sh SportmatchOrg/sportmatch 18 --keep   # + guarda prompts
.github/scripts/qa-review/run-local.sh SportmatchOrg/sportmatch 18 --publish
```

Lee la config del LLM de un `.env` en la raíz (ignorado por git). Es la herramienta del pilot:
permite iterar sobre `qa-criteria.md` y ver el efecto en findings reales sin esperar a un
workflow.

**Salvaguardas.** El modelo nunca ve el `QA_GITHUB_TOKEN`. Los checkouts van sin credenciales
persistidas. El validador aborta si el workspace quedó modificado, si el head SHA no es el
esperado, si hay más de 5 findings, si un criterio o severidad no existe, o si el JSON es
inválido — y **degrada a global** cualquier finding inline cuya línea no pertenezca al diff, en
vez de adivinar una posición. Si la PR recibió commits nuevos durante el análisis, no publica:
la corrida de ese push genera el borrador actualizado.

## Notas / ajustes posibles

- **Modelo de los workflows:** por defecto `gemini-2.5-flash` (Gemini free tier). Se cambia con la variable `LLM_MODEL` (ver `llm.sh`), sin tocar los workflows.
- **Endpoint del LLM:** el default es Gemini (`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`). Si Google cambia la ruta o el nombre del modelo, se ajusta con las variables `LLM_BASE_URL`/`LLM_MODEL` o editando `llm.sh`.
- **`copilot-instructions.md`** y **`AGENTS.md`** tienen `TODO`s de stack: completalos apenas se defina (WBS 3.1.1).

## Próximos agentes (fuera de esta tanda)
- Para managers (Lab 4): acceptance criteria (6.4).
- Testing/datos: datos mock (11.1), E2E Playwright (9.2), unit tests (9.1).
