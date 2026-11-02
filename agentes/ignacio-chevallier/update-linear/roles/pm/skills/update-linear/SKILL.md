---
name: update-linear
description: Redacta y publica el update semanal del proyecto SportMatch en Linear (avance, actividades clave, desvíos, riesgos y próximos pasos), con su salud (on track / at risk / off track). Usar todas las semanas después de /sincronizar-linear, o cuando pidan "dejá el update en Linear", "update semanal", "status update del proyecto", "cómo venimos para Linear".
---

# /update-linear — update semanal del proyecto en Linear

Un update por semana, en el proyecto **SportMatch** de Linear, siempre con la misma estructura. Lo leen el
equipo y quien sigue el proyecto: tiene que entenderse sin abrir el repo.

## Qué NO hace

- No publica sin el OK explícito de quien lo pidió (paso 4). Un update queda en el feed del proyecto y les
  llega a todos.
- No toca issues, estados, milestones ni la línea base. Si del update sale una acción, va en "Próximos
  pasos" y la ejecuta el PO.
- No inventa riesgos: cada riesgo tiene que poder señalarse (un issue, una corrida, una fecha).

## Paso 1 — Datos frescos

El update se arma sobre el snapshot de esta semana. Si `/sincronizar-linear` no corrió hoy, correrlo primero
(al menos los pasos 1, 2 y 4: sin el paso 4 no hay snapshot nuevo de actividades clave).

```sh
node scripts/linear-update.mjs
```

Imprime:
- el avance total en puntos y en issues;
- lo cerrado desde el snapshot anterior;
- el tablero de actividades clave con el avance de la semana anterior, las que cerraron en la semana y los
  issues abiertos de cada una.

Solo lee el repo: no llama a Linear.

## Paso 2 — Contexto que el script no tiene

- **Plan de la semana:** `docs/planning/Cronograma-y-PERT-v4.md`, sección "Cargados para la semana N"
  (qué tickets y cuántas horas tiene cada dev) y "Lectura contra la línea base".
- **Calendario:** el sprint corre de jueves a jueves. La fecha de cierre del sprint y del steering está en
  §4 del Cronograma.
- **Lo que pasó fuera de Linear:** bugs nuevos, corridas de workflows (por ejemplo el reporte de KPIs en
  `agents-copilot`), decisiones del PO. Preguntar si no está claro en la conversación.

## Paso 3 — Redactar

Siempre esta estructura y en este orden. Fechas `dd/mm`, sin año. Issues como `SPO-123`.

```markdown
## Avance al dd/mm · semana N (cierre del SX el dd/mm)

**NN % del alcance en puntos** (hechos de total · issues hechos de total). La semana N−1 cerró X issues (Y pts).

**Actividades clave**
- **Finalizadas: A de B.** Esta semana cerraron <actividad> (dd/mm), …
- **En curso:** <actividad> NN % · …
- **Pendientes (SX):** <actividades sin avance>.

**Desvíos**
- **<Actividad atrasada>:** línea base dd/mm, estimado dd/mm (+N días). <Qué tiene que pasar para cerrarla.>
- **Adelantos:** <trabajo de un sprint futuro que ya arrancó>.

**Riesgos**
- **<Título corto>.** <Qué pasa, por qué, y a qué afecta.>

**Próximos pasos (hasta el dd/mm)**
- <Acción concreta con sus issues.>
```

Reglas:
- **Desvío** = fin base contra fin estimado o real. Solo se listan las actividades **atrasadas** contra la
  línea base, y los adelantos que importen. Una actividad finalizada antes de tiempo no es un desvío para
  reportar.
- **"Esta semana cerraron"** sale de las filas que el script marca `CERRÓ ESTA SEMANA`.
- **Riesgos:** como mucho tres, de mayor a menor. Si no hay ninguno, la sección dice "Sin riesgos nuevos".
- **Próximos pasos:** solo lo que vence antes del próximo update o del cierre del sprint.

**Salud** del proyecto. Proponer una y justificarla en una línea:

| Salud | Cuándo |
|---|---|
| `onTrack` | El sprint cierra en fecha y no hay riesgos que lo amenacen |
| `atRisk` | Una actividad atrasada contra la línea base, o un riesgo que puede mover el cierre del sprint o un entregable con fecha (steering, challenge) |
| `offTrack` | El cierre del sprint o un entregable con fecha ya no se cumple |

## Paso 4 — Mostrar y pedir el OK

Mostrar el borrador completo y la salud propuesta. Publicar solo con un OK explícito. Si piden cambios,
volver a mostrar el texto antes de publicar.

## Paso 5 — Publicar

Guardar el texto aprobado en el scratchpad (no en el repo) y:

```sh
node --env-file=.env.local scripts/linear-update.mjs --post <archivo.md> --health atRisk
```

Imprime la URL del update. Pasársela a quien lo pidió.
