# Prompt · Crear piezas nuevas para el catálogo

Sirve para que cada integrante idee, construya y pruebe sus piezas nuevas (skills, agentes o comandos)
sin pisarse con las del resto. Se pega en Claude Code, Cursor o Codex, abierto en la carpeta de
`agents-copilot`. Completá primero el bloque **DATOS**.

Cuando las piezas estén listas, se suben con el Prompt 1 de la cátedra, igual que las demás (ver
[README.md](README.md)).

---

```text
Vas a ayudarme a idear, construir y probar piezas nuevas (skills, agentes o comandos de IA) para el
Catálogo Común de Agentes de la materia. Las piezas son mías: yo soy el autor. Vos proponés,
construís y probás, pero yo decido qué se hace.

DATOS (completar antes de usar)
- Nombre y apellido: ...
- Usuario de GitHub: ...
- Carpeta mía en agentes/: ignacio-chevallier | tomas-valle | matias-chialva | santos-bogo
- Mi rol en el equipo (PM, PO, Tech Lead, QA, dev): ...
- Cuántas piezas quiero hacer en esta tanda: N
- Herramienta en la que las voy a usar: claude-code | cursor | codex
- Ruta local del repo de SportMatch (para probar las piezas sobre el proyecto real): ...
- Ideas que ya traigo (opcional): ...

QUÉ ES UNA PIEZA DEL CATÁLOGO
- skill: paquete de instrucciones que la IA carga cuando la tarea lo necesita (SKILL.md).
- agente: asistente con rol propio (subagente).
- comando: instrucción que se ejecuta con /nombre.
Tiene que ser de IA: si un script sin modelo lo resuelve igual de bien, no es una pieza. Tiene que
servir para programar, testear, documentar, diseñar o gestionar un proyecto.

PASO 0. Leer lo que ya existe (no te saltees esto)
1. git pull en main.
2. Leé agentes/README.md: el reparto, la sección "Ideas reservadas" y qué cuenta y qué no.
3. Recorré TODAS las carpetas agentes/*/*/ (no solo la mía): el archivo principal y el ORIGEN.md
   de cada pieza. Hacé una lista de una línea por pieza: qué hace y para quién.
4. Mirá qué hay en el catálogo de los otros grupos, para no repetir lo que ya está bien resuelto y
   para ver qué categorías faltan:
   gh api 'repos/Laboratorio-4-2C-2026/catalogo-agentes/git/trees/main?recursive=1' --jq '.tree[].path'
   (leé las descripciones de las que se parezcan a una idea tuya).
5. Leé el AGENTS.md del repo de SportMatch para entender el proyecto, el stack y las reglas para
   agentes (sección 8: los agentes revisan y proponen, la decisión es humana).

PASO 1. Proponer ideas (no construyas nada todavía)
Proponé N + 3 ideas en una tabla:
  nombre | tipo | qué problema resuelve (una línea) | para quién (rol) | cómo la pruebo esta semana | se parece a…
Reglas para las ideas:
- Un dolor real que tengamos o hayamos tenido en el proyecto. Citá la evidencia: un archivo, un
  ticket, una PR, algo que hacemos a mano todas las semanas.
- Que no se solape con ninguna pieza de agentes/ ni con las "Ideas reservadas". Si se parece a
  algo, decí a qué y por qué es distinta. Dos piezas que hacen lo mismo con distinto disparador
  (manual y automático) cuentan como una sola.
- Preferí ideas reutilizables fuera de SportMatch (que tomen el contexto del repo en vez de tenerlo
  escrito adentro), pero una pieza específica del proyecto también vale si resuelve algo real.
- Que se pueda probar de verdad esta semana, sobre el proyecto real, sin pagar nada nuevo.
- Priorizá mi rol, pero no te limites a él.
- Mirá qué áreas faltan en lo que ya tenemos (por ejemplo frontend, diseño, documentación,
  despliegue, datos) y proponé al menos una idea de un área que no tengamos.
- No propongas copiar o adaptar piezas de terceros (skills.sh, repos públicos, otros grupos): el
  autor tiene que ser yo.
Al final, recomendá cuáles N harías vos y por qué. Esperá a que yo elija.

PASO 2. Reservar las elegidas (antes de construir)
Para que dos integrantes no hagan la misma pieza:
1. git pull. Si alguna idea elegida ya aparece en "Ideas reservadas" o en agentes/, avisame y no
   sigas con esa.
2. Agregá una fila por pieza en la sección "Ideas reservadas" de agentes/README.md:
   | nombre | tipo | integrante | fecha |
3. Mostrame el diff y, con mi OK, hacé commit ("docs: reservar ideas de <nombre>") y push a main.

PASO 3. Construir cada pieza
En agentes/<mi carpeta>/<nombre>/:
- Nombre: minúsculas, números y guiones, que diga qué hace. Sin prefijo de grupo (lo pone el Prompt 1).
- Formato según el tipo:
  - skill: SKILL.md con frontmatter `name` y `description`. Archivos de apoyo (plantillas,
    scripts, referencias) en la misma carpeta.
  - agente: <nombre>.md en el formato de subagente de mi herramienta (en Claude Code: frontmatter
    con `name`, `description` y, si hace falta, `tools`).
  - comando: <nombre>.md en el formato de comando de mi herramienta (en Claude Code: frontmatter
    con `description` y `argument-hint`, y `$ARGUMENTS` en el cuerpo).
- `description`: una o dos oraciones en español: qué hace y cuándo usarla. Mencioná la tecnología o
  el caso concreto para distinguirla de piezas parecidas.
- Instrucciones:
  - Claras y en pasos.
  - Qué hace y qué NO hace.
  - Si escribe en algún lado (Linear, GitHub, archivos), que lo proponga y espere confirmación.
  - Sin rutas locales ni datos de una persona.
  - Sin secretos: las claves van en variables de entorno.
- Al final, una sección:
  ## Ejemplo de uso
  **Pedido:** (algo concreto que alguien le pediría)
  **Resultado:** (qué devuelve o qué hace, en una o dos oraciones)
- Un ORIGEN.md con:
  # Origen: <nombre>
  - **Tipo:** skill | agente | comando
  - **Creada:** <fecha>, pieza nueva
  - **Autor:** <mi nombre>
  - **Colaboradores:** — (o quien haya aportado de verdad al diseño o al prompt)
  - **Madurez:** experimental | probado
  - **Prueba:** qué caso real se corrió y qué salió (paso 4)

PASO 4. Probar cada pieza sobre el proyecto real
- Corré la pieza al menos una vez sobre un caso real de SportMatch (un ticket, una PR, una pantalla,
  el repo).
- Si el resultado no sirve, corregí las instrucciones y volvé a probar. Contame qué cambiaste.
- Reemplazá el "Ejemplo de uso" por el caso que corriste de verdad.
- Anotá la prueba en ORIGEN.md. Madurez: "probado" si se corrió y funcionó en más de un caso;
  "experimental" si se corrió una sola vez o no se pudo correr.

PASO 5. Cerrar
1. Agregá cada pieza a la tabla "Reparto actual" de agentes/README.md, actualizá los conteos y sacá
   sus filas de "Ideas reservadas".
2. Mostrame:
   - una tabla con nombre | tipo | description | madurez | cómo se probó;
   - cuántas piezas tengo ahora y cuántas me faltan para 10;
   - cualquier duda o cosa que te haya parecido floja.
3. No hagas commit hasta que yo lo revise. Con mi OK: commit en main
   ("feat: piezas nuevas de <nombre>") y push.
```
