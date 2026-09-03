# API Test Agent en producción — estado y decisiones abiertas

> No es un issue para asignar: el trabajo mecánico ya está cubierto por
> `ISSUE-harness-e2e-sportmatch.md` (el dev) y
> `ISSUE-hotfix-triggers-sportmatch.md` (instala también `test-agent.yml`).
> Queda acá lo que necesita criterio.

## Hecho

- **Allowlist abierta.** `SportmatchOrg/sportmatch` está en `ALLOWED_REPOS`
  de `validate-output.py`. Ese commit es la decisión explícita de apuntar a
  producción.
- **El wrapper viaja con `install.sh`.** `test-agent.yml` es genérico: no
  hardcodea el repo destino, el reusable usa `github.repository`.
- **`AGENTS_REPO_TOKEN` no hace falta.** `agents-copilot` es público. Tampoco
  hace falta un PAT para escribir: `sportmatch` tiene
  `default_workflow_permissions: write`, así que la PR sale con autoría de bot.

## Decisiones abiertas

**1. Quién es dueño de los `it.failing`.** El agente marca así los tests que
documentan un incumplimiento del AC. Ya apareció un caso real: el AC-7 de
SPO-168 pide 400 al mandar `usuarioId` en el body, y `4d6c779` quitó ese
parámetro a propósito. No es un bug del código: es un ticket que quedó viejo.
Alguien tiene que decidir si se actualiza el AC o se agrega la validación.
Sin dueño, los `it.failing` se acumulan y nadie los mira.

~~**2. Fijar la versión de los agentes.**~~ **Decidido: se quedan en `@main`.**
La gracia del diseño es actualizar un agente sin tocar `sportmatch`, y un tag
fijo lo rompe.

El precio es que cada push a main pasa a ser, en el acto, el código que corre
contra producción. Por eso se agregó CI a este repo (`ci.yml`): los 67 tests
y la verificación de que cada wrapper apunte a un reusable que existe. Antes
la garantía era "alguien se acordó de correr los tests en su máquina".

**3. La mediana de iteraciones.** Las corridas cierran en 7-12 de 15. §11 del
plan dice que si toca el techo consistentemente, el problema es la precarga
de contexto (§5.3) y no el modelo. Vale mirarlo después del piloto.
