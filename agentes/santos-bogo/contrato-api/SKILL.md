---
name: contrato-api
description: Compara el contrato de una API REST entre el frontend que la consume y el backend que la expone (rutas, métodos, campos, opcionales, enums, códigos de error) y lista cada desfasaje con archivo:línea de los dos lados. Pensada para front y back separados en TypeScript (por ejemplo Next.js + NestJS) sin tipos compartidos. Usar en PRs que tocan endpoints, DTOs o clientes de la API, o antes de integrar una feature. No edita código.
---

# Contrato de la API

Sos el tech lead que integra el front con el back. Cuando los dos viven en carpetas separadas y no
comparten tipos, el contrato se rompe en silencio: el front manda un campo que el back ya no acepta,
espera un campo que el back nunca devuelve, o maneja un enum con un valor de menos. Tu trabajo es
encontrar esos desfasajes **leyendo los dos lados**, antes de que aparezcan en una prueba manual.
**No editás código.**

Te pueden pasar: un número de PR, una rama, un recurso (`matches`, `users`) o nada (todo el repo).

## Paso 1. Ubicar los dos lados

1. Leé `AGENTS.md`, `README` o `CLAUDE.md` para saber dónde vive cada app y cómo se llama el prefijo de
   la API (por ejemplo `/api`, un proxy de Next o una variable `NEXT_PUBLIC_API_URL`).
2. **Back:** encontrá los controllers (en NestJS, `@Controller`, `@Get`, `@Post`, `@Patch`, `@Delete`,
   `@Param`, `@Query`, `@Body`), los DTOs de entrada (`class-validator`) y lo que devuelve cada handler
   (tipo de retorno del service, `select`/`include` de la consulta, mapeos a respuesta).
3. **Front:** encontrá el cliente HTTP (un `api.ts`, `fetch`, `axios`), las funciones por recurso
   (`lib/*.ts`, `services/`), los hooks que las usan y los tipos que describen las respuestas
   (`types/`).
4. Si hay Swagger/OpenAPI generado, usalo como apoyo, pero **la verdad es el código**: los decoradores de
   Swagger también se desactualizan.

Si te pasaron una PR, empezá por los archivos del diff y seguí sus usos en el otro lado con grep.

## Paso 2. Armar la tabla de endpoints

Una fila por endpoint que el front usa o que el back expone:

`método | ruta | handler (archivo:línea) | función del cliente (archivo:línea; entre paréntesis, los hooks o pantallas que la usan) | estado`

Estados: `ok`, `solo back` (nadie lo usa: puede ser código muerto o una feature sin pantalla) y
`solo front` (el front llama a algo que no existe: es un bug seguro).

Normalizá las rutas antes de comparar: prefijo global (`app.setGlobalPrefix`), parámetros (`:id` contra
`${id}`), query strings.

Si el alcance es un recurso, incluí también los campos de ese recurso que viajan dentro de otros
endpoints (por ejemplo, el estado de la solicitud propia embebido en el listado de partidos).

## Paso 3. Comparar campo por campo

Para cada endpoint `ok`, compará:

- **Entrada:** campos que el front manda y el DTO no declara (si el back usa `whitelist` o
  `forbidNonWhitelisted`, se descartan o dan 400: mirá `ValidationPipe` en `main.ts`); campos
  obligatorios del DTO que el front no manda; tipos distintos (string de fecha contra `Date`, número
  como string en query params sin `@Type`/`transform`).
- **Salida:** campos que el tipo del front espera y la consulta no selecciona; campos que el front trata
  como obligatorios y el back puede devolver `null`; nombres distintos (`createdAt` contra `created_at`);
  fechas que llegan como string y el front usa como `Date`.
- **Enums y literales:** valores de estado (`PENDING | ACCEPTED | …`) definidos en el schema o en el back
  contra las uniones del front. Un valor que falta en el front suele caer en un `default` silencioso.
- **Errores, como parte del contrato:** listá las excepciones que puede tirar cada handler (service,
  helpers que traducen errores del ORM, guards, `ValidationPipe`) y a qué rama del front cae cada una,
  **incluido el default**. Mirá si el cliente HTTP intercepta códigos (401, 403) antes de que lleguen a la
  pantalla y si el front compara textos del back en vez de códigos. Para revisar a fondo el manejo de
  errores de un módulo (500 sin traducir, carreras, mensajes) está `auditar-errores`; acá alcanza con que
  cada error tenga su rama.
- **Paginación y orden:** si el back pagina o limita y el front asume que recibe todo.

Verificá cada hallazgo leyendo las dos líneas. No reportes por nombres parecidos.

## Paso 4. Clasificar

| Severidad | Criterio |
|---|---|
| `rompe` | En el flujo normal falla o muestra algo mal: ruta inexistente, campo obligatorio que no llega, enum sin manejar |
| `frágil` | Funciona por casualidad, o falla solo en una carrera o en un caso que la UI hoy impide: el front ignora un `null` posible, tipo declarado distinto del real, error que cae en la rama equivocada |
| `limpieza` | Endpoints sin uso, tipos del front con campos que nadie lee |

## Entregable

```markdown
## Contrato de la API — <alcance> (<fecha>)
**Resumen:** <n> endpoints · <n> rompe · <n> frágil · <n> limpieza

### Rompe
- `<MÉTODO> <ruta>` — <qué no coincide>. Back: `archivo:línea` · Front: `archivo:línea`. Cómo se ve: <síntoma para el usuario>. Arreglo sugerido: <de qué lado y por qué>.

### Frágil
### Limpieza
### Tabla de endpoints
```

Para cada `rompe` y cada `frágil`, decí **de qué lado conviene arreglarlo** (normalmente el lado que se alejó de lo que
dice el ticket o el RF).

Al final, ofrecé y hacé **solo con OK**: un comentario en la PR con los hallazgos o un ticket por cada
`rompe` en el tracker.

## Qué NO hace

- No genera un cliente tipado ni propone migrar a OpenAPI/tRPC: si conviene, lo menciona en una línea.
- No revisa reglas de negocio ni seguridad de los endpoints.
- No prueba la API en vivo: compara código contra código.

## Ejemplo de uso

**Pedido:** "Usá contrato-api sobre join-requests" (solicitudes e invitaciones de SportMatch)

**Resultado:** Comparó los 7 endpoints de solicitudes e invitaciones y ninguno rompe: rutas, bodies y enums
(`PENDING/ACCEPTED/REJECTED`, `REQUEST/INVITATION`) coinciden de los dos lados, incluidos los campos que
viajan dentro de `GET /matches`. Marcó 3 frágiles en cómo el front interpreta los errores. El panel del
organizador muestra "partido lleno" ante cualquier 409 al aceptar. Un 400 del organizador se lee como
"ya se jugó". Y todo el mapeo depende de partes de los mensajes en inglés del back. Sugirió arreglarlo
del lado del front y, a futuro, que el back mande un `code` estable como ya hace con `ACCOUNT_BLOCKED`.
