/**
 * Datos de prueba para los tests e2e.
 *
 * Este archivo es parte del HARNESS: el API Test Agent NO lo escribe ni lo
 * modifica (plan §3.6). Existe para que un spec se entienda sin ir a leer
 * `prisma/seed.ts`, y para que los datos sean deterministas.
 */
import type { PrismaService } from '../src/prisma/prisma.service';
import type { FirebaseUser } from '../src/auth/types';

/** Usuario autenticado por defecto en los tests. Es el organizador. */
export const TEST_USER: FirebaseUser = {
  uid: 'e2e-uid-organizador',
  email: 'organizador@e2e.test',
  nombre: 'Organizador E2E',
};

/** Segundo usuario, para los casos donde importa NO ser el organizador. */
export const OTHER_USER: FirebaseUser = {
  uid: 'e2e-uid-otro',
  email: 'otro@e2e.test',
  nombre: 'Otro E2E',
};

export interface Baseline {
  deporteId: string;
  organizadorId: string;
  otroId: string;
}

/**
 * Crea el mínimo indispensable para que `POST /partidos` funcione:
 * un Deporte (FK obligatoria) y los dos usuarios (el service resuelve el
 * organizador con `findByFirebaseUid`, y tira 404 si no existe).
 */
export async function seedBaseline(prisma: PrismaService): Promise<Baseline> {
  const deporte = await prisma.deporte.create({ data: { nombre: 'FUTBOL_E2E' } });

  const organizador = await prisma.user.create({
    data: {
      firebaseUid: TEST_USER.uid,
      email: TEST_USER.email,
      nombre: TEST_USER.nombre,
    },
  });

  const otro = await prisma.user.create({
    data: {
      firebaseUid: OTHER_USER.uid,
      email: OTHER_USER.email,
      nombre: OTHER_USER.nombre,
    },
  });

  return { deporteId: deporte.id, organizadorId: organizador.id, otroId: otro.id };
}

/** Una fecha futura estable (no depende de la hora a la que corra el test). */
export function futureDate(days = 7): Date {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  date.setUTCHours(18, 0, 0, 0);
  return date;
}

/** Payload válido de CreatePartidoDto. Los overrides pisan lo que haga falta. */
export function partidoPayload(
  deporteId: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    deporteId,
    nivel: 'INTERMEDIO',
    fecha: futureDate().toISOString(),
    ubicacion: 'Cancha E2E',
    cupo: 10,
    ...overrides,
  };
}
