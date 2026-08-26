---
name: qa-criteria-sportmatch
description: Criterios de QA de SportMatch (QA-01 … QA-10) para la review asistida de PRs. NO se carga automáticamente en la review nativa de Copilot; solo la invoca explícitamente el QA PR Review Agent.
---

# Criterios de QA — SportMatch (QA-01 … QA-10)

> **Alcance de este archivo.** Complementa a `../SKILL.md`, no lo reemplaza. `SKILL.md` cubre
> bugs, seguridad, resiliencia y cumplimiento de RF; este archivo cubre los criterios propios
> del equipo de QA.
>
> **Importante:** este archivo **no debe cargarse automáticamente** en la review nativa de
> Copilot. Solo lo consume el QA PR Review Agent (`.github/workflows/qa-review-reusable.yml`),
> que produce una review en estado `PENDING` para que un humano la edite y la envíe.
> Ver el plan, §7.

---

## Cómo se usa cada criterio

Cada criterio tiene:

- **Regla** — el enunciado del equipo, textual.
- **Evidencia** — de dónde sale el dato: check determinístico (`deterministic-facts.json`),
  Linear, el diff, o inspección del repo.
- **Severidad típica** — orientativa, no obligatoria.
- **Marcar** / **NO marcar** — el par más importante. La segunda lista existe para reducir
  falsos positivos, que son el principal riesgo de este agente.

### Reglas transversales (aplican a los diez criterios)

1. **Solo lo que introduce la PR.** Nunca marcar código preexistente que la PR no tocó.
   Si una línea no aparece como agregada (`+`) en el diff, no es material de finding.
2. **Evidencia antes que sospecha.** Si un criterio requiere afirmar que algo "ya existe"
   o que "no hace falta", primero hay que haberlo buscado en el repo. Sin evidencia, no hay
   finding.
3. **Máximo 5 findings.** No se generan findings para llenar cupo. Cero findings es un
   resultado válido y frecuente.
4. **Si hay findings BLOCKER o MAJOR, omitir los NIT.** El ruido baja la probabilidad de que
   el QA envíe la review.
5. **Español, breve, constructivo.** Los nombres de código se mantienen en su idioma real.
6. **Ante la duda, no marcar.** Un falso positivo cuesta más que un hallazgo omitido: el QA
   revisa esta review a mano y cada finding inválido le hace perder confianza en todas.

---

## QA-01 — Scope y tamaño de la PR

**Regla.** No salirse del scope del issue. PRs independientes y lo más concretas posibles por
cada cambio. Evitar PRs gigantes. (Máximo 1000 líneas de código por PR).

**Evidencia.** Determinística para el tamaño (`reviewableChangedLines`, `exceedsPrSizeLimit`),
agentic para el scope (diff + issue de Linear).

**Severidad típica.** `MAJOR`. **Tipo:** siempre `global`.

### Tamaño

El check determinístico ya calcula `reviewableChangedLines` como `additions + deletions`
**excluyendo** lockfiles, generados, binarios, vendor y salidas de build. Usar ese número; no
recalcularlo a ojo desde el diff.

Ejemplo de por qué importa la exclusión:

```text
Diff total:          4132 líneas
package-lock.json:   3500 líneas
Código revisable:     632 líneas   → dentro del límite, no hay finding
```

Si `exceedsPrSizeLimit` es `true`, generar un finding global. Si es `false`, **no** mencionar
el tamaño: una PR de 900 líneas está dentro de la regla y comentarla es ruido.

### Scope

Comparar el diff contra el issue de Linear (`linear-issue.json`: `title`, `description`).
El finding aplica cuando la PR incluye un cambio **sustantivo y separable** que no se explica
por el issue.

Ejemplo:

```text
SPM-42: agregar autenticación con Firebase

PR:
  + autenticación             ← en scope
  + rediseño del navbar       ← fuera de scope
  + refactor del mapa         ← fuera de scope
```

```text
QA-01 · MAJOR · global
El refactor del mapa no parece formar parte de SPM-42. Conviene separarlo en otra PR
para que cada cambio se pueda revisar y revertir por separado.
```

**Marcar**
- `exceedsPrSizeLimit == true`.
- Una feature, refactor o rediseño identificable que el issue no menciona ni implica.

**NO marcar**
- Cambios de soporte que la feature necesita: migración de Prisma, DTO nuevo, tipo, barrel
  file, actualización de un test existente, ajuste de config que el cambio requiere.
- Renombres o formateo arrastrados por el cambio principal.
- Que la PR sea "grande" si está por debajo del límite.
- Scope contra el ticket, si `linear-issue.json` vino vacío: no hay contra qué comparar, y el
  problema de trazabilidad es del DoD checker, no de esta review (ver §25 del plan).
  Sí se puede evaluar el scope contra el **título y la descripción de la PR**, pero el
  mensaje tiene que dejar claro cuál es la base:

```text
QA-01 · MAJOR · global
El título anuncia el modelo Partido, pero la PR también agrega Deporte y el enum Nivel.
(No pude leer el ticket, así que esto sale del título de la PR.)
```

---

## QA-02 — Comentarios innecesarios

**Regla.** Evitar comentarios innecesarios. Los comentarios deberían explicar principalmente
por qué se hace algo, no describir literalmente qué hace el código.

**Evidencia.** Agentic, sobre comentarios **agregados** por la PR.

**Severidad típica.** `NIT`, o `MINOR` si es un patrón repetido. **Tipo:** `inline`.

**Marcar**
- Comentarios que parafrasean la línea siguiente:

```ts
// Incrementa el contador
count++;

// Retorna el usuario
return user;
```

- Comentarios de andamiaje que quedaron: `// TODO: borrar esto`, `// aca va la logica`,
  encabezados tipo `// ---- FUNCIONES ----`.

**NO marcar**
- Comentarios que explican **por qué**: una decisión, una restricción externa, un workaround,
  una limitación de una librería, un caso borde no obvio.

```ts
// Prisma no soporta upsert compuesto en esta versión; el findFirst evita la race condition.
const existing = await prisma.match.findFirst(...);
```

- JSDoc / TSDoc sobre funciones y tipos públicos.
- Directivas: `// eslint-disable-next-line`, `// @ts-expect-error`, `// prettier-ignore`.
- Comentarios preexistentes que la PR no tocó.
- Un único comentario redundante y trivial si ya hay findings más importantes (regla
  transversal 4).

---

## QA-03 — Dependencias innecesarias

**Regla.** Evitar agregar dependencias si no son realmente necesarias. La pregunta debe llegar
hasta el punto de si realmente necesitamos un framework.

**Evidencia.** El check determinístico lista `newDependencies` comparando el `package.json`
de base contra el de head. Si la lista está vacía, **este criterio se omite por completo**.

**Severidad típica.** `MINOR`, o `MAJOR` si es un framework o una librería pesada.
**Tipo:** `global`, o `inline` sobre la línea del `package.json`.

### Procedimiento obligatorio

No alcanza con que la dependencia sea nueva. Antes de marcar hay que:

1. Buscar en el repo **todos** los usos de la dependencia (el Scout debe pedir esa búsqueda).
2. Ver qué hace concretamente en esos usos.
3. Recién entonces evaluar si el estándar del lenguaje, o algo que el repo ya tiene, lo cubre.

Ejemplo válido:

```text
lodash agregado → único uso: _.isEmpty(arr) en un if
                → Array.isArray(arr) && arr.length === 0 lo cubre
```

```text
QA-03 · MINOR · global
Se agregó lodash y el único uso es `_.isEmpty` en `matches.service.ts`. Para este caso
alcanza con JavaScript nativo y evitamos sumar la dependencia.
```

**Marcar**
- Una dependencia cuyos usos concretos se resuelven con el estándar del lenguaje.
- Una dependencia que duplica algo que el repo ya tiene (dos clientes HTTP, dos librerías de
  fechas, dos librerías de validación).
- Un framework o librería grande traído para un caso puntual.

**NO marcar**
- Una dependencia solo por ser nueva.
- Dependencias del stack ya decidido en `AGENTS.md` §4 (Next.js, NestJS, Prisma, Tailwind,
  `class-validator`, Google Maps).
- Bumps de versión de algo ya presente.
- `devDependencies` de tooling estándar: types, ESLint, Prettier, Jest/Vitest, testing-library.
- Transitivas que aparecen en el lockfile pero no en `package.json`.
- Una dependencia cuyos usos no se pudieron inspeccionar. Sin ver el uso, no hay finding.

---

## QA-04 — Debugging y código muerto

**Regla.** No dejar código comentado, `console.log`, logs temporales o debugging.

**Evidencia.** Determinística para los casos obvios (`debugStatements`), agentic para bloques
de código comentado.

**Severidad típica.** `MINOR`. **Tipo:** `inline`.

**Marcar**
- `console.log`, `console.debug`, `console.dir`, `console.table`, `console.trace`, `debugger`
  en código de producción — el check determinístico ya los ubica con `path` y `line`.
- Bloques de código real comentado (varias líneas de lógica desactivada).
- Variables, imports o funciones agregadas por la PR que no se usan en ninguna parte.

**NO marcar**
- `console.error` y `console.warn`: son manejo de errores legítimo, no debugging.
- El `Logger` de NestJS, o cualquier logger estructurado del proyecto.
- `console.*` dentro de tests (`*.spec.ts`, `*.test.ts`, `__tests__/`), scripts de seed,
  migraciones o herramientas de CLI.
- Un único `//` de una línea que documenta algo (eso es QA-02, y probablemente ni eso).
- Ocurrencias preexistentes que la PR no agregó.

---

## QA-05 — Evidencia visual en Linear

**Regla.** Suma mucho agregar screenshots/videos en Linear cuando existen cambios visuales.

**Evidencia.** `visualChangeLikely` (determinístico) + `linear-issue.json`
(`description`, `comments`, `attachments`).

**Severidad típica.** `NIT`. **Nunca `BLOCKER` ni `MAJOR`.** **Tipo:** `global`.

### Condiciones para que exista el finding

Las tres, juntas:

1. `visualChangeLikely == true`.
2. `linear-issue.json` se pudo consultar de verdad (tiene `id`).
3. No hay evidencia visual: ni imágenes/videos embebidos en la descripción, ni en los
   comentarios, ni attachments de imagen/video.

```text
QA-05 · NIT · global
La PR modifica UI pero no encontré capturas ni video en SPM-42. Una imagen del resultado
le ahorraría bastante tiempo a la review.
```

### Qué cuenta como evidencia, y qué no

`hasVisualEvidence` es un hecho calculado por código: busca imágenes o videos **embebidos o
adjuntos en el propio ticket**. Es la fuente de verdad de este criterio.

Que la descripción *mencione* diseños no es evidencia:

```text
"Las capturas del diseño muestran la barra en sus tres estados."   → NO es evidencia
"Mobile-first, como el diseño de Figma."                           → NO es evidencia
```

El punto de QA-05 es que quien revisa pueda ver el cambio **sin salir de Linear**. Un texto que
remite a un Figma no cumple eso. Si `hasVisualEvidence` es `false`, es `false`, aunque el ticket
hable de diseños.

**NO marcar**
- Si `linear-issue.json` está vacío o la consulta a Linear falló. En ese caso el estado real
  es **desconocido**, y afirmar que falta evidencia sería inventar. Se reporta como
  `evidence unavailable` en el log del job, no como finding.
- Si hay cualquier attachment de imagen o video, aunque no se pueda ver su contenido.
- Si el cambio es de tipos, tests, config o backend, aunque toque un archivo `.ts` dentro de
  `frontend/`.
- Si ya hay findings `MAJOR` (regla transversal 4).

---

## QA-06 — Hardcoding

**Regla.** Evitar lo más posible hardcodear algo.

**Evidencia.** Agentic, con inspección del repo para ver si el valor ya está centralizado.

**Severidad típica.** `MINOR`; `MAJOR` si depende del ambiente; `BLOCKER` si es un secreto
(y en ese caso el criterio que manda es el de seguridad de `SKILL.md` §3).

**Tipo:** `inline`.

**Marcar**
- URLs, endpoints, hosts y puertos embebidos en el código:
  `fetch("http://localhost:3001/api/matches")` → debería salir de una variable de entorno.
- IDs, claves o identificadores de un ambiente concreto.
- Un valor de configuración que **el repo ya centraliza** en otro lado, duplicado a mano.
  Requiere haber encontrado esa constante existente.
- Números mágicos repetidos sin nombre en varios lugares.

**NO marcar**
- Cualquier literal por ser literal. La mayoría de los literales están bien.
- Constantes del dominio que no cambian por ambiente: `MIN_PLAYERS = 2`, `MAX_RATING = 5`,
  `SPORTS = [...]`, códigos de estado HTTP.
- Valores en tests, fixtures, mocks, seeds y `docker-compose.yml`. Un `localhost` en un test
  o en un compose de desarrollo **no es** hardcoding de producción.
- Clases de Tailwind, unidades de CSS, breakpoints.
- Strings de UI en español (eso es QA-10, y ahí están bien).
- Un valor usado **una sola vez**, en el único lugar donde tiene sentido.

---

## QA-07 — Assets pesados, generados o dinámicos

**Regla.** Evitar versionar en Git assets pesados, generados o dinámicos. Usar object
storage/buckets para archivos grandes.

**Evidencia.** Determinística: `largeAssets` (archivos **nuevos** cuyo tamaño supera
`QA_MAX_ASSET_BYTES`, configurable; por defecto 500 KB).

**Severidad típica.** `MAJOR` si es realmente pesado, `MINOR` si está apenas sobre el límite.
**Tipo:** `global`.

**Marcar**
- Archivos nuevos listados en `largeAssets`: imágenes, videos, PDFs, fuentes, `.zip`, dumps.
- Salidas de build o generados versionados: `dist/`, `build/`, `.next/`, `coverage/`,
  `*.min.js`.
- Datos dinámicos versionados: dumps de base, `.csv` de datos reales, logs.

**NO marcar**
- Archivos que ya estaban en el repo y la PR solo modificó.
- Assets chicos por debajo del límite: un `.svg` de un ícono, un `.png` de pocos KB.
- Lockfiles: son grandes por naturaleza y **deben** versionarse.
- Migraciones de Prisma.

---

## QA-08 — Branches mergeadas

**Regla.** Borrar branches una vez mergeadas, manteniendo `main`, `dev` y las branches activas.

**Estado:** `NOT REVIEWED BY AGENT`.

Una PR **abierta** no puede evaluar si su branch debería borrarse: eso se define recién después
del merge. Se resuelve en la configuración del repo:

```text
Settings → General → Pull Requests → Automatically delete head branches
```

El agente **nunca** genera un finding `QA-08`. El validador rechaza cualquier finding con este
criterio.

---

## QA-09 — Componentización y layout

**Regla.** Usar componentes bien modularizables. No recrear la rueda cada vez; un botón con sus
variantes ya basta. No utilizar márgenes, siempre paddings.

**Evidencia.** Agentic para modularización (requiere buscar en el repo), determinística para
márgenes (`marginUsages`).

**Severidad típica.** `MINOR`. **Tipo:** `inline`.

### Parte A — Modularización

**Procedimiento obligatorio.** No se puede decir "reutilizá el que ya existe" sin haber
encontrado el que ya existe. El Scout debe pedir el archivo del componente candidato, y el
finding debe nombrarlo con su ruta real.

```text
PR crea frontend/components/PrimaryButton.tsx
   → buscar componentes existentes de botón
   → aparece frontend/components/ui/Button.tsx con variant="primary"
   → recién ahí, finding
```

```text
QA-09 · MINOR · inline
Esta variante ya está cubierta por `Button` (`frontend/components/ui/Button.tsx`,
`variant="primary"`). Reutilizarlo mantiene el comportamiento centralizado.
```

**Marcar**
- Un componente nuevo que duplica uno existente, **nombrando el archivo existente**.
- Un bloque de JSX idéntico repetido varias veces dentro de la misma PR.

**NO marcar**
- Un componente nuevo porque "podría abstraerse". Sin duplicación real no hay finding.
- Un componente con nombre parecido pero responsabilidad distinta.
- Componentes de una sola página que no se repiten.
- Abstracciones prematuras sugeridas ante dos usos.

### Parte B — Márgenes

El check determinístico lista en `marginUsages` las clases y propiedades de margen agregadas.

**Marcar**
- Clases de Tailwind agregadas: `m-4`, `mt-2`, `mx-6`, `mb-8`, `md:mt-4`, `-mt-1`.
- CSS agregado: `margin:`, `margin-top:`, etc.

Sugerir siempre el reemplazo concreto: padding en el contenedor, o `gap` en un flex/grid.

```text
QA-09 · NIT · inline
Acá conviene padding en el contenedor (o `gap` en el flex) en vez de `mt-4`, según la
convención del equipo.
```

**NO marcar**
- `mx-auto` para centrado horizontal: es el idiom estándar de Tailwind y no es spacing.
- `margin: 0`, `margin: auto` y resets.
- Márgenes preexistentes que la PR no agregó.
- Márgenes en CSS de terceros o generado.
- Más de una vez si es el mismo patrón repetido: un solo finding que mencione que se repite.

---

## QA-10 — Idioma

**Regla.** UI, todo lo que ven los usuarios, en español. Código, front y back, todo en inglés.

**Evidencia.** Agentic + heurísticas.

**Severidad típica.** `MINOR`. **Tipo:** `inline`.

### Parte A — UI que debería estar en español

```tsx
<p>No results found</p>          // → "No se encontraron resultados"
<button>Create match</button>    // → "Crear partido"
toast.error("Something went wrong")  // → "Algo salió mal"
```

También: `placeholder`, `aria-label`, `title`, `alt`, mensajes de validación de DTOs que
llegan al usuario.

**NO marcar**
- Texto que viene de una API o de datos externos.
- Nombres propios, marcas y términos que el equipo usa en inglés: "match", "rating", "swipe",
  "login", "email".
- Claves de i18n (`t("errors.notFound")`) — la clave va en inglés, la traducción no está ahí.
- Logs, mensajes de error internos, comentarios, tests.
- Texto en `console.error`, excepciones del backend que no llegan a la UI.

### Parte B — Código que debería estar en inglés

```ts
const usuarioActual = ...        // → currentUser
function crearPartido() {}       // → createMatch
interface Solicitud {}           // → Request / JoinRequest
```

Aplica a variables, funciones, clases, tipos, props, campos de Prisma, rutas de API y nombres
de archivo **agregados** por la PR.

**NO marcar**
- Identificadores preexistentes, aunque estén en español. Renombrarlos es otra PR (y sería
  QA-01).
- Campos que reflejan un contrato externo en español.
- Términos de dominio que el equipo mantiene en español deliberadamente y ya aparecen así en
  el resto del repo. Si el patrón ya existe, la PR es consistente, no incorrecta.
- Strings en español (eso es correcto por la Parte A).
- Comentarios en español: el equipo escribe en español y está bien.

---

## Severidades

| Severidad | Cuándo |
|---|---|
| `BLOCKER` | No debería mergearse: credenciales expuestas, vulnerabilidad grave, corrupción de datos. |
| `MAJOR` | Problema importante de diseño, scope o comportamiento. |
| `MINOR` | Corrección válida y localizada. |
| `NIT` | Sugerencia chica y no bloqueante. |

La severidad es **informativa**. El agente nunca elige el evento final de la review: el QA
decide `Approve` / `Comment` / `Request changes` y hace el submit.

---

## Estilo de los comentarios

**Bien**

```text
Este componente replica una variante que ya existe en `Button`. Conviene reutilizarla
para mantener el comportamiento centralizado.
```

**Evitar**

```text
CRITICAL ARCHITECTURAL ISSUE: This violates QA criterion #9 and introduces unnecessary
technical debt that should be immediately corrected...
```

Breve, concreto, en español, con el nombre real del archivo o símbolo. Sin mayúsculas de
alarma, sin sermón, sin repetir el criterio como si fuera una sentencia.

---

## Aprendizajes del pilot

> Esta sección se completa durante el pilot (Fase 14) con los patrones que el QA borró o editó.
> Cada línea acá es un falso positivo que ya no debería repetirse.

_(vacío por ahora)_
