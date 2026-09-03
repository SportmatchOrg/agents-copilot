/**
 * Harness de los tests e2e.
 *
 * Este archivo es parte del HARNESS: el API Test Agent NO lo escribe ni lo
 * modifica (plan §3.6). Las tres razones, en orden:
 *
 *  1. `resetDatabase` garantiza aislamiento entre tests. Sin eso, un spec que
 *     crea un partido pasa la primera corrida y falla la segunda por estado
 *     sucio — y el agente lo clasificaría como `suspected_bug`. Falso positivo
 *     garantizado, justo en la métrica que más nos importa (plan §11).
 *  2. El override del guard queda fuera del alcance del modelo: no puede
 *     "arreglar" un test deshabilitando la autenticación.
 *  3. Con `createTestApp()` dado, un spec son 20 líneas y no 120. Es lo que
 *     hace que el presupuesto de 5 iteraciones cierre (plan §5.3).
 */
import { INestApplication, ValidationPipe } from '@nestjs/common';
import type { ExecutionContext } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { AppModule } from '../src/app.module';
import { FirebaseAuthGuard } from '../src/auth/firebase-auth.guard';
import type { AuthenticatedRequest, FirebaseUser } from '../src/auth/types';
import { FIREBASE_ADMIN } from '../src/firebase/firebase.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { TEST_USER } from './fixtures';

/**
 * Tablas en orden de borrado. `CASCADE` resuelve las FK igual, pero listarlas
 * explícitas documenta el modelo y falla ruidosamente si alguien agrega una
 * entidad y se olvida de sumarla acá.
 */
const TABLES = ['participantes', 'partidos', 'users', 'deportes'] as const;

/** Usuario que devuelve el guard mockeado. Mutable vía `setAuthUser`. */
let currentUser: FirebaseUser = TEST_USER;

/** Cambia el usuario autenticado para el resto del test. */
export function setAuthUser(user: FirebaseUser): void {
  currentUser = user;
}

/** Vuelve al usuario por defecto. Lo llama `resetDatabase`. */
export function resetAuthUser(): void {
  currentUser = TEST_USER;
}

export interface TestContext {
  app: INestApplication;
  prisma: PrismaService;
}

/**
 * Levanta la app Nest real, in-process, con supertest como cliente.
 *
 * Dos reemplazos, ambos necesarios:
 *
 * - `FIREBASE_ADMIN`: el provider llama a `cert()` con las credenciales del
 *   entorno y explota con claves sintéticas. Como el guard tampoco se usa,
 *   se reemplaza por un objeto vacío.
 * - `FirebaseAuthGuard`: se sustituye por uno que inyecta `request.user`, que
 *   es de donde lee el decorador `@CurrentUser()`.
 *
 * El `ValidationPipe` replica EXACTAMENTE el de `main.ts`. Sin esto, los tests
 * de validación pasarían siempre y no valdrían nada.
 */
export async function createTestApp(): Promise<TestContext> {
  const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
    .overrideProvider(FIREBASE_ADMIN)
    .useValue({})
    .overrideGuard(FirebaseAuthGuard)
    .useValue({
      canActivate: (context: ExecutionContext): boolean => {
        context.switchToHttp().getRequest<AuthenticatedRequest>().user =
          currentUser;
        return true;
      },
    })
    .compile();

  const app = moduleRef.createNestApplication();

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  await app.init();

  return { app, prisma: app.get(PrismaService) };
}

/** Deja la base vacía y el usuario autenticado en el default. */
export async function resetDatabase(prisma: PrismaService): Promise<void> {
  resetAuthUser();
  await prisma.$executeRawUnsafe(
    `TRUNCATE TABLE ${TABLES.map((t) => `"${t}"`).join(', ')} RESTART IDENTITY CASCADE`,
  );
}

/** Cierra la app. Va en `afterAll` para que Jest no quede colgado. */
export async function closeTestApp(ctx: TestContext | undefined): Promise<void> {
  // Si `createTestApp` falló, `ctx` es undefined: cerrar acá tiraría un
  // TypeError que tapa el error real del arranque.
  if (!ctx) return;
  await ctx.prisma.$disconnect();
  await ctx.app.close();
}
