# SportMatch — Plan de implementación del API Test Agent

> Agente #9 del paquete. A diferencia de los ocho anteriores, **este sí es un
> agente** en el sentido estricto del término (§2). Todo lo demás del paquete
> son workflows.
>
> Documento hermano: `SPORTMATCH_QA_REVIEW_AGENT_PLAN.md`. Este plan reusa
> deliberadamente la infraestructura que aquel dejó construida (§6).
>
> **v2 (2026-08-27)** — revisado contra el código real de ambos repos. Cinco
> decisiones de la v1 estaban basadas en AGENTS.md, que no coincide con el
> código. Los cambios están marcados con ⚠️ en cada sección.

---

## 0. Repo objetivo y regla estricta

**Repo objetivo: `SportmatchOrg/sportmatch-sandbox`.**

**REGLA ESTRICTA: este agente NO escribe en `SportmatchOrg/sportmatch`.** Ni
PRs, ni commits, ni pedidos de permisos. Todo — el backend portado, el harness
de tests, los tests generados, el workflow — vive en el **sandbox**.

**Única excepción, ya ejecutada:** una lectura de `sportmatch@dev` para portar
el backend (§3.0). Autorizada explícitamente, de una sola vez, sin escritura.

---

## 1. Objetivo

Dado un ticket de Linear con criterios de aceptación, generar tests de
integración contra la API REST del backend, **correrlos de verdad**, iterar
hasta que cubran los AC, y entregar el resultado como PR en draft.

Lo que NO hace:

- No modifica código de aplicación. Solo escribe `back/test/*.e2e-spec.ts`.
- No escribe el harness de tests: eso lo hacemos nosotros (§3.6).
- No mergea nada. Entrega un draft y ahí termina su trabajo.
- No corre contra staging ni producción (§3.2).
- No "arregla" un test para que pase cuando sospecha que el bug es del código
  (§4). Esta es la regla más importante del documento.
- Los cambios figuran como autor **el agente**, nunca Ignacio Chevallier (§7.2).
  Requerimiento explícito.

---

## 2. Por qué esto es un agente y los otros ocho no

### 2.1. La distinción

Siguiendo la taxonomía de Anthropic (*Building effective agents*):

- **Workflow**: LLMs y herramientas orquestados por rutas de código
  predefinidas. Los ocho agentes actuales del paquete, incluido `qa-review`,
  entran acá: la secuencia de pasos está escrita en YAML y el número de llamadas
  al modelo se sabe de antemano.
- **Agente**: el LLM dirige dinámicamente su propio proceso y su uso de
  herramientas. Loop LLM → herramienta → feedback del entorno, sin número de
  pasos predecible.

### 2.2. El oráculo

Un agente necesita una señal del entorno, **externa al modelo**, que le diga si
lo que hizo está bien. Sin esa señal el loop no tiene contra qué iterar y lo que
queda es un workflow caro con temperatura.

Acá el oráculo es el **exit code de `npm run test:e2e`**. Es objetivo, barato y
repetible. Por eso este caso se eligió antes que un agente de auto-fix sobre los
criterios QA: no hay forma automática de verificar "está en español" o
"reutiliza el componente existente", así que ese agente iteraría contra su propia
opinión.

### 2.3. Qué lo hace agente, concretamente

1. El modelo decide **qué herramienta invocar** en cada paso.
2. Recibe el **resultado real** de esa invocación (stdout de Jest, contenido de
   un archivo) como input del paso siguiente.
3. **Nadie puede predecir cuántas iteraciones** hacen falta: depende de cuántos
   AC tenga el ticket, de si el endpoint existe, de si el fixture alcanza.
4. El propio modelo decide **cuándo terminó**.

---

## 3. Decisiones tomadas

### 3.0. ⚠️ Port del backend al sandbox (snapshot único)

**Hallazgo que motivó esto:** el sandbox no tenía backend. Contenía
`src/partido.js` — cinco líneas de JavaScript, `"test": "echo ok"` — y se
autodescribe como "stub para testing de agentes". Sin API no hay oráculo, y sin
oráculo esto no es un agente.

**Decisión:** portar `SportmatchOrg/sportmatch@dev` al sandbox **una sola vez**,
y **no sincronizar nunca más**. El snapshot *es* el sistema bajo prueba.

Qué se porta, respetando rutas exactas para que nada del plan tenga que
traducirse:

```
back/                    el servicio NestJS completo
docker-compose.yml       db + back (usamos solo db, §3.2)
.nvmrc .editorconfig     lo mínimo de raíz para que buildee
```

No se porta el frontend: este agente no lo toca.

**Consecuencia asumida:** el snapshot va a divergir de producción. Un
`suspected_bug` encontrado acá vale como hallazgo sobre *el código del día del
port*, no sobre producción. Es un costo aceptado a cambio de partir de algo real
en vez de un stub.

### 3.1. Dónde vive qué

| Artefacto | Repo | Por qué |
|---|---|---|
| Lógica del agente, prompts, herramientas, validador | `agents-copilot` | Mejorarlo no requiere tocar el repo destino |
| Backend portado | `sportmatch-sandbox`, `back/` | §3.0 |
| **Harness de tests** (config, setup, fixtures) | `sportmatch-sandbox`, `back/test/` | Lo escribimos nosotros, no el agente (§3.6) |
| **Tests generados** | `sportmatch-sandbox`, `back/test/*.e2e-spec.ts` | Única ruta escribible por el agente |

**Descartado: un repo nuevo solo para tests.** Un test que no vive al lado del
código que prueba no lo corre el CI, no rompe en la misma PR que introduce la
regresión, y se desincroniza en dos sprints. Es el clásico "repo de QA" muerto.
El sandbox no es ese caso: tiene la app entera adentro.

### 3.2. ⚠️ Oráculo: supertest in-process, con Postgres en Docker

**Cambio respecto de la v1**, forzado por el código real: los controllers están
protegidos con `@UseGuards(FirebaseAuthGuard)` y `.env.example` exige
`FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL` y `FIREBASE_PRIVATE_KEY`.

Contra un contenedor no se puede inyectar un mock del guard: haría falta un token
real de Firebase. Entonces los tests **no** son caja negra por HTTP. Son
`Test.createTestingModule` + `supertest`, con `overrideGuard(FirebaseAuthGuard)`
devolviendo un usuario fijo — el patrón estándar de NestJS, que además **ya está
prescrito por las skills del propio repo**: `back/.agents/skills/nestjs-best-practices/rules/test-e2e-supertest.md`
y `test-use-testing-module.md`.

Sigue siendo una prueba real de la API: supertest levanta la app Nest de verdad y
emite requests HTTP reales contra ella. Lo único simulado es la identidad.

Qué levanta el runner:

```
docker compose up -d db        ← SOLO Postgres
npx prisma migrate deploy      ← 3 migraciones existentes
npm run test:e2e               ← Jest levanta Nest in-process
```

**No se buildea la imagen de Nest.** Eso saca el paso más lento del job (build
de un Dockerfile de Node en cada corrida) y elimina el servicio `back` del
compose, con su dependencia de `back/.env` vía `env_file`.

Descartado pegarle a staging en Azure: es compartido (dos corridas se pisan y los
tests salen flaky, y un oráculo flaky es peor que ninguno) y mutable (el agente
necesita POST y DELETE). El runner ya es efímero: es el sandbox que necesitamos,
gratis.

### 3.3. Trigger: `workflow_dispatch` con el identifier del ticket

El QA lo lanza a mano pasando el identifier de Linear. Elegido sobre correr en
cada PR o sobre un cron porque el gasto es explícito y por decisión humana, no
mete ruido en las PRs durante el piloto, y no depende del dispatcher pendiente en
SPO-181 — en el sandbox controlamos el wrapper.

Migrar a un trigger automático es un cambio de una línea el día que las métricas
de §11 lo justifiquen.

### 3.4. Entrega: PR en draft

Rama `bot/tests-<IDENTIFIER>`, PR en draft contra `dev` del sandbox, con el
reporte del agente en el cuerpo. Un humano revisa y marca ready.

### 3.5. ⚠️ Alcance del piloto: RF-03 (Partidos)

**Cambio respecto de la v1.** La v1 eligió RF-01 (Autenticación) porque AGENTS.md
lo describe como "registro email+password, login" y sonaba autocontenido.
**AGENTS.md no coincide con el código:** no hay auth propia, la delega a Firebase.
RF-01 es el RF *más* acoplado a un servicio externo, no el menos.

Los módulos realmente implementados son dos:

| Módulo | Estado | Migración |
|---|---|---|
| `back/src/partidos/` | controller + service + repository + 2 DTOs | `init_partido`, `init_participante` |
| `back/src/users/` | controller + service + repository + 2 DTOs | `init_user` |

RF-03 gana: es el único con reglas de negocio verificables (validación de campos,
cupo, visibilidad) en vez de CRUD puro. Y el stub que ya había en el sandbox
(`src/partido.js`) también decía RF-03.

### 3.6. ⚠️ El harness lo escribimos nosotros, el agente solo escribe specs

**Decisión nueva, y es la que hace viable el presupuesto de 5 turnos.**

Nosotros escribimos, una vez, en `back/test/`:

| Archivo | Qué hace |
|---|---|
| `jest-e2e.json` | La config que `test:e2e` ya invoca y que hoy no existe |
| `setup-e2e.ts` | Truncado de tablas en `beforeEach` + `createTestApp()` con el guard overrideado |
| `fixtures.ts` | Usuario de prueba fijo, factories de partido |

El agente **solo** escribe `back/test/<algo>.e2e-spec.ts`, importando ese harness.

Tres razones, en orden de importancia:

1. **Aislamiento de la base.** Sin truncado garantizado entre tests, un spec que
   crea un partido pasa la primera corrida y falla la segunda por estado sucio —
   y el agente lo clasifica como `suspected_bug`. **Falso positivo garantizado**,
   que es justo la métrica que más nos importa mantener en cero (§11).
2. **El override del guard queda fuera del alcance del modelo.** No puede
   "arreglar" un test deshabilitando la autenticación.
3. **Achica lo que tiene que escribir.** Con `createTestApp()` y fixtures dados,
   un spec son 20 líneas y no 120. Los 5 turnos alcanzan.

### 3.7. Portabilidad: el sandbox es un stand-in, no el destino final

**Operamos el sandbox como si fuera producción**, con la intención de migrar al
repo real más adelante. Entonces nada de lo que construimos puede tener el
sandbox — ni sus rutas — hardcodeado. Esto no es prolijidad: es la diferencia
entre migrar cambiando inputs y migrar reescribiendo.

| Cosa | Cómo se parametriza | Default |
|---|---|---|
| Repo destino | input `target_repo` + var | `sportmatch-sandbox` |
| Rama base | input `base_branch` | `dev` |
| Raíz del servicio | `SERVICE_ROOT` | `back` |
| Ruta de specs | derivada de `SERVICE_ROOT` | `back/test/*.e2e-spec.ts` |
| Mapa RF → módulo | dict en config (§5.3) | `RF-03 → src/partidos` |
| Cadena de modelos | `LLM_MODEL_CHAIN` (§5.5) | §5.5 |
| Comando de tests | `TEST_CMD` | `npm run test:e2e` |

Ojo con `SERVICE_ROOT`: la v1 tenía `backend/` escrito a mano en seis secciones y
resultó ser `back/`. Si esa ruta vuelve a aparecer literal en el código, la
migración se rompe en los mismos seis lugares.

**El único hardcode permitido es el guardarraíl inverso.** El validador (§8)
aborta si el repo destino no está en una allowlist. Hoy esa allowlist tiene un
solo elemento — `sportmatch-sandbox` — y el día que se migre se agrega el
segundo: ese commit es la decisión explícita de apuntar a producción, no un
descuido de configuración.

Migrar a prod queda siendo: dos inputs, una línea en la allowlist, y volver al
PAT por el tema de permisos de §7.1.

---

## 4. Política ante un test que falla

**La decisión central del diseño.** Sin una política explícita, el modelo va a
debilitar los asserts hasta que la suite quede verde, y te va a ocultar
exactamente los bugs que fuiste a buscar.

Cuando un test falla, el agente clasifica en una de tres:

| Clase | Qué significa | Qué hace el agente |
|---|---|---|
| `test_error` | El test está mal escrito: ruta equivocada, payload inválido, fixture que no existe | Corrige el test y reintenta |
| `suspected_bug` | El test es correcto y el código no cumple el AC | **NO toca el test.** Lo marca con `it.failing(...)`, lo documenta y sigue con el resto |
| `blocked` | No se puede determinar: el endpoint no existe, el AC es ambiguo | Deja de intentar sobre ese AC y lo reporta |

Tres reglas duras que van en el prompt y **también** en el validador (§8), porque
un prompt no es un mecanismo de control:

1. **Prohibido debilitar un assert existente para lograr que un test pase.** Si
   la única forma de que pase es esperar menos, es `suspected_bug`.
2. Un test marcado `suspected_bug` en una iteración **no se puede reescribir ni
   eliminar** en una iteración posterior. Como `write_spec_file` reemplaza el
   archivo entero, el validador guarda un snapshot del bloque en la iteración que
   lo marcó y exige que siga presente, verbatim, en el archivo final.
3. Cada `suspected_bug` necesita: el AC que viola, el request que lo dispara, lo
   esperado y lo obtenido. Sin evidencia, no se reporta.

### Semántica de `it.failing` (leer antes de implementar)

`it.failing()` de Jest **pasa cuando el test falla** y falla cuando el test pasa.
Dos consecuencias que hay que aceptar a propósito:

- La suite queda **verde** aunque haya bugs marcados. Es lo que queremos: la PR
  no llega en rojo, y los bugs viven en el reporte, no en el exit code.
- Cuando un dev arregla el bug, **ese test empieza a fallar**. Es la señal de
  "ya podés sacarle el `.failing`". Hay que documentarlo en el cuerpo de la PR o
  parece un test roto.

Requiere Jest ≥ 28. Verificar en la fase 0.

Los `suspected_bug` son el **entregable de más valor** del agente, no su fracaso.
Van al cuerpo de la PR y a un comentario en el ticket de Linear.

---

## 5. Arquitectura del loop

### 5.1. Protocolo: acción JSON, no function calling nativo

`llm_client.call_json` ya existe y funciona contra cualquier endpoint
OpenAI-compatible. El tool calling nativo **no** está soportado de forma uniforme
entre los proveedores de OpenRouter.

Entonces el loop usa el mismo patrón que ya usa el Scout: el modelo devuelve una
acción por turno, el código la ejecuta, y el resultado se appendea al historial.

```json
{
  "thought": "el DTO exige cupo mínimo, agrego el caso de cupo 0",
  "action": "write_spec_file",
  "args": { "path": "back/test/partidos.e2e-spec.ts", "content": "..." }
}
```

Ventaja lateral: `thought` queda en el log de cada iteración. Es la transparencia
de los pasos de planificación que el artículo pide, y es lo único que te va a
permitir depurar por qué el agente se trabó.

### 5.2. ⚠️ Herramientas

**Se elimina `http_call`.** Con tests in-process (§3.2) no hay servidor al cual
pegarle: le pegaría a un contenedor que ni siquiera levantamos. La exploración se
hace con la precarga (§5.3) y con `run_tests` sobre un spec puntual.

| Herramienta | Args | Notas |
|---|---|---|
| `list_dir` | `path` | Excluye `node_modules`, `dist` |
| `read_file` | `path` | Solo lectura, 40 KB máx, cualquier ruta del repo |
| `search` | `term` | ripgrep, sin shell, máx 40 matches |
| `write_spec_file` | `path`, `content` | **Solo** `back/test/*.e2e-spec.ts`. Máx 200 líneas / 8 KB (§5.6) |
| `run_tests` | `pattern?` | `npm run test:e2e`. Exit code + stdout recortado a 8 KB |
| `finish` | `summary`, `acCoverage`, `suspectedBugs` | Termina el loop |

El path traversal se valida con la misma función `safe_resolve` que ya usa
[resolve-context.py](../.github/scripts/qa-review/resolve-context.py).

### 5.3. Presupuesto, precarga y condiciones de parada

- **Máx 5 iteraciones.**
- **Máx 3 corridas de** `run_tests`.
- **Máx 10 minutos** de wall clock en el step del agente.
- Corte por **requests al proveedor**: el límite real de los modelos free de
  OpenRouter es la cuota diaria, no el dinero (§5.5).

Parada normal: el modelo llama a `finish`. Parada por presupuesto: se entrega lo
que haya, marcado como `partial` — nunca se descarta el trabajo. Si repite la
misma acción con los mismos args dos veces seguidas, se lo corta por bucle.

**Cinco iteraciones no alcanzan para que el agente descubra el repo por su
cuenta.** Antes del loop, y de forma determinística, se precarga:

- `back/src/<módulo>/` completo — controller, service, repository, DTOs
- `back/prisma/schema.prisma`
- `back/test/setup-e2e.ts` y `fixtures.ts` (tiene que saber qué helpers tiene)
- Un spec de ejemplo, si ya existe alguno
- Los AC del ticket de Linear

El **mapeo RF → módulo es un dict estático** en config, no una llamada al
modelo: `RF-02 → back/src/users`, `RF-03 → back/src/partidos`. Agregar un módulo
es una línea.

Presupuesto realista de los 5 turnos, ya sin `http_call`:

| Turno | Uso esperado |
|---|---|
| 1 | `write_spec_file` — primer set de casos desde los AC |
| 2 | `run_tests` |
| 3 | corregir (`write_spec_file`) o clasificar el fallo (§4) |
| 4 | `run_tests` |
| 5 | `finish` |

### 5.4. El arnés alrededor

El loop es un nodo dentro de un workflow determinístico:

```
workflow_dispatch(SPM-42)
  → traer el ticket de Linear y sus AC          (código)
  → docker compose up -d db                      (código)
  → prisma migrate deploy                        (código)
  → healthcheck de Postgres                      (código, gate)
  → precarga de contexto (§5.3)                  (código)
  → ►► LOOP DEL AGENTE ◄◄                        (LLM + herramientas)
  → validar la salida                            (código, §8)
  → rama + PR draft + comentario en Linear       (código, único side effect)
  → subir artifacts (historial completo)         (código, always())
```

Si el healthcheck falla, el loop nunca arranca. Gastar cuota contra un stack que
no levantó es tirar el día.

### 5.5. Modelos: solo free de OpenRouter, con cadena de fallback

**Restricción:** únicamente modelos `:free` de OpenRouter. Como el tier gratis se
agota, la elección no es un modelo sino una **cadena**.

Criterios, en orden: soporte de **structured outputs** (el protocolo §5.1 vive o
muere con eso), competencia en **código TypeScript**, contexto suficiente, y
`seed` para reproducibilidad.

| Puesto | Modelo | Contexto | Por qué |
|---|---|---|---|
| **Primario** | `z-ai/glm-5.2:free` | 256k | El único que combina `structured_outputs` + `response_format` + `seed` + `reasoning_effort`. GLM es la familia más fuerte en código y uso agéntico de la lista |
| **Fallback 1** | `minimax/minimax-m3:free` | 1M | `structured_outputs` + `seed`. **Ya probado en este repo** — `qa-review-reusable.yml` lo declara verificado |
| **Fallback 2** | `nvidia/nemotron-3-super-120b-a12b:free` | 262k | `structured_outputs` + `seed`. Otra familia y otro proveedor: si se agota la cuota de uno, es poco probable que el otro esté igual |
| **Último recurso** | `openrouter/free` | 200k | El router propio de OpenRouter. No determinístico y puede rutear a un modelo sin structured outputs — por eso es último |

**Descartados, con motivo:** `poolside/laguna-s-2.1:free` y
`cohere/north-mini-code:free` están especializados en código, que suena ideal,
pero **no exponen `response_format` ni `structured_outputs`**; con 5 iteraciones,
un turno perdido por JSON malformado cuesta el 20% del presupuesto.
`nvidia/nemotron-3-ultra-550b-a55b:free` y `thinkingmachines/inkling:free` tienen
1M de contexto pero tampoco exponen structured outputs. Los `google/gemma-4-*`
sí, pero quedan cortos para escribir tests.

**Cuándo se avanza en la cadena:**

| Señal | Acción |
|---|---|
| `429` / cuota diaria agotada | Siguiente modelo |
| `402` | Siguiente modelo |
| `503` | **Backoff exponencial sobre el MISMO modelo** primero (ya está en `llm_client.py`), y recién si persiste, avanzar |
| JSON inválido dos veces seguidas | Siguiente modelo |

**Política sticky:** al cambiar de modelo se **conserva el historial** y se sigue
en la iteración donde estaba. No se reinicia: con 5 turnos no hay presupuesto.
Cada iteración registra **qué modelo la produjo** — sin ese dato no vas a poder
explicar un cambio de comportamiento a mitad de corrida.

**Configuración:** la cadena vive en `LLM_MODEL_CHAIN` (coma-separada), con la
precedencia `input > vars > default` que ya usa el QA agent. Nunca hardcodeada.
La lista de arriba es el default del 2026-08-27, verificada contra
`openrouter.ai/api/v1/models`, no una constante.

### 5.6. ⚠️ Límite de tokens de salida

`write_spec_file` manda el archivo **entero** en cada escritura. Los modelos free
suelen capear la salida en 4–8k tokens: un spec de 300 líneas reescrito dos veces
se trunca, rompe el JSON, y perdés un turno de cinco.

Mitigaciones, las tres juntas:

- **Cap duro de 200 líneas / 8 KB por spec**, validado por la herramienta.
- **Un archivo por módulo**, no uno por AC.
- El harness de §3.6 mantiene los specs cortos: sin él, cada archivo repetiría
  40 líneas de setup.
- `max_tokens` declarado explícitamente en cada request, no por default.

---

## 6. Lo que se reusa del QA agent

No se reescribe nada de esto:

- `llm_client.py` — reintentos, backoff ante 503, `report_unavailable`, la
  precedencia `input > vars > default`
- `qa_context.py` — bloques de contexto de Linear
- `safe_resolve` de `resolve-context.py` — validación de paths contra escape
- El patrón de artifacts con prompts y salidas crudas
- El `concurrency` a nivel job, nunca a nivel workflow

---

## 7. Seguridad y guardrails

### 7.1. En el sandbox: `GITHUB_TOKEN`, no PAT

Dos razones que apuntan al mismo lado:

1. **Autoría (§1).** Una PR creada con el PAT del QA figura como escrita por
   Ignacio Chevallier. Creada con el `GITHUB_TOKEN`, el autor es
   `github-actions[bot]` — que es lo que pide el requerimiento.
2. **El sandbox es nuestro.** Ahí podés declarar `contents: write` y
   `pull-requests: write` sin pedirle nada a nadie. El PAT existía para saltear un
   techo de permisos que en el sandbox no existe.

La regla general del paquete **sigue vigente para el repo de producción**: todo
lo que escriba allá va por el PAT, porque allá el techo de `permissions:` no lo
controlamos.

### 7.2. Autoría del agente

- PR creada con `GITHUB_TOKEN` → autor `github-actions[bot]`.
- Commits con identidad de bot, seteada antes de commitear:

  ```bash
  git config user.name  "sportmatch-test-agent[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  ```

- El cuerpo de la PR abre declarando que la generó el agente, con el ticket, el
  modelo que la produjo y cuántas iteraciones usó.
- **Nada de `Co-authored-by:`** con un mail humano. El validador aborta si aparece.

### 7.3. Prevención de loop

Con §7.1 el riesgo **desaparece por construcción**: una PR creada con
`GITHUB_TOKEN` no dispara otros workflows (una creada con PAT sí). Se deja igual
el `if:` que ignora ramas `bot/*` como segunda capa.

### 7.4. El resto

- El modelo **nunca ve ningún token de GitHub**. Ningún step del loop lo recibe
  en su `env`.
- Escritura restringida a `back/test/*.e2e-spec.ts`, validada en la herramienta y
  **re-verificada con `git diff --name-only`** antes de commitear. Si tocó algo
  fuera — el harness incluido — se aborta el job.
- **Sin credenciales de Firebase en CI.** El guard se overridea en el harness; no
  hay proyecto Firebase real involucrado.
- La base de datos es un Postgres efímero del runner con `root/root`. No hay
  datos reales en ningún momento.
- Nada se mergea solo. El draft es el checkpoint humano.

---

## 8. Validador determinístico

Entre la salida del agente y GitHub va un validador, igual que en
[validate-review.py](../.github/scripts/qa-review/validate-review.py).

**Aborta el job:**

- Archivos modificados fuera de `back/test/*.e2e-spec.ts`
- Un test marcado `suspected_bug` fue reescrito o eliminado (§4, regla 2)
- La suite no compila (`tsc --noEmit` sobre los tests)
- JSON de salida con forma inválida
- El repo destino no es `sportmatch-sandbox` (§0)
- Aparece un `Co-authored-by:` con un mail humano (§7.2)

**Degrada sin abortar:**

- `suspectedBugs` sin evidencia completa → se cae del reporte, se loguea
- AC declarado como cubierto sin un `it()` que lo referencie → se marca como no
  cubierto

### ⚠️ Cómo se mide la cobertura de AC

En la v1, `acCoverage` lo auto-reportaba el modelo — o sea, la métrica principal
de §11 la producía la cosa que estábamos midiendo.

**Convención obligatoria:** cada `it()` arranca con el identificador del AC.

```ts
it('[AC-2] rechaza crear un partido con cupo 0', async () => { ... });
```

El validador extrae los `[AC-n]` de los specs con una regex y los cruza contra la
lista de AC del ticket. La cobertura pasa a ser un dato medido, no declarado.

---

## 9. Estructura de archivos

En `agents-copilot` (la lógica):

```
.github/scripts/test-agent/
  run-agent.py            el loop
  tools.py                herramientas + validación de paths y de tamaño
  models.py               cadena de fallback + reglas de avance (§5.5)
  prefetch-context.py     precarga determinística + mapa RF → módulo (§5.3)
  agent_prompt.py         instrucciones + política de fallo (§4) + convención [AC-n]
  setup-stack.sh          docker compose up db + migrate + healthcheck
  validate-output.py      §8
  open-test-pr.py         rama, commit, PR draft, comentario en Linear
  run-local.sh            correrlo entero en local, sin GitHub Actions

.github/workflows/
  test-agent-reusable.yml el arnés (§5.4)
```

En `sportmatch-sandbox` (lo que la fase 0 deja listo):

```
back/                          el servicio portado (§3.0)
back/test/jest-e2e.json        config que test:e2e ya invoca y hoy no existe
back/test/setup-e2e.ts         createTestApp() + truncado en beforeEach  ← nuestro
back/test/fixtures.ts          usuario fijo + factories                   ← nuestro
back/test/*.e2e-spec.ts        ÚNICA ruta escribible por el agente
docker-compose.yml             db + back (usamos solo db)
.github/workflows/             el wrapper que llama al reusable
```

`run-local.sh` no es opcional: depurar un loop agéntico a través de GitHub
Actions es insoportable, y lo vas a necesitar desde la primera hora.

---

## 10. Fases

| # | Fase | Entregable | Sin LLM |
|---|---|---|---|
| 0a | **Port** | `sportmatch@dev` → sandbox: `back/`, `docker-compose.yml`, configs de raíz (§3.0) | Sí |
| 0b | **Harness** | `jest-e2e.json` + `setup-e2e.ts` con `overrideGuard` + `fixtures.ts`. Un spec de ejemplo escrito a mano que pase (§3.6) | Sí |
| 0c | **Verificar Jest ≥ 28** | `it.failing` tiene que existir (§4) | Sí |
| 1 | Herramientas | `tools.py` + tests: path traversal, cap de 200 líneas, extensión `.e2e-spec.ts` | Sí |
| 2 | Stack en CI | `setup-stack.sh`: Postgres + migrate + healthcheck, sin build de imagen | Sí |
| 3 | Modelos | `models.py`: cadena, avance por 429/402/503, modelo por iteración (§5.5) | Sí |
| 4 | Precarga | `prefetch-context.py` + mapa RF → módulo. Sin esto el loop de 5 turnos no cierra | Sí |
| 5 | Loop | `run-agent.py` con presupuesto y detección de bucle. Primer end-to-end sobre RF-03 | No |
| 6 | Política de fallo | §4 en el prompt + validador + snapshot. Se prueba plantando un bug en `partidos.service.ts` del sandbox | No |
| 7 | Entrega | PR draft con autoría de bot (§7.2) + comentario en Linear | Parcial |
| 8 | Piloto | 5 tickets reales, métricas de §11 | — |

**La fase 0b es la más importante y la más subestimada.** Ese spec de ejemplo
escrito a mano es el que prueba que el oráculo funciona antes de que ningún
modelo escriba una línea. Si no logramos que un test e2e pase a mano, el agente
tampoco va a poder.

Las fases 0 a 4 **no gastan un solo token**. Con modelos free y 5 iteraciones,
cada corrida desperdiciada por una herramienta rota cuesta cuota que no vuelve
hasta mañana.

---

## 11. Cuándo lo damos por bueno

Sobre 5 tickets del piloto:

- **≥ 70% de AC cubiertos**, medido con la convención `[AC-n]` de §8 — no
  autodeclarado
- **0 falsos** `suspected_bug` — un bug reportado que no era bug quema la
  confianza más rápido que cualquier otra cosa
- **0 asserts debilitados** entre iteraciones (auditable en el historial)
- **≤ 4 iteraciones de mediana** (de 5) — si toca el techo consistentemente, el
  problema es la precarga de §5.3, no el modelo
- **≥ 60% de las PRs draft** llegan a merge con edición menor
- **0 PRs con autoría humana** (§7.2)
- **0 tests que fallen por estado sucio de la base** — si aparece uno, el harness
  de §3.6 está mal, no el agente

Si el agente termina en 2 iteraciones de forma consistente, no necesitabas un
agente: convertilo en workflow de dos pasos y ahorrate el loop.

**Validación: la hace Ignacio.** No se delega ni se automatiza el criterio de
aceptación del piloto.

---

## 12. Riesgos

| Riesgo | Mitigación |
|---|---|
| El agente debilita asserts para llegar a verde | §4 + validador §8 + snapshot del bloque marcado |
| **Falso `suspected_bug` por estado sucio de la base** | §3.6: truncado en `beforeEach`, en un harness que el agente no puede tocar |
| El agente reescribe el archivo y borra un `suspected_bug` | §4 regla 2: snapshot verbatim, el validador aborta |
| Salida truncada por `max_tokens` | §5.6: cap de 200 líneas, un archivo por módulo, `max_tokens` explícito |
| Loop infinito / cuota quemada | §5.3: cuatro techos independientes |
| Se agota el tier free de OpenRouter | §5.5: cadena de 3 + `openrouter/free` |
| Cambio de modelo a mitad del loop altera la conducta | §5.5: sticky + modelo registrado por iteración |
| 5 iteraciones no alcanzan | §5.3: precarga determinística + harness que acorta los specs |
| Una PR figura como escrita por Ignacio | §7.2: `GITHUB_TOKEN` + identidad de bot + chequeo en el validador |
| Alguien apunta el agente al repo de producción | §0 + el validador aborta si el destino no es el sandbox |
| `it.failing` confunde ("¿por qué falla un test verde?") | §4: documentado en el cuerpo de la PR |
| El snapshot portado diverge de producción | §3.0: aceptado a propósito. El hallazgo vale sobre el snapshot |
| Contexto que revienta la ventana | Historial recortado: `thought` + acción + resultado a 8 KB |

---

## 13. Decisiones cerradas

| # | Pregunta | Decisión | Cómo se resolvió |
|---|---|---|---|
| 1 | ¿Contra qué corre? | Backend de prod **portado al sandbox**, snapshot único sin sync | §3.0 — el sandbox era un stub de 5 líneas |
| 2 | ¿Seed / fixtures? | Harness propio con truncado + factories, **escrito por nosotros** | §3.6 |
| 3 | ¿`test:e2e`? | El script ya existe y está roto: falta `back/test/jest-e2e.json` | Fase 0b |
| 4 | Presupuesto | Solo free de OpenRouter, cadena de fallback, **máx 5 iteraciones** | §5.5 |
| 5 | ¿Quién valida? | **Ignacio**, sobre las PRs draft | §11 |
| 6 | ¿Cómo pasa la auth? | `overrideGuard(FirebaseAuthGuard)` in-process con supertest | §3.2 |
| 7 | ¿Qué RF? | **RF-03 Partidos** (RF-01 es Firebase, no email+password) | §3.5 |
| 8 | ¿Cómo se mide cobertura? | Convención `[AC-n]` en el nombre del `it()`, verificada por regex | §8 |
| 9 | ¿El sandbox es el destino final? | **No.** Se opera como prod, pero todo queda parametrizado para migrar (§3.7) | §3.7 |
| 10 | ¿Los tickets de Linear aplican al sandbox? | **Sí.** El port es de hoy, así que los tickets vigentes describen ese código | §3.0 |
| 11 | ¿Dónde viven los tests a largo plazo? | **Solo en el sandbox.** Migrarlos a prod sería una decisión aparte, fuera de alcance | §3.1 |

---

## 14. Estado de la implementación (v1, 2026-08-27)

Implementado y verificado. Lo que la implementación reveló y el plan no preveía:

| Hallazgo | Dónde | Resolución |
|---|---|---|
| Prisma 7 genera el cliente con imports `./x.js` apuntando a `.ts` | `jest-e2e.json` | `moduleNameMapper` que quita el `.js` |
| `firebase-admin/auth` arrastra `jose`, ESM puro que rompe el runtime CJS de Jest | `test/stubs/` | Stub que **tira error si alguien lo llama**: un test que autentique de verdad sería un falso positivo silencioso |
| El provider `FIREBASE_ADMIN` llama a `cert()` al arrancar y explota con claves sintéticas | `setup-e2e.ts` | `.overrideProvider(FIREBASE_ADMIN)` además del `overrideGuard` |
| Prisma 7 carga su query compiler WASM con `import()` dinámico | `package.json` | `NODE_OPTIONS=--experimental-vm-modules` en `test:e2e` |
| Un heredoc de Python dentro de un `run: |` rompe el escalar de YAML | workflow | El summary lo genera `validate-output.py`, el YAML solo lo catea |

Verificado sin gastar un token: **13/13** tests de herramientas, los tres caminos
de aborto del validador (repo fuera de allowlist, harness tocado, `suspected_bug`
borrado), y la precarga contra el sandbox real — 4 AC detectados, 21k caracteres.

Verificado con el stack real: **7/7** tests e2e verdes, **dos corridas seguidas
sobre la misma base** — la garantía anti-falso-positivo de §3.6.

**Falta:** la primera corrida del loop contra un modelo real. Necesita
`LLM_API_KEY` de OpenRouter cargada como secret en el sandbox.

## 15. Lo que queda por confirmar

Nada bloquea arrancar la fase 0:

1. **AGENTS.md está desactualizado y el agente lo lee como contexto.** Dice
   `/backend/` (es `back/`), describe RF-01 como email+password (es Firebase) y
   lista RF-05/RF-06 como si existieran. Hoy le estaríamos dando datos falsos al
   modelo. Corregirlo **en el sandbox** antes del piloto. Irónicamente, es
   exactamente el trabajo del `context-curator`, que ya está instalado ahí.
2. **¿Los AC de los tickets vienen numerados?** La convención `[AC-n]` de §8
   asume que los AC son una lista. Si vienen en prosa, hay que numerarlos durante
   la precarga, y eso mete ambigüedad justo en la métrica principal de §11.
3. **`prisma/seed.ts` ya existe en el port.** Decidir si el harness lo usa o si
   `fixtures.ts` crea todo por su cuenta. Recomendación: fixtures propios, para
   que un spec se entienda sin ir a leer el seed.
