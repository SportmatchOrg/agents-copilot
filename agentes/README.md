# Agentes para el Catálogo Común

Zona de preparación de las piezas que el grupo sube a
[`Laboratorio-4-2C-2026/catalogo-agentes`](https://github.com/Laboratorio-4-2C-2026/catalogo-agentes).
La meta es 10 piezas por integrante, 40 en total, sin solapamientos.

## Cómo funciona

1. **`comun/`**: todas las piezas que ya existen, una carpeta por pieza, con el nombre y el formato
   originales. Cada una es autocontenida (prompt, workflow y scripts que usa) y trae un `ORIGEN.md`
   con de dónde salió, los commits por integrante y el autor propuesto.
2. **Reparto**: cada pieza se **mueve** (no se copia) a la carpeta de quien queda como autor:
   `git mv comun/<pieza> <integrante>/`. Una pieza vive en una sola carpeta, así que no hay
   solapamientos. Cuando `comun/` queda vacía, está todo repartido.
3. **Subida**: cada integrante corre el Prompt 1 de la cátedra con "Carpeta donde están nuestras
   piezas" = su carpeta. Para el bloque "Quién hizo cada pieza" se usa el `ORIGEN.md` de cada pieza.
   El prompt pone el prefijo `gNN-`, la ficha y el ejemplo de uso.

**Criterio de autoría (mixto):** si hay un autor claro, va el que figura en git. Las piezas
compartidas (marcadas "a acordar") se asignan por acuerdo y según el rol, siempre que haya habido un
aporte real. El resto figura como colaborador.

## Fuentes

- `agents-copilot` es la versión canónica. Las copias en `sportmatch` y `sportmatch-sandbox` se
  instalan con `install.sh`, y algunas difieren: ver las notas de cada `ORIGEN.md`.
- `sportmatch-linktree`: `roles/*/skills`, `prompt-auditoria-sportmatch.md`.
- `sportmatch-sim`: el agente simulador (`CLAUDE.md`).

**Afuera, a propósito:** skills de terceros (las de `sportmatch/{front,back}/.agents/` de Vercel,
Prisma, etc., y `brag`/`brag-slim` de `latent-spaces/brag`). No son del grupo.

## Reparto (24 piezas, 6 por integrante)

El autor de cada pieza es el dueño de la carpeta. Las piezas de autoría compartida se repartieron por acuerdo de grupo (2026-11-02) para quedar parejos.

| Carpeta | Pieza | Tipo | Repo | Commits por integrante | Colaboradores |
|---|---|---|---|---|---|
| `ignacio-chevallier/` | `auditoria-bugs` | comando | sportmatch-linktree | Ignacio Chevallier 1 | — |
| `ignacio-chevallier/` | `qa-review` | agente | agents-copilot | Ignacio Chevallier 13, Tomás Valle 2, Matías Chialva 1 | Tomás Valle, Matías Chialva |
| `ignacio-chevallier/` | `sincronizar-linear` | skill | sportmatch-linktree | Ignacio Chevallier 7 | — |
| `ignacio-chevallier/` | `sprint-health` | agente | agents-copilot | Ignacio Chevallier 2, Tomás Valle 1, Santos Bogo 1, Matías Chialva 1 | Tomás Valle, Santos Bogo, Matías Chialva |
| `ignacio-chevallier/` | `test-agent` | agente | agents-copilot | Ignacio Chevallier 40, Tomás Valle 1 | Tomás Valle |
| `ignacio-chevallier/` | `update-linear` | skill | sportmatch-linktree | Ignacio Chevallier 1 | — |
| `matias-chialva/` | `context-curator` | agente | agents-copilot | Matías Chialva 1 | — |
| `matias-chialva/` | `dod-checker` | agente | agents-copilot | Ignacio Chevallier 1, Matías Chialva 1 | Ignacio Chevallier |
| `matias-chialva/` | `pr-business-translator` | agente | agents-copilot | Ignacio Chevallier 1, Matías Chialva 1 | Ignacio Chevallier |
| `matias-chialva/` | `pr-review` | skill | agents-copilot | Ignacio Chevallier 2, Matías Chialva 1 | Ignacio Chevallier |
| `matias-chialva/` | `repo-onboarding` | agente | agents-copilot | Matías Chialva 1 | — |
| `matias-chialva/` | `weekly-status` | agente | agents-copilot | Tomás Valle 3, Ignacio Chevallier 2, Santos Bogo 1, Matías Chialva 1 | Tomás Valle, Ignacio Chevallier, Santos Bogo |
| `santos-bogo/` | `context-curator-workflow` | agente | agents-copilot | Ignacio Chevallier 3, Tomás Valle 2, Santos Bogo 1, Matías Chialva 1 | Ignacio Chevallier, Tomás Valle, Matías Chialva |
| `santos-bogo/` | `dod-checker-workflow` | agente | agents-copilot | Ignacio Chevallier 6, Tomás Valle 3, Santos Bogo 2, Matías Chialva 1 | Ignacio Chevallier, Tomás Valle, Matías Chialva |
| `santos-bogo/` | `dor-checker` | agente | agents-copilot | Santos Bogo 1 | — |
| `santos-bogo/` | `dor-readiness` | agente | agents-copilot | Tomás Valle 3, Ignacio Chevallier 2, Santos Bogo 1 | Tomás Valle, Ignacio Chevallier |
| `santos-bogo/` | `pr-business-translator-workflow` | agente | agents-copilot | Ignacio Chevallier 6, Tomás Valle 3, Santos Bogo 1, Matías Chialva 1 | Ignacio Chevallier, Tomás Valle, Matías Chialva |
| `santos-bogo/` | `repo-onboarding-workflow` | agente | agents-copilot | Tomás Valle 3, Ignacio Chevallier 2, Santos Bogo 1 | Tomás Valle, Ignacio Chevallier |
| `tomas-valle/` | `kpi-report` | agente | agents-copilot | Tomás Valle 3, Matías Chialva 1 | Matías Chialva |
| `tomas-valle/` | `pulse` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `security-agent` | agente | agents-copilot | Tomás Valle 7 | — |
| `tomas-valle/` | `semana` | skill | sportmatch-linktree | Tomás Valle 1 | — |
| `tomas-valle/` | `sportmatch-sim` | agente | sportmatch-sim | Tomás Valle 12 | — |
| `tomas-valle/` | `ticket` | skill | sportmatch-linktree | Tomás Valle 1 | — |

"Commits por integrante" cuenta solo los archivos propios de la pieza, no los de apoyo compartidos.
Es una pista, no la verdad: quien commitea no siempre es quien diseñó la pieza.

### Dudas abiertas

- **`sprint-health` y `kpi-report` no usan IA**: son automatizaciones determinísticas. Pueden no
  contar como pieza del catálogo.
- **Chat mode y workflow del mismo agente** (`context-curator`, `dod-checker`, `repo-onboarding`,
  `pr-business-translator`): se separaron porque tienen prompts y usos distintos (manual o
  automático). El bot del catálogo probablemente los marque como `relacionados`.
- **Faltan 16 piezas** para llegar a 40 (4 por integrante), 18 si `sprint-health` (Ignacio) y
  `kpi-report` (Tomás) no cuentan. Las piezas nuevas entran por `comun/` y se reparten igual.
