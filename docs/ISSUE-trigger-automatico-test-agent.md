# Disparar el API Test Agent automáticamente en cada PR

> **Depende de:** el harness e2e y los wrappers instalados en `sportmatch`
> (`ISSUE-harness-e2e-sportmatch.md` + `ISSUE-hotfix-triggers-sportmatch.md`).
> Sin `back/test/` el agente no tiene contra qué correr.

Hoy `test-agent.yml` es `workflow_dispatch` puro: corre solo si alguien entra a
Actions y aprieta el botón. Funciona, pero depende de que alguien se acuerde.
Este issue lo pasa a `pull_request`.

## Por qué PR y no issue

El pedido original decía "por cada issue/PR". El issue no sirve, por dos motivos:

- Los tickets viven en **Linear**, no en GitHub Issues. Un ticket de Linear no
  dispara nada en Actions: haría falta un webhook de Linear pegándole a
  `repository_dispatch`, que es un servicio más para mantener.
- Aunque existiera, **cuando se crea el ticket todavía no hay código**. El
  agente escribe tests e2e contra endpoints reales; sin implementación no tiene
  nada que testear y quema una corrida entera para producir nada.

El PR es el momento correcto: el código existe, el ticket ya está en el nombre
de la rama, y los tests llegan cuando todavía se pueden discutir.

## De dónde sale el ticket

De la rama. La convención del repo ya lo trae: `feature/SPO-179` → `SPO-179`.
Si la rama no matchea, el agente no corre y no pasa nada.

## El cambio

Todo en el wrapper `github/workflows/test-agent.yml` de `agents-copilot`.
**El reusable no se toca.**

```yaml
on:
  workflow_dispatch:
    inputs: ...                    # los tres de hoy, sin cambios
  pull_request:
    types: [opened, ready_for_review]
    branches: [dev]
    paths: ["back/**"]

jobs:
  ticket:
    runs-on: ubuntu-latest
    if: >-
      github.event_name == 'workflow_dispatch' ||
      (github.event.pull_request.head.repo.full_name == github.repository &&
       !startsWith(github.head_ref, 'bot/'))
    outputs:
      id: ${{ steps.x.outputs.id }}
    steps:
      - id: x
        env:
          HEAD_REF: ${{ github.head_ref }}     # por env, NO interpolado en el
          MANUAL: ${{ inputs.ticket }}         # script: el repo es público y un
        run: |                                 # nombre de rama es input hostil
          id="${MANUAL:-$(printf '%s' "$HEAD_REF" \
              | grep -oiE '[a-z]+-[0-9]+' | head -1 | tr '[:lower:]' '[:upper:]')}"
          echo "id=$id" >> "$GITHUB_OUTPUT"
          [ -n "$id" ] || echo "::notice::rama sin ticket; el agente no corre"

  test-agent:
    needs: ticket
    if: needs.ticket.outputs.id != ''
    permissions:
      contents: write
      pull-requests: write
    uses: SportmatchOrg/agents-copilot/.github/workflows/test-agent-reusable.yml@main
    with:
      ticket: ${{ needs.ticket.outputs.id }}
      rf: ${{ inputs.rf }}
      llm_model_chain: ${{ inputs.llm_model_chain }}
      base_branch: ${{ github.head_ref || 'dev' }}    # ← la línea que importa
      service_root: back
    secrets:
      LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
```

### Por qué `base_branch: github.head_ref` es la línea que importa

En el reusable, `base_branch` se usa **dos veces**: como `ref:` del checkout del
repo destino, y como `--base` de la PR draft.

Si queda en `dev`, el agente hace checkout de `dev` y **testea código que no
incluye la feature del PR**: escribe tests contra endpoints que todavía no
existen y los da por rotos. Apuntándolo a la rama del PR, las dos cosas caen en
su lugar solas: testea el código nuevo, y deja su PR draft contra la rama de la
feature, para que el dev la mergee dentro de la suya antes de mandar todo a `dev`.

Por eso el reusable no necesita ningún cambio.

## Los guardarraíles, uno por uno

| Guardarraíl | Por qué |
|---|---|
| `types: [opened, ready_for_review]` | **Sin `synchronize`.** Con `synchronize` cada push a un PR abierto dispara otra corrida: un PR con 15 commits son 15 corridas del loop. |
| `paths: ["back/**"]` | El agente solo testea la API. Un PR de CSS no tiene por qué gastar cuota. |
| `branches: [dev]` | Solo el flujo real de features. |
| `head.repo.full_name == github.repository` | `sportmatch` es **público**: un PR desde un fork corre sin secrets, `LLM_API_KEY` llega vacío y el job falla en rojo por diseño de GitHub, no por un bug. Mejor no arrancarlo. |
| `!startsWith(github.head_ref, 'bot/')` | Cinturón. El tirante ya está: la PR del agente se crea con `GITHUB_TOKEN`, y GitHub no dispara workflows con PRs creadas por ese token. Igual el guard queda escrito, porque el día que alguien cambie ese token el loop infinito no avisa. |
| `concurrency` por ticket | Ya está en el reusable, con `cancel-in-progress`. Dos PRs del mismo ticket no se pisan. |

## El costo, que es la objeción real

El header de `test-agent.yml` dice hoy, textual:

> Se dispara A MANO a propósito: el gasto es una decisión humana, y un loop
> agéntico automático es la forma más rápida de quemar la cuota diaria de
> modelos sin que nadie se entere.

Este issue contradice ese comentario, así que hay que **reescribirlo**, no
borrarlo. Lo que cambia el cálculo:

- El loop son 5 iteraciones por corrida. Con `paths` + `opened` (no
  `synchronize`), el techo es *PRs de backend por día*, no *pushes por día*.
- La cadena default de `models.py` son modelos `:free`. Cuando la cuota diaria
  se agota, la corrida falla; no aparece una factura.
- **Apagarlo no requiere una PR**: Actions → API Test Agent → ⋯ → *Disable
  workflow*. Es la feature nativa de GitHub, no hace falta inventar un
  `vars.TEST_AGENT_ENABLED`.

Si aun así el volumen molesta, el plan B es una **label**: agregar
`github.event.label.name == 'e2e'` con `types: [labeled]`. Sigue siendo
automático para quien lo quiere, y explícito. No lo pongo de entrada porque es
volver a depender de que alguien se acuerde.

## Ojo con `install.sh`

`install.sh:55` copia `github/workflows/*.yml` entero. Este cambio viaja a
**todo repo donde se corra el instalador**, no solo a `sportmatch`. Si eso no se
quiere, el trigger va como un archivo aparte y no en la plantilla del paquete.

## Listo cuando

- [ ] Un PR nuevo a `dev` que toca `back/**` desde una rama `feature/SPO-xxx`
  dispara `API Test Agent` solo.
- [ ] El agente hace checkout de la rama del PR (verificable en el log del step
  de checkout: el `ref` es la feature, no `dev`).
- [ ] La PR draft del bot queda **contra la rama de la feature**, no contra `dev`.
- [ ] La PR draft queda asignada a quien abrió el PR original (`GITHUB_ACTOR` en
  un `pull_request` es el autor, así que `asignar()` funciona sin cambios).
- [ ] Un PR desde una rama sin ticket en el nombre no dispara nada, y deja el
  `::notice::` en el resumen.
- [ ] Un PR que solo toca `front/**` no dispara nada.
- [ ] Pushear un commit más al PR **no** dispara una segunda corrida.
- [ ] La PR del propio bot no dispara otra corrida.
- [ ] `workflow_dispatch` con un ticket a mano sigue funcionando igual que hoy.
- [ ] El comentario del header de `test-agent.yml` ya no dice que es manual.

## Fuera de alcance

- El trigger desde Linear (`repository_dispatch` + webhook).
- El cron: es otra discusión, y este trigger probablemente lo hace innecesario.
- Cambios al reusable. Si aparece uno necesario, este diseño está mal.
