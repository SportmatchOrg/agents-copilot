# Changelog — paquete de agentes

La versión vive en `github/VERSION` y queda registrada en el repo destino como
`.github/agents-version`, así siempre se sabe qué tiene instalado cada repo.

## 2.0.0

Refactor de la infraestructura compartida + los bugs que esa duplicación escondía.
Los prompts y el comportamiento de cada agente no cambian: cambia cómo se ejecutan.

### Bugs corregidos

| # | Dónde | Qué pasaba |
|---|-------|------------|
| 1 | `repo-onboarding.yml` | **El agente nunca abría un PR.** Usaba `git diff --quiet -- docs/ONBOARDING.md`, y `git diff` no ve archivos untracked: como el archivo no existía en el repo, siempre daba "sin cambios". Ahora `git add` + `git diff --cached --quiet`. |
| 2 | `repo-onboarding.yml` | El dedup buscaba `gh pr list --head bot/onboarding-refresh`, que matchea el nombre exacto, pero las ramas llevan la fecha al final. Nunca encontraba el PR anterior. Ahora filtra por prefijo. |
| 3 | `dod-checker.yml`, `pr-business-translator.yml` | **Los dos agentes se pisaban los comentarios.** `gh pr comment --edit-last` edita el último comentario del *usuario actual*, y ambos comentan como `github-actions[bot]`. Ahora cada uno marca el suyo (`.github/scripts/pr-comment.sh`). |
| 4 | `sprint-health.yml`, `dor-readiness.yml`, `weekly-status.yml` | La salida del LLM se interpolaba dentro de código Python (`resp = """${{ ... }}"""`) y de un heredoc de bash. Como el LLM lee diffs de PRs y tickets de Linear, un `"""` o una línea `EOF` en su salida rompía el script — o ejecutaba comandos en el runner. Ahora la respuesta vive en un archivo y nunca se interpola. |
| 5 | los 3 workflows con Linear | `jq -e '.errors, .error'` toma el exit code del **último** output: con `{"errors":[...]}` daba "sin error", así que un token vencido se reportaba como "no hay ciclo activo" y el equipo salía a buscar el problema donde no estaba. Ahora `linear.sh` normaliza a `{status: ok\|empty\|error, message, nodes}`. |
| 6 | los 7 workflows | El volcado a `GITHUB_OUTPUT` usaba el delimitador fijo `EOF_LLM`: una respuesta que lo contuviera rompía el paso. Ya no se usa `GITHUB_OUTPUT` para el texto generado. |
| 7 | 4 workflows | Un webhook de Discord sin configurar tiraba el job (`os.environ[...]` + `urlopen("")`). Ahora `notify.sh` avisa en el log y sigue. |
| 8 | `dod-checker.yml` | El identificador de Linear se extraía con `[a-z]+-[0-9]+`: una rama `fix/2fa-login` matcheaba `fix-2`. Con `LINEAR_TEAM_KEY` seteada ahora busca solo ese prefijo. |

### Cambios estructurales

- **`.github/actions/agent-run`** (composite action): centraliza la llamada al LLM.
  Deja la respuesta en `response.md` y expone `available` / `reason`, así cada
  workflow degrada con un `if:` en vez de repetir un `grep` del sentinel en cada paso.
- **`.github/scripts/notify.sh`**: Discord en un solo lugar (antes, 10 heredocs de
  Python copiados). Trunca al límite de 2000 chars, reintenta una vez, nunca tira el job.
- **`.github/scripts/pr-comment.sh`**: comentario sticky por agente.
- **`.github/scripts/agents-section.sh`**: los prompts inyectan las secciones reales
  de `AGENTS.md` (DoD, tabla de RF) en vez de repetirlas a mano. `AGENTS.md` pasa a
  ser fuente de verdad de verdad: se edita una vez, no siete.
- **`linear.sh`**: nuevos subcomandos `active-issues` y `backlog-unscheduled`; las
  queries GraphQL dejan de estar sueltas en tres workflows.
- Los diffs que se mandan al LLM **filtran lockfiles**: un `package-lock.json` se
  comía la ventana de contexto y el agente no llegaba a ver el código del cambio.
- **`install.sh`**: idempotente. No pisa archivos editados a mano (los deja como
  `.nuevo` y los lista); `--force` y `--dry-run`; escribe `.github/agents-version`.

### Qué revisar al actualizar un repo que ya tenía v1

- Instalá con `bash install.sh <repo> --dry-run` primero para ver qué diverge.
- Los workflows nuevos requieren `.github/actions/` y los scripts nuevos: si copiás
  a mano en vez de usar `install.sh`, no te olvides de esa carpeta.
- Recomendado: setear la variable `LINEAR_TEAM_KEY` (ver README).

## 1.x

Versión inicial: 8 agentes (chat modes + workflows), `llm.sh` provider-agnostic con
reintento en 429/503, integración con Linear desde el DoD checker, dedup del issue
del curador de contexto y agente Definition of Ready.
