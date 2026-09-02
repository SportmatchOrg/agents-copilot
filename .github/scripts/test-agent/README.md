# API Test Agent

Escribe tests e2e de la API a partir de un ticket de Linear, los corre de verdad contra una base real, itera sobre los fallos y abre una PR draft.

---

## ¿Es un agente?

Sí. Es el único de los nueve del paquete que lo es.

Los otros ocho (qa-review, dod-checker, dor-readiness, pr-business-translator, context-curator, weekly-status, sprint-health, repo-onboarding) son **pipelines con un LLM adentro**: el workflow decide de antemano qué pasos se ejecutan y en qué orden, se le pasa un prompt al modelo, y su salida se formatea. El modelo produce texto; no toma decisiones sobre el control de flujo.

Acá el modelo:

1. **elige** qué herramienta invocar en cada turno (`read_file`, `search`, `write_spec_file`, `run_tests`, `finish`),
2. **recibe el resultado real de esa ejecución** como input del turno siguiente.
3. **decide cuándo terminó** (`finish`).

El número de iteraciones no se sabe de antemano; solo su techo (5). Esas tres propiedades juntas elección de herramienta, observación real, condición de parada propia — son lo que separa un agente de una llamada a un LLM.

El loop vive en `[run-agent.py](run-agent.py)`. Es un ReAct clásico:

```
system + contexto precargado
   ↓
┌─ modelo responde {thought, action, args}
│      ↓
│  el harness ejecuta la herramienta   ← código, no el modelo
│      ↓
│  observación → se agrega al historial
└──────┘  hasta finish / 5 iteraciones / 600s / bucle detectado
```



### Lo agéntico es UN nodo, no todo el workflow

```
ticket → Postgres + migrate → precarga → ►LOOP◄ → validador → PR draft
         determinístico        determ.    agente   determ.    determ.
```

El modelo no elige el repo, ni la rama, ni si se publica, ni qué se commitea. Todo eso lo decide código. La razón: un prompt no es un mecanismo de control. Si la política de "no debilites un assert para que el test pase" viviera solo en el prompt, el modelo terminaría aflojando expects hasta dejar la suite verde y nos ocultaría exactamente los bugs que fuimos a buscar. Por eso la misma regla está en `[agent_prompt.py](agent_prompt.py)` **y** verificada en `validate-output.py](validate-output.py)`.

---



## ¿Dónde se ejecuta?

En un runner `ubuntu-latest` de GitHub Actions, disparado por el workflow reutilizable `[test-agent-reusable.yml` (`workflow_call`). El repo destino lo llama; este repo aporta la lógica.

Dos checkouts en el mismo runner:


| Ruta              | Qué es                                                   |
| ----------------- | -------------------------------------------------------- |
| `target/`         | el repo bajo test (hoy `sportmatch-sandbox`), rama `dev` |
| `agents-copilot/` | este repo, con los scripts del agente                    |


El modelo **no** corre en el runner: es una llamada HTTP a OpenRouter. Lo que corre en el runner es el loop, las herramientas y la suite de Jest.

También corre local, sin GitHub, con `[run-local.sh](run-local.sh)`:

```bash
LLM_API_KEY=... ./run-local.sh ~/dev/sportmatch-sandbox SPM-42 RF-03
```

Depurar un loop agéntico a través de la UI de Actions es insoportable, y con cuota diaria de modelos free cada corrida desperdiciada cuesta un día.

---



## ¿Cuál es su infraestructura?

**Runtime del modelo.** OpenRouter, tier gratuito, con una *cadena* de modelos y fallback (`[models.py](models.py)`). No es un modelo: cuando la cuota diaria de uno se agota (HTTP 429/402) se pasa al siguiente **conservando el historial** y la iteración en curso con 5 turnos no hay presupuesto para reiniciar el loop. 5xx hace backoff exponencial sobre el mismo modelo antes de avanzar. La cadena por defecto se pisa con `LLM_MODEL_CHAIN`.

**Oráculo.** Postgres en Docker (`docker compose up -d db`) + `prisma migrate deploy` + `prisma generate`, todo levantado por `setup-stack.sh](setup-stack.sh)` *antes* del loop. No se buildea la imagen de Nest: los tests son in-process con supertest, así que el contenedor `back` no se usa. El stack termina corriendo el spec de ejemplo escrito a mano: si ese no pasa, el problema es el entorno y el job aborta sin gastar una sola llamada al modelo.

**Contexto.** `[prefetch-context.py](prefetch-context.py)` precarga sin modelo de por medio: el ticket de Linear (GraphQL), el módulo completo del RF, el schema de Prisma, el harness de tests y el spec de ejemplo. Con 5 iteraciones el agente no puede gastar turnos descubriendo el repo.

**Presupuestos** (todos duros, en código):


| Límite                | Valor                         | Dónde                                                  |
| --------------------- | ----------------------------- | ------------------------------------------------------ |
| Iteraciones           | 5                             | `agent_prompt.MAX_ITERATIONS`                          |
| Corridas de tests     | 3                             | `run-agent.MAX_TEST_RUNS`                              |
| Tiempo total del loop | 600 s                         | `run-agent.MAX_WALL_SECONDS`                           |
| Tamaño de un spec     | 400 líneas / 12 KB            | `tools.MAX_SPEC_*`                                     |
| Timeout de la suite   | 600 s                         | `tools.TEST_TIMEOUT`                                   |
| Reintentos gratis     | 2                             | rechazos por validación de entrada no cobran iteración |
| Corte por bucle       | 2 acciones idénticas seguidas | `run-agent`                                            |


**Salida.** `agent-output.json` (lo que el agente declara), `agent-history.json` (el loop turno por turno, con qué modelo contestó cada uno), `validated.json` (lo que el validador aprueba) y `summary.md`. Todo se sube como artifact 14 días —
es la única forma de entender por qué el agente se trabó.

**Secrets y permisos.** `LLM_API_KEY` (requerido), `LINEAR_API_KEY` (opcional: sin él trabaja sin criterios de aceptación), `AGENTS_REPO_TOKEN` (PAT de lectura sobre este repo, que es privado). El `GITHUB_TOKEN` solo se expone en el último
step, el de la PR. Ningún step del loop lo recibe.

---



## ¿Qué herramientas tiene disponibles?

Seis, definidas en `[tools.py](tools.py)`. El modelo no ejecuta nada: emite una acción JSON y ese módulo la resuelve.


| Acción            | Args                                     | Qué hace                                                        | Tope                                    |
| ----------------- | ---------------------------------------- | --------------------------------------------------------------- | --------------------------------------- |
| `list_dir`        | `path`                                   | lista un directorio del repo                                    | excluye `node_modules`, `dist`, `.git`… |
| `read_file`       | `path`                                   | lee un archivo                                                  | 40 KB                                   |
| `search`          | `term`                                   | ripgrep dentro del servicio                                     | 40 coincidencias                        |
| `write_spec_file` | `path`, `content`                        | escribe un spec (archivo entero)                                | 400 líneas / 12 KB                      |
| `run_tests`       | `pattern?`                               | corre `npm run test:e2e` y devuelve exit code + cola del output | 3 corridas, 600 s, 8 KB de output       |
| `finish`          | `summary`, `acCoverage`, `suspectedBugs` | termina el loop                                                 | —                                       |




### Lo que no puede hacer

- **Escribir fuera de** `back/test/*.e2e-spec.ts`**.** El harness (`setup-e2e.ts`, `fixtures.ts`, `jest-e2e.json`, `stubs/`) está fuera de su alcance a propósito: si pudiera tocarlo, podría "arreglar" un test deshabilitando la autenticación o el truncado de la base. El spec de ejemplo tampoco se puede pisar.
- **Salirse del repo.** Toda ruta pasa por `safe_resolve`: nada de `..`, rutas absolutas ni symlinks hacia afuera.
- **Ejecutar comandos arbitrarios.** No hay `bash`. `run_tests` corre un comando fijo (`TEST_CMD`), no uno que el modelo componga.
- **Tocar GitHub.** Rama, commit y PR los hace `open-test-pr.py](open-test-pr.py)` después de que el validador aprobó.



### La regla que define el entregable

Cuando un test falla, el agente clasifica: 

- `test_error` (lo arregla), 
- `suspected_bug` (**no toca el test**, lo marca `it.failing(...)` y lo reporta con evidencia)
- `blocked`.

En Jest un `it.failing` pasa cuando falla: la suite queda verde y el bug vive en el reporte. Un `suspected_bug` legítimo vale más que diez tests verdes.

El validador verifica esto y aborta el job si un bloque marcado `suspected_bug` desapareció en una iteración posterior — como `write_spec_file` reemplaza el archivo entero, esa es la única forma de detectar que lo reescribió.



---

## Archivos


|                                              |                                                  |
| -------------------------------------------- | ------------------------------------------------ |
| `[run-agent.py](run-agent.py)`               | el loop — lo único agéntico                      |
| `[agent_prompt.py](agent_prompt.py)`         | system prompt y política ante fallos             |
| `[tools.py](tools.py)`                       | las seis herramientas y sus guardarraíles        |
| `[models.py](models.py)`                     | cadena de modelos con fallback                   |
| `[prefetch-context.py](prefetch-context.py)` | contexto precargado sin modelo                   |
| `[setup-stack.sh](setup-stack.sh)`           | el oráculo: Postgres + migrate + spec de ejemplo |
| `[validate-output.py](validate-output.py)`   | validador determinístico                         |
| `[open-test-pr.py](open-test-pr.py)`         | rama, commit y PR draft                          |
| `[run-local.sh](run-local.sh)`               | corrida completa sin GitHub Actions              |
| `[test_tools.py](test_tools.py)`             | tests de los guardarraíles de `tools.py`         |


