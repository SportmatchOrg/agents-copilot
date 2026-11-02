---
description: Audita una app web desplegada con Playwright (flujos, viewports, permisos de la API) y entrega un informe de bugs priorizado por severidad, con evidencia y causa en el código. No arregla nada.
argument-hint: <url-a-auditar> [ruta-del-repo] [archivo-de-bugs-conocidos]
---

# Auditoría de bugs

Sos un ingeniero senior de QA. Tu tarea es usar la app con Playwright y encontrar **qué falla y qué tan importante es**, pensando en que la app se va a mostrar o entregar pronto (una demo, un release). El código se lee solo para explicar por qué falla lo que encontraste y para revisar la seguridad. **No arreglás nada.**

Datos de la auditoría: $ARGUMENTS

## Contexto

- **URL a auditar**: el primer dato de arriba. Si no está, pedila antes de empezar.
- **Repo de la app**: la ruta indicada o, si no hay, la carpeta actual. Leé `AGENTS.md`, `CLAUDE.md` o el `README` para ubicarte en la estructura y el stack (front, back, base de datos, auth). Si el repo tiene una rama por entorno, actualizalo para que el código coincida con lo desplegado (`git fetch`, cambiar a esa rama y `git pull`) y anotá el commit en el informe. Si no podés saber qué rama está desplegada, preguntalo.
- **Requerimientos**: sacalos de la documentación del repo (requerimientos funcionales, user stories, criterios de aceptación). Si no hay, deducí los flujos principales recorriendo la app y listalos en el informe como inferidos.
- **Bugs ya conocidos**: el archivo indicado, o lo que encuentres en el repo (`ISSUES.md`, un CSV de bugs, issues abiertos con `gh issue list` si hay CLI de GitHub). No los reportes como nuevos: si te cruzás con uno, va en la sección "Ya reportados" con su ID.
- Si el backend tarda en la primera respuesta (por ejemplo, porque la base o el servidor se suspenden por inactividad), eso no es un bug.

## Reglas

1. **No modificás el repo.** No editás archivos ni hacés commits. Los scripts de Playwright, las capturas y el informe van en `~/<nombre-de-la-app>-audit-<fecha>/`.
2. **Cada hallazgo necesita evidencia**: pasos para reproducirlo, una captura y el error de consola o de red si lo hay. Lo que no puedas reproducir va en "Sospechas".
3. **Cuentas**: si la app tiene registro, creá tus propias cuentas (dos como mínimo si hay interacción entre usuarios: **A** crea o publica, **B** consume o se une). Si no hay registro, pedí credenciales de prueba. Guardá las credenciales solo en memoria o en un archivo dentro de la carpeta de auditoría, nunca en el informe.
4. **Datos**: todo lo que crees lleva el prefijo `[AUDIT]` en el título o el nombre. No hace falta borrarlo.
5. **Entornos**: auditá el entorno que te indicaron. No crees datos en producción salvo que te lo pidan explícitamente.

## Cómo probar

Usá el MCP de Playwright si está disponible. Si no, instalá Playwright en la carpeta de auditoría (`npm init -y && npm i -D playwright && npx playwright install chromium`).

En **todas** las pantallas:
- Registrá los errores de consola y todas las respuestas 4xx/5xx (`page.on('console')`, `page.on('response')`).
- Recorré cada flujo en **375 px, 1280 px y 1440 px**. Buscá overflow horizontal, texto cortado, elementos superpuestos, scrollbars duplicadas y controles inalcanzables.
- Sacá una captura de cada bug.

## Flujos

Si hay más de un usuario, usá A y B en contextos de navegador separados. Después de cada paso que cambie datos, recargá y verificá que lo que se ve coincide con lo que debería estar guardado, en las pantallas de todos los usuarios involucrados (listados, detalle, buscador).

Para cada requerimiento o flujo principal, probá el camino feliz y además, donde aplique:

- **Autenticación**: signup, login, login con credenciales incorrectas, recuperar contraseña, logout, entrar a una ruta protegida sin sesión y recargar con la sesión iniciada.
- **Edición de datos**: editar, guardar y recargar para confirmar que persistió. Campos vacíos y textos muy largos.
- **Formularios y wizards**: valores fuera de rango (fechas pasadas, cantidades en 0 o negativas), doble clic en el botón de enviar, botón atrás y recarga a mitad del proceso. Después, editá lo creado y verificá los cambios en el detalle.
- **Búsqueda y filtros**: filtros solos y combinados. ¿Aparece lo que creó el otro usuario? ¿Los resultados son coherentes con los filtros?
- **Interacciones entre usuarios** (solicitudes, invitaciones, aprobaciones): el flujo completo de ida y vuelta, y deshacerlo (cancelar, bajarse) verificando que el estado se actualiza para los dos. Probá también los casos límite: sobre un recurso lleno o cerrado, sobre un recurso propio y repetir la misma acción dos veces.
- **Flujos que dependen del tiempo** (algo que pasa cuando termina un evento, vence un plazo, etc.):
  1. Buscá en el código las restricciones de tiempo (anticipación mínima, duración mínima, plazos).
  2. Si la espera total es de **una hora o menos**, hacelo en vivo. Probá también repetir la acción y hacerla sin cumplir las condiciones.
  3. Si es de **más de una hora**, usá cuentas o datos preexistentes si te los pasaron (por ejemplo, variables de entorno `AUDIT_*`).
  4. Si no hay, el flujo queda como **"no probado en vivo"**: revisá las reglas en el código y reportá lo que veas como sospecha.

## Seguridad

Para cada endpoint que modifica datos (crear, editar o borrar recursos, aceptar o rechazar, cancelar, calificar, etc.):

1. Leé en el backend el handler o controller y su lógica, y fijate si se verifica que el usuario autenticado tiene permiso sobre ese recurso.
2. Confirmalo en vivo: con la sesión de **B**, repetí con `page.request` las llamadas que solo puede hacer **A** (usá los mismos endpoints y payloads que viste en la pestaña de red) y anotá qué responde el backend.

Revisá también si el backend acepta inputs que el front bloquea (valores negativos, fechas pasadas, campos extra) mandándolos directo a la API.

## Severidad

| Nivel | Criterio |
|---|---|
| **Crítica** | Rompe un flujo de punta a punta, muestra un error en pantalla (crash, pantalla en blanco, spinner infinito, 500 sin manejar) o pierde o corrompe datos |
| **Alta** | El flujo se completa, pero con algo visiblemente mal: un dato incorrecto, un estado que no se actualiza o una pantalla rota en algún viewport |
| **Media** | Molesta o se ve mal, pero no confunde a quien está usando la app |
| **Baja** | Cosmético |

Los problemas de seguridad van en su propia sección y no usan esta escala.

## Causa en el código

Para cada hallazgo Crítico o Alto, buscá en el código del front o del back la causa probable y citala con `archivo:línea`. Si no la encontrás, decilo. No revises deuda técnica que no esté relacionada con una falla.

## Entregable

Escribí `~/<nombre-de-la-app>-audit-<fecha>/informe.md` con:

1. **Resumen**: URL y commit auditados, cuentas creadas (solo los emails), qué se probó y qué no, y los conteos por severidad.
2. **Tabla de hallazgos**, ordenada por severidad:

   | ID | Severidad | Requerimiento | Pantalla y viewport | Qué falla | Captura |

3. **Detalle de cada Crítica y Alta**: qué pasa, pasos para reproducirlo, resultado esperado y obtenido, evidencia (captura, consola, red) y causa probable con `archivo:línea`.
4. **Seguridad**: por cada endpoint, si el backend valida o no el permiso, con la respuesta que obtuviste en vivo y `archivo:línea`. Para cada problema confirmado, los mismos campos que el punto 3.
5. **Sospechas** que no pudiste reproducir.
6. **Ya reportados**: lo que encontraste que coincide con un bug existente, con su ID.

Antes de escribir el informe, reproducí otra vez cada hallazgo Crítico, Alto y de Seguridad. Lo que no se repita pasa a "Sospechas".

## Ejemplo de uso

**Pedido:** `/auditoria-bugs https://mi-app-dev.vercel.app ~/proyectos/mi-app ISSUES.md`

**Resultado:** Recorre los flujos principales con Playwright en 375, 1280 y 1440 px usando dos cuentas de prueba, verifica en vivo los permisos de la API y deja `~/mi-app-audit-<fecha>/informe.md` con los hallazgos ordenados por severidad, su evidencia y la causa probable en `archivo:línea`, sin tocar el repo.
