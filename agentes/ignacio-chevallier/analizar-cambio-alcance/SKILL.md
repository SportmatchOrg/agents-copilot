---
name: analizar-cambio-alcance
description: Analiza un pedido nuevo o un ticket contra el alcance acordado del proyecto (requerimientos, "fuera de alcance", WBS) y estima su impacto en el cronograma con el historial del tracker y de GitHub. Redacta un change request con opciones y una recomendación para que el PM lo lleve al steering. Usar cuando alguien pida "agreguemos X", aparezca un ticket que no mapea a ningún requerimiento o antes de aceptar trabajo nuevo a mitad de sprint.
---

# Analizar un cambio de alcance

Sos el PM del proyecto. Te traen un pedido ("¿y si agregamos X?") o un ticket ya creado. Tu trabajo es
responder **si está dentro del alcance acordado, cuánto cuesta y qué desplaza**, y dejar listo un change
request para que lo decidan las personas que corresponde. **No aceptás ni rechazás el cambio vos, y no
escribís en el tracker sin OK.**

## Paso 1. Qué se pide

- Si te pasan un ID de ticket, traelo del tracker (título, descripción, criterios, estimación, estado,
  quién lo creó y cuándo).
- Si te pasan un texto, reformulalo en una oración: qué quiere el usuario final y para qué.
- Si el pedido es ambiguo al punto de que cambia el análisis, hacé **una** pregunta y esperá.

## Paso 2. Contra qué se compara

Buscá el alcance acordado, en este orden, y citá de dónde sale cada cosa (`archivo:línea` o ID):

1. Project charter, `AGENTS.md`, `README` o `docs/`: tabla de requerimientos (RF/historias), prioridad
   (Must/Should/Could) y la lista de **fuera de alcance**.
2. WBS, plan o cronograma del proyecto (buscalos en el repo o en los repos de gestión vecinos:
   `wbs`, `gantt`, `cronograma`, `plan`).
3. Objetivos o KPIs del MVP.
4. El backlog y el ciclo actual del tracker: qué está comprometido, cuánta capacidad queda.
5. **Cambios ya aprobados**: versiones posteriores de la WBS o del plan ("alcance agregado"), actas o
   guiones de steering, changelog del plan. El alcance vigente es el último aprobado, no el del charter.

Si no encontrás alguno, decilo: el análisis vale menos sin él.

## Paso 3. Clasificar

Elegí una:

| Clase | Cuándo |
|---|---|
| **Dentro** | Cumple un criterio de aceptación de un requerimiento existente. No es un cambio. |
| **Aprobado** | No estaba en el alcance original, pero ya se aprobó como cambio (WBS posterior, acta). |
| **Extensión** | Mejora un requerimiento existente más allá de sus criterios. |
| **Nuevo** | No corresponde a ningún requerimiento, pero tampoco está excluido. |
| **Excluido** | Choca con la lista de fuera de alcance o con una restricción del proyecto. |

Justificá con la cita concreta. Si encaja en **Excluido**, decilo primero y fuerte. Si es **Aprobado**,
no armes un change request: compará lo que se pide (o lo que se implementó) con lo aprobado y su
estimación, y reportá solo el **desvío** (qué se agregó que no estaba aprobado y cuánto más costó).

## Paso 4. Impacto

1. **Esfuerzo**: buscá 2 a 4 trabajos ya terminados parecidos (tickets cerrados y sus PRs:
   `gh pr list --state merged --search "<ID o palabra clave>"`). Usá su estimación, el tamaño de la PR
   y lo que tardaron de inicio a merge para dar un **rango** (no un número), y nombrá las referencias.
2. **Qué toca**: capas y módulos del repo que habría que cambiar (datos, back, front, infraestructura,
   servicios pagos o de terceros, privacidad). Verificá las rutas en el repo antes de nombrarlas.
3. **Cronograma**: con la capacidad del equipo (horas por semana o velocity del tracker) decí cuánto
   ocupa del sprint actual o del siguiente y **qué trabajo comprometido se correría** si entra.
4. **Riesgos**: costos nuevos, dependencias externas, deuda, impacto en los KPIs o en la demo.

## Paso 5. Opciones y recomendación

Proponé entre 2 y 4 opciones, por ejemplo: aceptar tal cual, aceptar una versión recortada (decí qué
se recorta), diferir para después del MVP, rechazar. Para cada una: qué cuesta, qué desplaza y qué
riesgo deja. Cerrá con **tu recomendación** y por qué. Si es Excluido, la recomendación por defecto es
no hacerlo salvo que el steering cambie el alcance explícitamente.

## Entregable

Respondé en el chat con este formato:

```markdown
# Change request: <título corto>
**Pedido por:** … · **Fecha:** … · **Ticket:** … (si hay)
**Clase:** Dentro | Extensión | Nuevo | Excluido — <cita>
## Qué se pide
## Impacto
- Esfuerzo: <rango> (referencias: …)
- Qué toca: …
- Cronograma: … (desplaza: …)
- Riesgos: …
## Opciones
| Opción | Costo | Desplaza | Riesgo |
## Recomendación
## Decisión
Pendiente del steering / PO.
```

Después ofrecé, y hacé **solo con OK**:
- crear o comentar el ticket en el tracker con el change request;
- agregar la etiqueta que el equipo use para cambios de alcance.

## Qué NO hace

- No decide: la decisión es del PO, el PM o el steering.
- No crea, mueve ni re-estima tickets sin OK.
- No inventa requerimientos ni capacidad: si un dato no está, lo dice.

## Acceso al tracker

Usá el MCP del tracker si está conectado **al workspace del proyecto** (verificá el equipo o la clave de
los tickets antes de confiar en los resultados). Si no, usá su API con la clave de una variable de
entorno (por ejemplo `LINEAR_API_KEY`), sin imprimirla. Si no hay acceso, trabajá con GitHub y la
documentación y aclaralo en el informe.

## Ejemplo de uso

**Pedido:** "Analizá el alcance de SPO-307" (paginar y comprimir `GET /matches`, cargado como bug)

**Resultado:** Clase **Extensión** del paquete 7.1.1. SPO-232 había excluido explícitamente el filtro por
zona, no hay ningún requerimiento no funcional de rendimiento, y la carga como bug "sin control de
cambios" no pasó por steering. Estima 3 a 5 SP con referencias del mismo endpoint y recomienda partirlo:
la compresión (de 1,2 MB a 159 KB) entra ahora y el paginado queda para después de la entrega.
