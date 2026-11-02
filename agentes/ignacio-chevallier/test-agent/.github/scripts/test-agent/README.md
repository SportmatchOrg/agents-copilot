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

**El arnés corre el oráculo, el modelo no lo pide.** Medido sobre dos corridas con historial: el 45% de los turnos eran un `run_tests` y NINGUNO vino después de algo que no fuera un write. No era una decisión, era un reflejo que costaba una llamada entera, con su deadline de 200s y su chance de volver con JSON roto. Ahora cada `write_spec_file` devuelve la escritura y el veredicto en una observación, y la corrida va al historial como turno `forced` que no gasta iteración. Las únicas acciones son `write_spec_file` y `finish`: `read_file`, `list_dir` y `search` tuvieron cero usos en 31 turnos y se fueron.

**El oráculo corre tres varas.** `run_tests` corre Jest, después `tsc --noEmit` y después ESLint sobre los specs del agente. Las tres porque las tres lo juzgan: el validador aborta si no compila y el CI del repo destino corre `npm run lint`. En la PR #61 el spec compiló, pasó los tests y el CI la volteó con 8 errores de `res.body` sin tipar. Los errores de lint se parsean de `--format json` y se rinden una línea por problema con archivo, línea y regla: el `stylish` por default alinea con padding y va precedido del path absoluto, así que recortar por la cola le dejaba al modelo una línea cortada al medio y después espacios, y se colgó reescribiendo lo mismo hasta morir en la iteración 4 de 15. Las dos varas se informan JUNTAS aunque el compile ya haya fallado: cortar en el tsc mandó una corrida a un ping-pong de 15 iteraciones — el agente tipaba `res.body` para callar al lint, eso destapaba TS18048 en `.find()`, destipaba para callar al compile, y volvía el lint. ESLint se invoca derecho y acotado a los specs escritos, sin `--fix`: el `npm run lint` del repo destino lleva `--fix` sobre `src/`, que el agente tiene prohibido tocar.

**Contrato de imports.** El prefetch deriva de los archivos del harness qué símbolo se exporta desde cuál y lo pone como bloque aparte. El contenido completo ya iba en el contexto y no alcanzó: en SPO-197 el agente importó `TEST_USER`/`OTHER_USER` de `setup-e2e` (viven en `fixtures`) en las dos corridas, porque `setup-e2e.ts` los **importa** y el símbolo aparece ahí sin estar re-exportado.

**Tope de 200s por llamada.** `urlopen(timeout=...)` es por operación de socket, no un deadline total: mientras lleguen bytes la llamada no corta, y el free tier mantiene la conexión viva mientras el pedido espera en cola. Así hubo llamadas de 387s, 464s y 600s, y una corrida con `MAX_WALL_SECONDS=1800` terminó en 2393s. El pedido va a un hilo daemon y se lo abandona si no vuelve en `REQUEST_DEADLINE` (200s, pisable con `LLM_REQUEST_DEADLINE`); un modelo que no contesta en 200s no se reintenta, se cambia.

**La cadena se reordena con datos, no con el papel.** nex-n2.5-pro y dots-3 entraron por declarar `structured_outputs` y ese fue el criterio equivocado: son patológicamente razonadores —62093 y 59274 caracteres de `reasoning` para devolver `content` vacío— y entre las dos se comieron la mayor parte de los 1896s de la corrida 6. `effort: low` no las frena. Quedaron los dos nemotron, que son los únicos que produjeron trabajo útil.

**Razonamiento y tope de salida.** Los modelos de la cadena razonan, y el razonamiento se cobra contra `max_tokens`. En SPO-197 nemotron gastó los 8000 tokens pensando (19428 chars de `reasoning`) y lo cortaron a mitad del JSON: cuatro `finish_reason='length'` seguidos con las dos keys y 0 iteraciones. Se pide `reasoning: {effort: low}` —la forma portable, los cuatro modelos la declaran— y el tope subió a 16000. Si un modelo rechaza el campo se reintenta sin él, sin quemar el modelo.

**Segunda cuenta (opcional).** El tope `free-models-per-day` de OpenRouter se cobra por **cuenta**, no por modelo: cuando pega, los cuatro modelos de la cadena devuelven 429 en ~300ms y el fallback de modelos no sirve para nada (SPO-197 murió así en la iteración 5 de 15). La rotación no mira solo la cuota: un cuelgue de 200s o una respuesta vacía también son fallos de capacidad, y son lo que otra cuenta puede arreglar (con el trigger atado al 429, la corrida 7 murió con 0 iteraciones y la segunda key sin estrenar). Con el secret `LLM_API_KEY_FALLBACK` seteado a una key de **otra** cuenta, la cadena reinicia desde el primer modelo con esa key. Solo rota si hubo un 402/429: si la cadena murió por JSON roto, otra cuenta devuelve el mismo JSON roto. Una key más del mismo dueño no compra nada.

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


