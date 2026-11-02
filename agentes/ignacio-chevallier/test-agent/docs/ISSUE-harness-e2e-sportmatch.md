# Instalar el harness de tests e2e en `sportmatch`

> **Bloquea a:** `ISSUE-hotfix-triggers-sportmatch.md`. Hacer este primero.

`back/package.json` declara `"test:e2e": "jest --config ./test/jest-e2e.json"`,
pero `back/test/` **no existe**. Ese script está roto: hoy nadie puede correr
un test e2e en el repo.

## Qué correr

Requiere Docker levantado (usa el Postgres del `docker-compose.yml` del repo).

```bash
git clone https://github.com/SportmatchOrg/agents-copilot.git
cd agents-copilot
bash .github/scripts/test-agent/install-harness.sh ../sportmatch
```

Si algo falla no declara éxito y deja el error a la vista. No corras los e2e con `DATABASE_URL` apuntando a Neon: el harness aborta si detecta una base que no sea local.

## Qué queda en el diff

```
back/test/jest-e2e.json                 config de Jest para e2e
back/test/setup-e2e.ts                  createTestApp() + resetDatabase()
back/test/fixtures.ts                   seedBaseline(), partidoPayload(), usuarios
back/test/env-e2e.ts                    env mínimo para que Nest arranque
back/test/stubs/firebase-admin-auth.ts

back/package.json                       +NODE_OPTIONS=--experimental-vm-modules
                                        en test:e2e (Prisma 7 lo necesita)
```

**Ningún test**: la carpeta arranca limpia a propósito. No toca `src/`, `prisma/` ni las migraciones.

## Listo cuando

- [ ] El script imprimió `✅ harness instalado y verificado`.
- [ ] `cd back && npm run test:e2e` corre sin error.
- [ ] El diff toca solo lo de arriba.
- [ ] Commiteado en una PR a `dev`.

Con esto mergeado, se puede avanzar con el hotfix de los workflows.