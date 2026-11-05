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
3. **Subida**: una sola persona corre el Prompt 1 de la cátedra para las 44 piezas, con "Carpeta donde
   están nuestras piezas" = `agentes/` y grupo `11`, y abre un solo PR. Cada pieza le cuenta a su autor
   porque el autor sale de la ficha, no de quién hizo el push. Para el bloque "Quién hizo cada pieza" se
   usa el `ORIGEN.md`. El prompt pone el prefijo, la ficha y el ejemplo de uso. Cada integrante revisa
   sus filas de la tabla antes de confirmar la subida.

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

## Reparto actual (44 piezas)

| Carpeta | Pieza | Tipo | Repo | Commits por integrante | Colaboradores |
|---|---|---|---|---|---|
| `ignacio-chevallier/` | `auditoria-bugs` | comando | sportmatch-linktree | Ignacio Chevallier 1 | — |
| `ignacio-chevallier/` | `qa-review` | agente | agents-copilot | Ignacio Chevallier 13, Tomás Valle 2, Matías Chialva 1 | Tomás Valle, Matías Chialva |
| `ignacio-chevallier/` | `sincronizar-linear` | skill | sportmatch-linktree | Ignacio Chevallier 7 | — |
| `ignacio-chevallier/` | `test-agent` | agente | agents-copilot | Ignacio Chevallier 40, Tomás Valle 1 | Tomás Valle |
| `ignacio-chevallier/` | `update-linear` | skill | sportmatch-linktree | Ignacio Chevallier 1 | — |
| `ignacio-chevallier/` | `revisar-migracion` | comando | agents-copilot | pieza nueva | — |
| `ignacio-chevallier/` | `revisar-diseno` | agente | agents-copilot | pieza nueva | — |
| `ignacio-chevallier/` | `analizar-cambio-alcance` | skill | agents-copilot | pieza nueva | — |
| `ignacio-chevallier/` | `partir-pr` | comando | agents-copilot | pieza nueva | — |
| `ignacio-chevallier/` | `estimar-ticket` | skill | agents-copilot | pieza nueva | — |
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
| `matias-chialva/` | `ver-pr-en-vivo` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `dor-checker` | agente | agents-copilot | Santos Bogo 1 | — |
| `santos-bogo/` | `dor-readiness` | agente | agents-copilot | Tomás Valle 3, Ignacio Chevallier 2, Santos Bogo 1 | Tomás Valle, Ignacio Chevallier |
| `santos-bogo/` | `contrato-api` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `revisar-consultas` | agente | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `auditar-errores` | comando | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `revisar-privacidad` | agente | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `revisar-react-query` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `revisar-despliegue` | agente | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `revisar-ia-app` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `revisar-textos` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `reglas-de-negocio` | skill | agents-copilot | pieza nueva | — |
| `santos-bogo/` | `plan-actualizacion` | comando | agents-copilot | pieza nueva | — |
| `tomas-valle/` | `radar-de-sprint` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `security-agent` | agente | agents-copilot | Tomás Valle 7 | — |
| `tomas-valle/` | `planear-sprint` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `sportmatch-sim` | agente | sportmatch-sim | Tomás Valle 12 | — |
| `tomas-valle/` | `redactar-ticket` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `qa-con-capturas` | agente | agents-copilot | pieza nueva | — |
| `tomas-valle/` | `usabilidad-sintetica` | agente | agents-copilot | pieza nueva | — |
| `tomas-valle/` | `antes-despues-release` | agente | agents-copilot | pieza nueva | — |
| `tomas-valle/` | `triage-incidente` | agente | agents-copilot | pieza nueva | — |
| `tomas-valle/` | `auditar-steering` | skill | agents-copilot | pieza nueva | — |
| `tomas-valle/` | `explicar-kpi` | skill | agents-copilot | pieza nueva | — |

"Commits por integrante" cuenta solo los archivos propios de la pieza, no los de apoyo compartidos.
Es una pista, no la verdad: quien commitea no siempre es quien diseñó la pieza.

| Integrante | Piezas | Faltan para 10 |
|---|---|---|
| Ignacio | 10 | 0 |
| Tomás | 11 | 0 |
| Matías | 11 | 0 |
| Santos | 12 | 0 |

## Piezas nuevas

Para crear las que faltan, cada integrante usa [PROMPT-crear-piezas.md](PROMPT-crear-piezas.md). Antes
de construir una pieza, la reserva acá con un commit a `main`, así nadie hace la misma.

### Ideas reservadas

| Nombre | Tipo | Integrante | Fecha |
|---|---|---|---|
| `implementar-conmigo` | comando | Matías Chialva | 2026-11-03 |
| `revisar-para-aprender` | comando | Matías Chialva | 2026-11-03 |
| `entrevista-po-tl` | skill | Matías Chialva | 2026-11-03 |
| `alternativas-pantalla` | skill | Matías Chialva | 2026-11-03 |

## Estado para el Prompt 1

Ya resuelto en cada pieza, para que el Prompt 1 no tenga que inventarlo:

- **`## Ejemplo de uso`** al final del archivo principal de todas las piezas.
- **`description`** en el frontmatter de los agentes de workflow (`qa-review`, `test-agent`,
  `security-agent`, `weekly-status`, `dor-readiness`), cuyo `.md` es el prompt extraído.
- **`auditoria-bugs`** generalizado: comando de Claude Code para cualquier app web, sin rutas locales.

Al correr el Prompt 1, avisarle:

- **DATOS:** autor, colaboradores y madurez salen del `ORIGEN.md` de cada pieza; nombres y usuarios, de
  la tabla de arriba.
- **Carpetas:** el bot busca el archivo principal en la raíz de la pieza. Las skills que están en
  `roles/*/skills/<nombre>/` o `github/skills/<nombre>/` suben todo ese contenido a la raíz, con sus
  `references/` y `scripts/`.
- **`sportmatch-sim`**: el archivo principal es `sportmatch-sim.md`. `CLAUDE.md` **no se renombra**,
  porque el workflow corre `claude -p "... según CLAUDE.md"`.
- **`qa-review`** depende de la skill `pr-review` (de Matías) y no la trae copiada, para no duplicarla.
  Es una "referencia a revisar" del paso 6, no algo que haya que cambiar.
- **`planear-sprint`** carga `redactar-ticket` por ruta. Esa ruta ya tiene el nombre final
  (`.claude/skills/g11-redactar-ticket/SKILL.md`): no marcarla como referencia a cambiar.
- **`pr-review`** tiene `name: pr-review-sportmatch` y pasa a `g11-pr-review`. Copilot code review la
  busca por carpeta, así que no se rompe nada. Su `references/qa-criteria.md` no lleva `name` a propósito:
  no agregárselo, porque el bot lo sacaría de la carpeta como si fuera otra pieza.
- En los chat modes que traen su versión workflow, el archivo principal es el `.chatmode.md`. El
  `*-workflow.md` es de apoyo.

## Versión final en el catálogo

El Prompt 1 ya se corrió el 2026-11-04. La versión final de las 44 piezas está en la copia local de
`catalogo-agentes`, rama `g11-carga-inicial`, no en `agentes/`. Solo allá están las descriptions
reescritas, las referencias con `g11-`, las fichas revisadas, el ejemplo nuevo de `triage-incidente` y
los nombres de los devs reemplazados por su lane.

No volver a correr el Prompt 1 sobre `agentes/`: se perderían esos cambios. Una vez subidas, las piezas
se cambian con el Prompt 2 del catálogo.
