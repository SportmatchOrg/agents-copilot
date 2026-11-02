---
name: semana
description: Planea el sprint que viene de SportMatch. Cierra el que termina (velocity real y arrastre), decide el alcance cruzando el plan, el repo, la WBS y los diseños, lo pone a consideración del PO, y con su OK redacta y crea los tickets en Linear y escribe el plan de sprint. Usar cuando el PO pida planear la semana, armar el sprint que viene, "qué hacemos la semana que viene", o el jueves cuando cierra un sprint.
---

# /semana — planear el sprint que viene

Decide qué se hace la semana que viene y lo deja ejecutable: tickets creados en Linear y el plan escrito
en `gestion/sprints/`.

**Un solo gate de aprobación: el alcance (Paso 5).** Antes de ese OK no se escribe nada, ni en Linear ni en
disco. Después de ese OK, los tickets se crean sin volver a preguntar uno por uno — el PO ya aprobó la lista.

Es la única skill del workspace que escribe en Linear. Tratarla en consecuencia.

## Qué NO hace

- No crea, edita ni mueve nada antes del OK del Paso 5.
- No mueve tickets a `Todo`, no cancela zombies, no cierra el sprint anterior. Todo eso se **propone** en
  el reporte; lo ejecuta el PO.
- No pone fechas en las descripciones ni en los pasos de un ticket. La **única** fecha que va a Linear es
  el `dueDate` del Paso 7; el orden día por día vive en el plan de sprint.
- **No estira la semana.** Si el alcance no entra en la capacidad, dice qué se cae.
- **No propone versiones provisorias de pantallas diseñadas** para hacer entrar el alcance.

## Paso 1 — Fijar la ventana

1. Fecha de hoy, del contexto de la sesión.
2. Sprint vigente = `gestion/sprints/Sprint N/Plan sprint N (...).md` con el N más alto. Ignorar los que
   tienen el blockquote de "documento histórico".
3. El que se planea es **N+1**, de jueves 18h a jueves 18h, de clase a clase.
4. **Cuántos sprints quedan hasta la demo del jueves 17/09 18h.** Decirlo siempre, arriba. Con la ventana
   jueves→jueves son cuatro, no cinco: el S5 arranca el 10/09 y cierra con la demo, y después no hay nada.
   Freeze de features: viernes 11/09.

Si hoy no es jueves, `/semana` sigue siendo válida — se está planeando en adelanto y el arrastre del Paso 2
es una proyección, no un hecho. Decirlo.

## Paso 2 — Cerrar el que termina

Misma recolección que `/pulse`, en paralelo:

- **Linear:** `list_issues` del proyecto SportMatch con
  `fields: ["title","status","assignee","estimate","updatedAt","labels","dueDate"]`.
- **PRs:** `gh pr list --state open --json number,title,headRefName,isDraft,statusCheckRollup` y
  `gh pr list --state merged --limit 20 --json number,title,headRefName,mergedAt`, desde `sportmatch/`.
- **Repo:** `git -C sportmatch log dev --since="<inicio del sprint>" --pretty=format:'%h %an %ad %s' --date=short`
  y `git -C sportmatch branch -r`.

Y de ahí salen tres números que el plan nuevo necesita:

1. **Velocity real por dev.** SP Done / SP comprometidos. Si la semana todavía no cerró, **no hay velocity**:
   decirlo y planear con la capacidad nominal de 6 SP.
2. **El sprint en curso se planifica como si cerrara completo.** Todo lo que está en `Todo`,
   `In Progress` o `In Review` se asume **Done el jueves a las 18h**. Es la regla del PO y no se
   negocia: la semana que viene arranca con la capacidad limpia, 6 SP por dev.
   El arrastre **no se descuenta de la capacidad** — se registra como **riesgo**, con su `SPO-###` y su
   estado real (PR en review casi entra; `Todo` sin rama no arrancó). Si un ticket no cierra, lo que se
   cae es el ticket que dependía de él, y eso se dice en la sección de riesgos del plan.
3. **Desfasaje Linear ↔ repo.** Un ticket en `Todo` con rama y commits está más avanzado de lo que dice el
   board; uno en `Done` sin PR mergeada, menos. No cambia la capacidad, pero sí el tamaño del riesgo.

## Paso 3 — De dónde sale el alcance

Seis fuentes, en este orden. Ninguna sola alcanza:

1. **La sección "Semanas siguientes"** del plan vigente — los títulos ya escritos para este sprint. Es el
   punto de partida, no la respuesta: se escribieron una semana antes, con menos información.
2. **El arrastre** del Paso 2. Va primero y ocupa capacidad real de esta semana.
3. **El backlog WBS** (`SPO-31`…`SPO-112`) del módulo que toca, con sus dependencias ya cargadas.
4. **El repo** — qué falta de verdad. `git`, no el plan: el plan dice lo que se esperaba, no lo que pasó.
5. **Los diseños.** El índice de las **14 pantallas** está en
   `sportmatch-linktree/generated/figma/screens-mobile.html`: número, nombre y descripción de cada una, en
   el orden del recorrido del jugador. El alcance de front se elige **de esa lista**, y cada pantalla se
   construye entera o no se construye.
   **No se planifica una versión simplificada de una pantalla diseñada** para "ganar tiempo": eso se
   reescribe después y cuesta el doble. Si una pantalla no entra en la semana, se corre entera a la
   siguiente. Ver `.claude/skills/ticket/SKILL.md`, sección "Las pantallas se construyen como están
   diseñadas".
6. **Los tickets en pausa** — Canceled con nota arriba (SPO-160 tema visual, SPO-162 ciudad). No están
   descartados: se reabren cuando se toma la decisión que los frenó. **Preguntarle al PO si ya se tomó**,
   no asumir que sigue pendiente.

## Paso 4 — Capacidad

**18 SP** = 3 devs × 6 SP, **repartido por lane**. Capacidad limpia: el sprint en curso se asume cerrado
(Paso 2). El total esconde una lane parada — repartir siempre por dev, nunca planear contra el total.

Reglas del corte:

- Lo que desbloquea a otra lane va primero en la semana, no último.
- Una sola dependencia cruzada fuerte por semana, y con plan B. Dos son un riesgo, no un plan.
- Cada corte se justifica **contra el 17/09**, no contra la semana. Si algo se cae y no vuelve a entrar
  antes de la demo, eso es lo que hay que decir.

## Paso 5 — Mostrar el alcance y esperar el OK

El único gate. Formato:

```
**Sprint N · jue dd/mm 18h → jue dd/mm 18h · <título de la semana>**
Quedan <N> sprints hasta la demo del 17/09.

CIERRE DEL SPRINT N-1
Velocity por lane, y el arrastre con su SPO-### y su estado real.

OBJETIVO
Una frase con el resultado observable el jueves a las 18h.

| Lane | Ticket | SP | RF · WBS | Nuevo / arrastre |
|---|---|---|---|---|

SE CAE
Qué no entra, y contra el 17/09 qué significa.

RIESGO PRINCIPAL
Uno solo, el que puede hundir la semana.

DECISIONES QUE NECESITO
Solo si las hay: tickets en pausa, dependencias del manager, cosas que no puedo resolver leyendo.
```

Con el OK, seguir. Sin el OK, parar — todavía no se escribió nada.

## Paso 6 — Redactar los tickets, secuencial

Cargar `.claude/skills/ticket/SKILL.md` y aplicar sus **Pasos 0 a 4** a cada ticket de la lista aprobada,
**uno por uno, en esta sesión**. No despachar subagentes.

Secuencial a propósito: cada ticket ve los anteriores, y así las dependencias cruzadas quedan finas y las
referencias entre hermanos ("misma estructura que el ticket de `partidos` de esta semana") salen bien.

El Paso 5 de `/ticket` se saltea: el OK ya se dio sobre el alcance.

## Paso 7 — Crear en Linear

1. Todos los tickets, en **Backlog**, con label, estimate, assignee y **`dueDate` = el jueves que cierra
   el sprint que se está planeando** (formato `YYYY-MM-DD`, la fecha sola). Es la misma para todos los
   tickets de la semana: marca el cierre del sprint, no una entrega individual. Un ticket que se manda al
   backlog sin sprint asignado va **sin** `dueDate`.
2. Después, **las relaciones "blocked by"** de la cadena completa — relaciones reales, no texto.
3. Reportar la tabla de `SPO-###` creados con sus URLs.

Los tickets se crean en Backlog y los mueve a `Todo` el PO cuando arranca el sprint. **No moverlos acá.**

## Paso 8 — Escribir el plan

`gestion/sprints/Sprint N/Plan sprint N (dd-mm al dd-mm).md`. La plantilla viva es
`gestion/sprints/Sprint 2/Plan sprint 2 (20-08 al 27-08).md` — leerla y respetar su estructura:

1. `# Sprint N — jueves dd/mm 18h al jueves dd/mm 18h`
2. Cabecera de capacidad: tres líneas en negrita sueltas — **Capacidad** · **Escala** · **Sprints**
3. `## Objetivo de la semana` — el resultado observable, con la parte demostrable en negrita
4. `## Supuestos` — sobre todo qué se asume del arrastre
5. `## Convención de los tickets` — el formato y las reglas técnicas que aplican esta semana
6. **Un `#` por dev**, con rol, nombre y SP en el título (`# Back — Juan Rudolph · 6 SP`).
   Tickets que ya existen en Linear: tabla, o `## SPO-### · Título · N SP *(ya existe)*`.
   Tickets nuevos: `## 🆕 Título · N SP · RF-XX · WBS X.X.X`, párrafo de justificación, bullets de
   implementación con snippets, y `**Criterios de aceptación**` en checkboxes.
7. `# Orden dentro de la semana` — tabla día × dev, más **qué no se puede correr** y por qué
8. `# Estado en Linear` — tabla resumen de tickets por dev + `**Pendiente:**` en bullets
9. `# Definición de terminado del sprint` — recorrido end-to-end numerado, reproducible, que empieza por
   levantar la app
10. `# Semanas siguientes (solo títulos)` — `## Sprint N · fechas — *Título*` con bullets por lane
11. `# Qué queda explícitamente afuera hasta el 17/09`
12. `# Riesgos` — bullets con la primera frase en negrita

Y **agregar el blockquote de "documento histórico"** arriba del plan del sprint anterior, para que ninguna
sesión futura planee contra él.

## Reglas

- **Linear y el repo son la verdad; el plan viejo es la expectativa.** Planear desde el delta.
- **No inventar números.** Sin semana cerrada no hay velocity. Sin dato, se dice que no hay.
- **Contra el calendario.** Cada decisión se mide contra el 17/09. Cuando algo no entra, se dice qué se cae.
- **Alcance honesto.** Si la semana cierra sin cubrir algo que se va a notar en la review, va explícito en
  los riesgos del plan.
- **Nada provisorio.** Una pantalla del diseño entra entera o no entra. Si el alcance propuesto incluye una
  versión "simple por ahora" de algo ya diseñado, está mal planteado: se corre la pantalla completa al
  sprint siguiente y se dice por qué.
- **`gestion/qa-criteria.md` es el estándar base.** Es con lo que QA revisa cada PR, así que los tickets
  que salgan de acá tienen que poder pasar esa review. Lo que más impacta al planificar: QA-01, que pide
  **un objetivo por PR y menos de 1000 líneas revisables** — un ticket que no entra en eso hay que partirlo
  al planificar, no al implementar.
- **Sin adornos.** El PO lee esto para decidir, no para sentirse bien.
- Si falta un dato (`gh` sin auth, el plan vigente ausente), decirlo en una línea y seguir con el resto.

## Argumentos

`/semana` — planea el que viene.
`/semana 4` — fuerza el número de sprint.
`/semana --solo-plan` — hace todo menos tocar Linear: redacta los tickets dentro del documento y escribe el
plan. Es el modo recomendado las primeras corridas.
