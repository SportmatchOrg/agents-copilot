# Capacitación SportMatch — práctica end-to-end

Objetivo: que cada uno de los **3 devs** entienda para qué sirve cada tecnología del stack y **la use de verdad** sobre un repo que se parece a SportMatch, implementando **la misma feature end-to-end** (base de datos + backend + frontend) y pasándola por el flujo **branch → commit → PR → review** para ver a los **agentes de IA** en acción.

**Por qué la misma tarea para los 3:** además del review del agente, se **comentan los PRs entre ellos** (practican hacer code review, no solo recibirlo) y ven **soluciones distintas al mismo problema**. Sobre el "pisarse": no es problema — el objetivo es interactuar y revisarse, no entregar código. No se intenta mergear los 3 (ahí sí habría conflictos); se mergea **uno solo como referencia** y los otros dos se cierran.

**El flujo, en 5 bloques:**
1. Intro teórica corta (1 recurso por tecnología + por qué la elegimos)
2. Levantar el repo con Docker
3. Tarea previa: **un solo dev** instala los agentes en la rama base
4. Implementar la feature completa (los 3, la misma)
5. Branch + PR + cross-review + ver los agentes

---

## Bloque 1 — Intro teórica corta (1 recurso c/u + por qué lo elegimos)

Solo lo esencial: qué es, dónde lo van a usar en SportMatch y por qué está en el stack.

### TypeScript
Como ya vienen usando **JavaScript**, acá lo importante es ver **qué agrega TS sobre JS**.
- **Recurso (~2 min):** [TypeScript in 100 Seconds — Fireship](https://www.youtube.com/watch?v=zQnBQ4tB3ZA)

- **Para qué:** JavaScript con tipos. Detecta errores al escribir, no en producción.
- **Dónde lo usan:** en TODO — front y back están en TypeScript.
- **Por qué lo elegimos:** un solo lenguaje para los dos servicios, menos bugs en runtime (ayuda a RNF-04 Resiliencia) y autocompletado que se potencia con Prisma y NestJS.

### Next.js (frontend)
- **Recurso (~2 min):** [Next.js in 100 Seconds — Fireship](https://www.youtube.com/watch?v=Sklc_fQBmcs)
- **Para qué:** framework de React para armar webs con routing, render y buen rendimiento.
- **Dónde lo usan:** toda la interfaz — pantallas de partidos, perfil, login (RF-01 a RF-04).
- **Por qué lo elegimos:** rapidísimo para construir una web responsiva (RNF-01), ecosistema enorme y deploy simple.

### NestJS (backend)
- **Recurso (~6 min):** [What NestJS actually is — no-fluff (DEV)](https://dev.to/ramkashyap2050/what-nestjs-actually-is-a-simple-no-fluff-explanation-3m9e) · video: [NestJS explicado](https://www.youtube.com/watch?v=0M8AYU_hPas)
- **Para qué:** framework de Node en TypeScript para APIs, con estructura por módulos e inyección de dependencias.
- **Dónde lo usan:** la API REST que expone partidos, solicitudes, ratings (RF-03, RF-05, RF-06).
- **Por qué lo elegimos:** da estructura y "barandas" (módulos + validación con DTOs) en vez de un Express en blanco — ideal para un equipo que recién arranca y para un monolito modular.

### Docker
- **Recurso (~2 min):** [Docker in 100 Seconds — Fireship](https://www.youtube.com/watch?v=Gjnup-PuquQ)
- **Para qué:** empaqueta cada servicio (front, back, base de datos) en contenedores que corren igual en cualquier máquina.
- **Dónde lo usan:** `docker compose up` levanta todo el entorno local; y es la base del deploy en Azure.
- **Por qué lo elegimos:** mata el "en mi máquina anda", todos corren lo mismo con un comando, y se alinea con la infra (Azure).

> **Prisma + PostgreSQL** y **Tailwind** no llevan intro aparte: los tocan directo en la feature. Prisma = ORM tipado para hablar con Postgres (migraciones y queries con tipos); Tailwind = clases utilitarias para estilar rápido y responsive.

---

## Bloque 2 — Levantar el repo (con el stack, no vacío)

El repo de práctica es **[`SportmatchOrg/sportmatch-onboarding`](https://github.com/SportmatchOrg/sportmatch-onboarding)**: una copia de un starter que ya combina el stack (Nest.js + Next.js + Prisma + Tailwind en un monorepo), con Docker agregado encima.

**Lo único que hay que tener instalado es Docker Desktop.** Ni Node, ni yarn, ni Postgres.

```bash
git clone https://github.com/SportmatchOrg/sportmatch-onboarding.git
cd sportmatch-onboarding
docker compose up
```

La primera vez tarda unos minutos porque construye la imagen e instala las dependencias. Cuando termina:

| Servicio | URL | Qué es |
|----------|-----|--------|
| `web` | http://localhost:3001 | Frontend, Next.js |
| `api` | http://localhost:3008 | Backend, NestJS |
| `db` | `localhost:5432` | Postgres (`root` / `root` / base `db`) |

Hay un cuarto contenedor, `migrate`, que aplica las migraciones de Prisma y se apaga solo. Que aparezca como *Exited (0)* está bien.

**Para confirmar que quedó todo bien:** abrí http://localhost:3001 en el navegador y corré los tests del backend, que tienen que dar 2 en verde.

```bash
docker compose exec -w /app/apps/api api npx jest
```

> Meta de este bloque: que vean el entorno completo corriendo con **un comando**, y entiendan qué contenedor es cada cosa. El resto de los comandos (Prisma, logs, reconstruir) están en el README del repo.

---

## Bloque 3 — Tarea previa: instalar los agentes (**un solo dev**)

Esta la hace **uno solo**, antes que las features. Los otros dos, mientras tanto, siguen con el Bloque 2 en su máquina.

**Por qué uno solo y por qué antes:** GitHub solo dispara un workflow si el archivo ya está en la **rama base**. Si cada dev instalara los agentes en su propia rama, no se ejecutaría ninguno. Va una vez sobre `dev`, mergeado, y a partir de ahí corre sobre los PRs de los tres.

Es la primera vuelta completa al flujo de trabajo del equipo — rama, commit, PR, merge — con un cambio chico y sin riesgo. Sirve de ensayo antes de la feature.

### Qué hacer

**1. Clonar los dos repos, uno al lado del otro**

`agents-copilot` es la fuente del paquete de agentes; `sportmatch-onboarding` es el destino.

```bash
git clone https://github.com/SportmatchOrg/agents-copilot.git
git clone https://github.com/SportmatchOrg/sportmatch-onboarding.git
```

**2. Correr el instalador**

Copia `AGENTS.md` a la raíz y el contenido de `github/` a `.github/`.

```bash
bash agents-copilot/install.sh sportmatch-onboarding
```

**3. Rama, commit y PR contra `dev`**

```bash
cd sportmatch-onboarding
git checkout -b chore/agentes-ia
git add AGENTS.md .github
git commit -m "chore: agregar agentes de IA"
git push -u origin chore/agentes-ia
```

Abrí el PR hacia `dev` desde GitHub y **mergealo**. En este PR todavía no van a comentar los agentes: recién quedan activos una vez mergeados.

**4. Avisar al manager**

Los agentes necesitan los secrets cargados en el repo (`LLM_API_KEY`, `LINEAR_API_KEY` y los tres webhooks de Discord). Eso lo hace el manager una sola vez, no va en el código. Avisale cuando el PR esté mergeado.

**5. Verificar que quedaron activos**

En la pestaña **Actions** del repo tienen que aparecer los 5 workflows listados. Si aparecen, los tres ya pueden abrir PRs y los agentes van a comentar.

### Qué queda instalado

| Archivo | Para qué |
|---------|----------|
| `AGENTS.md` | Contexto del proyecto que leen los agentes y Copilot |
| `.github/copilot-instructions.md` | Reglas de code review para Copilot |
| `.github/chatmodes/` | Los modos de chat de Copilot en el editor |
| `.github/workflows/` | Los 5 agentes automáticos |
| `.github/scripts/llm.sh` | La llamada al LLM que usan los workflows |

---

## Bloque 4 — La feature (la misma para los 3, end-to-end)

Todos implementan **la misma historia completa**, tocando las **tres capas**. Es chica a propósito y está calcada de SportMatch.

### Feature: "Partidos" — listar partidos de punta a punta

**1. Base de datos (Prisma + PostgreSQL)**
- Agregá una entidad `Partido` (`id`, `deporte`, `fecha`, `cupo`) al esquema, en `packages/database/prisma/schema.prisma`.
- Corré una **migración** de Prisma:
  ```bash
  docker compose exec -w /app/packages/database api npx prisma migrate dev --name add_partido
  ```
- Sembrá 2-3 partidos de ejemplo (seed).

**2. Backend (NestJS + REST) — CRUD de partidos**
- El backend está en `apps/api`. Creá un **módulo** `partidos` (controller + service) con `GET /partidos` (listar), `POST /partidos` (crear, con DTO validado) y `DELETE /partidos/:id` (eliminar), usando Prisma. Ya hay un `PrismaService` en `apps/api/src/modules/prisma` para inyectar.
- Cuando funcionen, **generá tests** sobre esos endpoints y **corrélos** (NestJS usa Jest), y probá los endpoints con **Postman** contra `http://localhost:3008`. Es un adelanto de lo que vamos a pedir en tickets reales.
  ```bash
  docker compose exec -w /app/apps/api api npx jest
  ```

**3. Frontend (Next.js + Tailwind) — vista de partidos tipo swipe**
- El frontend está en `apps/web`. Creá la ruta `/partidos` (App Router) que haga fetch a `GET /partidos`.
- **Ojo con la URL de la API:** desde el navegador es `http://localhost:3008`. Si el fetch corre del lado del servidor (Server Component), el contenedor `web` tiene que llamar a `http://api:3008` — dentro de la red de Docker cada servicio se resuelve por su nombre, no por `localhost`.
- Mostrá cada partido pensado como **card**, con navegación tipo **swipe** (descartar / abrir siguiente). Libertad total para el diseño: buscá que quede **visualmente atractivo** (esto anticipa la Vista Swipe del proyecto, WBS 7.2).
- Mantené los estados de "cargando" y "sin partidos".

**Criterio de aceptación (end-to-end):** los 3 endpoints (GET/POST/DELETE) funcionan y tienen tests que pasan, y la vista `/partidos` muestra las cards con swipe, responsive. Referencias: RF-03 (CRUD de partidos), RF-04 (descubrimiento/swipe), RNF-01 (responsividad).

> Cada dev lo hace **completo y solo**, en su propia rama. Así los 3 pasan por las 3 tecnologías.

---

## Bloque 5 — Branch → commit → PR → cross-review + agentes

Acá está el corazón: interactuar con git, **revisarse entre ellos** y ver el efecto de los agentes.

**Pasos (cada dev con su versión de la feature):**
1. Crear la rama, ej. `feature/partidos-<nombre>` (el nombre evita choques de ramas).
2. Commitear con la convención del equipo: `feat(RF-03): listar partidos end-to-end`.
3. `git push` y **abrir un Pull Request** hacia `dev`.
4. **Observar a los agentes** sobre cada PR:

| Agente | Qué van a ver |
|--------|----------------|
| **Code review de Copilot** | Comentarios en el diff: bugs, estilo, seguridad, según `AGENTS.md` y `copilot-instructions.md` |
| **Traductor a negocio** | Un comentario que explica el PR sin jerga: qué historia, riesgo, qué probar |
| **DoD checker** | El veredicto de Definition of Done (qué cumple y qué falta) |
| **Curador de contexto** | Si cambiaron el modelo de Prisma (estructura), puede abrir un issue proponiendo actualizar `AGENTS.md` |

5. **Cross-review:** cada dev revisa y comenta los PRs de los otros dos — comparan enfoques y practican dar feedback (lo que el agente hace, pero ahora ellos).
6. Se mergea **un solo PR** como solución de referencia; los otros dos se **cierran** (no se intenta mergear los tres → sin conflictos).
7. (Opcional) provocar y resolver un conflicto simple, para practicar `merge`.

**Cierre:** mini-demo donde comparan las 3 soluciones y qué les comentaron los agentes. Con eso quedan listos para el desarrollo real.

---

## Checklist del dev (para tildar)

- [ ] Vi el intro de cada tecnología y leí el "por qué lo elegimos"
- [ ] Levanté el repo con `docker compose up` y abrió en el navegador
- [ ] Los tests del backend me dieron en verde
- [ ] (Solo el dev que le tocó) Instalé los agentes y los mergeé a `dev`
- [ ] Implementé la feature completa: modelo + migración (Prisma), endpoint (NestJS), pantalla (Next.js + Tailwind)
- [ ] Cumple el criterio de aceptación end-to-end
- [ ] Creé mi rama, commiteé con la convención y abrí el PR
- [ ] Vi los comentarios de los agentes en mi PR
- [ ] Revisé y comenté los PRs de mis 2 compañeros

---

## Notas
- Todo gratis. Para créditos de Azure (la infra), tramiten el **GitHub Student Pack**.
- Si un enlace de video/blog cambia, la **doc oficial** de cada tecnología es la fuente estable.
- El playground es descartable: el aprendizaje y el hábito de trabajar con agentes es lo que queda.
