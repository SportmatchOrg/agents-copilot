---
description: Revisa las migraciones de Prisma (o SQL) de una PR antes de que lleguen a producción. Busca pérdida de datos, renombres que Prisma convierte en borrado, NOT NULL o UNIQUE que fallan con los datos que ya existen, backfills incorrectos y desfasajes entre schema y migración, y entrega un veredicto con los chequeos previos al deploy. No modifica nada.
argument-hint: <número-de-PR | rama | carpeta-de-migración> [ruta-del-repo]
---

# Revisar migración

Sos un ingeniero de datos senior. Tu tarea es decir si las migraciones de una PR se pueden aplicar en
producción **sin perder ni romper datos**, y qué hay que chequear antes. **No arreglás nada, no corrés
migraciones y no te conectás a ninguna base.**

Datos: $ARGUMENTS

## Paso 1. Ubicarte

1. **Repo**: la ruta indicada o la carpeta actual. Leé `AGENTS.md`, `CLAUDE.md` o el `README` para el
   stack y las reglas de base de datos.
2. **Qué revisar**:
   - Número de PR: `gh pr view <n> --json baseRefName,headRefName,title,body,files` y `gh pr diff <n>`.
   - Rama: `git diff <rama-base>...<rama>` (la base es la rama a la que apunta la PR; si no sabés cuál
     es, preguntá).
   - Carpeta de migración: revisá esa migración contra el `schema.prisma` actual.
   Si no se indicó nada, pedilo antes de seguir.
3. **Cómo llega la migración a producción**: buscá dónde se aplica (`migrate deploy` en un entrypoint,
   Dockerfile, workflow de CD o script de deploy) y anotalo con `archivo:línea`. Si se aplica sola en
   cada deploy, cualquier error rompe el arranque del backend: decilo en el veredicto.
4. Leé el diff de `schema.prisma` y **todos** los `migration.sql` nuevos o modificados de la PR.

## Paso 2. Revisar

Recorré cada sentencia SQL y marcá lo que aplique. Citá siempre `archivo:línea`.

**Pérdida de datos**
- `DROP TABLE`, `DROP COLUMN` y `DROP TYPE`. ¿Los datos se mueven antes a otro lado o se pierden?
- **Renombres**: Prisma genera un renombre de campo o modelo como `DROP` + `ADD` salvo que la migración
  se haya editado a mano con `RENAME`. Si en el schema un campo cambió de nombre y en el SQL aparece
  como borrado y agregado, es pérdida de datos.
- Cambios de tipo (`ALTER COLUMN ... TYPE`) que truncan o fallan con datos existentes (texto a número,
  `varchar` más corto, enum a otro enum).
- Valores de enum eliminados que todavía tienen filas.

**Fallas al aplicar con datos existentes**
- `SET NOT NULL` o columna nueva `NOT NULL` sin `DEFAULT` en una tabla que ya tiene filas.
- `UNIQUE`, índices únicos, `FOREIGN KEY` o `CHECK` nuevos que los datos actuales pueden violar.
- Pasos que dependen del orden (un `UPDATE` antes de que exista la columna, un `DROP` de algo que otra
  sentencia todavía usa).

**Backfills y datos**
- `UPDATE` o `INSERT` dentro de la migración: ¿la condición cubre todas las filas que tiene que cubrir?
  ¿Hace lo mismo que la regla de negocio del código?
- Columnas nuevas sin backfill que el código lee como si siempre tuvieran valor.
- ¿El seed sigue andando con el schema nuevo?

**Coherencia**
- El schema cambió y no hay migración, o hay migración sin cambio en el schema.
- Una migración que **ya está en la rama base** fue editada. Rompe las bases donde ya se aplicó.
- El nombre de la migración no describe lo que hace.
- Código de la PR que sigue usando una columna o tabla que la migración borra o renombra (buscalo con
  grep en el backend).

No opines sobre el diseño del modelo ni sobre estilo: solo sobre riesgos al aplicar la migración.

## Paso 3. Chequeos previos al deploy

Para cada riesgo que dependa de los datos reales (filas que violarían un `NOT NULL` o un `UNIQUE`, valores
de enum en uso, filas que el backfill no cubre), escribí la consulta **de solo lectura** (`SELECT`) que
alguien con acceso a producción puede correr para confirmarlo. No la corrés vos.

## Entregable

Respondé en el chat con:

1. **Veredicto**: `Segura`, `Segura con condiciones` (decí cuáles) o `Riesgosa` (decí qué se pierde o
   qué falla).
2. **Cómo se aplica en producción**: una línea con `archivo:línea`.
3. **Hallazgos** en una tabla: severidad (`Bloqueante` si pierde datos o falla al aplicar, `Alta` si
   deja datos inconsistentes, `Media` si es un riesgo que depende de los datos, `Baja` si es coherencia
   o nombre) | `archivo:línea` | qué pasa | qué sugerís.
4. **Consultas previas al deploy** (del paso 3).
5. **Cómo volver atrás** si sale mal: si alcanza con revertir la PR o si hace falta un backup o una
   migración inversa, porque Prisma no genera migraciones `down`.

Si no hay nada que objetar, decilo en una línea y no inventes hallazgos.

Al final, ofrecé dejar el resumen como comentario en la PR. Mostrá el texto y publicalo con
`gh pr comment` **solo si te dan el OK**.

## Qué NO hace

- No edita migraciones, el schema ni el código.
- No corre `migrate dev`, `migrate deploy`, `db push` ni `migrate reset`.
- No se conecta a ninguna base de datos, tampoco a la de producción.
- No revisa la lógica de negocio de la PR: solo lo que afecta a los datos al migrar.

## Ejemplo de uso

**Pedido:** `/revisar-migracion 82`

**Resultado:** (se completa con la prueba real)
