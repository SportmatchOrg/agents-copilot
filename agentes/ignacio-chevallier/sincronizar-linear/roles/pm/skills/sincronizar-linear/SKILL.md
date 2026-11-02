---
name: sincronizar-linear
description: Resincroniza el estado de Linear con el Gantt y las vistas de leadership después de que el PO agregó o movió issues. Corre sync-linear.mjs, asigna los issues nuevos a su paquete de la WBS v4, regenera el cronograma, actualiza el tablero semanal de actividades clave del steering y deja el repo verde. Usar cuando el PO cargó tickets nuevos, antes de un steering, cuando el Gantt muestra fechas viejas, cuando toca el tablero semanal de actividades clave, o cuando alguien pida "resincronizá Linear", "actualizá el Gantt", "actualizá el tablero", "el panel no muestra los issues nuevos".
---

# /sincronizar-linear — poner el Gantt al día con Linear

Lo que cambia entre sincronizaciones es **que el PO agrega issues**. Todo lo demás del flujo es
mecánico: el único paso con criterio es decidir a qué paquete de la WBS pertenece cada issue nuevo.

El plan completo y por qué cada pieza es así: `docs/planning/plan-linear.md`.

## Las piezas

| Archivo | Qué es | Quién lo edita |
|---|---|---|
| `docs/planning/linear-wbs-map.csv` | issue → paquete de la WBS. Una fila por par | **A mano** (este skill) |
| `docs/planning/linear-issues.csv` | estado, puntos y fechas reales | Generado, no tocar |
| `docs/planning/actividades-clave.csv` | actividad clave → paquetes de la WBS y línea base | **A mano** (paso 5) |
| `leadership/gantt.html` | bloques `linear-begin` y `gen-begin` | Generado, no tocar |
| `leadership/steering.html` | bloque `actividades-begin`: un snapshot por semana | Generado, no tocar |
| `scripts/sync-linear.mjs` | trae Linear, reporta y escribe el repo | — |
| `scripts/generate-v4.py` | recalcula el cronograma con las fechas reales | — |

## Qué NO hace

- **No escribe en Linear sin `--push`**, y `--push` solo suma issues al proyecto y pone milestones que
  faltan. Nunca toca estados, títulos, asignados ni estimates.
- **No pisa un milestone puesto a mano.** Si difiere del CSV, lo reporta y sigue: manda Linear.
- No inventa el paquete de un issue cuya descripción no da para decidirlo. Ahí se pregunta.
- No commitea: el commit lo decide quien corre el skill.
- **Nunca cambia la línea base.** Ver la regla del paso 4.

## Paso 1 — Traer Linear y ver qué falta

```sh
node --env-file=.env.local scripts/sync-linear.mjs
```

Sin `--push` no escribe nada en Linear. Con `--corte`, los issues en Todo, In Progress e In Review cuentan como Done (solo en el repo), para cerrar la semana antes de un steering. Actualiza `linear-issues.csv`, el bloque del Gantt, y agrega al
mapa los issues nuevos con `wbs_id` vacío.

Lo que reporta y qué significa cada cosa. Que los paquetes de las épicas 1 y 2 no tengan milestone es esperado y no se reporta:

| Aviso | Qué hacer |
|---|---|
| `sin paquete en el CSV` | Paso 2. Es el trabajo real |
| `sin proyecto` | Paso 3: `--push` los suma |
| `milestone distinto al del CSV` | Decidir cuál está bien. Si manda Linear, corregir el CSV; si manda el CSV, corregirlo en Linear a mano |
| `sin estimate` | Pedirle al PO que lo cargue: sin puntos, el issue no suma al avance |
| `en el CSV pero ya no en Linear` | Borrar esas filas del CSV |

## Paso 2 — Asignar los issues nuevos a su paquete

Para cada issue con `wbs_id` vacío, leer su descripción en Linear — con `get_issue` del MCP de Linear,
o abriendo la URL que el propio CSV dejó en la fila:

```sh
grep ',,' docs/planning/linear-wbs-map.csv   # las filas sin paquete, con su link
```

1. **Si la descripción dice `WBS X.Y.Z`, ese es el paquete.** Lo escribió quien redactó el ticket y vale
   más que cualquier inferencia por el título. Casi todos los tickets lo traen.
2. Si no lo trae, el milestone del issue da la épica, y los paquetes de esa épica están en
   `docs/planning/WBS-SportMatch-v4.md`. Elegir entre esos.
3. Si ni el milestone ni la descripción alcanzan, **preguntar al PO**. No adivinar.

Reglas de la fila:

- **Un issue puede cubrir varios paquetes**: una fila por cada uno.
- **La primera fila del issue es su paquete principal** y de ahí sale el milestone. El orden dentro de un
  issue es a mano: no reordenar el CSV por `wbs_id`.
- **`fechas`** decide si esa fila mueve la barra del Gantt:

| `fechas` | Cuándo |
|---|---|
| `si` | El ticket es alcance del paquete: su trabajo es lo que el paquete promete |
| `no` | Hotfix, arreglo de UI, o un retoque sobre un paquete que ya estaba cerrado (por ejemplo SPO-225 sobre 6.4.2) |

Un ticket abierto sobre un paquete pendiente puede ir con `si` sin problema: solo cuentan los tickets
ya cerrados. Marcar `no` a un ticket que sí es alcance del paquete **esconde** trabajo del cronograma.

## Paso 3 — Escribir en Linear

```sh
node --env-file=.env.local scripts/sync-linear.mjs --push
```

Suma al proyecto los issues sueltos y le pone milestone a los que no tienen, según la primera fila del
CSV. Es un cambio que el equipo ve en el overview del proyecto: correrlo con el CSV a medio completar
manda issues al milestone equivocado.

## Paso 4 — Recalcular el cronograma

```sh
python3 scripts/generate-v4.py
```

Escribe solo el bloque `gen-begin` de `leadership/gantt.html` con las fechas reales de lo cerrado. Los
otros tres archivos que deja en `scripts/_v4_*` van a mano y **solo si cambiaron**:

- `_v4_wbs.js` → `leadership/wbs.html` (cambia solo si cambió la WBS)
- `_v4_pert.js` → `leadership/pert.html` (ídem)
- `_v4_calendario.md` → `docs/planning/Cronograma-y-PERT-v4.md`, §4 y §9: **solo las filas de paquetes nuevos**

### La línea base no se toca nunca

En `Cronograma-y-PERT-v4.md`, las fechas y horas de §4 (plan por sprint), §8 (ES / EF / LS / LF / holgura) y
§9 (calendario semana a semana) son la **línea base**, y lo mismo vale para `fin_base` en
`actividades-clave.csv`. No se cambian nunca, aunque el generador dé otras fechas. Lo que sí se puede:

- **Agregar** filas de paquetes nuevos (alcance nuevo, por ejemplo la épica 13.0), sin mover las existentes, y
  sumar sus horas a los totales.
- **Actualizar los marcadores de estado** (✅ 🟡 ⬜) de §4 y §8 con lo cerrado en Linear.

Por eso `_v4_calendario.md` **no se pega entero** sobre los bloques `v4:sprints` y `v4:semanas`: se copian
solo las filas nuevas. Las fechas reales y el plan de lo pendiente se ven en el Gantt, que sí se regenera
completo. Antes de commitear, `git diff` sobre el Cronograma tiene que mostrar solo filas agregadas y cambios
de estado.

## Paso 5 — Tablero de actividades clave (todas las semanas)

El mismo `generate-v4.py` del paso 4 escribe el tablero en la card "Actividades clave" de
`leadership/steering.html`, bajo el jueves que cierra la semana en curso (el de hoy si es jueves). Correrlo dos veces en la misma semana pisa el snapshot
de esa semana; los anteriores quedan como historial y se eligen con el selector de la card.
Cada fila se abre con un clic y muestra de dónde sale su avance: sus issues, su estado y sus puntos.

Qué sale solo y de dónde:

| Columna | Cálculo |
|---|---|
| Avance | Puntos de los issues en Done / puntos de todos los issues de la actividad. Cada issue cuenta una vez; solo filas con `fechas=si` y no cancelados. Sin issues, 0 % |
| Estado | `Finaliz.` al 100 %, `En curso` si hay avance o algún ticket arrancado, `Pend.` si no hay ninguna de las dos |
| F. fin estimado | El fin más tardío de sus paquetes en el Gantt, nunca antes del corte. Si la actividad no tiene paquetes de desarrollo (8.2), queda la línea base |
| F. fin real / Desvío | Último ticket cerrado. Desvío = base − real: positivo es antes de lo planeado |

Lo que se edita en `actividades-clave.csv` **antes** de correr el paso 4:

- **`avance` / `estado`**: vacíos = automático. Se cargan solo cuando el número no refleja la realidad (por
  ejemplo, trabajo hecho sin ticket). **Vaciarlos** cuando Linear se ponga al día.
- **`wbs`**: prefijos separados por espacio (`5.1 5.2`, `6.1.4`). Un prefijo que no existe en la WBS corta el script.
- **`fin_base`**: es la línea base, así que no se toca salvo que se rebaselinee el plan.

Antes del steering, comparar con la semana anterior: si una actividad retrocede (por ejemplo, de `Finaliz.`
vuelve a `En curso`), casi siempre es un ticket nuevo con `fechas=si` sobre un paquete cerrado que debería ir
con `no` (paso 2).

## Paso 6 — Verificar

```sh
npm run check
```

Los tres fallos que aparecen después de sincronizar, y qué significan:

| Falla | Qué pasó |
|---|---|
| `issues sin paquete: …` | Volver al paso 2: quedó una fila vacía |
| `dependency violations changed` | Un paquete arrancó antes que aquel del que depende. **Mirarlo, no silenciarlo**: si es real, agregarlo a `KNOWN_DEP_VIOLATIONS` con un comentario que diga por qué |
| `el bloque LINEAR coincide con el mapa` | El bloque quedó desfasado del CSV: correr de nuevo el paso 1 |

Después, abrir el Gantt y hacer clic en una épica, un paquete y un entregable: el panel de abajo tiene
que listar los issues con su estado y el avance en puntos.

```sh
python3 -m http.server 8000   # http://localhost:8000/leadership/gantt.html
```

## Paso 7 — Dejarlo registrado

Los archivos que cambian y se commitean juntos:

```
docs/planning/linear-wbs-map.csv      # las filas nuevas
docs/planning/linear-issues.csv       # el snapshot de Linear
docs/planning/actividades-clave.csv   # solo si cambiaron actividades o se pisó avance/estado
leadership/gantt.html                 # bloques linear-begin y gen-begin
leadership/steering.html              # snapshot semanal de actividades clave
docs/planning/Cronograma-y-PERT-v4.md # solo filas nuevas y estados, nunca fechas de la línea base
```

Si el paso 4 movió fechas de paquetes que ya estaban planificados, vale la pena decirlo en el commit:
es información de cronograma, no ruido.

## Para el PO: que el flujo salga barato

Un issue creado **con milestone** y **con estimate** no necesita nada más que el paso 1. Sin milestone,
el issue aparece sin épica y hay que rastrearlo a mano; sin estimate, no suma al avance de su milestone.

Después de commitear, el update semanal del proyecto en Linear se arma con [`/update-linear`](../update-linear/SKILL.md).
