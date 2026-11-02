# Auditoría de bugs · SportMatch

Sos un ingeniero senior de QA. Tu tarea es usar la app SportMatch con Playwright y encontrar **qué falla y qué tan importante es**, pensando en que la app se va a mostrar en una demo en vivo. El código se lee solo para explicar por qué falla lo que encontraste y para revisar la seguridad. **No arreglás nada.**

## Contexto

- Repo de la app: `~/Projects/university/sportmatch` (`front/` Next.js 16 + React 19 + Tailwind 4; `back/` NestJS 11 + Prisma 7 + PostgreSQL; auth con Firebase). Leé `AGENTS.md` para ubicarte en la estructura.
- Entorno a auditar: **dev**, `https://sportmatch-git-dev-sportmatch2.vercel.app`. Actualizá el repo local para que el código coincida con lo desplegado (`git fetch && git switch dev && git pull`) y anotá el commit en el informe.
- La primera respuesta del backend puede tardar varios segundos porque la base se suspende por inactividad. Eso no es un bug.
- Bugs ya conocidos. No los reportes como nuevos: si te cruzás con uno, va en la sección "Ya reportados" con su ID.
  - `~/Projects/university/sportmatch-linktree/ISSUES.md`
  - `~/Projects/university/sportmatch-linktree/sportmatch-bugs-2026-10-29/bugs.csv`
- Requerimientos: RF-01 Auth · RF-02 Perfil · RF-03 Creación de partidos · RF-04 Swipe y mapa · RF-05 Solicitudes para unirse · RF-06 Ratings y no-show.

## Reglas

1. **No modificás el repo.** No editás archivos ni hacés commits. Los scripts de Playwright, las capturas y el informe van en `~/sportmatch-audit-<fecha>/`.
2. **Cada hallazgo necesita evidencia**: pasos para reproducirlo, una captura y el error de consola o de red si lo hay. Lo que no puedas reproducir va en "Sospechas".
3. **Cuentas**: creá tus propias cuentas en el signup (dos como mínimo: **A** crea partidos, **B** se une). Guardá las credenciales solo en memoria o en un archivo dentro de la carpeta de auditoría, nunca en el informe.
4. **Datos**: todo lo que crees lleva el prefijo `[AUDIT]` en el título o el nombre. No hace falta borrarlo.

## Cómo probar

Usá el MCP de Playwright si está disponible. Si no, instalá Playwright en la carpeta de auditoría (`npm init -y && npm i -D playwright && npx playwright install chromium`).

En **todas** las pantallas:
- Registrá los errores de consola y todas las respuestas 4xx/5xx (`page.on('console')`, `page.on('response')`).
- Recorré cada flujo en **375 px, 1280 px y 1440 px**. Buscá overflow horizontal, texto cortado, elementos superpuestos, scrollbars duplicadas y controles inalcanzables.
- Sacá una captura de cada bug.

## Flujos

Usá A y B en contextos de navegador separados. Después de cada paso que cambie datos, recargá y verificá que lo que se ve coincide con lo que debería estar guardado, en las pantallas de los dos usuarios (`/mis-partidos`, el detalle del partido, el buscador).

1. **RF-01 Auth**: signup, login, login con credenciales incorrectas, forgot-password, logout, entrar a una ruta protegida sin sesión y recargar con la sesión iniciada.
2. **RF-02 Perfil**: editar, guardar y recargar para confirmar que persistió. Probá campos vacíos y textos muy largos.
3. **RF-03 Crear y editar partido** (A): el wizard completo, incluido el asistente de IA. Probá fecha pasada, cupo 0, doble clic en "crear", botón atrás y recarga a mitad del wizard. Editá el partido y verificá los cambios en el detalle.
4. **RF-04 Descubrimiento** (B): buscador, filtros (solos y combinados), swipe y mapa. ¿Aparece el partido de A? ¿Los resultados son coherentes con los filtros?
5. **RF-05 Solicitudes**: B solicita unirse, A ve la solicitud y la acepta. Después B se baja y verificá que deja de figurar como aceptado. Probá también solicitar unirse a un partido lleno, a un partido propio y dos veces al mismo.
6. **RF-06 Ratings y no-show**:
   1. Primero buscá en `back/src/` la anticipación mínima para crear un partido y su duración mínima.
   2. Si con eso la espera total hasta que el partido termine es de **una hora o menos**: A crea un partido que empiece lo antes posible, B se une, A lo acepta, esperás a que termine y los dos se califican. Probá también calificar dos veces y calificar sin haber participado, y el no-show si la app lo expone.
   3. Si la espera es de **más de una hora**: usá la cuenta de `AUDIT_RATER_EMAIL` y `AUDIT_RATER_PASSWORD`, que ya participó en partidos terminados de dev.
   4. Si esas variables no están: RF-06 queda como **"no probado en vivo"**. Revisá en el código las reglas de rating y reportá lo que veas como sospecha.

## Seguridad

Para cada endpoint que modifica datos (editar o borrar un partido, aceptar o rechazar solicitudes, bajarse, calificar):

1. Leé en `back/src/` el controller y el service y fijate si se verifica que el usuario autenticado tiene permiso sobre ese recurso.
2. Confirmalo en vivo: con la sesión de **B**, repetí con `page.request` las llamadas que solo puede hacer **A** (usá los mismos endpoints y payloads que viste en la pestaña de red) y anotá qué responde el backend.

Revisá también si el backend acepta inputs que el front bloquea (cupo negativo, fecha pasada, campos extra) mandándolos directo a la API.

## Severidad

| Nivel | Criterio |
|---|---|
| **Crítica** | Rompe un flujo de punta a punta, muestra un error en pantalla (crash, pantalla en blanco, spinner infinito, 500 sin manejar) o pierde o corrompe datos |
| **Alta** | El flujo se completa, pero con algo visiblemente mal: un dato incorrecto, un estado que no se actualiza o una pantalla rota en algún viewport |
| **Media** | Molesta o se ve mal, pero no confunde a quien está mirando la demo |
| **Baja** | Cosmético |

Los problemas de seguridad van en su propia sección y no usan esta escala.

## Causa en el código

Para cada hallazgo Crítico o Alto, buscá en `front/src/` o `back/src/` la causa probable y citala con `archivo:línea`. Si no la encontrás, decilo. No revises deuda técnica que no esté relacionada con una falla.

## Entregable

Escribí `~/sportmatch-audit-<fecha>/informe.md` con:

1. **Resumen**: commit auditado, cuentas creadas (solo los emails), qué se probó y qué no, y los conteos por severidad.
2. **Tabla de hallazgos**, ordenada por severidad:

   | ID | Severidad | RF | Pantalla y viewport | Qué falla | Captura |

3. **Detalle de cada Crítica y Alta**: qué pasa, pasos para reproducirlo, resultado esperado y obtenido, evidencia (captura, consola, red) y causa probable con `archivo:línea`.
4. **Seguridad**: por cada endpoint, si el backend valida o no el permiso, con la respuesta que obtuviste en vivo y `archivo:línea`. Para cada problema confirmado, los mismos campos que el punto 3.
5. **Sospechas** que no pudiste reproducir.
6. **Ya reportados**: lo que encontraste que coincide con un bug existente, con su ID.

Antes de escribir el informe, reproducí otra vez cada hallazgo Crítico, Alto y de Seguridad. Lo que no se repita pasa a "Sospechas".
