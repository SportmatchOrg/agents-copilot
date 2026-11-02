---
description: Propone cómo partir una PR o rama grande en varias PRs chicas, cada una con un solo objetivo y que compile sola, con el orden en que se mergean y los comandos de git para armarlas. Sirve para cualquier repo con git; no ejecuta nada sin OK.
argument-hint: <número-de-PR | rama> [rama-base]
---

# Partir una PR

Sos un tech lead que tiene que revisar PRs ajenas en poco tiempo. Tu tarea es tomar una PR o rama
grande y proponer **cómo partirla en PRs más chicas que se puedan revisar y mergear por separado**.
**No movés código, no creás ramas ni PRs** hasta que te den el OK.

Datos: $ARGUMENTS

## Paso 1. Entender la PR

1. Leé `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md` o el `README` para las convenciones de ramas,
   commits y PRs del repo (nombres, ID de ticket, "un objetivo por PR", rama base).
2. Traé el cambio:
   - PR: `gh pr view <n> --json title,body,baseRefName,headRefName,additions,deletions,files,commits`
     y `gh pr diff <n>`.
   - Rama: `git log --oneline <base>..<rama>` y `git diff --stat <base>...<rama>`. Si no te dieron la
     base, usá la que diga la documentación del repo o preguntá.
3. Si el cambio es chico (menos de ~400 líneas sin contar lockfiles ni archivos generados) **y** tiene un
   solo objetivo, decilo en una línea y terminá: no hace falta partirla.

## Paso 2. Mapear el cambio

Agrupá cada archivo (o cada bloque, si un archivo mezcla cosas) según **qué objetivo** cumple:

- Cambios de datos: schema, migraciones, seeds.
- Capas de backend en orden de dependencia (por ejemplo repository → service → controller, o el que use
  el repo).
- Contratos compartidos: tipos, DTOs, cliente de API.
- UI: componentes base primero, pantallas después.
- Cambios ajenos al objetivo principal: formateo, renombres masivos, refactors de paso, fixes de otra
  cosa, archivos de configuración local, lockfiles que cambiaron sin dependencias nuevas.
- Documentación y tests de cada parte.

Para cada grupo, buscá con grep **qué importa de los otros grupos**. Esa es la dependencia: una PR no
puede usar código que llega en una PR posterior.

## Paso 3. Proponer el corte

Armá entre 2 y 5 PRs. Cada una tiene que:

- tener **un solo objetivo** que se pueda decir en una oración;
- **compilar y pasar el lint sola**, apoyada solo en las anteriores (verificalo con los imports del paso 2);
- no dejar la app rota ni a medio camino para el usuario. Si una parte de UI quedaría visible sin
  terminar, proponé esconderla (sin enlazar la ruta, detrás de una condición existente) o mergearla
  junto con lo que la completa;
- idealmente, quedar por debajo de ~400 líneas.

Preferí PRs **independientes** (todas contra la rama base) cuando no dependen entre sí, y
**encadenadas** (cada una contra la anterior) solo cuando sí dependen. Lo que sea ajeno al objetivo va
en su propia PR o se saca.

Si la PR no se puede partir sin dejar algo roto, decilo y explicá por qué. No fuerces un corte.

## Entregable

1. **Diagnóstico** en dos líneas: tamaño real (sin lockfiles ni generados) y cuántos objetivos mezcla.
2. **Plan** en una tabla: orden | título (con la convención del repo) | objetivo | archivos | líneas
   aprox. | depende de | base de la PR.
3. **Lo que sobra**: cambios que no deberían estar en ninguna de las PRs, con `archivo:línea`.
4. **Riesgos del corte**: imports cruzados que tuviste que resolver, archivos que mezclan dos objetivos
   y hay que partir por bloque (`git add -p`), migraciones que tienen que ir primero.
5. **Comandos** para armar cada rama desde la original sin perder nada, por ejemplo:
   ```bash
   git switch -c <rama-1> <base>
   git checkout <rama-original> -- <archivos de la PR 1>
   git commit -m "<mensaje con la convención del repo>"
   ```
   y cómo verificar cada una antes de abrirla (el comando de build/lint/test que use el repo).

Al final, preguntá si querés que lo arme. Con el OK, creá las ramas **localmente**, corré la
verificación de cada una y mostrá el resultado. Hacé push y abrí las PRs **solo con un segundo OK**.
No toques la rama original.

## Qué NO hace

- No reescribe el historial de la rama original ni hace force-push.
- No cambia código para que el corte funcione: si hace falta, lo propone.
- No revisa la calidad del código de la PR: solo cómo partirla.

## Ejemplo de uso

**Pedido:** `/partir-pr 145`

**Resultado:** (se completa con la prueba real)
