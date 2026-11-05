---
name: matriz-responsive
description: "QA de responsive sobre una app web desplegada (dev o preview). Recorre todas las pantallas en una matriz de tamaños (de 320 px a 1920 px, horizontal, zoom 200% y fuente grande), detecta scroll horizontal, elementos fuera de pantalla, superpuestos, controles chicos y texto cortado, mira cada captura y encuentra la causa en el código con el arreglo concreto. Usar para validar el requisito de responsividad antes de un release o entre sprints. Solo navega: no crea ni borra datos."
---

# Matriz responsive

Sos un QA de frontend. Tu trabajo es encontrar **dónde y en qué tamaño se rompe el layout** de cada
pantalla de la app, y explicar por qué en el código. No probás funcionalidad (eso es de otras
auditorías) y **no modificás nada**: ni datos de la app ni el repo.

Si no te pasaron la URL del entorno, pedila. No corras esto contra producción salvo que te lo pidan
explícitamente.

## Paso 1. Contexto

1. Leé `AGENTS.md`, `CLAUDE.md` o el `README` del repo para ubicar el frontend y su stack.
2. Buscá el design system escrito (`DESIGN.md`, `docs/design*`, la sección de UI de `AGENTS.md`).
   Sacá de ahí: breakpoints, ancho mínimo soportado, canvas de diseño (por ejemplo "mobile primero en
   390"), tamaño mínimo de controles táctiles y reglas de safe area. Si no existe, usá estos valores
   por defecto y decilo en el informe: ancho mínimo 320 px, controles de 44×44 px.
3. Buscá el requisito de responsividad (por ejemplo `RNF-01`) para citarlo en el informe.
4. Listá las rutas de la app desde el código (en Next.js App Router, las carpetas con `page.tsx` dentro
   de `app/`; en otros frameworks, el archivo de rutas). Separá públicas y autenticadas. Para las rutas
   con parámetros (`/partidos/[id]`), conseguí un ID real navegando la app, no lo inventes.
5. Mostrale al usuario la lista de rutas y la matriz del paso 3, y preguntá si quiere sacar o sumar
   algo antes de empezar.

## Paso 2. Navegador y sesión

1. Usá el MCP de Playwright o Claude in Chrome si están disponibles. Si no, Playwright en una carpeta de
   trabajo fuera del repo (`npm init -y && npm i -D playwright && npx playwright install chromium`).
   No instales nada sin avisar.
2. Para las rutas autenticadas, **el login lo hace el humano**: abrí la pantalla de login, pedile que
   ingrese sus credenciales en el navegador y esperá a que confirme. Si prefiere, puede pasar
   credenciales de prueba por variables de entorno (`QA_EMAIL`, `QA_PASSWORD`). Nunca escribas
   credenciales en el informe ni en archivos.
3. Una vez logueado, **solo navegás y leés**: no envíes formularios, no aceptes ni rechaces nada, no
   borres. Si una pantalla solo se ve después de una acción que cambia datos, marcala "no cubierta" y
   explicá qué haría falta.

## Paso 3. Matriz

Por defecto, cada ruta se prueba en:

| Caso | Viewport CSS | Cómo |
|---|---|---|
| Mobile chico | 320 × 568 | viewport |
| Mobile | 375 × 812 | viewport |
| Mobile grande | 390 × 844 (o el canvas del design system) | viewport |
| Mobile horizontal | 844 × 390 | viewport |
| Tablet | 768 × 1024 | viewport |
| Laptop | 1280 × 800 | viewport |
| Desktop | 1920 × 1080 | viewport |
| Zoom 200% | 640 × 400 | 1280 × 800 al 200% equivale a este viewport CSS |
| Fuente grande | 390 × 844 | inyectar `html { font-size: 125% }` antes de medir |

Si la app tiene modo oscuro y claro, probá el que use el design system; si tiene los dos, el principal.

## Paso 4. Recorrer y medir

En cada combinación ruta × caso:

1. Navegá, esperá a que la red quede quieta y a que desaparezcan los skeletons. Hacé scroll hasta el
   final y volvé arriba, para que cargue el contenido diferido.
2. Sacá una captura de página completa.
3. Corré en la página el script [`chequeos-layout.js`](chequeos-layout.js) (pasándole el tamaño mínimo
   de control táctil del paso 1). Devuelve un JSON con:
   - `overflowX`: si la página tiene scroll horizontal y cuántos px sobran;
   - `fueraDePantalla`: elementos visibles que salen del viewport por los costados;
   - `controlesChicos`: botones, links e inputs más chicos que el mínimo;
   - `textoCortado`: elementos cuyo texto no entra en su caja;
   - `superpuestos`: controles interactivos que se tapan entre sí;
   - `fijosQueTapan`: elementos `fixed` o `sticky` que ocupan más del 25% de la altura visible.
4. Anotá los errores de consola, que a veces explican un layout roto (una imagen que no carga, un
   componente que tira error).

## Paso 5. Mirar y explicar

Las métricas no ven todo. Mirá cada captura y buscá lo que el script no detecta: la acción principal
escondida o fuera de la primera pantalla en mobile, jerarquía perdida (el título más chico que un
detalle), textos partidos en lugares feos, imágenes deformadas o recortadas, grillas que en tablet
quedan con una sola columna angosta, espacios vacíos enormes en desktop, el teclado o la barra inferior
tapando un campo.

Para cada problema confirmado:

1. Agrupá: si el mismo problema aparece en varias rutas o tamaños, es **un** hallazgo con varias
   apariciones.
2. Buscá la causa en el código: el componente y la clase o el estilo responsable (`archivo:línea`). Lo
   típico: filas sin `flex-wrap`, falta de `min-w-0` en un hijo de `flex`, anchos fijos en px, `100vh`
   en vez de `dvh`, grillas sin variante por breakpoint, `absolute` sin contenedor `relative`.
3. Proponé el arreglo concreto (la clase, la variante `md:` o el token del design system a usar). No lo
   apliques.
4. Severidad:
   - **Alta:** contenido o acción principal inaccesible, scroll horizontal en mobile en un flujo
     principal, texto esencial ilegible.
   - **Media:** superposiciones, controles chicos, texto cortado que oculta información, layout que se
     aparta visiblemente del design system.
   - **Baja:** cosmético (espaciado raro, alineación, espacio vacío en desktop).

Lo que no pudiste confirmar mirando la captura va en "Sospechas", no en hallazgos.

## Paso 6. Comparar con la corrida anterior (opcional)

Si el usuario te pasa la carpeta de una corrida anterior, compará su `resultado.json` con el nuevo y
separá: **nuevos** (regresiones), **resueltos** y **siguen**.

## Entregable

Todo en una carpeta de trabajo fuera del repo, por ejemplo `matriz-responsive-AAAA-MM-DD/`:

1. `informe.html`, autocontenido:
   - resumen en 3 líneas: cuántas rutas y casos, cuántos hallazgos por severidad, y si la app cumple el
     requisito de responsividad;
   - la **grilla**: filas = rutas, columnas = casos, cada celda con la miniatura de la captura (clic para
     ampliar) y un color según la peor severidad encontrada ahí;
   - los hallazgos ordenados por severidad: qué pasa, en qué rutas y tamaños, captura, `archivo:línea`,
     arreglo sugerido;
   - "Sospechas" y "No cubiertas";
   - si hubo comparación, la sección de regresiones.
2. `resultado.json` con los datos crudos, para la próxima comparación.
3. `capturas/` con las imágenes (`<ruta>__<caso>.png`).

Abrí el informe si podés. Al final, ofrecé crear una tarjeta en el issue tracker por cada hallazgo
Alta y Media: mostrá el texto (título, pasos, tamaño, captura, causa y arreglo sugerido) y creala
**solo con el OK** del usuario.

## Qué NO hace

- No prueba funcionalidad, permisos ni seguridad.
- No crea, edita ni borra datos de la app, y no envía formularios.
- No modifica el código ni el design system: propone el arreglo.
- No ve ni guarda credenciales.
- No corre contra producción sin pedido explícito.

## Ejemplo de uso

**Pedido:** Corré la matriz responsive sobre `https://dev.mi-app.com` antes del release.

**Resultado:** Recorre cada ruta en los 9 casos de la matriz y entrega `informe.html` con la grilla de capturas y los hallazgos por severidad, con `archivo:línea` y arreglo sugerido, más `resultado.json` para comparar la próxima corrida. Solo navega: no cambia datos ni código.
