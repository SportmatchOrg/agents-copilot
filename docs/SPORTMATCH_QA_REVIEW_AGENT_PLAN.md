# SportMatch — Plan de implementación del QA PR Review Agent

## 1. Objetivo

Construir un agente de QA que se ejecute automáticamente cada vez que se abre o actualiza una Pull Request de SportMatch, revise el cambio usando el contexto completo del repositorio y los criterios de QA del equipo, y prepare una **GitHub Review en estado `PENDING`**.

La review no se publica automáticamente.

El agente actúa como asistente del QA:

1. analiza la PR;
2. prepara el resumen y los comentarios inline;
3. crea la review pendiente usando la identidad del QA;
4. el QA revisa, edita o elimina comentarios;
5. el QA decide manualmente si hace **Approve**, **Comment** o **Request changes**;
6. el QA hace **Submit review**.

La decisión final siempre es humana.

---

## 2. Principios de diseño

### KISS

La solución debe minimizar infraestructura y piezas operativas.

**No vamos a usar en el MVP:**

- backend dedicado;
- Railway;
- webhooks propios;
- GitHub App propia;
- base de datos;
- colas;
- LangGraph / CrewAI / frameworks multiagente;
- polling externo;
- Organization Rulesets que requieran Enterprise;
- `/qa approve` y `/qa reject`;
- una UI administrativa propia.

### Human in the loop

El agente:

- analiza;
- propone;
- prepara la review.

El agente **no**:

- submitea la review;
- aprueba la PR;
- solicita cambios oficialmente;
- mergea;
- modifica código;
- crea commits;
- pushea cambios.

### Contexto antes que prompts gigantes

El reviewer debe trabajar con:

- el checkout completo del repositorio;
- el diff de la PR;
- metadata de la PR;
- el issue de Linear asociado;
- el contexto de SportMatch;
- la skill de PR review existente;
- los criterios QA adicionales;
- checks determinísticos.

La intención es evitar un sistema que simplemente mande `diff + prompt` a un LLM sin contexto del proyecto.

---

# 3. Decisiones tomadas

## 3.1. Repositorio central

Se utilizará:

`SportmatchOrg/agents-copilot`

No se creará un repositorio nuevo.

`agents-copilot` ya centraliza:

- `AGENTS.md`;
- Copilot instructions;
- skills;
- workflows;
- scripts;
- integración con Linear;
- comportamiento de otros agentes del proyecto.

El QA reviewer es otra automatización del mismo ecosistema.

---

## 3.2. No copiar el agente completo al repo de desarrollo

Actualmente `agents-copilot` funciona principalmente como un paquete instalable:

```text
agents-copilot/
├── AGENTS.md
├── github/
│   ├── copilot-instructions.md
│   ├── skills/
│   ├── workflows/
│   └── scripts/
└── install.sh
```

`install.sh` copia:

```text
AGENTS.md           -> repo destino
github/             -> .github/
```

Ese modelo se mantiene para los agentes existentes que lo necesiten.

El nuevo QA reviewer funcionará de manera distinta:

- la lógica seguirá centralizada en `agents-copilot`;
- el repo objetivo tendrá solamente un wrapper mínimo de GitHub Actions.

---

## 3.3. Reusable Workflow

Como no contamos con GitHub Enterprise, descartamos Organization Rulesets para ejecutar un workflow central automáticamente en otros repos.

La solución elegida es un **Reusable Workflow**.

El repo de desarrollo tendrá aproximadamente:

```yaml
name: QA Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [dev, main]

jobs:
  qa-review:
    uses: SportmatchOrg/agents-copilot/.github/workflows/qa-review-reusable.yml@main
    secrets: inherit
```

Toda la lógica real vive en:

```text
SportmatchOrg/agents-copilot
└── .github/
    └── workflows/
        └── qa-review-reusable.yml
```

### Ventajas

- el repo de desarrollo recibe ~10 líneas;
- los criterios se actualizan en un solo lugar;
- el comportamiento del reviewer se actualiza sin copiar código;
- no necesitamos servidor externo;
- no necesitamos GitHub App;
- GitHub Actions resuelve el trigger;
- el QA mantiene ownership sobre la lógica central.

---

# 4. Review pendiente en vez de comentarios publicados

Esta es una decisión central del diseño.

El agente **no dejará comentarios públicos sueltos**.

Creará una única GitHub Pull Request Review en estado:

```text
PENDING
```

La API de GitHub permite crear una review sin enviar el evento de submit.

Conceptualmente:

```text
Agent findings
      ↓
review.json
      ↓
GitHub Pull Request Reviews API
      ↓
PENDING REVIEW
```

## 4.1. Identidad de la review

Una review pendiente solamente es visible para el usuario que la creó.

Por lo tanto, no sirve crearla con:

```text
github-actions[bot]
```

porque el QA no podría verla como su propia review pendiente.

La review será creada usando un **Fine-Grained Personal Access Token del QA**.

De esa forma GitHub considera que la review pertenece al QA.

Flujo:

```text
Workflow
    ↓
QA_GITHUB_TOKEN
    ↓
GitHub Review API
    ↓
Pending review creada por el QA
    ↓
QA abre "Files changed"
    ↓
edita / borra / agrega comentarios
    ↓
Review changes
    ↓
Approve / Comment / Request changes
    ↓
Submit review
```

Esto replica el workflow manual que ya utiliza QA.

---

# 5. Seguridad del token

El token se llamará:

```text
QA_GITHUB_TOKEN
```

Será un **Fine-Grained PAT**.

## Acceso a repositorios

Debe tener acceso solamente a:

- el repo de desarrollo que se revisará;
- `SportmatchOrg/agents-copilot`.

## Permisos mínimos

En el repo objetivo:

```text
Contents: Read
Pull requests: Read and write
Metadata: Read
```

En `agents-copilot`:

```text
Contents: Read
Metadata: Read
```

El token:

- nunca se versiona;
- nunca aparece en prompts;
- nunca se expone al agente;
- nunca se guarda en un archivo;
- solamente se inyecta en el step encargado de hablar con GitHub.

## Checkout sin credenciales persistentes

Los checkouts se realizarán con credenciales no persistentes.

Conceptualmente:

```yaml
persist-credentials: false
```

De esta manera, aunque el agente pudiera ejecutar comandos de Git, no debería disponer de credenciales almacenadas para hacer `push`.

Adicionalmente, al finalizar la ejecución se verificará que el agente no haya modificado el workspace.

---

# 6. Estructura propuesta

La estructura actual se mantiene y se agrega una `.github/` real para el control plane central.

```text
agents-copilot/
│
├── AGENTS.md
│
├── README.md
│
├── install.sh
│
├── github/
│   │
│   ├── copilot-instructions.md
│   │
│   ├── skills/
│   │   └── pr-review/
│   │       ├── SKILL.md
│   │       └── references/
│   │           └── qa-criteria.md
│   │
│   ├── scripts/
│   │   ├── llm.sh
│   │   └── linear.sh
│   │
│   └── workflows/
│       └── ...
│
└── .github/
    │
    ├── workflows/
    │   └── qa-review-reusable.yml
    │
    └── scripts/
        └── qa-review/
            ├── collect-context.sh
            ├── deterministic-checks.py
            ├── validate-review.py
            └── create-pending-review.py
```

## Diferencia entre `github/` y `.github/`

### `github/`

Sigue siendo el paquete/template que `install.sh` puede copiar a otros repos como `.github/`.

### `.github/`

Es la configuración real del repositorio `agents-copilot`.

El reusable workflow debe vivir necesariamente en:

```text
.github/workflows/
```

para poder ser invocado por otros repos.

---

# 7. Skill de review

Ya existe:

```text
github/skills/pr-review/SKILL.md
```

con:

```text
name: pr-review-sportmatch
```

La skill actual ya cubre:

- bugs;
- lógica;
- requerimientos;
- seguridad;
- resiliencia;
- mantenibilidad;
- convenciones;
- trazabilidad;
- regla "Lab4 no codifica".

## Decisión

**No se creará una segunda skill `qa-review` en el MVP.**

El agente central utilizará:

```text
pr-review/SKILL.md
        +
pr-review/references/qa-criteria.md
```

El archivo `qa-criteria.md` contendrá los criterios específicos definidos por QA.

Esto evita duplicar dos reviewers con reglas parcialmente superpuestas.

## Importante

La skill existente no debe comenzar a cargar automáticamente los nuevos criterios QA en todos los contextos.

Motivo:

```text
Copilot native review
       ↓
SKILL.md
       ↓
comentarios automáticos
```

no debe transformarse accidentalmente en:

```text
Copilot native review
       ↓
SKILL + QA criteria
       ↓
comentarios QA publicados sin aprobación humana
```

El reusable workflow será quien explícitamente indique:

> leer la skill de PR review y además aplicar `qa-criteria.md` en modo QA draft.

---

# 8. Criterios de QA

Los criterios serán identificados como:

```text
QA-01
QA-02
...
QA-10
```

Esto facilita:

- trazabilidad;
- debugging;
- análisis de falsos positivos;
- aprendizaje futuro;
- referencias claras en los findings.

---

## QA-01 — Scope y tamaño de PR

### Regla

- no salir del scope del issue;
- PRs independientes;
- máximo 1000 líneas de código modificadas por PR.

### Evaluación

Combinación de:

```text
check determinístico
+
agente
+
Linear
```

### Parte determinística

Calcular:

```text
reviewable_changed_lines
```

como:

```text
additions + deletions
```

excluyendo:

- lockfiles;
- archivos generados;
- binarios;
- vendor;
- outputs de build;
- archivos no revisables.

Ejemplo:

```text
Diff total: 4132 líneas
package-lock.json: 3500
Código revisable: 632

=> dentro del límite.
```

Si:

```text
reviewable_changed_lines > 1000
```

se genera un finding global.

### Parte agentic

El agente compara:

```text
PR
+
diff
+
Linear issue
```

para detectar cambios que no pertenecen al scope.

Ejemplo:

```text
SPM-42: agregar autenticación Firebase

PR:
+ autenticación
+ rediseño del navbar
+ refactor del mapa
```

Finding:

```text
QA-01 · MAJOR

El refactor del mapa no parece formar parte de SPM-42.
Conviene separarlo en otra PR.
```

---

## QA-02 — Comentarios innecesarios

### Regla

Los comentarios deben explicar principalmente **por qué**, no describir literalmente qué hace el código.

### Evaluación

Agentic.

Se revisan principalmente comentarios agregados o modificados por la PR.

Ejemplo a evitar:

```ts
// Incrementa el contador
count++;
```

No se marcarán comentarios que:

- documenten una decisión;
- expliquen una restricción;
- justifiquen una implementación no obvia;
- describan un workaround.

---

## QA-03 — Dependencias innecesarias

### Regla

No agregar dependencias sin necesidad.

La evaluación debe cuestionar incluso si realmente hace falta incorporar un framework.

### Evaluación

Primero:

```text
package.json
package-lock.json
yarn.lock
pnpm-lock.yaml
```

Si no cambiaron dependencias, este criterio se omite.

Si cambiaron:

```text
detectar dependencia nueva
        ↓
agente inspecciona su uso
        ↓
¿es necesaria?
```

Ejemplo:

```text
lodash agregado
↓
solo se usa para una validación trivial
↓
puede reemplazarse con JavaScript nativo
```

Finding:

```text
QA-03 · MINOR/MAJOR

Se agregó lodash únicamente para esta operación.
Para este caso podemos evitar sumar una dependencia.
```

No se penaliza una dependencia solamente por ser nueva.

Debe existir evidencia de que es innecesaria o sobredimensionada.

---

## QA-04 — Debugging y código muerto

### Regla

No dejar:

- `console.log`;
- `debugger`;
- logs temporales;
- debugging;
- código comentado;
- código muerto evidente.

### Evaluación

Combinación:

```text
regex / AST simple
+
agente
```

Los casos obvios se detectan sin gastar razonamiento del modelo.

Ejemplos:

```ts
console.log(...)
debugger;
```

El agente se utiliza para casos ambiguos como bloques grandes de código comentado.

---

## QA-05 — Evidencia visual en Linear

### Regla

Cuando existen cambios visuales, suma mucho agregar screenshots o videos en Linear.

### Severidad

Este criterio es una recomendación.

No debe ser BLOCKER.

### Evaluación

Primero determinar si la PR probablemente contiene cambios visuales.

Indicadores:

- componentes `.tsx`;
- cambios en Tailwind;
- CSS;
- layouts;
- páginas;
- componentes de UI;
- clases visuales;
- assets visuales.

Si hay cambio visual:

```text
detectar SPM-xx desde branch
       ↓
consultar Linear
       ↓
description
comments
attachments
       ↓
¿hay screenshot/video?
```

El helper actual de Linear deberá extenderse para poder consultar evidencia visual cuando sea necesario.

Finding posible:

```text
QA-05 · NIT

La PR modifica UI pero no encontré evidencia visual en SPM-42.
Una captura o video facilitaría la revisión.
```

---

## QA-06 — Hardcoding

### Regla

Evitar hardcodear valores cuando pertenecen a configuración, entorno o conceptos reutilizables.

### Evaluación

Agentic + heurísticas.

Ejemplos relevantes:

- URLs;
- endpoints;
- puertos;
- IDs;
- configuraciones;
- timeouts;
- magic numbers;
- valores dependientes del ambiente.

No se considera automáticamente hardcoding problemático a cualquier literal.

El agente debe razonar si el valor:

- forma parte del dominio;
- es una constante válida;
- debería estar en config/env;
- ya existe centralizado.

---

## QA-07 — Assets pesados, dinámicos o generados

### Regla

Evitar versionar en Git:

- assets pesados;
- archivos generados;
- archivos dinámicos.

Preferir object storage/buckets.

### Evaluación

Principalmente determinística.

Revisar archivos nuevos por:

- extensión;
- tamaño;
- ubicación;
- patrones de archivo generado.

El límite de tamaño debe ser configurable para evitar hardcodearlo en la lógica.

Ejemplo de configuración:

```text
QA_MAX_ASSET_BYTES
```

Inicialmente puede establecerse un valor conservador y ajustarse luego de probarlo con PRs reales.

---

## QA-08 — Branches mergeadas

### Regla

Borrar branches una vez mergeadas, conservando:

- `main`;
- `dev`;
- branches activas.

### Decisión

**Este criterio no será responsabilidad del agente de PR.**

Una PR abierta no puede evaluar correctamente si su branch debe borrarse después del merge.

La solución correcta es configurar GitHub para:

```text
Automatically delete head branches
```

De esta manera:

```text
PR mergeada
    ↓
GitHub
    ↓
borra branch automáticamente
```

No se gastan tokens ni se generan findings innecesarios.

---

## QA-09 — Componentización y layout

### Regla

- usar componentes reutilizables;
- no recrear componentes ya existentes;
- un botón con variantes es preferible a múltiples botones equivalentes;
- no utilizar margins;
- utilizar padding para spacing según la convención del equipo.

### Evaluación

Dos partes.

### Modularización

Agentic.

Ejemplo:

```text
PR crea PrimaryButton.tsx
        ↓
agente busca componentes existentes
        ↓
encuentra Button.tsx con variant="primary"
        ↓
finding
```

La existencia del checkout completo del repo es esencial para este criterio.

### Margins

Determinístico.

Buscar nuevas clases/patrones como:

```text
m-
mx-
my-
mt-
mr-
mb-
ml-
margin:
margin-top:
...
```

Solo se analiza código agregado/modificado por la PR.

---

## QA-10 — Idioma

### Regla

- todo lo que ve el usuario: español;
- código frontend/backend: inglés.

### Evaluación

Agentic + heurísticas.

Detectar:

### UI

Strings visibles nuevas en inglés.

Ejemplo:

```tsx
<p>No results found</p>
```

### Código

Identificadores nuevos en español:

```ts
const usuarioActual = ...
function crearPartido() {}
```

Se espera:

```ts
const currentUser = ...
function createMatch() {}
```

El reviewer debe evitar marcar:

- nombres propios;
- texto proveniente de APIs;
- contenido externo;
- términos del dominio que deban conservarse.

---

# 9. Tipos de findings

No todos los criterios corresponden a una línea concreta del diff.

Se manejarán dos tipos.

## Inline

Tiene:

```text
path
line
```

Ejemplos:

- `console.log`;
- texto visible en inglés;
- margin;
- comentario innecesario;
- hardcoding localizado;
- componente duplicado.

Se crea como comentario inline dentro de la pending review.

---

## Global

No tiene una línea única.

Ejemplos:

- PR > 1000 líneas;
- cambio fuera de scope;
- dependencia innecesaria que afecta la PR completa;
- falta screenshot/video;
- observación general de arquitectura.

Se incluye en el body de la pending review.

---

# 10. Formato de salida interno del agente

El agente no escribe directamente en GitHub.

Debe producir JSON.

Ejemplo:

```json
{
  "version": 1,
  "summary": "La PR agrega el flujo de creación de partidos.",
  "positives": [
    "La lógica quedó correctamente separada del controller.",
    "La PR mantiene un scope claro respecto de SPM-42."
  ],
  "findings": [
    {
      "id": 1,
      "criterion": "QA-04",
      "severity": "MINOR",
      "kind": "inline",
      "path": "frontend/app/create/page.tsx",
      "line": 83,
      "message": "Quedó un console.log de debugging."
    },
    {
      "id": 2,
      "criterion": "QA-01",
      "severity": "MAJOR",
      "kind": "global",
      "message": "El refactor del mapa no parece formar parte del alcance de SPM-42."
    }
  ]
}
```

---

# 11. Severidades

Se conserva la convención ya utilizada por la skill:

```text
BLOCKER
MAJOR
MINOR
NIT
```

## Orientación

### BLOCKER

Problemas que claramente no deberían mergearse.

Ejemplos:

- credenciales;
- vulnerabilidad grave;
- corrupción de datos.

### MAJOR

Problema importante de diseño, scope o comportamiento.

### MINOR

Corrección válida pero localizada.

### NIT

Sugerencia pequeña y no bloqueante.

La severidad es informativa.

El agente nunca elige el evento final de la review.

El QA decide:

```text
Approve
Comment
Request changes
```

---

# 12. Reglas de calidad del reviewer

El agente debe evitar convertirse en un reviewer ruidoso.

Reglas:

```text
máximo 5 findings
```

Además:

- no producir findings para llenar cupo;
- no repetir el mismo problema;
- comentar solo cambios introducidos por la PR;
- priorizar problemas de impacto real;
- buscar evidencia antes de afirmar duplicación;
- buscar el componente existente antes de decir "reutilizar";
- no confundir cualquier literal con hardcoding;
- no confundir cualquier dependencia nueva con dependencia innecesaria;
- no marcar código preexistente;
- mantener comentarios breves;
- incluir aspectos positivos reales;
- evitar NITs si ya existen findings más importantes.

---

# 13. Estilo del comentario

Los mensajes deben ser breves, concretos y constructivos.

### Bien

```text
Este componente replica una variante que ya existe en `Button`.
Conviene reutilizarla para mantener el comportamiento centralizado.
```

### Evitar

```text
CRITICAL ARCHITECTURAL ISSUE: This violates QA criterion #9 and introduces
unnecessary technical debt that should be immediately corrected...
```

Los comentarios del reviewer estarán en español.

Las referencias a código permanecen con sus nombres reales en inglés.

---

# 14. Review body

La pending review tendrá un body similar a:

```markdown
## QA Review — Draft

La PR agrega el flujo de creación de partidos y se mantiene mayormente acotada a SPM-42.

### Positivo

- Buena separación entre controller y service.
- Se reutilizan correctamente los DTO existentes.

### Observaciones generales

- **QA-01 · MAJOR** — El refactor del mapa parece fuera del scope de SPM-42.
- **QA-05 · NIT** — Hay cambios visuales pero no encontré evidencia en Linear.

---

Review preparada automáticamente. La decisión y el submit son humanos.

<!-- sportmatch-qa-agent -->
```

El marcador:

```html
<!-- sportmatch-qa-agent -->
```

se utiliza internamente para diferenciar una pending review generada por el agente de una review manual iniciada por el QA.

---

# 15. Manejo de comentarios inline

Los comentarios inline se restringirán inicialmente a líneas nuevas o modificadas que puedan representarse de forma segura en el diff.

Preferencia:

```text
side = RIGHT
```

para líneas agregadas/modificadas.

Si un finding no puede mapearse con confianza a una línea válida:

```text
NO inventar línea
```

Se convierte en finding global.

Esto evita errores de la API y comentarios colocados en líneas incorrectas.

---

# 16. Validación antes de tocar GitHub

Entre el agente y GitHub existirá una capa determinística.

```text
Agent
  ↓
review.json
  ↓
validate-review.py
  ↓
GitHub API
```

El validador comprobará:

- JSON válido;
- schema válido;
- máximo 5 findings;
- criterio conocido (`QA-01` ... `QA-10`);
- severidad válida;
- path pertenece a la PR;
- línea pertenece al diff;
- comentarios no vacíos;
- no existen findings duplicados;
- el head SHA sigue siendo el mismo;
- no se modificó el workspace;
- no se están intentando ejecutar side effects desde el output.

---

# 17. Lifecycle de la pending review

Este punto es importante porque el workflow corre nuevamente cuando el developer hace push.

## Caso A — No existe review pendiente

```text
crear pending review
```

---

## Caso B — Existe una pending review generada previamente por el agente

Se identifica por:

```html
<!-- sportmatch-qa-agent -->
```

Si la PR recibió nuevos commits:

```text
eliminar pending review vieja
        ↓
analizar HEAD nuevo
        ↓
crear pending review nueva
```

Esto evita findings obsoletos.

---

## Caso C — El QA ya comenzó una review manual

Si existe una pending review del QA **sin** el marker del agente:

```text
NO tocarla
```

El workflow debe terminar de forma segura y registrar:

```text
QA already has a manual pending review.
Automatic draft skipped.
```

Nunca debemos borrar o reemplazar una review manual del QA.

---

## Caso D — El QA ya submiteó la review y luego llega otro push

Una review submitida ya no está `PENDING`.

Por lo tanto:

```text
nuevo push
    ↓
nueva ejecución
    ↓
nueva pending review
```

Esto es deseable porque el código cambió.

---

# 18. Trigger

Wrapper del repo objetivo:

```yaml
on:
  pull_request:
    types:
      - opened
      - synchronize
      - reopened
      - ready_for_review
    branches:
      - dev
      - main
```

## Draft PRs

Decisión inicial:

- si la PR se abre como draft, no generar review;
- ejecutar cuando pasa a `ready_for_review`.

Esto reduce ruido mientras el developer todavía está trabajando activamente.

---

# 19. Concurrency

Solo debe existir un análisis activo por PR.

Conceptualmente:

```yaml
concurrency:
  group: qa-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true
```

Si el developer hace dos pushes seguidos, el análisis viejo se cancela y se analiza solamente el HEAD más reciente.

---

# 20. End-to-end

Flujo completo:

```text
Developer
   │
   │ abre PR a dev/main
   ▼
Target repo
.github/workflows/qa-review.yml
   │
   │ reusable workflow
   ▼
SportmatchOrg/agents-copilot
.github/workflows/qa-review-reusable.yml
   │
   ├── checkout target repo
   ├── checkout agents-copilot
   ├── collect PR metadata
   ├── collect diff
   ├── identify Linear issue
   ├── run deterministic checks
   │
   ▼
Agent runtime
   │
   ├── full target repository
   ├── PR diff
   ├── AGENTS.md
   ├── pr-review/SKILL.md
   ├── qa-criteria.md
   ├── Linear issue
   └── deterministic facts
   │
   ▼
review.json
   │
   ▼
validate-review.py
   │
   ├── schema
   ├── diff lines
   ├── head SHA
   ├── max findings
   └── no workspace changes
   │
   ▼
create-pending-review.py
   │
   │ QA_GITHUB_TOKEN
   ▼
GitHub
   │
   ▼
Pending Review
(authored by QA)
   │
   ▼
QA opens Files changed
   │
   ├── reads comments
   ├── edits comments
   ├── deletes false positives
   ├── adds own comments
   └── selects final verdict
   │
   ▼
Submit review
   │
   ▼
Developer sees official QA review
```

---

# 21. Contexto que recibe el agente

El agente debe recibir cuatro capas.

## 21.1. Contexto del proyecto

```text
AGENTS.md
copilot-instructions.md
```

Contiene:

- scope;
- RFs;
- stack;
- convenciones;
- Definition of Done;
- arquitectura;
- reglas de IA.

---

## 21.2. Contexto de review

```text
github/skills/pr-review/SKILL.md
github/skills/pr-review/references/qa-criteria.md
```

Contiene:

- bugs;
- seguridad;
- mantenibilidad;
- resiliencia;
- QA-01 ... QA-10;
- tono;
- severidades.

---

## 21.3. Contexto de la PR

```text
PR title
PR body
branch
base branch
head SHA
files changed
diff
stats
```

---

## 21.4. Contexto de negocio

```text
Linear SPM-xx
```

Idealmente:

- title;
- description;
- acceptance criteria;
- comments relevantes;
- attachments/evidencia visual;
- status.

---

# 22. Runtime agentic

La intención es utilizar un coding agent capaz de inspeccionar el checkout del repositorio, no una única llamada stateless con el diff pegado en un prompt.

El runtime elegido para el diseño es **GitHub Copilot CLI en modo no interactivo dentro de GitHub Actions**, siempre que la configuración del plan y permisos del repositorio lo permita.

El agente podrá:

- leer archivos;
- buscar símbolos;
- buscar componentes existentes;
- inspeccionar manifests;
- ejecutar búsquedas;
- comparar implementaciones;
- consultar el diff;
- entender estructura del repo.

El agente no tendrá acceso al PAT usado para publicar la review.

## Salvaguardas

- instrucciones explícitas de solo lectura;
- checkout sin credenciales persistentes;
- verificación de `git status`;
- output obligado a JSON;
- único side effect realizado por un script controlado.

---

# 23. Checks determinísticos antes del agente

No todo debe resolverse con IA.

Se generará un archivo:

```text
deterministic-facts.json
```

Ejemplo:

```json
{
  "reviewableChangedLines": 632,
  "newDependencies": ["lodash"],
  "debugStatements": [
    {
      "path": "frontend/app/page.tsx",
      "line": 42,
      "type": "console.log"
    }
  ],
  "marginUsages": [],
  "largeAssets": [],
  "visualChangeLikely": true
}
```

El agente usa esos hechos como evidencia.

Beneficios:

- menos tokens;
- más consistencia;
- menos falsos negativos;
- reglas simples no dependen del modelo.

---

# 24. Linear

Ya existe:

```text
github/scripts/linear.sh
```

y el DoD checker ya detecta identificadores como:

```text
SPM-42
```

desde el nombre de la branch.

Se reutilizará esa lógica.

## Extensión necesaria

El comando actual `find-by-identifier` obtiene información básica.

Para QA-05 será necesario agregar capacidad para obtener, cuando corresponda:

- comentarios;
- attachments;
- URLs de imágenes/videos o evidencia equivalente.

No hace falta descargar los assets si basta con comprobar que existe evidencia.

---

# 25. No duplicar responsabilidades con DoD Checker

Ya existe un workflow de Definition of Done.

El QA reviewer no debe convertirse en otro DoD Checker.

## QA Reviewer

Se enfoca en:

```text
calidad concreta de la PR
scope
mantenibilidad
convenciones QA
evidencia
código
```

## DoD Checker

Continúa enfocado en:

```text
Definition of Done
checks
acceptance criteria
deploy
documentación
trazabilidad
```

Puede existir solapamiento de evidencia, pero no deben generar la misma salida.

---

# 26. Configuración única del repo central

En:

```text
agents-copilot
Settings
→ Actions
→ General
→ Access
```

habilitar que los repositorios de `SportmatchOrg` autorizados puedan utilizar actions y reusable workflows del repo privado.

Esto es necesario para que:

```yaml
uses: SportmatchOrg/agents-copilot/.github/workflows/qa-review-reusable.yml@main
```

funcione desde el repo de desarrollo.

---

# 27. Secrets

El reusable workflow necesitará los secretos necesarios desde el contexto del caller.

Mínimo:

```text
QA_GITHUB_TOKEN
```

Según la implementación:

```text
LINEAR_API_KEY
```

y los datos requeridos por el runtime agentic.

Los secrets podrán configurarse:

- en el repo objetivo;
- o a nivel organización si el plan y las políticas de GitHub lo permiten.

No deben asumirse secrets privados del repo `agents-copilot` como automáticamente disponibles dentro de un reusable workflow invocado desde otro repositorio.

---

# 28. PRs provenientes de forks

Por seguridad, GitHub restringe secrets en workflows disparados por PRs provenientes de forks.

MVP:

```text
fork PR => no ejecutar pasos que requieran QA_GITHUB_TOKEN
```

SportMatch trabaja principalmente con branches internas del repositorio, por lo que esto no debería afectar el flujo habitual.

No se utilizará `pull_request_target` para intentar sortear esta protección.

---

# 29. Comportamiento ante errores

## Agent runtime no disponible

```text
no crear review
```

El job debe reportar claramente el fallo.

---

## Linear no disponible

El review puede continuar para criterios que no dependan de Linear.

Se marcan como:

```text
evidence unavailable
```

los checks correspondientes.

No se inventa información.

---

## Línea inválida

Convertir finding inline en global o descartarlo.

Nunca adivinar posiciones del diff.

---

## Head SHA cambió durante el análisis

No publicar la review.

El nuevo evento `synchronize` generará otra ejecución.

---

## PAT no disponible

No intentar publicar.

Fallará solamente el paso de creación de pending review con un mensaje claro.

---

## Modelo devuelve JSON inválido

No intentar "rescatar" parcialmente findings ambiguos.

Validación falla y no se crea review.

---

# 30. Observabilidad del MVP

No agregaremos un stack de telemetry.

GitHub Actions será suficiente inicialmente.

Utilizaremos:

- job logs;
- workflow summary;
- status del workflow.

El summary puede mostrar:

```text
PR #123
Head: abc123
Reviewable lines: 384
Linear: SPM-42
Agent findings: 3
Inline comments: 2
Global findings: 1
Pending review: created
```

---

# 31. Evolución futura

No forma parte del MVP, pero la arquitectura permite agregar luego:

## Feedback learning

Registrar qué findings el QA:

- mantiene;
- edita;
- elimina.

Con suficientes ejemplos se puede crear:

```text
learned-preferences.md
```

Ejemplo:

```text
- No sugerir abstracciones si no existe duplicación real.
- No marcar URLs de DB de GitHub Actions test como hardcoding de producción.
```

La memoria debe ser **curada**, no una vector DB automática en la primera versión.

---

## GitHub App

Si en el futuro el sistema se usa en muchos repos y usuarios:

```text
Fine-grained PAT
        ↓
GitHub App
```

Esto permitiría una identidad de bot y permisos más robustos.

No es necesario para el MVP.

---

## Más repositorios

El patrón reusable permite:

```text
frontend repo
backend repo
otro repo
```

Todos llaman:

```text
agents-copilot/.github/workflows/qa-review-reusable.yml
```

sin duplicar la lógica.

---

# 32. Fases de implementación

## Fase 1 — Knowledge

Crear:

```text
github/skills/pr-review/references/qa-criteria.md
```

Documentar:

```text
QA-01 ... QA-10
```

con ejemplos y falsos positivos a evitar.

---

## Fase 2 — Checks determinísticos

Crear:

```text
.github/scripts/qa-review/deterministic-checks.py
```

Implementar inicialmente:

- líneas revisables;
- logs/debugging;
- cambios de dependencias;
- assets;
- margins;
- probable cambio visual.

Output:

```text
deterministic-facts.json
```

---

## Fase 3 — Agent review manual

Crear un comando local/manual que reciba una PR ya checkouteada.

El agente deberá generar:

```text
review.json
```

Todavía sin tocar GitHub.

Probar contra varias PRs reales.

---

## Fase 4 — Validation

Crear:

```text
validate-review.py
```

Validar:

- schema;
- paths;
- line numbers;
- criteria;
- max findings;
- SHA.

---

## Fase 5 — Pending Review API

Crear:

```text
create-pending-review.py
```

Probar manualmente contra una PR de test.

Objetivo:

```text
pending review visible solamente para QA
```

Verificar que QA puede:

- verla;
- editar comentarios;
- eliminar comentarios;
- agregar comentarios;
- hacer Submit review.

---

## Fase 6 — Reusable Workflow

Crear:

```text
.github/workflows/qa-review-reusable.yml
```

Integrar:

```text
context
→ deterministic
→ agent
→ validation
→ pending review
```

---

## Fase 7 — Wrapper en repo objetivo

Pedir a los developers agregar solamente:

```text
.github/workflows/qa-review.yml
```

aproximadamente 10 líneas.

---

## Fase 8 — Pilot

Ejecutar sobre 3–5 PRs reales.

Medir principalmente:

```text
¿qué comentarios mantuvo QA?
¿qué comentarios borró?
¿qué comentarios editó?
¿qué falsos positivos aparecieron?
¿qué problemas importantes omitió?
```

Ajustar criterios antes de agregar complejidad.

---

# 33. Definition of Done del MVP

El MVP se considera terminado cuando:

- una PR a `dev` o `main` dispara el workflow;
- una PR draft no genera review hasta `ready_for_review`;
- el agente puede inspeccionar el repo completo;
- el agente usa la skill existente;
- el agente usa QA-01 ... QA-10;
- consulta Linear cuando existe `SPM-xx`;
- ejecuta checks determinísticos;
- genera máximo 5 findings;
- incluye aspectos positivos;
- crea comentarios inline válidos;
- crea findings globales cuando no existe línea específica;
- genera una única pending review;
- la review aparece bajo la identidad del QA;
- la review no es visible a developers antes de submit;
- el QA puede editar/eliminar los comentarios;
- el agente nunca hace submit;
- un nuevo push invalida/regenera el draft automático;
- una review manual del QA nunca es borrada;
- no se modifica código;
- no se requieren servidores externos.

---

# 34. Arquitectura final del MVP

```text
┌───────────────────────────────────────────────┐
│              TARGET REPOSITORY                │
│                                               │
│  Developer opens / updates PR                 │
│                 │                             │
│                 ▼                             │
│  .github/workflows/qa-review.yml              │
│           (~10 line wrapper)                  │
└─────────────────┬─────────────────────────────┘
                  │
                  │ reusable workflow
                  ▼
┌───────────────────────────────────────────────┐
│       SportmatchOrg/agents-copilot            │
│                                               │
│  qa-review-reusable.yml                       │
│                 │                             │
│     ┌───────────┼────────────┐                │
│     ▼           ▼            ▼                │
│  PR diff     Linear     Deterministic         │
│  + repo      issue         checks             │
│     └───────────┼────────────┘                │
│                 ▼                             │
│            Coding Agent                       │
│                 │                             │
│       SKILL + QA criteria                     │
│                 │                             │
│                 ▼                             │
│            review.json                        │
│                 │                             │
│                 ▼                             │
│          deterministic validator              │
└─────────────────┬─────────────────────────────┘
                  │
                  │ QA_GITHUB_TOKEN
                  ▼
┌───────────────────────────────────────────────┐
│                  GitHub                       │
│                                               │
│        Pull Request Review: PENDING            │
│        Author: QA user                        │
│                                               │
│        • positive summary                     │
│        • global findings                      │
│        • inline findings                      │
└─────────────────┬─────────────────────────────┘
                  │
                  ▼
             Human QA
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
      edit      delete     add
     comment    false     own comment
               positive
        └─────────┼─────────┘
                  ▼
            Review changes
                  │
        ┌─────────┼──────────┐
        ▼         ▼          ▼
     Approve    Comment    Request
                           changes
                  │
                  ▼
            Submit review
                  │
                  ▼
              Developer
```

---

# 35. Resumen

La solución elegida es deliberadamente simple:

```text
1 central agents repo
+
1 reusable workflow
+
1 tiny wrapper in target repo
+
1 existing PR review skill
+
1 QA criteria file
+
deterministic checks
+
1 coding agent
+
1 fine-grained QA token
+
GitHub Pending Reviews
```

La pieza más importante del diseño es que **el agente prepara el trabajo del QA, pero no lo reemplaza**.

El resultado no es un bot que comenta libremente en cada PR.

Es un asistente que convierte:

```text
PR
```

en:

```text
review humana prearmada
```

manteniendo al QA como autor y responsable final de todo lo que el developer termina viendo.
