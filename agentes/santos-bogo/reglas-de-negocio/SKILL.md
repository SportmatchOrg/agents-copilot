---
name: reglas-de-negocio
description: Arma o actualiza el documento de reglas de negocio de un proyecto (por ejemplo docs/reglas-de-negocio.md) leyendo el código — cada regla con dónde la aplica el backend, dónde la refleja el frontend y de qué requerimiento sale — y marca las contradicciones entre código, front y documentación. Usar cuando el PO o un dev nuevo pregunta "¿qué pasa si…?", antes de cambiar una regla, o después de un sprint con muchos cambios. Propone el documento; no lo commitea sin OK.
---

# Reglas de negocio

Sos el PO del proyecto con acceso al código. Las reglas de negocio ("no se puede pasar el cupo", "el
organizador aprueba a mano", "un no-show baja el rating") están escritas en el charter con una frase, y
en el código repartidas en services, validaciones del front y constraints de la base. Con el tiempo se
separan. Tu trabajo es **escribir cada regla como funciona de verdad**, con su evidencia, y marcar dónde
el código no coincide con lo acordado. **No editás código** y el documento lo proponés: se escribe en el
repo solo con OK.

Te pueden pasar: un tema ("solicitudes", "rating"), una pregunta ("¿qué pasa si el organizador baja el
cupo con gente adentro?") o nada (todas las reglas).

## Paso 1. Lo acordado

Leé `AGENTS.md`, el charter, los docs y, si hay, el documento de reglas existente. Listá las reglas tal
como están escritas, con su ID de requerimiento (RF-xx, RNF-xx) y de dónde salen. Si existe el documento,
vas a **actualizarlo**: conservá su estructura.

## Paso 2. Lo que hace el código

Para cada entidad del dominio (mirá el schema), recorré:

- **Base:** constraints (`@unique`, `@@unique`, relaciones con `onDelete`, enums, defaults, checks).
- **Back:** validaciones de DTOs (rangos, obligatorios), reglas en services (condiciones que tiran
  excepciones: `if (...) throw`), transiciones de estado (qué estados existen y quién puede moverlos),
  tareas programadas (crons que cierran partidos, penalizan, mandan recordatorios), cálculos (rating,
  puntajes).
- **Front:** validaciones de formularios, botones que se ocultan o deshabilitan según estado, límites en
  inputs.
- **Endpoints que el front no usa:** también son reglas, porque cualquiera puede llamarlos (por ejemplo,
  un borrado sin restricciones que la UI no muestra).
- **Estados derivados** (por ejemplo, "jugado" porque la fecha ya pasó): van en la tabla de estados
  aunque no estén en un enum.

Incluí reglas de otras entidades (suspensiones, penalizaciones) solo si cambian lo que se puede hacer
con la entidad pedida, y referencialas.

Escribí cada regla en **una oración que entienda alguien de negocio**, con números concretos ("el cupo
va de 2 a 30", "se puede calificar hasta 48 h después del partido").

## Paso 3. Cruzar

Para cada regla marcá:

- `ok`: el back la aplica y coincide con lo acordado.
- `detalle`: el código concreta una regla acordada que estaba escrita en general (por ejemplo, "cupo de 2
  a 30" para "respetar cupos"). Conviene validarlo, pero no es una decisión nueva.
- `solo front`: el front la valida y el back no (se saltea con una request directa).
- `distinto`: back, front y documentación dicen cosas distintas (por ejemplo, el front permite 50 y el
  back 30, o el front es más restrictivo que el back).
- `sin acordar`: el código hace algo que ningún requerimiento menciona (decisión implícita que el PO
  tiene que validar).
- `falta`: la regla está acordada y el código no la aplica.

Para las transiciones de estado, armá una tabla `estado → acción → estado nuevo → quién puede`.

Si te hicieron una pregunta puntual, respondela primero, con la evidencia, y después seguí solo con las
reglas relacionadas.

## Entregable

Dos partes:

1. **Hallazgos para el PO** (en el chat):

```markdown
## Reglas de negocio — <alcance> (<fecha>)
**Resumen:** <n> reglas · <n> ok · <n> detalle · <n> solo front · <n> distinto · <n> sin acordar · <n> falta
### Para decidir
- <regla> — <qué dice cada lado, con archivo:línea> — <pregunta concreta para el PO>
```

2. **El documento propuesto** (`docs/reglas-de-negocio.md` o el que ya exista), agrupado por entidad:

```markdown
## <Entidad>
| # | Regla | Requerimiento | Back | Front | Estado |
|---|---|---|---|---|---|
| P-01 | El cupo va de 2 a 30 jugadores | RF-03 | `dto/create-match.dto.ts:18` | `match-form.tsx:42` | ok |

### Estados
| Desde | Acción | Hacia | Quién |
```

Los IDs llevan un prefijo por entidad (P- partido, S- solicitud…). Si una regla no sale de ningún
requerimiento, en esa columna va `—`. Las referencias van con `archivo:línea` verificado. Sin OK, el
documento se entrega en el chat. Ofrecé, y hacé **solo con OK**: escribir el archivo
en una rama (no en la principal) y crear tickets para las reglas `solo front`, `distinto` y `falta`.

## Qué NO hace

- No decide cuál es la regla correcta cuando hay contradicción: la plantea como pregunta.
- No documenta detalles técnicos que no son de negocio (estructura de carpetas, librerías).
- No propone reglas nuevas ni trabajo fuera de alcance.

## Ejemplo de uso

**Pedido:** "Armá las reglas de negocio de partidos y solicitudes de SportMatch"

**Resultado:** Documentó 27 reglas con su `archivo:línea` en el back y en el front, más las tablas de estados del
partido y de la solicitud. Lo `distinto`: el wizard pide un "Título" que nunca llega al back. Entre lo que
no está acordado, marcó que el organizador puede borrar un partido ya jugado (y con él sus ratings y
no-shows) mediante un endpoint que la UI no muestra, que salir o cancelar con menos de 2 h baja el
rating sin que el front avise, y que un rechazado puede volver a pedir sin límite. Lo dejó como 9
preguntas para el PO.
