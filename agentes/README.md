# Agentes para el Catálogo Común — Grupo 11

Zona de preparación de las piezas que el grupo sube a
[`Laboratorio-4-2C-2026/catalogo-agentes`](https://github.com/Laboratorio-4-2C-2026/catalogo-agentes)
con prefijo `g11-`. La meta es 10 piezas por integrante, 40 en total, sin solapamientos.

| Integrante | GitHub | Carpeta |
|---|---|---|
| Ignacio Chevallier Boutell | `IgnacioChevallier` | `ignacio-chevallier/` |
| Tomás Valle Durán | `TomasValleDuran` | `tomas-valle/` |
| Matías Chialva | `Matichialvaa` | `matias-chialva/` |
| Santos Bogo | `santosbogo` | `santos-bogo/` |

Los usuarios salen de `integrantes.yml` del catálogo.

## Cómo funciona

1. **`comun/`**: piezas sin asignar, una carpeta por pieza. Cada pieza es autocontenida (prompt,
   workflow y scripts que usa) y trae un `ORIGEN.md` con de dónde salió, los commits por integrante,
   el autor y los colaboradores.
2. **Reparto**: cada pieza se **mueve** (no se copia) a la carpeta de su autor. Una pieza vive en una
   sola carpeta, así que no hay solapamientos.
3. **Subida**: cada integrante corre el Prompt 1 de la cátedra con "Carpeta donde están nuestras
   piezas" = su carpeta y grupo `11`. Para el bloque "Quién hizo cada pieza" se usa el `ORIGEN.md`.
   El prompt pone el prefijo, la ficha y el ejemplo de uso.

**Criterio de autoría (mixto):** si hay un autor claro, va el que figura en git. Las piezas
compartidas se reparten por acuerdo y según el rol, siempre que haya habido un aporte real. El resto
figura como colaborador.

## Fuentes

- `agents-copilot` es la versión canónica. Las copias en `sportmatch` y `sportmatch-sandbox` se
  instalan con `install.sh`, y algunas difieren: ver las notas de cada `ORIGEN.md`.
- `sportmatch-linktree`: `roles/*/skills`, `prompt-auditoria-sportmatch.md`.
- `sportmatch-sim`: el agente simulador (`CLAUDE.md`).

**Afuera, a propósito:** `sprint-health` y `kpi-report` (no usan IA, así que no son agentes de IA), y las skills de terceros (las de `sportmatch/{front,back}/.agents/` de Vercel,
Prisma, etc., y `brag`/`brag-slim` de `latent-spaces/brag`). No son del grupo.

**Fusionados:** las versiones workflow de `context-curator`, `dod-checker`, `repo-onboarding` y
`pr-business-translator` son el mismo agente que su chat mode, con otro disparador. Van como
archivos de apoyo dentro del chat mode y no cuentan como pieza aparte. `dor-readiness` sí es una
pieza propia: hace un trabajo distinto al de `dor-checker`.

## Reparto actual (22 piezas)

| Carpeta | Pieza | Tipo | Repo | Commits por integrante | Colaboradores |
|---|---|---|---|---|---|
| `ignacio-chevallier/` | `auditoria-bugs` | comando | sportmatch-linktree | Ignacio Chevallier 1 | — |
| `ignacio-chevallier/` | `qa-review` | agente | agents-copilot | Ignacio Chevallier 13, Tomás Valle 2, Matías Chialva 1 | Tomás Valle, Matías Chialva |
| `ignacio-chevallier/` | `sincronizar-linear` | skill | sportmatch-linktree | Ignacio Chevallier 7 | — |
| `ignacio-chevallier/` | `test-agent` | agente | agents-copilot | Ignacio Chevallier 40, Tomás Valle 1 | Tomás Valle |
| `ignacio-chevallier/` | `update-linear` | skill | sportmatch-linktree | Ignacio Chevallier 1 | — |
| `matias-chialva/` | `context-curator` | agente | agents-copilot | Matías Chialva 1 | Ignacio Chevallier, Tomás Valle, Santos Bogo |
| `matias-chialva/` | `dod-checker` | agente | agents-copilot | Ignacio Chevallier 1, Matías Chialva 1 | Ignacio Chevallier, Tomás Valle, Santos Bogo |
| `matias-chialva/` | `pr-business-translator` | agente | agents-copilot | Ignacio Chevallier 1, Matías Chialva 1 | Ignacio Chevallier, Tomás Valle, Santos Bogo |
| `matias-chialva/` | `pr-review` | skill | agents-copilot | Ignacio Chevallier 2, Matías Chialva 1 | Ignacio Chevallier |
| `matias-chialva/` | `repo-onboarding` | agente | agents-copilot | Matías Chialva 1 | Tomás Valle, Ignacio Chevallier, Santos Bogo |
| `matias-chialva/` | `weekly-status` | agente | agents-copilot | Tomás Valle 3, Ignacio Chevallier 2, Santos Bogo 1, Matías Chialva 1 | Tomás Valle, Ignacio Chevallier, Santos Bogo |
| `matias-chialva/` | `implementar-conmigo` | comando | agents-copilot | pieza nueva | — |
| `matias-chialva/` | `revisar-para-aprender` | comando | agents-copilot | pieza nueva | — |
| `matias-chialva/` | `matriz-responsive` | skill | agents-copilot | pieza nueva | — |
| `matias-chialva/` | `alternativas-pantalla` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `dor-checker` | agente | agents-copilot | Santos Bogo 1 | — |
| `santos-bogo/` | `dor-readiness` | agente | agents-copilot | Tomás Valle 3, Ignacio Chevallier 2, Santos Bogo 1 | Tomás Valle, Ignacio Chevallier |
| `tomas-valle/` | `pulse` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `security-agent` | agente | agents-copilot | Tomás Valle 7 | — |
| `tomas-valle/` | `semana` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `sportmatch-sim` | agente | sportmatch-sim | Tomás Valle 12 | — |
| `tomas-valle/` | `ticket` | skill | sportmatch-linktree | Tomás Valle 1 | — |

"Commits por integrante" cuenta solo los archivos propios de la pieza, no los de apoyo compartidos.
Es una pista, no la verdad: quien commitea no siempre es quien diseñó la pieza.

| Integrante | Piezas | Faltan para 10 |
|---|---|---|
| Ignacio | 5 | 5 |
| Tomás | 5 | 5 |
| Matías | 10 | 0 |
| Santos | 2 | 8 |

## Piezas nuevas

Para crear las que faltan, cada integrante usa [PROMPT-crear-piezas.md](PROMPT-crear-piezas.md). Antes
de construir una pieza, la reserva acá con un commit a `main`, así nadie hace la misma.

### Ideas reservadas

| Nombre | Tipo | Integrante | Fecha |
|---|---|---|---|
| `revisar-migracion` | comando | Ignacio Chevallier | 2026-11-02 |
| `revisar-diseno` | agente | Ignacio Chevallier | 2026-11-02 |
| `analizar-cambio-alcance` | skill | Ignacio Chevallier | 2026-11-02 |
| `partir-pr` | comando | Ignacio Chevallier | 2026-11-02 |
| `estimar-ticket` | skill | Ignacio Chevallier | 2026-11-02 |

## Estado para el Prompt 1

Ya resuelto en cada pieza, para que el Prompt 1 no tenga que inventarlo:

- **`## Ejemplo de uso`** al final del archivo principal de todas las piezas.
- **`description`** en el frontmatter de los agentes de workflow (`qa-review`, `test-agent`,
  `security-agent`, `weekly-status`, `dor-readiness`), cuyo `.md` es el prompt extraído.
- **`auditoria-bugs`** generalizado: comando de Claude Code para cualquier app web, sin rutas locales.

Al correr el Prompt 1, avisarle:

- **`sportmatch-sim`**: el archivo principal es `sportmatch-sim.md`. `CLAUDE.md` **no se renombra**,
  porque el workflow corre `claude -p "... según CLAUDE.md"`.
- **`qa-review`** depende de la skill `pr-review` (de Matías) y no la trae copiada, para no duplicarla.
  Es una "referencia a revisar" del paso 6, no algo que haya que cambiar.
- **`pr-review`** tiene `name: pr-review-sportmatch` y pasa a `g11-pr-review`. Copilot code review la
  busca por carpeta, así que no se rompe nada.
- En los chat modes que traen su versión workflow, el archivo principal es el `.chatmode.md`. El
  `*-workflow.md` es de apoyo.
