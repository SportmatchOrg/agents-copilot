# Guía de testing — Agentes de IA SportMatch (fase sandbox)

Objetivo: validar **en un repo descartable** que los 7 agentes funcionan (workflows + code review + chat modes) antes de instalarlos en el repo de capacitación. Cuando todo esto pase, recién ahí se llevan a capacitación.

> **Cómo usar este documento en Claude Code:** abrilo en el repo y pedile a Claude Code que vaya ejecutando los pasos. La mayoría son comandos `gh`/`git` que Claude Code puede correr. Los pasos marcados 🖐️ **MANUAL** requieren que los hagas vos en una UI (Discord, Linear, GitHub web, VS Code) — Claude Code no puede.

---

## Prerrequisitos

- [ ] `gh` (GitHub CLI) instalado y logueado: `gh auth status`
- [ ] Cuenta con **GitHub Copilot activo** (plan Student sirve) — para chat modes y code review
- [ ] **VS Code** con la extensión de GitHub Copilot — para probar los chat modes
- [ ] Una **API key de Google Gemini** (gratis, sin tarjeta) desde Google AI Studio (ver Paso 0.3)
- [ ] Un servidor de **Discord** donde puedas crear un webhook de test
- [ ] Una cuenta de **Linear** donde puedas crear un team de test y una API key

---

## Paso 0 — Credenciales de test (no uses las reales)

### 0.1 🖐️ MANUAL — Webhook de Discord de test
1. En Discord, creá (o elegí) un canal `#sandbox-agentes`.
2. Editar canal → Integraciones → Webhooks → Nuevo webhook → Copiar URL.
3. Guardá la URL, la vas a cargar como secret.

### 0.2 🖐️ MANUAL — Linear de test
1. En Linear creá un team de test (ej. `SANDBOX`) con un ciclo/sprint activo y 2-3 issues de mentira.
2. Settings → API → Personal API keys → crear una. Guardala.

### 0.3 🖐️ MANUAL — API key de Gemini (free tier)
1. Entrá a **Google AI Studio** → *Get API key* → creá una key (gratis, sin tarjeta).
2. Guardala; la cargás como secret `LLM_API_KEY`.
3. (Opcional) Probala rápido:
```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions" \
  -H "Authorization: Bearer TU_KEY" -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"decí OK"}]}' | head
```
Si responde un JSON con `choices`, funciona.

> **Nota:** NO usamos GitHub Models (fue retirado el 30/07/2026). Los workflows llaman a Gemini vía `.github/scripts/llm.sh`. Para cambiar a Groq/OpenRouter/OpenAI, seteá las variables `LLM_BASE_URL` y `LLM_MODEL` (ver cabecera de `llm.sh`).

---

## Paso 1 — Crear el sandbox

```bash
# Repo privado descartable, se clona local
gh repo create sportmatch-sandbox --private --clone
cd sportmatch-sandbox

# Rama dev (los workflows disparan en dev/main)
git branch -M main
git commit --allow-empty -m "chore: init sandbox"
git push -u origin main
git checkout -b dev && git push -u origin dev
```

---

## Paso 2 — Instalar el paquete de agentes

Desde la carpeta `agentes-copilot/` de SportMatch, copiá al sandbox (ajustá `RUTA`):

```bash
RUTA="RUTA/A/agentes-copilot"
cp "$RUTA/AGENTS.md" ./AGENTS.md
mkdir -p .github/chatmodes .github/skills/pr-review .github/workflows
cp "$RUTA/github/copilot-instructions.md"   .github/
cp "$RUTA/github/chatmodes/"*.chatmode.md    .github/chatmodes/
cp "$RUTA/github/skills/pr-review/SKILL.md"  .github/skills/pr-review/
cp "$RUTA/github/workflows/"*.yml            .github/workflows/

git add AGENTS.md .github
git commit -m "chore: instalar agentes de IA (Copilot)"
git push
```

> Recordá: en el paquete la carpeta se llama `github/` (sin punto). Al copiar, el destino **sí** es `.github/` (con punto), como arriba.

---

## Paso 3 — Cargar los secrets en el repo

```bash
gh secret set LLM_API_KEY               --body "PEGAR_GEMINI_API_KEY"
# Son 3 webhooks distintos (uno por canal); para el sandbox podés usar el mismo webhook de test en los tres.
gh secret set DISCORD_WEBHOOK_QA        --body "PEGAR_URL_DEL_WEBHOOK"
gh secret set DISCORD_WEBHOOK_PLANNING  --body "PEGAR_URL_DEL_WEBHOOK"
gh secret set DISCORD_WEBHOOK_PROGRESS  --body "PEGAR_URL_DEL_WEBHOOK"
gh secret set LINEAR_API_KEY            --body "PEGAR_LINEAR_API_KEY"
# GITHUB_TOKEN ya viene incluido, no se carga.
gh secret list   # verificar que aparezcan los cinco

# (Opcional) para usar otro proveedor en vez de Gemini, seteá variables:
# gh variable set LLM_BASE_URL --body "https://api.groq.com/openai/v1/chat/completions"
# gh variable set LLM_MODEL    --body "llama-3.3-70b-versatile"
```

---

## Paso 4 — Seed mínimo (para que los agentes tengan algo que mirar)

```bash
# Estructura y archivos de mentira que simulan una feature de SportMatch
mkdir -p src
cat > package.json <<'EOF'
{ "name": "sportmatch-sandbox", "version": "0.0.1",
  "scripts": { "test": "echo ok", "lint": "echo ok", "build": "echo ok" } }
EOF
cat > src/partido.js <<'EOF'
// RF-03 Creación de partido (stub para testing de agentes)
function crearPartido(deporte, fecha, cupo) {
  return { deporte, fecha, cupo };
}
module.exports = { crearPartido };
EOF
git add . && git commit -m "feat(RF-03): stub de creación de partido" && git push
```

---

## Checklist de pruebas

Marcá cada uno cuando lo veas funcionar. La columna "Cómo dispararlo" incluye el comando; "Qué deberías ver" es el criterio de éxito.

### ✅ Test 1 — Curador de contexto (`context-curator.yml`, on push)
- **Dispara:** push a `dev`/`main`.
- **Cómo dispararlo:** ya se disparó con el push del Paso 4. O manual:
  ```bash
  gh workflow run context-curator.yml --ref dev
  gh run watch $(gh run list --workflow=context-curator.yml -L1 --json databaseId -q '.[0].databaseId')
  ```
- **Qué deberías ver:** el run termina en verde. Como el `AGENTS.md` tiene `TODO`s de stack y ya hay un `package.json`, es probable que detecte drift y **abra un issue** con la propuesta + mensaje en Discord. Si dice "SIN CAMBIOS", también es válido (no abre nada).
- **Verificar:** `gh issue list` y el canal de Discord.
- [ ] Pasó

### ✅ Test 2 — Traductor a negocio (`pr-business-translator.yml`, on PR)
- **Dispara:** abrir/actualizar un PR hacia `dev`.
- **Cómo dispararlo:**
  ```bash
  git checkout -b feature/RF-05-solicitudes
  cat > src/solicitud.js <<'EOF'
  // RF-05 Sistema de solicitudes
  function solicitarUnirse(partidoId, usuarioId) { return { partidoId, usuarioId, estado: "pendiente" }; }
  module.exports = { solicitarUnirse };
  EOF
  git add . && git commit -m "feat(RF-05): solicitar unirse a partido" && git push -u origin feature/RF-05-solicitudes
  gh pr create --base dev --title "RF-05: sistema de solicitudes" --body "Implementa solicitar unirse."
  ```
- **Qué deberías ver:** en ~1-2 min aparece un **comentario en el PR** titulado "Resumen para negocio (IA)" con las 4 secciones (qué hace, historia RF-05, riesgo, qué probar) + aviso en Discord.
- **Verificar:** `gh pr view --comments` y Discord.
- [ ] Pasó

### ✅ Test 3 — DoD checker (`dod-checker.yml`, on PR)
- **Dispara:** el mismo PR del Test 2 (mismo evento).
- **Qué deberías ver:** otro **comentario en el PR** titulado "Definition of Done — chequeo automático" con la tabla de criterios. "PR mergeada" y "deploy a staging" deben salir ⏳ **PENDIENTE** (correcto: el PR sigue abierto); el resto evaluado.
- **Verificar:** `gh pr view --comments` y Discord.
- [ ] Pasó

### ✅ Test 4 — Code review nativo de Copilot (agente 2)
- 🖐️ **MANUAL.** En el mismo PR: pedí review de Copilot (o activá el automático en Settings → Code review → Automatic reviews).
- **Qué deberías ver:** comentarios inline de Copilot sobre el diff, teniendo en cuenta `AGENTS.md`, `copilot-instructions.md` y la skill `pr-review` (menciona severidades / RF).
- **Nota:** el review automático y las agent skills pueden requerir un plan superior a Copilot Student — si no aparece, probá el review manual.
- [ ] Pasó (o documentado que el tier no lo permite)

### ✅ Test 5 — Sprint Health (`sprint-health.yml`, cron → manual)
- **Cómo dispararlo** (sin esperar al cron):
  ```bash
  gh workflow run sprint-health.yml --ref dev
  gh run watch $(gh run list --workflow=sprint-health.yml -L1 --json databaseId -q '.[0].databaseId')
  ```
- **Qué deberías ver:** el run lee Linear (team de test) + PRs, y **postea el semáforo en Discord**. Si Linear no responde, el mensaje lo dice (no rompe).
- **Verificar:** Discord + logs del run (`gh run view --log`).
- [ ] Pasó

### ✅ Test 6 — Status Reporter (`weekly-status.yml`, cron → manual)
- **Cómo dispararlo:**
  ```bash
  gh workflow run weekly-status.yml --ref dev
  gh run watch $(gh run list --workflow=weekly-status.yml -L1 --json databaseId -q '.[0].databaseId')
  ```
- **Qué deberías ver:** genera el reporte, lo **commitea** en `docs/status-reports/AAAA-MM-DD.md` y postea resumen en Discord.
- **Verificar:** `git pull && ls docs/status-reports/` + Discord.
- [ ] Pasó

### ✅ Test 7 — Chat modes en VS Code (agentes 1, 3, 4, 7 en modo manual)
- 🖐️ **MANUAL.** Abrí el sandbox en VS Code (con Copilot). En Copilot Chat, abrí el selector de modo: deberían aparecer `context-curator`, `repo-onboarding`, `dod-checker`, `pr-business-translator`.
- **Probá `repo-onboarding`:** pedile "generá el README". Debería producir un README con setup real basado en el `package.json`.
- **Probá `dod-checker`:** pedile que evalúe el PR de RF-05.
- **Qué deberías ver:** cada modo responde en su rol, citando RF y la DoD de `AGENTS.md`.
- [ ] Pasó

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| Workflow falla en el step de IA | `LLM_API_KEY` inválida, o el output dice "ERROR LLM: ..." | Revisá el secret; el mensaje de error crudo del proveedor aparece en los logs del run (`gh run view --log`) |
| "ERROR LLM: model not found" | Nombre de modelo desactualizado | Cambiá la variable `LLM_MODEL` (ej. `gemini-2.5-flash` → el modelo Gemini vigente) |
| Rate limit del proveedor | Muchas corridas seguidas en el free tier | Esperá unos minutos; el volumen real (2 devs) no lo alcanza. O cambiá de proveedor con `LLM_BASE_URL`/`LLM_MODEL` |
| "Resource not accessible" al comentar/crear issue | Faltan permisos en el workflow | Confirmá el bloque `permissions:` (pull-requests/issues: write) |
| No llega nada a Discord | Webhook mal cargado | Son 3 secrets distintos (`DISCORD_WEBHOOK_QA`, `_PLANNING`, `_PROGRESS`) enrutados por canal — confirmá cuál usa el workflow que estás probando y reejecutá `gh secret set` sobre ese; probá el webhook con un `curl` manual |
| Sprint Health dice "linear no disponible" | API key inválida o query sin datos | Verificá `LINEAR_API_KEY` y que el team de test tenga un ciclo activo con issues |
| Los chat modes no aparecen en VS Code | Carpeta mal ubicada | Deben estar en `.github/chatmodes/` (con punto) y el repo abierto en la raíz |
| Code review de Copilot no comenta | Tier de Copilot / no habilitado | Probá review manual; documentá si Student no lo soporta |

---

## Criterio de "listo para pasar a capacitación"

Pasás a instalarlos en el repo de capacitación cuando:
- [ ] Tests 1, 2, 3, 5, 6 en verde (los workflows automáticos)
- [ ] Test 7 (chat modes) funcionando en VS Code
- [ ] Test 4 (code review) funcionando **o** documentado que el tier no lo permite
- [ ] Discord y Linear de test respondiendo correctamente
- [ ] Ningún secret real filtrado en el sandbox

Cuando esté todo, borrá el sandbox (`gh repo delete sportmatch-sandbox`) o dejalo como referencia, y replicá la instalación (Pasos 2-3) en el repo de capacitación con los canales/keys reales.
