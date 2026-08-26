# Activar el QA PR Review Agent en `sportmatch`

> Issue listo para pegar en GitHub. Asignar a un dev.
> Etiquetas sugeridas: `chore`, `ci`.

---

## Qué es esto

Tenemos un agente de QA que, cuando abrís o actualizás una PR, prepara una
**GitHub Review en estado `PENDING`**: un borrador con un resumen del cambio, lo
que está bien, y hasta 5 observaciones según los criterios de QA del equipo.

**Lo importante para vos: ese borrador no lo ves.** Una review pendiente solo es
visible para quien la creó, que acá es el QA. No vas a ver un bot comentando tus
PRs. Recién ves algo cuando el QA revisa ese borrador, borra lo que no aplica,
agrega lo suyo y hace **Submit** — igual que hoy, pero con el trabajo previo
hecho.

El agente **no** aprueba, **no** pide cambios, **no** mergea y **no** toca
código.

Toda la lógica vive en `SportmatchOrg/agents-copilot`. Este repo solo necesita un
archivo que diga *"cuando pase esto, corré aquello"*. Si mañana cambian los
criterios de QA, se actualizan allá y este repo los toma solo, sin PR.

Ya está probado de punta a punta contra `SportmatchOrg/sportmatch-sandbox`.

---

## Qué hay que cambiar

Dos archivos. Nada más.

### 1. Nuevo: `.github/workflows/qa-review.yml`

Copiar tal cual de `SportmatchOrg/agents-copilot` →
`github/workflows/qa-review.yml`. Sin los comentarios queda así:

```yaml
name: QA Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [dev, main]

jobs:
  qa-review:
    permissions:
      contents: read
      pull-requests: read
    if: github.event.pull_request.draft == false
    uses: SportmatchOrg/agents-copilot/.github/workflows/qa-review-reusable.yml@main
    secrets: inherit
```

Conservá los comentarios del archivo original: explican por qué cada línea está
ahí.

### 2. Actualizar: `.github/scripts/linear.sh`

Copiar la versión de `agents-copilot` → `github/scripts/linear.sh`. El cambio es
**puramente aditivo**: agrega un subcomando `issue-context` que trae comentarios
y attachments de un ticket. Los cuatro subcomandos existentes
(`find-by-identifier`, `team-id`, `comment`, `create-issue`) quedan idénticos, así
que el DoD checker y los demás agentes no se ven afectados.

Estrictamente hablando **el agente de QA no lo necesita** — lee su propia copia
desde `agents-copilot`. Se actualiza para que el paquete instalado en este repo
no siga quedándose atrás.

---

## Qué NO hay que hacer

- **No corras `install.sh`.** Pisaría `.github/copilot-instructions.md`, que en
  este repo está muy customizado (123 líneas acá contra 44 en el paquete base).
  Copiá los dos archivos a mano.
- **No toques `AGENTS.md` ni `.github/copilot-instructions.md`.** Las versiones de
  este repo son las buenas.
- **No copies `qa-criteria.md`** a `.github/skills/`. Es a propósito: si viviera
  ahí, la review nativa de Copilot podría levantarlo y empezar a publicar
  comentarios de QA sin aprobación humana, que es exactamente lo que este diseño
  evita. El agente lo lee desde `agents-copilot`.
- **No cambies el `@main`** del `uses:`.
- **No saques el bloque `permissions`.** Con la config actual de este repo el
  workflow anda igual sin él, pero un workflow llamado solo puede *reducir* los
  permisos que le pasa el llamador, nunca ampliarlos: si alguien baja el permiso
  por defecto de Actions a *read*, sin ese bloque el workflow deja de arrancar.
- **No saques `secrets: inherit`.**
- **No copies scripts del agente a este repo.** La lógica es central a propósito.

---

## Pasos

```bash
git checkout dev && git pull
git checkout -b chore/qa-review-agent

# 1. el wrapper (archivo nuevo)
#    copiar agents-copilot/github/workflows/qa-review.yml
#    a      .github/workflows/qa-review.yml

# 2. linear.sh (actualización aditiva)
#    copiar agents-copilot/github/scripts/linear.sh
#    a      .github/scripts/linear.sh

git add .github/workflows/qa-review.yml .github/scripts/linear.sh
git status          # que no aparezca NADA más
git commit -m "chore: activar el QA PR Review Agent"
git push -u origin chore/qa-review-agent
```

Abrí la PR contra `dev` y avisá acá.

### Después del merge: el archivo también tiene que llegar a `main`

Para eventos de `pull_request`, GitHub lee el workflow desde la **rama base** de
la PR. Si el archivo solo está en `dev`, las PRs que apunten a `main` nunca lo
van a disparar. Alcanza con que entre en el próximo merge `dev → main`; no hace
falta una PR aparte.

---

## Cómo sabemos que funcionó

**Ojo con el orden:** la PR que agrega el wrapper **no lo va a ejecutar**. GitHub
lee el workflow desde la rama base, y en `dev` todavía no existe. Es esperable y
no es un error.

La verificación se hace en la **PR siguiente** a `dev`, que puede ser cualquiera:

- En la pestaña **Checks** aparece un workflow llamado **QA Review**.
- Termina en verde.
- **Vos no ves ninguna review ni comentario nuevo.** Eso es lo correcto.

El QA confirma por su lado que le apareció el borrador.

Si el modelo está caído, el check igual termina en **verde**, con un warning en
el run diciendo que no se generó borrador. No es un problema de tu código y no
bloquea nada.

---

## Si algo falla

Si ves este error, **no toques el archivo** y avisá acá:

```
This run likely failed because of a workflow file issue
(el run falla sin crear ningún job y sin logs)
```

Es un tema de permisos o de visibilidad de secrets del lado de la organización, y
se resuelve fuera de este repo.

---

## Definición de listo

- [ ] `.github/workflows/qa-review.yml` existe en `dev`
- [ ] `.github/scripts/linear.sh` actualizado, con el subcomando `issue-context`
- [ ] `AGENTS.md` y `copilot-instructions.md` **sin cambios** en el diff de la PR
- [ ] El check **QA Review** corre y termina en verde en la primera PR posterior
- [ ] El QA confirma que ve el borrador
- [ ] El developer confirma que **no** ve nada
- [ ] El archivo llegó también a `main`

---

## Contexto para quien quiera el detalle

- Diseño completo: `agents-copilot/docs/SPORTMATCH_QA_REVIEW_AGENT_PLAN.md`
- Criterios QA-01…QA-10: `agents-copilot/github/skills/pr-review/references/qa-criteria.md`
- Lógica del agente: `agents-copilot/.github/workflows/qa-review-reusable.yml`
  y `agents-copilot/.github/scripts/qa-review/`
