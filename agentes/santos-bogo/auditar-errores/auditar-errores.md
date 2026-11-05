---
description: Audita el manejo de errores de punta a punta en una app web con API REST — errores del ORM que terminan en 500, throws genéricos en la lógica de negocio, códigos HTTP mal elegidos y pantallas que no le muestran al usuario qué pasó — y entrega una matriz error → respuesta → mensaje en pantalla con archivo:línea. Pensado para NestJS + Prisma + Next.js, pero sirve para otros stacks. No edita código.
argument-hint: "[módulo | número-de-PR | rama] (vacío = todo el repo)"
---

# Auditar errores

Sos el tech lead responsable de que, cuando algo falle, el usuario entienda qué pasó y el equipo sepa
dónde mirar. Los errores mal manejados son los bugs más caros: un 500 donde debería ir un 409, un
"Algo salió mal" donde el usuario podía corregir el dato, o un error que se traga en silencio.
**No editás código.**

Alcance: $ARGUMENTS (si está vacío, todo el repo). Un módulo incluye toda su carpeta en el back y las
pantallas del front que llaman a sus endpoints (buscá la ruta REST en el front).

## Paso 1. Cómo maneja errores el proyecto hoy

1. Leé `AGENTS.md`/`README` para ubicar back y front.
2. **Back:** buscá filtros globales (`@Catch`, `ExceptionFilter`, `useGlobalFilters`), helpers que
   traducen errores del ORM (por ejemplo un mapa de códigos `P2002`, `P2025`), interceptores y el
   `ValidationPipe`. Anotá qué cubren y qué no. Si hay un helper que traduce códigos, anotá qué códigos
   recibe **cada llamada**: los que no se le pasan siguen terminando en 500.
3. **Front:** buscá el cliente HTTP (cómo convierte una respuesta no-2xx en error), los lugares donde se
   muestran errores (toasts, mensajes en formularios, error boundaries `error.tsx`, `onError` de
   mutaciones) y si hay un diccionario de mensajes.

Escribí en cinco líneas "la política actual". Todo lo que sigue se mide contra eso.

## Paso 2. Back: de dónde sale cada error

Recorré los services y repositories del alcance:

- **Errores del ORM sin traducir.** Con Prisma, los típicos: `P2002` (único duplicado → 409),
  `P2025` (registro no encontrado en `update`/`delete` → 404 o 409), `P2003` (FK → 400/409). Para cada
  `update`, `delete`, `create` con relaciones o `findUniqueOrThrow`, preguntate qué pasa si falla y si
  algo lo traduce. Si no, termina en 500.
- **Carreras:** para cada `update`/`delete` por id, preguntate qué otra acción (del mismo usuario en otra
  pestaña, o de otro usuario) puede borrar o cambiar esa fila entre la lectura y la escritura.
- **`throw new Error(...)` genérico** en lógica de negocio: Nest lo convierte en 500. Debería ser una
  `HttpException` con el código correcto.
- **Código HTTP equivocado:** 400 para "no tenés permiso" (debería ser 403), 404 para "partido lleno"
  (409), 500 para validaciones, o el mismo estado con códigos distintos en endpoints hermanos.
- **Errores tragados:** `catch {}` vacío, `catch` que loguea y devuelve `null` o `[]` como si nada. Si es
  intencional y está explicado (por ejemplo, una notificación que falla después de guardar), marcalo ok.
- **Mensajes que filtran internos:** stack traces, SQL, nombres de tablas o datos de otro usuario en el
  `message`.
- **Llamadas externas** (IA, storage, mails, push) sin timeout ni manejo de caída.

## Paso 3. Front: qué ve el usuario

Para cada error del paso 2 que puede llegar al front, seguí la llamada:

- ¿Se muestra algo? ¿El mensaje sirve para actuar ("Ya pediste unirte a este partido"), es genérico o
  es **incorrecto** (por ejemplo, "el partido está lleno" para cualquier 409)? Un mensaje falso es peor
  que uno genérico.
- ¿La UI deja llegar a ese error (botón visible, acción posible) o ya lo impide?
- ¿El mensaje del back está en otro idioma que la UI y se muestra tal cual?
- ¿El front compara textos literales del back (frágil) en vez del código HTTP?
- ¿Qué pasa con 401 (sesión vencida), errores de red y timeouts?
- ¿Los formularios marcan el campo con error o solo muestran un toast?
- ¿Hay `error.tsx`/error boundary para errores de render?

## Paso 4. Probar uno o dos (opcional)

Si hay un entorno **local** levantado, podés reproducir uno o dos errores con `curl` (por ejemplo, pedir
unirse dos veces) para confirmar el código. Nunca contra producción ni bases compartidas.

## Entregable

```markdown
## Errores — <alcance> (<fecha>)
**Política actual:** <cinco líneas>
**Resumen:** <n> terminan en 500 · <n> código incorrecto · <n> mensaje incorrecto · <n> sin mensaje útil · <n> tragados

### Matriz
| Situación | Dónde se produce | Respuesta hoy | Debería | Qué ve el usuario | Prioridad |
|---|---|---|---|---|---|
| <situación de usuario> | `<archivo>:<línea>` | 500 | 409 | "Algo salió mal" | alta |

### Lo que está bien
### Detalle de los de prioridad alta
### Propuesta de política (si falta una)
```

Priorizá: **alta** si se llega con un uso normal **y** termina en 500, muestra un mensaje falso o deja al
usuario trabado; **media** si se llega con un uso normal y el mensaje es solo genérico, o si una carrera
da 500; **baja** si solo afecta a admins, es un caso teórico o la UI ya lo impide.

Ofrecé, y hacé **solo con OK**: un ticket por cada alta o un comentario en la PR.

## Qué NO hace

- No revisa seguridad (permisos, accesos indebidos): para eso hay otras piezas.
- No agrega logging ni monitoreo nuevo: si falta, lo menciona.
- No reescribe los mensajes de UI: los marca y sugiere el texto.

## Ejemplo de uso

**Pedido:** `/auditar-errores join-requests`

**Resultado:** El manejo es prolijo: hay un helper que traduce P2002 y P2025 y el front pasa todo a español. Igual
encontró tres problemas. El panel del organizador dice "el partido está lleno" ante cualquier 409 al
aceptar, aunque la solicitud ya estuviera resuelta. Si el jugador cancela justo cuando lo aceptan, el
back devuelve 500, porque ese catch solo mapea P2002. Y "el partido ya se jugó" es 400 en solicitudes y
409 en invitaciones. Propuso que el back mande un `code` estable por error, como ya hace con la cuenta
bloqueada, en vez de que el front compare textos en inglés.
