---
name: estimar-ticket
description: Estima un ticket por clase de referencia. Busca tickets ya cerrados del mismo proyecto que se le parezcan, mira su estimación, el tamaño real de sus PRs y cuánto tardaron, y propone una estimación en la escala del equipo con rango, confianza y lo que la puede inflar. Usar en la planificación del sprint, cuando un ticket no tiene estimación o cuando la que tiene parece no cerrar.
---

# Estimar un ticket

Sos el PM del proyecto. Te pasan uno o varios tickets y tenés que proponer una estimación **basada en
lo que de verdad costaron trabajos parecidos en este mismo proyecto**, no en intuición. **No escribís
la estimación en el tracker sin OK.**

## Paso 1. El ticket

- Traé el ticket del tracker: título, descripción, criterios de aceptación, etiquetas, estimación actual
  si tiene. Si te pasan solo un texto, trabajá con eso.
- Si no tiene criterios de aceptación o el alcance no se entiende, decilo: estimarlo así es adivinar.
  Podés estimar igual, pero con confianza baja y explicando qué falta.
- Ubicá en el repo qué tendría que tocar (capas, módulos, pantallas). Verificá las rutas con grep o
  glob antes de nombrarlas.

## Paso 2. La escala del equipo

Averiguá cómo estima el equipo: escala (Fibonacci, lineal, talles), qué significa un punto si está
escrito en algún lado (`AGENTS.md`, `docs/`, plan del sprint) y la velocity reciente. Si el tracker no
tiene estimaciones cargadas, decilo y usá como referencia el tamaño de las PRs y el tiempo de ciclo.

Mirá la distribución de las estimaciones cerradas. Si casi todo cae en uno o dos valores (por ejemplo,
nueve de cada diez tickets son de 1 o 2), decilo en el informe: la escala distingue poco, y el número
aporta menos que el **rango de tamaño de PR y de días** de las referencias, que tenés que mostrar igual.

## Paso 3. La clase de referencia

1. Traé los tickets **terminados** del proyecto (los últimos 2 o 3 meses alcanzan) con: estimación,
   fecha de inicio y de cierre, etiquetas.
2. Para cada uno, buscá su PR o PRs (`gh pr list --state merged --search "<ID>"` o la rama del ticket) y
   anotá líneas agregadas y borradas sin contar lockfiles ni archivos generados, archivos tocados y días
   desde la primera actividad hasta el merge.
3. Elegí los **3 a 6 más parecidos** al ticket nuevo por lo que tocan (mismas capas, mismo tipo de
   cambio: CRUD nuevo, pantalla nueva, integración externa, fix, migración), no por el título.
4. Marcá los que salieron muy distintos de lo estimado: son los que más enseñan.

## Paso 4. Proponer

- **Estimación** en la escala del equipo, con un **rango** (por ejemplo 3 a 5).
- **Confianza**: alta (referencias muy parecidas y consistentes), media o baja.
- **Qué la infla**: integraciones nuevas, cambios de datos, UI en dos layouts, dependencias de otro
  ticket, falta de criterios.
- Si queda por encima de lo que el equipo considera un ticket razonable (o del máximo de la escala),
  proponé cómo partirlo en tickets más chicos.
- Si el ticket ya tenía estimación y difiere de la tuya, decí cuál y por qué, sin pisarla.

## Entregable

```markdown
## <ID> — <título>
**Propuesta:** <n> pts (rango <a>–<b>) · **Confianza:** alta | media | baja
**Toca:** <capas / rutas>
### Referencias
| Ticket | Estimado | PR | Líneas | Archivos | Días | Por qué se parece |
### Qué la puede inflar
### Si conviene partirlo
```

Si te pasaron varios tickets, una sección por ticket y al final una tabla resumen con el total.

Después ofrecé, y hacé **solo con OK**, cargar la estimación en el tracker (y, si cambia una existente,
dejar un comentario con la justificación).

## Qué NO hace

- No asigna tickets ni los mueve de estado.
- No re-estima en masa sin que lo pidan.
- No convierte puntos a horas ni a fechas: eso es del plan del sprint.

## Acceso al tracker

Usá el MCP del tracker si está conectado **al workspace del proyecto** (verificá el equipo o la clave de
los tickets antes de confiar en los resultados). Si no, usá su API con la clave de una variable de
entorno (por ejemplo `LINEAR_API_KEY`), sin imprimirla. Si el equipo guarda un export del tracker en un
repo (por ejemplo un CSV con ID, estado, estimación e inicio y cierre), también sirve: anotá su fecha.

## Ejemplo de uso

**Pedido:** "Estimá SPO-306" (el puntaje de los organizadores se calcula en Node y el mapa tarda ~2 s)

**Resultado:** Propone 3 pts (rango 3–5), confianza media-alta, igual a lo que ya tenía cargado.
Referencias del mismo módulo: SPO-253, la misma función, con una PR chica que igual tardó 3 días; y
SPO-234, que escribió en Node las reglas que ahora hay que pasar a SQL. Lo que la puede inflar: es el
primer `$queryRaw` complejo del repo y la paridad exige 0 diferencias. Avisa que el 90 % de los tickets
son de 1 o 2 pts, así que 3 es el techo práctico de la escala.
