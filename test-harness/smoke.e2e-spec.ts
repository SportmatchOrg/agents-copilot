/**
 * Spec de humo — NO se instala en el repo.
 *
 * `install-harness.sh` lo escribe, lo corre y lo borra; `setup-stack.sh` hace
 * lo mismo antes de cada corrida del agente cuando el repo no tiene un spec de
 * ejemplo propio. Así el repo destino queda con `back/test/` limpio —solo
 * configuración— sin perder la única prueba que importa: que el oráculo
 * funciona ANTES de que un modelo escriba una línea.
 *
 * No asserta reglas de negocio a propósito. Verifica el harness:
 * que Nest arranca, que el guard de Firebase está overrideado, que Prisma
 * conecta y que el truncado entre tests corre sin explotar.
 */
import request from 'supertest';
import type { Server } from 'http';
import {
  closeTestApp,
  createTestApp,
  resetDatabase,
  type TestContext,
} from './setup-e2e';
import { seedBaseline } from './fixtures';

describe('humo — el harness e2e funciona', () => {
  let ctx: TestContext;
  let server: Server;

  beforeAll(async () => {
    ctx = await createTestApp();
    server = ctx.app.getHttpServer() as Server;
  });

  afterAll(async () => {
    await closeTestApp(ctx);
  });

  beforeEach(async () => {
    await resetDatabase(ctx.prisma);
  });

  it('el truncado deja la base vacía al empezar cada test', async () => {
    expect(await ctx.prisma.user.count()).toBe(0);
    await seedBaseline(ctx.prisma);
    expect(await ctx.prisma.user.count()).toBe(2);
  });

  it('y el test anterior no dejó estado', async () => {
    // Esta es LA garantía del harness: sin truncado entre tests, el agente
    // reporta bugs que no existen. Si este falla, no instales nada más.
    expect(await ctx.prisma.user.count()).toBe(0);
  });

  it('la app responde a un request autenticado', async () => {
    // El usuario del token tiene que existir en la base: los endpoints lo
    // resuelven con findByFirebaseUid, que tira 404 si no está. Por eso el
    // seed va acá y no en el beforeEach.
    await seedBaseline(ctx.prisma);
    await request(server).get('/partidos').expect(200);
  });
});
