# Runbook v2 — QA PR Review Agent

## Arquitectura elegida

Proveedor inicial:

```text
OpenRouter
```

Modelo inicial:

```text
tencent/hy3:free
```

Configuración:

```text
LLM_BASE_URL=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL=tencent/hy3:free
LLM_API_KEY=<OpenRouter API Key>
```

**El modelo nunca se hardcodea en el código.**

Si mañana Hy3 deja de estar disponible:

```text
LLM_MODEL=otro/modelo:free
```

y el resto del sistema no cambia.

---

# Cambio respecto del runbook anterior

No utilizaremos Copilot CLI como runtime del agente.

La arquitectura será:

```text
GitHub PR
    ↓
Reusable Workflow
    ↓
checkout del repo completo
    ↓
checks determinísticos
    ↓
Linear context
    ↓
QA Agent
    │
    ├── Paso 1: Scout
    │      ↓
    │   decide qué archivos necesita inspeccionar
    │
    ├── nuestro código lee esos archivos
    │
    └── Paso 2: Reviewer
           ↓
       review.json
    ↓
validator
    ↓
GitHub Reviews API
    ↓
PENDING REVIEW
    ↓
QA humano
    ↓
Submit review
```

---

# ¿Por qué dos pasos?

No queremos mandar el repositorio entero al modelo.

Tampoco queremos depender de que el modelo soporte tool calling.

Por eso implementaremos un agente muy simple.

## Paso 1 — Scout

Recibe:

```text
PR metadata
diff
repo tree
Linear issue
SKILL.md
QA criteria
deterministic facts
```

Y responde algo como:

```json
{
  "filesToRead": [
    "frontend/components/Button.tsx",
    "frontend/components/CreateButton.tsx",
    "frontend/lib/api.ts"
  ],
  "searches": [
    "Button",
    "NEXT_PUBLIC_API_URL"
  ]
}
```

Nuestro código lee esos archivos y ejecuta las búsquedas.

El modelo **no tiene acceso al filesystem directamente**.

---



# Paso 2 — Reviewer

Ahora recibe:

```text
PR
+
diff
+
criterios
+
Linear
+
checks determinísticos
+
archivos solicitados
+
resultados de búsquedas
```

y genera:

```text
review.json
```

Ejemplo:

```json
{
  "version": 1,
  "summary": "La PR agrega el flujo de creación de partidos.",
  "positives": [
    "La lógica de negocio quedó correctamente separada del controller."
  ],
  "findings": [
    {
      "criterion": "QA-09",
      "severity": "MINOR",
      "kind": "inline",
      "path": "frontend/components/CreateButton.tsx",
      "line": 18,
      "message": "Esta variante ya está cubierta por el componente Button existente."
    }
  ]
}
```

---



# Ventaja de esta arquitectura

Tenemos comportamiento agentic:

```text
observar
↓
decidir qué investigar
↓
obtener contexto
↓
razonar
↓
producir findings
```

pero sin:

```text
LangGraph
CrewAI
MCP
tool calling obligatorio
vector database
Copilot CLI
servidor
```

Sigue siendo KISS.

---



# Checklist general

- [ ] **Fase 0 — Verificar OpenRouter + Hy3**
- [ ] **Fase 1 — Crear** `qa-criteria.md`
- [ ] **Fase 2 — Implementar checks determinísticos**
- [ ] **Fase 3 — Recolectar contexto de PR**
- [ ] **Fase 4 — Integrar Linear**
- [ ] **Fase 5 — Implementar Scout**
- [ ] **Fase 6 — Implementar Reviewer**
- [ ] **Fase 7 — Validar** `review.json`
- [ ] **Fase 8 — Probar Pending Review**
- [ ] **Fase 9 — Manejar lifecycle de Pending Reviews**
- [ ] **Fase 10 — Crear reusable workflow**
- [ ] **Fase 11 — Agregar wrapper al repo de desarrollo**
- [ ] **Fase 12 — Test end-to-end**
- [ ] **Fase 13 — Pilot con PRs reales**
- [ ] **Fase 14 — Ajustar falsos positivos**

---



# Fase 0 — Verificar OpenRouter



## Objetivo

Antes de desarrollar el agente, comprobar que podemos llamar correctamente al modelo elegido desde la infraestructura que ya existe.

Actualmente `agents-copilot` ya tiene:

```text
github/scripts/llm.sh
```

y ese script ya permite configurar:

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

Por lo tanto, reutilizaremos esa abstracción inicialmente.

## Configuración

```text
LLM_BASE_URL=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL=tencent/hy3:free
```

Secret:

```text
LLM_API_KEY=<OpenRouter key>
```



## Checklist

- [ ] Crear una API key de OpenRouter.
- [ ] Configurar `LLM_API_KEY`.
- [ ] Configurar `LLM_BASE_URL`.
- [ ] Configurar `LLM_MODEL=tencent/hy3:free`.
- [ ] Crear un prompt mínimo.
- [ ] Ejecutarlo usando `llm.sh`.
- [ ] Verificar respuesta HTTP 200.
- [ ] Verificar que podemos pedir JSON.
- [ ] Verificar que el modelo responde correctamente en español.
- [ ] Verificar límites/rate limits del endpoint gratuito.



## Smoke test

Prompt:

```text
Respondé únicamente JSON válido.

{
  "status": "ok",
  "model": "hy3"
}
```

Esperamos:

```json
{
  "status": "ok",
  "model": "hy3"
}
```



## Definition of Done

No avanzamos hasta poder ejecutar:

```text
agents-copilot
      ↓
llm.sh
      ↓
OpenRouter
      ↓
Hy3
      ↓
JSON válido
```

---



# Fase 1 — Criterios QA

Crear:

```text
github/skills/pr-review/references/qa-criteria.md
```

Documentar:

- [ ] QA-01 Scope / máximo 1000 líneas.
- [ ] QA-02 Comentarios innecesarios.
- [ ] QA-03 Dependencias innecesarias.
- [ ] QA-04 Debugging.
- [ ] QA-05 Screenshots/videos.
- [ ] QA-06 Hardcoding.
- [ ] QA-07 Assets.
- [ ] QA-08 Branch cleanup.
- [ ] QA-09 Componentización / no margins.
- [ ] QA-10 Idioma.

Cada criterio debe contener:

```text
Rule
Evidence
Typical severity
What to flag
What NOT to flag
Examples
```

QA-08 se documenta, pero queda marcado como:

```text
NOT REVIEWED BY AGENT
```

porque se resolverá con auto-delete branches de GitHub.

---



# Fase 2 — Checks determinísticos

Crear:

```text
.github/scripts/qa-review/deterministic-checks.py
```

Debe detectar:

- [ ] líneas revisables;
- [ ] PR > 1000 líneas;
- [ ] `console.log`;
- [ ] `debugger`;
- [ ] nuevas dependencias;
- [ ] margins;
- [ ] assets grandes;
- [ ] posible cambio visual.

Output:

```text
deterministic-facts.json
```

Ejemplo:

```json
{
  "reviewableChangedLines": 412,
  "exceedsPrSizeLimit": false,
  "newDependencies": ["lodash"],
  "debugStatements": [],
  "marginUsages": [],
  "largeAssets": [],
  "visualChangeLikely": true
}
```

---



# Fase 3 — Context collector

Crear:

```text
.github/scripts/qa-review/collect-context.sh
```

Generar:

```text
qa-context/
├── meta.json
├── diff.patch
├── files.json
├── repo-tree.txt
└── deterministic-facts.json
```

Metadata:

```text
PR number
title
body
base
branch
head SHA
changed files
```

---



# Fase 4 — Linear

Reutilizar:

```text
github/scripts/linear.sh
```

Extraer el identificador:

```text
santos/spm-42-login
          ↓
        SPM-42
```

Obtener:

```text
title
description
acceptance criteria
status
```

Para QA-05 extender luego con:

```text
comments
attachments
```

Output:

```text
qa-context/linear-issue.json
```

---



# Fase 5 — Scout Agent

Crear:

```text
.github/scripts/qa-review/run-scout.py
```



## Input

```text
SKILL.md
qa-criteria.md
meta.json
diff.patch
repo-tree.txt
deterministic-facts.json
linear-issue.json
```



## Responsabilidad

El Scout **no hace la review**.

Solo responde:

> ¿Qué necesito inspeccionar para revisar bien esta PR?



## Output

```text
scout.json
```

Schema:

```json
{
  "filesToRead": [],
  "searches": []
}
```



## Límites

```text
máximo 12 archivos
máximo 10 búsquedas
```

Esto protege contexto y costo.

---



# Fase 6 — Context Resolver

Crear:

```text
.github/scripts/qa-review/resolve-context.py
```

Lee `scout.json`.

Por cada:

```text
filesToRead
```

lee el archivo correspondiente.

Por cada:

```text
searches
```

ejecuta:

```text
rg
```

sobre el repo.

Output:

```text
qa-context/
└── agent-context/
    ├── files/
    └── searches.json
```



## Seguridad

El modelo solamente puede solicitar lecturas.

No existen herramientas:

```text
write
edit
commit
push
delete
```

---



# Fase 7 — Reviewer Agent

Crear:

```text
.github/scripts/qa-review/run-reviewer.py
```

Recibe todo el contexto.

## Debe aplicar

```text
pr-review/SKILL.md
+
qa-criteria.md
+
Linear
+
diff
+
deterministic facts
+
selected repo context
```



## Reglas

- [ ] solamente cambios de la PR;
- [ ] máximo 5 findings;
- [ ] incluir positivos;
- [ ] buscar evidencia;
- [ ] no generar problemas para llenar cupo;
- [ ] mensajes breves;
- [ ] español;
- [ ] no sugerir abstracciones sin evidencia;
- [ ] no considerar todo literal hardcoding;
- [ ] no considerar toda dependencia mala.

Output:

```text
review.json
```

---



# Fase 8 — Validator

Crear:

```text
.github/scripts/qa-review/validate-review.py
```

Validar:

- [ ] JSON válido;
- [ ] máximo 5 findings;
- [ ] criterio válido;
- [ ] severidad válida;
- [ ] archivo cambiado;
- [ ] línea válida;
- [ ] línea pertenece al diff;
- [ ] no duplicados;
- [ ] head SHA todavía vigente.

El modelo nunca habla directamente con GitHub.

---



# Fase 9 — Pending Review

Crear:

```text
.github/scripts/qa-review/create-pending-review.py
```

Usar:

```text
QA_GITHUB_TOKEN
```

El script crea:

```text
Pull Request Review
state = PENDING
```

con:

```text
body
+
inline comments
```

El agente no recibe `QA_GITHUB_TOKEN`.

---



# Fase 10 — Lifecycle

Implementar:

```text
sin pending automática
→ crear

pending automática vieja
→ reemplazar

pending manual QA
→ NO TOCAR

review submitida + nuevo push
→ crear nueva pending
```

Marker:

```html
<!-- sportmatch-qa-agent -->
```

---



# Fase 11 — Reusable Workflow

Crear:

```text
.github/workflows/qa-review-reusable.yml
```

Pipeline:

```text
checkout
   ↓
collect-context
   ↓
deterministic-checks
   ↓
Linear
   ↓
Scout (OpenRouter)
   ↓
resolve-context
   ↓
Reviewer (OpenRouter)
   ↓
validate
   ↓
create pending review
```

---



# Fase 12 — Wrapper

Pedir a los developers agregar:

```text
.github/workflows/qa-review.yml
```

Con aproximadamente:

```yaml
name: QA Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [dev, main]

jobs:
  qa-review:
    if: github.event.pull_request.draft == false
    uses: SportmatchOrg/agents-copilot/.github/workflows/qa-review-reusable.yml@main
    secrets: inherit
```

Esta debería ser prácticamente toda la integración necesaria en el repo de desarrollo.

---



# Fase 13 — End-to-end

Probar PR preparada con:

```text
console.log
margin
texto inglés
componente reutilizable correcto
< 1000 líneas
```

Esperamos aproximadamente:

```text
QA-04
QA-09
QA-10
+
positivo por componente reutilizado
```

---



# Fase 14 — Pilot

Probar:

```text
3–5 PRs reales
```

Por cada finding clasificar:

```text
KEEP
EDIT
DELETE
```

El KPI más importante inicialmente:

```text
accepted findings / generated findings
```

No necesitamos 100 findings.

Necesitamos pocos findings que QA realmente quiera enviar.

---



# Fase 15 — Ajustar

Los patrones aprendidos se agregan a:

```text
qa-criteria.md
```

Ejemplo:

```text
No marcar URLs de fixtures de testing como hardcoding.

No sugerir una nueva abstracción salvo que exista una duplicación
real o un componente equivalente en el repositorio.

Si ya existen MAJOR findings, evitar NITs irrelevantes.
```

No agregamos todavía:

```text
vector DB
memory service
training
fine tuning
```

---



# Arquitectura final

```text
                PR
                 │
                 ▼
         reusable workflow
                 │
        ┌────────┴────────┐
        ▼                 ▼
 deterministic         Linear
    checks
        └────────┬────────┘
                 ▼
           repo tree + diff
                 │
                 ▼
          OPENROUTER HY3
              SCOUT
                 │
          filesToRead
          searches
                 │
                 ▼
          context resolver
          (read only)
                 │
                 ▼
          OPENROUTER HY3
             REVIEWER
                 │
                 ▼
             review.json
                 │
                 ▼
              validator
                 │
                 ▼
        GitHub Reviews API
                 │
                 ▼
          PENDING REVIEW
                 │
                 ▼
                QA
                 │
      edit / delete / add
                 │
                 ▼
            Submit review
```

---



# Primer paso



## Fase 0 — Smoke test de OpenRouter

**Este es el primer paso que hacemos juntos.**

Todavía no tocamos:

```text
workflow
GitHub token
pending reviews
Linear
repo de developers
```

Primero verificamos solamente:

```text
agents-copilot
      ↓
OpenRouter
      ↓
tencent/hy3:free
      ↓
respuesta JSON
```

Cuando eso funcione, marcamos:

```text
[x] Fase 0 — OpenRouter funcionando
```

y pasamos inmediatamente a:

```text
Fase 1 — qa-criteria.md
```

A partir de ahí empezamos a construir el reviewer real.