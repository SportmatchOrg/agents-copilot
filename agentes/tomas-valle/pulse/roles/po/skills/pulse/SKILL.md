---
name: pulse
description: Radar de mitad de sprint de SportMatch. Cruza el plan de la semana con el estado real en Linear, las PRs de GitHub y el repo, y reporta qué va a entrar, qué está en riesgo y qué hacer hoy. Usar cuando el PO pida el estado del sprint, "cómo venimos", un chequeo de avance, o antes de una review o una daily.
---

# /pulse — radar de mitad de sprint

Reporte de control para el PO. **Es un radar, no un robot:** lee y reporta, nunca escribe.

## Qué NO hace

- No crea, edita ni mueve issues en Linear.
- No comenta en PRs ni le escribe a los devs.
- No mergea nada.

Si del reporte sale una acción (mover un ticket, cancelar un zombie, pedir un review), se **propone**; la
ejecuta el PO o una sesión aparte donde lo pida explícitamente.

## Paso 1 — Fijar el marco

1. Fecha de hoy (del contexto de la sesión).
2. Sprint vigente = el `gestion/sprints/Sprint N/Plan sprint N (...).md` con el número más alto. Ignorar los que tienen nota
   de "documento histórico".
3. Del plan, extraer: ventana del sprint, capacidad, **tabla de tickets por dev con SP**, **orden día por
   día**, **definición de terminado**, **riesgos** y las dependencias declaradas.
4. Calcular **cuánto queda hasta el cierre: el jueves a las 18h**, la hora de la clase. El sprint corre de
   clase a clase, así que el jueves de cierre todavía es tiempo de trabajo hasta la tarde.

El día manda sobre el foco del reporte:

| Momento | Qué importa |
|---|---|
| Jue (post-clase) – vie | ¿arrancó lo que desbloquea al resto? |
| Sáb – lun | ¿las dependencias cruzadas llegan a tiempo? |
| Mar – jue 18h | qué entra a la review y qué se arrastra |

## Paso 2 — Recolectar el estado real (en paralelo)

- **Linear:** `list_issues` del team `Sportmatch - DirProy` con
  `fields: ["title","status","assignee","estimate","updatedAt","labels","dueDate"]`. Para las cadenas de bloqueo,
  `get_issue` de los tickets del sprint.
- **PRs:** `gh pr list --state open --json number,title,headRefName,author,isDraft,statusCheckRollup,updatedAt`
  y `gh pr list --state merged --limit 20 --json number,title,headRefName,mergedAt`, ejecutados
  desde `sportmatch/`.
- **Repo:** `git -C sportmatch log dev --since="<inicio del sprint>" --pretty=format:'%h %an %ad %s' --date=short`
  y `git -C sportmatch branch -r` para ver ramas `feature/SPO-###` con trabajo empezado.

El número de ticket viaja en la rama, el commit y el título de la PR (`SPO-###`): es la llave para cruzar
Linear con GitHub.

## Paso 3 — Los cruces

Esto es el trabajo real. Ir uno por uno:

1. **Quemado vs capacidad.** SP Done / SP comprometidos, y el desglose en vuelo (In Progress + In Review) vs
   sin empezar (Todo/Backlog). **Por dev**, no solo total: el total esconde una lane parada.
2. **Retraso contra el orden del plan.** Cada ticket contra el día que el plan le asignó. Un ticket que el
   plan ponía el jueves y sigue en Todo el martes **es el titular del reporte**.
3. **Cadenas de bloqueo.** Si A bloquea a B y A no está Done, B tampoco llega. Reportar la cadena entera con
   su SP total, no el ticket suelto.
4. **PRs paradas.** Abierta hace más de 24 h con CI verde = está esperando review, y puede estar frenando a
   otro. CI roja = frenada de verdad. Draft = todavía no cuenta.
5. **Desfasaje Linear ↔ repo.** Ticket en `Todo` que ya tiene rama y commits (el dev arrancó y no movió el
   ticket → el board miente hacia abajo). Ticket en `Done` sin PR mergeada (miente hacia arriba). Ticket en
   `In Review` sin PR abierta.
6. **DoD alcanzable.** Recorrer los pasos de la definición de terminado del plan y marcar cuáles ya son
   **imposibles** para el jueves 18h, con el ticket que los hunde.
7. **Deriva contra el diseño.** Una PR de front que construye algo que **no** es la pantalla del diseño, o
   una versión simplificada de una que sí está diseñada. Es el desvío más caro porque no se ve como retraso
   — se ve como avance, y se descubre cuando hay que reescribirlo. Contrastar contra el índice de las 14
   pantallas en `sportmatch-linktree/generated/figma/screens-mobile.html`. Si aparece, va en el reporte con
   el `SPO-###` y la pantalla que debería haber sido.
8. **Riesgo de rechazo en la review de QA.** Contra `gestion/qa-criteria.md`, mirando solo lo que la PR
   agrega: PRs de más de 1000 líneas revisables o con dos objetivos mezclados (QA-01), dependencias nuevas
   sin justificar (QA-03), `console.log` (QA-04), y **cambios visuales sin captura en el ticket de Linear**
   (QA-05, el que más se olvida). No es hacer la review — es avisar qué va a volver.
9. **Ruido en la métrica.** Tickets de sprints viejos todavía en Todo/In Progress, y tickets del sprint sin
   estimate, label o assignee.

## Paso 4 — El reporte

Máximo ~40 líneas. En español. Este orden:

```
**<Sprint N> · <día> de 7 · quedan <N> días**

TITULAR: dos o tres líneas con lo único que importa hoy.

| Lane | Comprometido | Hecho | En vuelo | Sin empezar | Veredicto |
|---|---|---|---|---|---|

RIESGOS
- Uno por línea, con SPO-###, evidencia y consecuencia concreta.

DoD EN RIESGO
- Solo los pasos que hoy no cierran, con el ticket que los hunde.

RECOMENDACIÓN
- Qué hacer hoy, para quién, y qué se cae si no pasa.

RUIDO (si hay)
- Una línea.
```

## Reglas

- **Cada afirmación con evidencia:** `SPO-###`, `PR #N`, una fecha, un commit. Nada de "parece que" ni "podría".
- **Linear y el repo son la verdad; el plan es la expectativa.** El reporte es el delta entre los dos.
- **La deriva de diseño se reporta como riesgo, no como opinión.** Nombrar la pantalla del diseño y el
  ticket, sin discutir la decisión: puede haber sido deliberada del PO.
- **No inventar métricas.** Si una semana no cerró, no hay velocity. Si falta un dato (`gh` sin auth, plan
  ausente), decirlo en una línea y seguir con el resto.
- **Sin adornos.** Ni felicitaciones, ni "buen trabajo equipo", ni resumen de lo que ya está bien salvo que
  cambie una decisión. El PO lee esto para saber dónde meter la mano.
- **Contra el 17/09.** Si algo compromete la demo y no solo la semana, decirlo aparte.
- Con argumento (`/pulse pache`, `/pulse SPO-164`), acotar el reporte a esa lane o ese ticket, con los
  mismos cruces.
