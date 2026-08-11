# Agentes de IA — SportMatch (versión GitHub Copilot)

Paquete de agentes para el repo de desarrollo, en formato **nativo de GitHub Copilot** (gratis con el plan **Copilot Student** del GitHub Student Developer Pack). Basado en el *Catálogo de Agentes de IA — Laboratorio IV*.

> **"Lab4 no codifica".** Los agentes revisan, verifican y reportan; no mergean código solos. Cuando detectan algo, dejan un comentario/sugerencia en el PR o proponen una tarjeta para Linear. La decisión final es humana.

## Cómo se mapean los 7 agentes a Copilot

Copilot no usa "subagentes" como Claude; usa **chat modes**, **custom instructions**, **agent skills** y **workflows**. Cada agente se implementa con la pieza nativa que corresponde:

| # | Agente | Pieza de Copilot | Cómo se usa |
|---|--------|------------------|-------------|
| 1 | Curador de contexto | Chat mode **+ workflow** | Manual en Chat, **y** automático en `push` a dev/main (abre issue si hay drift) |
| 2 | Code reviewer | **Copilot code review** + agent skill + `copilot-instructions.md` | Automático en cada PR |
| 3 | Traductor a negocio | Chat mode **+ workflow** | Manual en Chat, **y** automático al abrir un PR (comenta el PR) |
| 4 | Onboarding de repo | Chat mode | A demanda (no tiene evento de git natural) |
| 7 | DoD checker | Chat mode **+ workflow** | Manual en Chat, **y** automático en el PR (deja el veredicto DoD) |
| 9 | Sprint Health | Workflow (cron + LLM) | Automático, diario → Discord |
| 10 | Status Reporter | Workflow (cron + LLM) | Automático, semanal → Discord |

Además: **`AGENTS.md`** en la raíz — Copilot code review **ya lo lee automáticamente** como contexto. Es el archivo más importante; completalo primero (tiene `TODO`s para el stack).

### Modo dual: chat mode vs. workflow

Los agentes 1, 3 y 7 vienen en **dos formas** que no se pisan:

- **Workflow automático** (`.yml`) — corre solo ante el evento de git (push o PR) como baseline. Deja el resultado en GitHub (comentario en el PR o issue) **y** avisa por Discord.
- **Chat mode** (`.chatmode.md`) — para cuando querés profundizar a mano desde VS Code.

El **Onboarding** queda solo como chat mode: no hay un push o merge que naturalmente lo dispare (se corre cuando entra alguien o el README envejece). Si igual lo quieren programado, se puede agregar un workflow con `cron` semanal.

Qué evento dispara cada workflow:

| Workflow | Evento | Salida |
|----------|--------|--------|
| `pr-business-translator.yml` | Al abrir/actualizar un PR | Comentario en el PR + Discord |
| `dod-checker.yml` | PR abierto / listo para revisión | Veredicto DoD como comentario + Discord |
| `context-curator.yml` | `push` a dev/main | Issue si detecta drift de AGENTS.md + Discord |
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
│   ├── skills/pr-review/SKILL.md            → .github/skills/pr-review/SKILL.md
│   └── workflows/*.yml                      → .github/workflows/
```

> La carpeta va sin punto (`github/`) por una limitación de la herramienta que la generó. **Al instalar hay que renombrarla a `.github/`.**

## Instalación

Desde la raíz del repo de SportMatch:

```bash
cp ruta/agentes-copilot/AGENTS.md ./AGENTS.md
mkdir -p .github/chatmodes .github/skills/pr-review .github/workflows
cp ruta/agentes-copilot/github/copilot-instructions.md      .github/
cp ruta/agentes-copilot/github/chatmodes/*.chatmode.md      .github/chatmodes/
cp ruta/agentes-copilot/github/skills/pr-review/SKILL.md    .github/skills/pr-review/
cp ruta/agentes-copilot/github/workflows/*.yml              .github/workflows/
git add AGENTS.md .github && git commit -m "chore: agentes de IA (Copilot)"
```

## Puesta en marcha

**Chat modes (agentes 1, 3, 4, 7)** — se usan en **VS Code con Copilot**. En el chat, abrí el selector de modo y elegí, por ejemplo, *"repo-onboarding"* o *"dod-checker"*. Requiere Copilot activo (plan Student).

**Code review automático (agente 2)** — activá **Copilot code review automático** en el repo: *Settings → Code review → Automatic reviews* (o vía ruleset). A partir de ahí revisa cada PR usando `AGENTS.md`, `copilot-instructions.md` y la skill `pr-review`. Ojo: desde el 1/6/2026 el code review **consume minutos de GitHub Actions**.

**Todos los workflows (agentes 1, 3, 7, 9, 10)** — corren con un **LLM vía endpoint compatible con OpenAI**, llamado desde `.github/scripts/llm.sh`. Por defecto usan el **free tier de Google Gemini** (gratis, sin tarjeta). Configurá estos secrets en *Settings → Secrets and variables → Actions*:

| Secret | Para qué | Dónde |
|--------|----------|-------|
| `LLM_API_KEY` | Inferencia (genera los textos) | Google AI Studio → Get API key (gratis) |
| `LINEAR_API_KEY` | Leer el ciclo/sprint activo (agentes 9 y 10) | Linear → Settings → API → Personal API key |
| `DISCORD_WEBHOOK_QA` | Canal de QA/preview: DoD checker y traductor a negocio | Discord → canal → Integraciones → Webhooks |
| `DISCORD_WEBHOOK_PLANNING` | Canal de planning: curador de contexto | Discord → canal → Integraciones → Webhooks |
| `DISCORD_WEBHOOK_PROGRESS` | Canal de progreso: sprint health y status semanal | Discord → canal → Integraciones → Webhooks |

Las notificaciones van enrutadas por canal, así que son **tres** webhooks distintos. Si querés todo en un solo canal, poné la misma URL en los tres.

`GITHUB_TOKEN` ya viene incluido.

> **Cambiar de proveedor de LLM sin tocar los workflows:** el script `llm.sh` es *provider-agnostic*. Para usar Groq, OpenRouter, OpenAI, etc., seteá dos **variables** de repo (*Settings → Secrets and variables → Actions → Variables*): `LLM_BASE_URL` y `LLM_MODEL`, y poné la key de ese proveedor en el secret `LLM_API_KEY`. Los valores por proveedor están documentados en la cabecera de `.github/scripts/llm.sh`.

> **⚠️ GitHub Models fue retirado el 30/07/2026.** Por eso NO usamos `actions/ai-inference`: esa API ya no existe. Este paquete llama directo a un proveedor externo.

> **Sobre el "cron":** el horario lo pone GitHub Actions con la línea `cron:` de cada workflow (en UTC; ya ajustado a hora Argentina en los comentarios).

## Notas / ajustes posibles

- **Modelo de los workflows:** por defecto `gemini-2.5-flash` (Gemini free tier). Se cambia con la variable `LLM_MODEL` (ver `llm.sh`), sin tocar los workflows.
- **Endpoint del LLM:** el default es Gemini (`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`). Si Google cambia la ruta o el nombre del modelo, se ajusta con las variables `LLM_BASE_URL`/`LLM_MODEL` o editando `llm.sh`.
- **`copilot-instructions.md`** y **`AGENTS.md`** tienen `TODO`s de stack: completalos apenas se defina (WBS 3.1.1).

## Próximos agentes (fuera de esta tanda)
- Para managers (Lab 4): acceptance criteria (6.4), Definition of Ready (5.1).
- Testing/datos: datos mock (11.1), E2E Playwright (9.2), unit tests (9.1).
