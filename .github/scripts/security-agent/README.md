# Security Agent

Revisa la seguridad de la API del back en dos capas y deja un comentario en la PR con lo que encontró. Levanta el back **dentro del runner**, contra una base que nace y muere en el job: nunca le pega al Azure de dev ni al de prod.

```
PR → Postgres descartable + build + back con auth simulada
   → endpoints → baseline → [►LOOP◄ → replay] → comentario en la PR
     determ.     determ.       agente   determ.
```

---

## Las dos capas

**1. Baseline, sin modelo.** Todo lo que se puede verificar con una regla fija va acá: es gratis, no alucina y corre igual con la cuota agotada. Corre en **cada PR que toca `back/`**.

| Check | Tipo | Qué verifica |
|---|---|---|
| BL-01 | estático | todo endpoint tiene `FirebaseAuthGuard` (salvo `GET /` y `GET /health`) |
| BL-02 | dinámico | sin sesión, todo endpoint protegido da 401 |
| BL-03 | dinámico + estático | un campo de más en el body da 400; el `@Body()` es una clase DTO |
| BL-04 | estático | ninguna ruta queda inalcanzable porque otra con parámetro la pisa |
| BL-05 | estático | no hay `$queryRawUnsafe` / `$executeRawUnsafe` |

**2. Loop, con modelo.** Lee el código y le pega a la API como tres usuarios (A, B, C) buscando lo que requiere criterio: un usuario que modifica lo de otro, reglas de negocio que se saltean (cupo, unirse dos veces, calificar sin haber jugado), datos de otros usuarios que se filtran, 500 ante un input inválido. Corre **solo con el label `security-agent` en la PR o a mano**: un loop automático en cada PR quema la cuota diaria de modelos free.

## Por qué los hallazgos del agente son confiables

- **La evidencia no es texto del modelo.** Cada `http` lo ejecuta el arnés y queda en `calls.json` con request y respuesta reales. Un hallazgo solo puede *citar* números de request.
- **Replay.** `replay.py` resetea la base, re-ejecuta la exploración hasta el último request citado (traduciendo los ids, que cambian entre corridas) y exige el mismo status en cada request citado. Lo que no se reproduce se descarta y figura solo como conteo.

## Herramientas del loop

| Acción | Args | Tope |
|---|---|---|
| `http` | `method`, `path`, `as` (A/B/C/null), `body` | solo 127.0.0.1, nunca rutas `/__sec` |
| `read_file` | `path` | dentro de `back/`, 40 KB |
| `finish` | `summary`, `findings[]` | — |

Presupuesto: 20 acciones y 1500 s. Controllers, services, guards y DTOs van precargados. El cliente de modelos es el del test agent (`test-agent/models.py`, cadena con fallback): se importa, no se copia.

## Autenticación simulada

`boot-server.js` levanta el `dist/` real con el `FirebaseAuthGuard` reemplazado: sin header `x-sec-user` responde 401, y con `x-sec-user: A|B|C` entra como ese usuario, que se crea con `ensureExists` igual que en el guard real. El `ValidationPipe` es copia exacta del de `main.ts`. **No prueba** la verificación del token de Firebase: eso queda para revisión humana del guard.

## Correr en local

```bash
git clone --branch dev git@github.com:SportmatchOrg/sportmatch.git /tmp/sm-target
echo 'LLM_API_KEY=sk-or-...' >> agents-copilot/.env      # está en el .gitignore
.github/scripts/security-agent/run-local.sh /tmp/sm-target
SEC_SKIP_AGENT=1 .github/scripts/security-agent/run-local.sh /tmp/sm-target   # solo baseline
```

Usa su propio Postgres (`sportmatch-security-db`, puerto 55432) y **no** el `docker compose` del repo: el compose fija `name: sportmatch` y engancharía el contenedor y el volumen locales del dev, y el reset del agente le truncaría la base.

## Archivos

| | |
|---|---|
| `setup-stack.sh` / `teardown.sh` | Postgres descartable, build, arranque, gates |
| `boot-server.js` | el back real con auth simulada + `/__sec/reset` |
| `target.py` | único cliente HTTP del blanco |
| `endpoints.py` | mapa de endpoints desde los controllers |
| `baseline.py` | chequeos BL-01…BL-05 |
| `agent_prompt.py` / `run-agent.py` | instrucciones y loop |
| `replay.py` | validador: re-ejecuta y confirma cada hallazgo |
| `report.py` | comentario de la PR |
| `run-local.sh` | corrida completa sin GitHub |

Instalación en un repo: copiar `github/workflows/security-agent.yml` a `.github/workflows/`, crear el label `security-agent` y cargar el secret `SECURITY_LLM_API_KEY`. Es una key propia del agente y tiene prioridad sobre `LLM_API_KEY`: así el loop no comparte la cuota diaria con el test agent ni con el QA agent. Sin ninguna de las dos, corre solo el baseline.
