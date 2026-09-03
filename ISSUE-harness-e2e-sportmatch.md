# Instalar el harness de tests e2e en `sportmatch`

> Para el equipo de back. Es un comando. ~10 minutos, la mayoría esperando a npm.

## Qué pasa hoy

`sportmatch` **no tiene `back/test/`** — ni un archivo. Y `back/package.json`
declara:

```json
"test:e2e": "jest --config ./test/jest-e2e.json"
```

apuntando a un config que no existe. **Ese script está roto en producción**,
independientemente de cualquier agente: hoy nadie puede correr un test e2e.

## Qué hacer

```bash
git clone https://github.com/SportmatchOrg/agents-copilot.git
cd agents-copilot
bash .github/scripts/test-agent/install-harness.sh ../sportmatch
```

Necesita Docker corriendo (levanta el Postgres del `docker-compose.yml` del
propio repo).

El script copia el harness, arregla el `test:e2e`, y **verifica que funcione**
corriendo un spec de humo que después borra. Si algo falla, no declara éxito y
te deja el spec en su lugar para que veas el error.

## Qué queda en el repo

```
back/test/jest-e2e.json               config de Jest para e2e
back/test/setup-e2e.ts                createTestApp() + resetDatabase()
back/test/fixtures.ts                 seedBaseline(), partidoPayload(), usuarios
back/test/env-e2e.ts                  variables mínimas para que Nest arranque
back/test/stubs/firebase-admin-auth.ts
```

**Ningún test.** Es a propósito: la carpeta arranca limpia y los specs los
escribe el agente. Tampoco toca `prisma/`, ni `src/`, ni las migraciones.

El único cambio fuera de `back/test/` es una línea en `package.json`:

```json
"test:e2e": "NODE_OPTIONS=--experimental-vm-modules jest --config ./test/jest-e2e.json"
```

Prisma 7 carga su query compiler WASM con un `import()` dinámico y sin ese flag
Jest lo rechaza en runtime.

## Qué mirar antes de aprobar

Tres decisiones del harness que conviene que alguien de back valide:

1. **`setup-e2e.ts` overridea `FirebaseAuthGuard` y el provider `FIREBASE_ADMIN`.**
   Los tests no autentican de verdad: inyectan un usuario fijo. Lo único
   simulado es la identidad; el resto es la app Nest real con su `ValidationPipe`.
2. **`stubs/firebase-admin-auth.ts` tira error si alguien lo llama.** `jose` es
   ESM puro y rompe el runtime CJS de Jest. Que explote es deliberado: un test
   que autentique de verdad sería un falso positivo silencioso.
3. **`resetDatabase()` hace `TRUNCATE ... RESTART IDENTITY CASCADE`** en cada
   `beforeEach`. Es lo que evita que un spec pase la primera corrida y falle la
   segunda por estado sucio.

## Verificación

- [ ] `cd back && npm run test:e2e` corre sin error (sin tests todavía).
- [ ] El script imprimió `✅ harness instalado y verificado`.
- [ ] El diff toca solo `back/test/` y una línea de `back/package.json`.

## Después de esto

El API Test Agent puede apuntar a `sportmatch`. Los dos pasos que faltan son
nuestros y de una línea cada uno (allowlist del validador y
`AGENTS_REPO_TOKEN`): ver `ISSUE-test-agent-a-produccion.md`.
