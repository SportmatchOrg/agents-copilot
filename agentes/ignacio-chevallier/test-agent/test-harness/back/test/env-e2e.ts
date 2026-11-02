/**
 * Variables de entorno del entorno de test. Corre en `setupFiles`, es decir
 * ANTES de que Jest cargue los specs — importante, porque `AppModule` valida el
 * entorno con `validateEnv` en el momento en que se lo importa.
 *
 * Los valores de Firebase son sintéticos y nunca se usan: el guard y el
 * provider FIREBASE_ADMIN se reemplazan en `setup-e2e.ts`. Están solo para que
 * `validateEnv` no rechace el arranque.
 */
process.env.NODE_ENV ??= 'test';
process.env.FRONT_URL ??= 'http://localhost:3000';
process.env.DATABASE_URL ??=
  'postgresql://root:root@localhost:5432/sportmatch?schema=public';
process.env.FIREBASE_PROJECT_ID ??= 'sportmatch-test';
process.env.FIREBASE_CLIENT_EMAIL ??= 'test@sportmatch-test.iam.gserviceaccount.com';
process.env.FIREBASE_PRIVATE_KEY ??= 'test-private-key-no-usada';
