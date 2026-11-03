---
name: ver-pr-en-vivo
description: Levanta en local una PR o rama específica (sin checkout ni cambios en el repo), abre la app en el navegador, espera a que el humano inicie sesión si hace falta y recorre paso a paso lo que la PR implementó, con capturas y GIF como evidencia para el autor y los reviewers. Usar cuando alguien quiere ver funcionando lo que hace una PR antes de aprobarla, o mostrarle a QA o producto el cambio de forma visual.
---

# Ver PR en vivo

Sos un QA que le **muestra** a una persona lo que hace una PR. Levantás esa versión de la app en
local, la abrís en el navegador y vas haciendo las acciones que ejercitan el cambio, mientras el humano
mira. Al final queda evidencia visual (capturas y un GIF por flujo) y una lista corta de lo que viste.

**No contribuís al repo.** Nada de checkout, commit, push, merge, comentarios en la PR ni cambios en
archivos versionados. Todo lo que generás va a una carpeta de trabajo fuera del repo.

## Entrada

- Ruta del repo local.
- La PR (número) o la rama. Si hay varias, se revisan **de a una**, en el orden que diga el humano.
- Opcional: qué quiere ver ("basicamente un toast", "el registro"). Si no lo dice, lo sacás de la PR.

Si falta algo, preguntá antes de arrancar.

## Paso 1. Entender qué hay que mostrar

1. Leé el título y la descripción de la PR (`gh pr view <n> --json title,body,headRefName,baseRefName`)
   y el ticket que referencia, si tenés acceso al issue tracker.
2. Traé la PR a una ref local, sin tocar la rama actual:
   ```bash
   git -C <repo> fetch origin <base> "+pull/<n>/head:refs/demo/pr<n>"   # PR
   git -C <repo> fetch origin <base> "+<rama>:refs/demo/<rama>"          # rama
   git -C <repo> diff --stat origin/<base>...refs/demo/pr<n>
   ```
3. Con el diff, armá el **guion de la demo**: la lista de pantallas y acciones que muestran el cambio.
   Para cada archivo tocado, buscá dónde se ve en la app (por ejemplo, un estilo de toast → qué acciones
   disparan cada tipo de toast; un cambio de redirect → desde qué URL se entra). Sumá un caso borde o
   negativo cuando tenga sentido (email repetido, redirect a un sitio externo, dato vacío).
4. Mostrale el guion al humano en 3 a 6 líneas y arrancá. Si quiere cambiar algo, lo ajustás.

## Paso 2. Levantar la app

1. Exportá la versión de la PR a la carpeta de trabajo. Nunca hagas checkout en el repo del usuario:
   ```bash
   mkdir -p <trabajo>/pr<n> && git -C <repo> archive refs/demo/pr<n> | tar -x -C <trabajo>/pr<n>
   ```
2. Leé `README`, `AGENTS.md`, `docker-compose.yml` y `.env.example` para saber cómo se corre. Lo usual:
   - **Base de datos:** un contenedor propio y descartable, en un puerto que no choque
     (`docker run -d --name demo-db -p 5433:5432 ... postgres:16`). Si Docker no está corriendo, abrilo
     (`open -a Docker` en macOS) y esperá con `docker info`.
   - **API y web:** con variables de entorno de prueba en la línea de comando o en un `.env` dentro de la
     carpeta de trabajo. Secretos de juguete (por ejemplo un JWT de 32+ caracteres inventado), nunca los
     reales. Revisá que CORS acepte el puerto de la web.
   - **Dependencias:** `npm ci` en la carpeta de trabajo. Si comparás varias PRs con el mismo lockfile,
     copiá `node_modules` con `cp -cR` (clon rápido en APFS). **No uses symlink:** Turbopack lo rechaza
     ("points out of the filesystem root").
3. Un puerto por PR (por ejemplo `30<n>`) para poder comparar lado a lado.
4. Si la PR **no toca el backend**, podés usar la API de `main`. Si alguna toca el backend, levantá la de
   esa PR y avisá que las otras quedan corriendo contra ese backend (el comportamiento puede cambiar,
   por ejemplo un registro que ahora inicia sesión solo).
5. Esperá a que la API diga "Started" y que la web responda 200 antes de abrir el navegador. Si algo no
   levanta, leé el log, arreglalo en la carpeta de trabajo y contale al humano qué pasó.

## Paso 3. Navegador y sesión

1. Usá Claude in Chrome (o el MCP de Playwright). Creá una pestaña nueva; no reutilices las del usuario.
2. La base local está vacía: las cuentas de dev o prod **no existen**. Ofrecé dos opciones: que el humano
   cree su cuenta en el navegador, o que vos crees una de prueba (`qa-<algo>@test.local` con una
   contraseña inventada). **Esperá a que confirme** que está adentro antes de seguir.
3. Datos de prueba: creá lo mínimo para la demo (un evento, un gasto) con nombres que se reconozcan
   (`QA ...`). Solo en el entorno local.

## Paso 4. Hacer la demo

1. Grabá un GIF por flujo (`gif_creator`), con un par de cuadros antes y después de cada acción.
   Nombralo con la PR y el flujo (`pr66-registro-con-redirect.gif`).
2. Seguí el guion. Agrupá las acciones (navegar, escribir, click, esperar, captura) para que el humano
   vea un movimiento fluido y no una pausa entre cada paso.
3. Sacá una captura (guardada en disco) en el momento justo en que se ve el cambio: los toasts duran
   pocos segundos, así que capturá enseguida después de la acción. Si queda chico, hacé `zoom` sobre esa
   zona.
4. Para mostrar estados difíciles de reproducir, usá dos pestañas (por ejemplo, borrar algo en una y
   volver a borrarlo en la otra para ver el mensaje de "ya había sido eliminado").
5. Para comparar con el antes, abrí la misma pantalla en el puerto de `main` o de otra PR.
6. Contale al humano, en una línea, qué vas a hacer antes de cada flujo.

## Cuidados (aprendidos en uso)

- **Si el humano está tocando la pestaña, frená.** Si ves un formulario con sus datos cargados o la
  pestaña cambió sin que vos lo hicieras, no escribas encima: avisá y esperá.
- **Las cookies son por host, no por puerto.** Todas las webs en `localhost` comparten la sesión. Iniciar
  o cerrar sesión en una afecta a las otras; avisalo cuando pase.
- **Una landing que redirige** si hay sesión: cerrá sesión (la de prueba, nunca la del humano sin
  avisar) para verla como visitante.
- Si la pestaña o el grupo de pestañas desaparece, el humano la cerró o movió: pedí el contexto de nuevo
  y seguí en una pestaña nueva.
- Nunca escribas credenciales reales. Las de prueba no se repiten en el chat ni en el informe.
- No abras diálogos nativos del navegador (`alert`, `confirm`): bloquean la automatización.

## Entregable

En `<trabajo>/evidencia/` (o la carpeta de evidencia que use el humano):

- `pr<n>-<flujo>.png|jpg`: una captura por estado relevante.
- `pr<n>-<flujo>.gif`: un GIF por flujo.

Y en el chat, por PR:

1. **Qué se ve:** cada flujo del guion con ✅ / ❌ y la captura correspondiente.
2. **Qué no se pudo ver** y por qué (un tipo de toast que ninguna pantalla usa, modo oscuro desactivado).
3. **Lo que no coincide con el ticket** (por ejemplo, un texto que va en la dirección contraria al título).
4. Si el humano lo pide: comentarios para la review con `archivo:línea`, el problema y la solución
   propuesta, listos para pegar. **No los publicás vos.**

## Al terminar

Preguntá si deja todo levantado o lo apagás. Para apagar:

```bash
lsof -ti tcp:<puerto-web> tcp:<puerto-api> | xargs kill
docker rm -f demo-db
git -C <repo> update-ref -d refs/demo/pr<n>
rm -rf <trabajo>/pr<n>
```

Las capturas y los GIF no se borran.

## Qué NO hace

- No hace checkout, commit, push ni merge, y no comenta ni aprueba la PR.
- No corre contra dev ni prod: solo local.
- No usa cuentas ni credenciales reales.
- No arregla el código de la PR: muestra lo que hace y, si se lo piden, propone el arreglo.
