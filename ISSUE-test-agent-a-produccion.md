# Llevar el API Test Agent a `sportmatch`

> Depende de `ISSUE-hotfix-triggers-sportmatch.md` solo en orden, no en
> contenido: conviene que los 8 agentes estén sanos antes de sumar el noveno.

El agente funciona. Sobre 4 tickets reales del sandbox entrega PRs draft con
tests e2e que corren de verdad, cobertura de AC medida (no autodeclarada) y
los bugs que encuentra marcados con `it.failing`. Falta lo que no podemos
hacer nosotros.

## 1. El harness e2e — lo único que bloquea

Es un issue aparte porque lo hace el equipo de back:
**`ISSUE-harness-e2e-sportmatch.md`**. Se reduce a un comando
(`install-harness.sh`), que además verifica lo que instala y deja
`back/test/` con solo configuración, sin tests.

Sin eso el agente no tiene contra qué correr: `sportmatch` no tiene
`back/test/` y su `test:e2e` apunta a un config inexistente.

## 2. Dos trámites de una línea

- Agregar `SportmatchOrg/sportmatch` a `ALLOWED_REPOS` en
  `validate-output.py`. Ese commit **es** la decisión explícita de apuntar a
  producción: hoy el validador aborta si el destino no es el sandbox.
- Cargar `AGENTS_REPO_TOKEN` en `sportmatch` (PAT con `Contents: Read` sobre
  `agents-copilot`, que es privado).

No hace falta PAT para escribir: `sportmatch` ya tiene
`default_workflow_permissions: write` y `can_approve_pull_request_reviews:
true`, así que va con `GITHUB_TOKEN` y la PR queda con autoría de bot.

## 3. Una decisión de proceso, no técnica

**Quién es dueño de los `it.failing`.** El agente marca así los tests que
documentan un incumplimiento del AC. Ya apareció un caso real: el AC-7 de
SPO-168 pide que el endpoint devuelva 400 al mandar un body con `usuarioId`,
y `4d6c779` quitó ese parámetro a propósito. No es un bug del código: es un
ticket que quedó viejo. Alguien tiene que decidir si se actualiza el AC o se
agrega la validación. Sin dueño, los `it.failing` se acumulan y nadie los mira.

## Fijar la versión del agente

El wrapper del sandbox usa `@main`. Para producción conviene un tag (`@v1`)
que se mueva a propósito: con `@main`, un push a `agents-copilot` cambia en
silencio el agente que corre contra el repo real.

## Fuera de alcance

- Migrar los tests generados del sandbox a `sportmatch`. Se generan de nuevo.
- El snapshot del sandbox deja de importar: en producción el agente hace
  checkout del repo real, sin fixture congelada que se desactualice.
