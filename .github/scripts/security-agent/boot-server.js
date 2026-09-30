#!/usr/bin/env node
/**
 * Levanta el back REAL de SportMatch (el `dist/` compilado) en un puerto, con
 * la autenticación reemplazada por usuarios simulados. Es el blanco de la parte
 * dinámica del Security Agent.
 *
 * Por qué un server de verdad y no supertest in-process como el test agent: acá
 * el modelo no escribe specs, manda requests sueltos y mira la respuesta. Un
 * server en un puerto es lo que le permite a `http` ser una herramienta de una
 * línea, y a `baseline.py` y al replay pegarle igual que el agente.
 *
 * Autenticación simulada, mismo contrato que el guard real:
 *   - sin `x-sec-user`          → 401 (igual que un request sin bearer token)
 *   - `x-sec-user: A | B | C`   → ese usuario. Si el back tiene `ensureExists`
 *                                 (el guard real de sportmatch lo llama), se
 *                                 llama igual; si no, no.
 *   Los tres quedan registrados en cada reset, como después de un login.
 * Lo que NO prueba: la verificación del token de Firebase en sí. Eso queda para
 * la revisión estática del guard.
 *
 * Además expone, FUERA de las rutas de Nest:
 *   POST /__sec/reset  → trunca todas las tablas y corre el seed del repo.
 *   Es lo que hace reproducible una corrida: el replay arranca del mismo estado.
 *
 * Uso (cwd = <repo>/back, después de `npm run build`):
 *   SEC_PORT=3900 DATABASE_URL=... node boot-server.js
 */
'use strict';

const path = require('path');
const { spawnSync } = require('child_process');

const BACK = process.cwd();
const PORT = Number(process.env.SEC_PORT || 3900);

// Nunca contra una base que no sea local. El reset hace TRUNCATE de TODO.
const HOSTS_PERMITIDOS = /@(localhost|127\.0\.0\.1|\[::1\]|db|postgres)[:/]/;
if (!HOSTS_PERMITIDOS.test(process.env.DATABASE_URL || '')) {
  console.error('boot-server aborta: DATABASE_URL no apunta a una base local.');
  process.exit(1);
}

// `AppModule` valida el entorno al importarse. Firebase no se usa (el guard y
// el provider se reemplazan), pero `validateEnv` exige que existan.
process.env.NODE_ENV ??= 'test';
process.env.FRONT_URL ??= 'http://localhost:3000';
process.env.FIREBASE_PROJECT_ID ??= 'sportmatch-security';
process.env.FIREBASE_CLIENT_EMAIL ??= 'sec@sportmatch-security.iam.gserviceaccount.com';
process.env.FIREBASE_PRIVATE_KEY ??= 'clave-sintetica-no-usada';

const req = (p) => require(path.join(BACK, 'node_modules', p));
const dist = (p) => require(path.join(BACK, 'dist', p));

const { Test } = req('@nestjs/testing');
const { ValidationPipe, UnauthorizedException } = req('@nestjs/common');
const { AppModule } = dist('app.module');
const { FirebaseAuthGuard } = dist('auth/firebase-auth.guard');
const { FIREBASE_ADMIN } = dist('firebase/firebase.module');
const { UsersService } = dist('users/users.service');
const { PrismaService } = dist('prisma/prisma.service');

// `name` y `nombre` a la vez: el `FirebaseUser` de sportmatch usa `name` y el
// del sandbox `nombre`. Cada back lee el suyo y el otro no molesta.
const user = (letra) => ({
  uid: `sec-uid-${letra.toLowerCase()}`,
  email: `${letra.toLowerCase()}@security.test`,
  name: `Usuario ${letra}`,
  nombre: `Usuario ${letra}`,
});
const USERS = { A: user('A'), B: user('B'), C: user('C') };

async function main() {
  let app;

  const stubGuard = {
    async canActivate(context) {
      const request = context.switchToHttp().getRequest();
      const who = String(request.headers['x-sec-user'] || '').toUpperCase();
      const current = USERS[who];
      if (!current) {
        throw new UnauthorizedException('Missing bearer token');
      }
      // Mismo contrato que el guard real de CADA repo: el de sportmatch crea
      // el usuario si no existe (`ensureExists`); el del sandbox no.
      const users = app.get(UsersService);
      if (typeof users.ensureExists === 'function') {
        await users.ensureExists(current);
      }
      request.user = current;
      return true;
    },
  };

  // A, B y C arrancan registrados, que es lo que hace el front al loguearse
  // (sportmatch: el guard; sandbox: `GET /users/me` → `upsertFromFirebase`).
  // Sin esto, en un back donde el guard no crea usuarios, todo endpoint que
  // resuelve al usuario actual da 404 y el agente no puede probar nada.
  async function provisionUsers() {
    const users = app.get(UsersService);
    const register =
      typeof users.ensureExists === 'function' ? users.ensureExists.bind(users)
        : typeof users.upsertFromFirebase === 'function' ? users.upsertFromFirebase.bind(users)
          : null;
    if (!register) {
      throw new Error('UsersService no tiene ensureExists ni upsertFromFirebase');
    }
    for (const u of Object.values(USERS)) {
      await register(u);
    }
  }

  const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
    .overrideProvider(FIREBASE_ADMIN)
    .useValue({})
    .overrideGuard(FirebaseAuthGuard)
    .useValue(stubGuard)
    .compile();

  app = moduleRef.createNestApplication({ logger: ['error', 'warn'] });

  // Replica EXACTA del `main.ts`. Si difiere, los hallazgos de validación no
  // valen nada.
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  const prisma = app.get(PrismaService);
  app.use('/__sec/reset', async (request, response) => {
    if (request.method !== 'POST') {
      response.status(405).end();
      return;
    }
    try {
      const tables = await prisma.$queryRawUnsafe(
        `SELECT tablename FROM pg_tables
         WHERE schemaname = 'public' AND tablename <> '_prisma_migrations'`,
      );
      if (tables.length) {
        const list = tables.map((t) => `"${t.tablename}"`).join(', ');
        await prisma.$executeRawUnsafe(`TRUNCATE TABLE ${list} RESTART IDENTITY CASCADE`);
      }
      const seed = spawnSync('npx', ['tsx', 'prisma/seed.ts'], {
        cwd: BACK,
        env: process.env,
        encoding: 'utf-8',
      });
      if (seed.status !== 0) {
        response.status(500).json({ ok: false, step: 'seed', stderr: (seed.stderr || '').slice(-2000) });
        return;
      }
      await provisionUsers();
      response.json({ ok: true });
    } catch (error) {
      response.status(500).json({ ok: false, step: 'reset', error: String(error) });
    }
  });

  await app.listen(PORT, '127.0.0.1');
  console.log(`security target listo en http://127.0.0.1:${PORT}`);
}

main().catch((error) => {
  console.error('boot-server no pudo arrancar:', error);
  process.exit(1);
});
