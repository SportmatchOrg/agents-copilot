---
name: ticket
description: Redacta un ticket de SportMatch listo para que un dev lo ejecute sin preguntar nada — referencia RF/WBS, pasos con snippets reales del repo, criterios de aceptación verificables y dependencias. Verifica cada ruta de archivo contra el repo antes de escribirla, muestra el borrador y crea en Linear solo con el OK del PO. Usar cuando el PO pida "armá un ticket para X", "pasá esto a Linear", "escribí el ticket de la pantalla Y", o quiera bajar un paquete de la WBS a algo ejecutable.
---

# /ticket — redactar un ticket ejecutable

Un ticket bien escrito es el que un dev abre y ejecuta **sin volver a preguntar**. Eso se logra de una sola
forma: nombrando archivos que existen y criterios que alguien más puede verificar.

**Escribe en Linear solo después del OK explícito del PO.** Invocar `/ticket` no es aprobación.

## Qué NO hace

- No crea, edita ni cancela nada en Linear antes del OK (`CLAUDE.md` §4: escribir es un acto visible para el equipo).
- No inventa rutas de archivo, nombres de función ni snippets sacados de la doc oficial de la librería.
- **No inventa pantallas ni escribe versiones provisorias de una pantalla que ya está diseñada.**
- No pone fechas en la descripción. La única fecha del ticket es el `dueDate` del Paso 6.
- No mezcla las dos escalas: SP en el campo `Estimate`, horas Md (si aplican) como texto `Estimación (Md): 14h`.
- No toca el issue del backlog WBS del que salió el ticket: queda como referencia.

## Paso 0 — Leer las reglas, no recordarlas

Obligatorio **antes** de escribir cualquier paso técnico. Las reglas del repo cambian y la memoria no:

- **`gestion/qa-criteria.md` — siempre.** Son los criterios QA-01 … QA-10 con los que el equipo de QA
  revisa cada PR. Un ticket cuyos criterios de aceptación ignoran esto genera trabajo que después se
  rechaza en la review. Es el estándar base de todo lo que se escribe acá.
- `sportmatch/AGENTS.md` — siempre. 11 secciones; las que más se olvidan son la 5 (4 capas del back),
  la 6 (nada de `.spec.ts`), la 7 (Prisma 7) y la 10 (ramas y commits).
- `sportmatch/front/AGENTS.md` + `sportmatch/front/DESIGN.md` — si el ticket es de front.
- Un ticket hermano ya escrito, con `get_issue`, para copiar el registro y el nivel de detalle:
  **SPO-155** (back, 4 capas) · **SPO-165** (front, layout) · **SPO-167** (infra, workflow).

## Paso 1 — Ubicar el pedido

Resolver el pedido del PO a cuatro coordenadas:

| Coordenada | De dónde sale |
|---|---|
| **RF-XX** | tabla de `CLAUDE.md` §6 (RF-01 auth · RF-02 perfil · RF-03 partido · RF-04 descubrimiento · RF-05 solicitudes · RF-06 rating) |
| **WBS X.X.X** | `grep -n` en `gestion/WBS.md` — 82 paquetes, cada uno con `**Descripción:**` y `**Dependencias:**` |
| **Lane y dev** | Infra → Juan Francisco Siaba · Back → Juan Rudolph · Front → Pache |
| **Sprint** | el plan vigente, o el que viene si el PO no dice |

Con argumento `SPO-58` (un paquete del backlog WBS, rango `SPO-31`…`SPO-112`): leer ese issue, tomar su
descripción y sus dependencias, y **bajarlo a un ticket ejecutable nuevo**. El original no se edita.

Si el pedido no cae en ningún paquete de la WBS, decirlo: es alcance nuevo, y eso es una decisión del PO,
no algo que se resuelve escribiendo el ticket igual.

## Paso 2 — Verificar contra la realidad

Los tres cruces, en paralelo. **Este paso es el que hace que el ticket sirva.**

1. **Repo.** Cada archivo que el ticket va a nombrar: o existe (verificado con `Read`/`Glob`/`ls`), o el
   ticket dice explícitamente que se crea. Un ticket que manda a editar un archivo inexistente le quema
   veinte minutos al dev antes de que pregunte.
   También: ¿ya hay una rama `feature/SPO-###` o una PR abierta que toque esto?
   (`gh pr list --state open` desde `sportmatch/`).
2. **Linear.** `list_issues` del proyecto SportMatch: ¿hay un duplicado, o un ticket en pausa (Canceled con
   nota arriba) que ya lo cubre? ¿Qué lo bloquea? Las cadenas se leen con
   `get_issue` + `includeRelations: true`.
3. **Diseño** — solo si es front. Ver la sección siguiente, que es una regla dura:
   - `sportmatch-linktree/generated/figma/screens-mobile.html` — **el índice de las 14 pantallas**, con su
     número, nombre y descripción. Es la fuente de verdad de qué pantallas existen.
   - `sportmatch/front/DESIGN.md` — tokens, tipografía, radios, inventario de componentes, y el checklist
     de §16 "Building new UI".
   - `sportmatch-linktree/prototype/sportmatch/app/overrides.js` — la implementación de referencia de cada
     pantalla, con sus medidas y transiciones reales.
   - `sportmatch-linktree/prototype/sportmatch/media/screenshots/` — las capturas (algunas están recortadas
     o rotas; el prototipo manda sobre la captura).

## Las pantallas se construyen como están diseñadas

**No se escriben versiones "simples por ahora" de una pantalla que ya está diseñada.** Es la regla que más
plata cuesta cuando se rompe: lo construido se tira y se hace dos veces.

Antecedente real: el sprint 2 pidió "un formulario único, **no** el wizard" para crear partido, con el
wizard de 5 pasos agendado para más adelante "reusando el form". Resultado: el formulario se reescribe
entero. Lo mismo pasó con un listado de partidos que no existe en el diseño, inventado para no construir
el mazo de tarjetas.

Antes de escribir un ticket de front, ubicar la pantalla en el índice de 14:

| # | Pantalla | # | Pantalla |
|---|---|---|---|
| 01 | Iniciar sesión | 08 | Crear · Horario |
| 02 | Crear cuenta | 09 | Crear · Jugadores |
| 03 | Mapa de partidos *(inicio)* | 10 | Crear · Revisión |
| 04 | Descubrir *(mazo de tarjetas)* | 11 | Tus partidos |
| 05 | Detalle del partido | 12 | Perfil |
| 06 | Crear · Deporte | 13 | Ajustes |
| 07 | Crear · Lugar | 14 | Editar perfil |

Y aplicar esto:

- **Si la pantalla está en la lista, el ticket la construye como está.** Completa, no una aproximación.
- **Si no entra en el sprint, se corre entera al siguiente.** Media pantalla bien hecha es progreso; una
  pantalla distinta y provisoria es trabajo que se tira.
- **Si el pedido del PO no corresponde a ninguna pantalla del diseño, decirlo antes de escribir el ticket.**
  Puede ser alcance nuevo legítimo, pero es una decisión del PO, no algo que se resuelve redactando igual.

**Lo que sí se puede omitir:** un dato que todavía no existe en el modelo. Si el diseño muestra rating,
distancia o un título de partido y esos campos no están, el slot se omite — pero el layout, el componente y
las medidas son los definitivos, y el dato entra después sin rehacer nada. Eso **no** es simplificar: es
renderizar la pantalla real con la información disponible.

Si falta material para una pantalla que sí hay que construir, **pedirle una foto al PO antes de redactar**.
Adivinar el layout es peor que esperar dos minutos.

## Todo el código nuevo va en inglés

**Decisión del PO del 03/09.** Desde acá, todo lo que un ticket manda a escribir se nombra en inglés:
modelos y enums de Prisma, campos, DTOs, servicios, funciones, variables, hooks, componentes, nombres de
archivo y rutas nuevas de la API. Sin excepción para los términos de dominio.

Lo que el repo ya tiene en español (`Partido`, `Participante`, `Deporte`, `cupo`, `ubicacion`,
`organizadorId`, `estoy_anotado`, `/partidos`) **se deja quieto**: lo cambia el ticket de refactor general,
no un ticket de feature. Lo que no se hace es sumar castellano nuevo para "mantener la consistencia".

Cómo se escribe un ticket con esta regla:

- **Nombrá lo nuevo como va a quedar después del refactor**, aunque hoy conviva con lo viejo. Una entidad
  nueva que apunta a `Partido` lleva `matchId String` + `match Partido @relation(...)`: el día que
  `Partido` pase a `Match`, ese módulo no se toca. Es feo por una semana y correcto para siempre.
- **Un módulo nuevo se nombra entero en inglés**, carpeta incluida (`back/src/join-requests/`), aunque
  cuelgue de una ruta que todavía está en castellano.
- **La UI sigue en español.** QA-10 Parte A no cambia: textos, `aria-label`, `placeholder` y mensajes de
  validación que ve el usuario van en rioplatense. Lo que cambia es solo la Parte B.
- **El ticket lo dice explícitamente en las Notas**, con los nombres viejos que quedan alrededor. Si no,
  el dev copia la convención del archivo de al lado y vuelve el castellano.

## Paso 3 — Estimar

Escala **1 / 2 / 3 / 4**. 1 SP = 1 hora. Nada de Fibonacci.

Si el ticket pinta 5, **se parte en dos** y se explica el corte. Un dev tiene 6 SP por semana: un ticket de
5 se come la semana entera y no deja ver el avance hasta el final.

## Paso 4 — Redactar

El formato es fijo:

```
**Referencia:** RF-XX · WBS X.X.X

**Descripción**

Qué y por qué, dos o tres líneas. El "por qué" es lo que le permite al dev decidir bien cuando algo
del paso a paso no cierra.

**Pasos**

1. Numerados, con snippets de código reales — rutas del repo, nombres de archivo que existen.
2. ...

**Criterios de aceptación**

- [ ] Verificables por alguien que no escribió el código.
- [ ] Incluyen siempre el caso de error.

**Notas**

* Decisiones tomadas, alcance excluido, plan B.

**Bloqueado por:** SPO-XXX
```

## Paso 5 — Mostrar y esperar

Imprimir el ticket completo, y debajo una línea de metadata:

```
lane · label · N SP · assignee · bloqueado por SPO-### · bloquea a SPO-###
```

**Parar acá.** No crear nada. Si el PO pide cambios, se corrige y se vuelve a mostrar.

En **modo lote** (invocado desde `/semana`), saltear este paso: el OK ya se dio sobre el alcance de la semana.

## Paso 6 — Crear en Linear

Con el OK dado, `save_issue`:

| Campo | Valor |
|---|---|
| `team` | `Sportmatch - DirProy` (`e7dd5c5f-9e5e-4853-8b42-c8cfcd6644f4`) |
| `project` | SportMatch (`1ca5132a-732a-4df2-9bd1-1fe0499370c2`) |
| `state` | **Backlog** — pasa a Todo cuando arranca su sprint |
| `labels` | `Infra` / `Backend` / `Frontend` |
| `estimate` | los SP del Paso 3 |
| `assignee` | el dev de la lane |
| `dueDate` | el **jueves que cierra el sprint** del ticket (`YYYY-MM-DD`). Sin sprint asignado, vacío |

Sobre milestones: los tickets de sprint (`SPO-135` en adelante) **no los usan** y `list_milestones` devuelve
vacío. Verificar antes de asignar uno; no asumir que están cargados.

Después de crear, **cargar las relaciones "blocked by" como relaciones reales**, no como texto en la
descripción. El campo `**Bloqueado por:**` del body es para que el dev lo lea; la relación es para que el
board lo sepa.

Reportar identificador y URL.

## Reglas de calidad

Lo que separa un ticket bueno de uno inútil:

- **Cada ruta fue verificada.** Los snippets salen del repo, no de la documentación de la librería.
- **Apuntar al hermano ya hecho** en vez de re-explicar la convención: "misma estructura que `users`
  (SPO-155)" dice más y se lee más rápido que quince líneas de arquitectura.
- **Los criterios de back siempre cierran con:** los códigos de error que apliquen (400 body inválido ·
  401 sin token · 403 recurso ajeno · 404 id inexistente · 409 duplicado o cupo lleno), ningún archivo
  `.spec.ts`, el service no importa `PrismaService`, `npm run lint` y `npm run build` pasan.
- **Los criterios de front siempre cierran con:** `apiFetch` y nunca `fetch` pelado, cero colores
  hardcodeados sueltos, se ve a 375px, hay estado de loading y de error, `npm run build` y `npm run lint`
  pasan.
- **Los criterios de aceptación incorporan los criterios de QA** de `gestion/qa-criteria.md`, porque son
  los que el equipo de QA aplica en la review. Los que se traducen a un criterio escribible:

  | Criterio | Qué exigir en el ticket |
  |---|---|
  | QA-01 | Un solo objetivo por PR, y menos de 1000 líneas revisables. Si el ticket no entra en eso, se parte |
  | QA-02 | Comentarios que expliquen *por qué*, no que parafraseen la línea siguiente |
  | QA-03 | Ninguna dependencia nueva sin justificar. Si el ticket necesita una, el ticket lo dice y explica por qué no alcanza el estándar |
  | QA-04 | Sin `console.log` ni código comentado. `console.error` y `console.warn` sí valen |
  | QA-05 | Cambio visual ⇒ captura o video **en el ticket de Linear**. Un link a Figma no cuenta |
  | QA-06 | URLs, puertos y config por variable de entorno, nunca embebidos |
  | QA-07 | Assets nuevos por debajo de 500 KB; nada generado ni versionado de más |
  | QA-09 | Reusar el componente que ya existe, nombrándolo. **Padding y `gap`, nunca `margin`** (salvo `mx-auto`) |
  | QA-10 | UI en español, **código nuevo siempre en inglés**, sin la excepción de "término de dominio" (ver la sección de arriba) |

- **Plan B en las Notas** cuando el ticket depende de otra lane. Referencia: SPO-166 — "si el módulo
  `partidos` no está mergeado el lunes 24, se arranca por la UI y las validaciones de cliente".
- **Nada de datos inventados.** Los tiles sin datos reales van en `—`, no con números de relleno.
- **Lo que queda afuera se dice.** Un ticket que no aclara su límite se expande solo.

## Argumentos

`/ticket <descripción libre>` — el caso normal.
`/ticket SPO-58` — baja un paquete del backlog WBS a un ticket ejecutable.
`/ticket --lote` — modo orquestador: devuelve el borrador sin el gate del Paso 5.
