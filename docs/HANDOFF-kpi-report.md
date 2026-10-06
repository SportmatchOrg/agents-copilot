# Handoff — Reporte diario de KPIs (challenge Lab4)

Para el tech lead: qué es esto, qué hay que configurar y cómo se usa. La decisión
completa está en el ADR-001 del equipo ("Reporte diario de KPIs de SportMatch").

## Qué hace

Un workflow de este repo reporta todos los días los **10 KPIs** de SportMatch al
dashboard de la cátedra (`lab4-kpis/kpis`, Supabase):

```
20 × GET /health del back ──────────┐
PRs mergeados a dev (API de GitHub) ─┼─► junta los 10 ─► ¿los 10 READY? ─► POST al dashboard
POST /kpis/snapshots del back ───────┘        │ no
  (calcula los 7 de negocio y                 └─► no publica nada, job rojo, aviso en Discord
   los guarda en su base: SPO-277)
```

| Calcula | KPIs |
|---|---|
| El back (`POST /kpis/snapshots`) | `team_completion_rate`, `time_to_full`, `user_return_rate`, `no_show_rate`, `matches_per_active_user`, `match_cancellation_rate`, `late_withdrawal_rate` |
| Este workflow | `health_latency_p95` (p95 de 20 llamadas a `/health`), `api_reachable` (1/0), `pr_lead_time` (mediana en horas, PRs humanos a `dev`, 30 días) |

**Todo o nada:** si un KPI queda `NO_DATA` o `ERROR`, no se publica ninguno. El
dashboard no permite corregir ni borrar un valor, y un `NO_DATA` nunca se manda
como `0`.

## Por qué hay código si este repo no se despliega

Nada de esto se despliega. Cuando se dispara el workflow, GitHub levanta una
máquina temporal, hace checkout de este repo, corre el script de Python y la
descarta, igual que los otros agentes de `.github/scripts/`. El trabajo (20
llamadas y su p95, paginar GitHub, validar al back, chequear los 10, publicar,
avisar a Discord) no entra cómodo en un YAML, así que vive en un script y el
YAML solo lo llama.

**No usa ningún modelo:** es código determinístico. El challenge prohíbe agentes
de IA como mecanismo de reporting.

## Archivos

| Archivo | Para qué |
|---|---|
| `.github/workflows/kpi-report.yml` | Disparador: botón "Run workflow" con los inputs. El `schedule` está comentado |
| `.github/workflows/kpi-report-reusable.yml` | El job: corre el script, sube el artifact y avisa a Discord si falla |
| `.github/scripts/kpi-report/report.py` | Lo que ejecuta el job: llamadas HTTP, publicación y aviso |
| `.github/scripts/kpi-report/kpi_lib.py` | Las cuentas y validaciones (p95, mediana, fechas, armado del lote), sin red |
| `.github/scripts/kpi-report/kpi-catalog.json` | Los 10 KPIs con id, tipo, unidad y descripción. Es lo que se da de alta en el dashboard |

## Antes de configurar

1. **SPO-276 y SPO-277 desplegados** en el back del ambiente que se quiera usar.
2. **`KPI_API_KEY` cargada en el App Service de Azure** (dev y prod, un valor
   distinto en cada uno). Está anotada en el documento compartido de env vars.
3. **Claves del dashboard:** un profesor emite una `X-Project-Key` por ambiente
   desde el portal (Equipos → SportMatch → Claves). Se muestra **una sola vez**.
   La de `prod` no se puede emitir hasta que la cátedra configure el calendario.

## Configuración (Settings de `agents-copilot`)

**Environments** → crear `dev` y `prod`, cada uno con:

| Nombre | Tipo | Valor |
|---|---|---|
| `SPORTMATCH_API_URL` | Variable | dev: `https://sportmatch-dev-aqhcazaacaf7e6g0.brazilsouth-01.azurewebsites.net` · prod: `https://sportmatch-prod-akbwbvf4fbewf3ax.brazilsouth-01.azurewebsites.net` |
| `KPI_API_KEY` | Secret | La misma que se cargó en Azure para ese ambiente |
| `KPI_PROJECT_KEY` | Secret | La clave del dashboard para ese ambiente (`kpi_…`) |

**Secrets and variables → Actions**, a nivel repo:

| Nombre | Tipo | Valor |
|---|---|---|
| `KPI_SUPABASE_URL` | Variable | `https://rzlalzowistpiphmdqpp.supabase.co` |
| `KPI_SUPABASE_PUBLISHABLE_KEY` | Variable | La publishable key del dashboard (es pública y compartida por todos los equipos; la da la cátedra, ver `docs/TEAM_GUIDE.md` de `lab4-kpis/kpis`) |
| `DISCORD_WEBHOOK_PROGRESS` | Secret | El mismo webhook que ya usa `sportmatch` |
| `SPORTMATCH_PR_READ_TOKEN` | Secret | Fine-grained PAT, **solo** repo `SportmatchOrg/sportmatch`, permiso **Pull requests: Read-only**. Hace falta porque `sportmatch` es privado y el token de este repo no lo puede leer |

Opcional: en el Environment `prod`, *Required reviewers* para que publicar en
prod pida aprobación.

## Primera puesta en marcha

Desde **Actions → Reporte de KPIs → Run workflow**:

| # | env | mode | Qué verificar |
|---|---|---|---|
| 1 | `dev` | `catalog` | Verde. Da de alta los 10 KPIs en el dashboard (env dev) |
| 2 | `dev` | `dry-run` | Summary con los 10 en `READY`. No publica |
| 3 | `dev` | `report` | Verde y "publicado (10 KPIs)". Los valores de `dev` no cuentan para la nota |
| 4 | `prod` | `catalog` | Igual que el 1, con la clave de prod. **Los IDs quedan para siempre** |
| 5 | `prod` | `dry-run` | Los 10 en `READY` con datos reales |
| 6 | `prod` | `report` | Primer envío que cuenta para la nota |
| 7 | — | — | Descomentar el `schedule` en `kpi-report.yml` (01:15 de Buenos Aires; va a `prod` en modo `report`) |

Si en el paso 2 o 5 algún KPI sale `NO_DATA`, es falta de datos en esa ventana
(por ejemplo, ningún partido completó cupo desde que existe `filledAt`), no un
bug del workflow. Hasta que haya muestra, el día no se publica.

## Uso

- **Inputs:** `env` (dev | prod), `mode` (dry-run | report | catalog) y `date`
  (`YYYY-MM-DD`; vacío = ayer en Buenos Aires; nunca hoy ni futuro).
- **Reintentar un día:** correr `report` con esa `date`. Si ya se había
  publicado, el dashboard ignora el duplicado y conserva el primer valor. Ojo:
  la nota cuenta por el día en que se envía, así que mandar días pasados no suma.
- **Salida:** tabla de los 10 en el summary de la corrida y artifact
  `kpi-<env>-<run>` (90 días) con el lote, la respuesta del back, las 20
  duraciones de `/health` y los PRs usados. Cada llamada al back deja además su
  corrida en las tablas `kpi_runs` / `kpi_results` de la base de SportMatch.
- **Discord:** solo avisa cuando falla, con los KPIs afectados y el link a la corrida.

## Errores frecuentes

| En el summary / Discord | Causa probable |
|---|---|
| `BACK_HTTP_401` | `KPI_API_KEY` del Environment distinta de la de Azure |
| `BACK_HTTP_503` | Azure no tiene `KPI_API_KEY` cargada |
| `BACK_HTTP_404` | SPO-277 todavía no está desplegado en ese ambiente |
| `BACK_UNREACHABLE` | Back caído o URL mal cargada (mirar `api_reachable`) |
| `GITHUB_HTTP_404` / `401` en `pr_lead_time` | Falta `SPORTMATCH_PR_READ_TOKEN` o no tiene acceso a `sportmatch` |
| `SUPABASE_HTTP_403` | `KPI_PROJECT_KEY` falta, es inválida o fue rotada |
| `SUPABASE_HTTP_401` | La clave es de otro ambiente (clave de dev corriendo con `env=prod`, o al revés) |
| `SUPABASE_HTTP_409` | Algún KPI no está en el catálogo de ese ambiente: correr `catalog` |
| `NO_DATA` en un KPI de negocio | Sin muestra en los 30 días; no es un error de configuración |
