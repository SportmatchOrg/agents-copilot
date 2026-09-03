/**
 * Stub de `firebase-admin/auth` para los tests e2e (parte del HARNESS).
 *
 * Dos razones:
 *  1. `firebase-admin/auth` arrastra `jose`, que es ESM puro y rompe el runtime
 *     CommonJS de Jest.
 *  2. En los tests el `FirebaseAuthGuard` está reemplazado (`setup-e2e.ts`), así
 *     que `getAuth` no debería ejecutarse nunca.
 *
 * Si algo llega a llamarlo, tiene que fallar ruidosamente: un test que valida
 * autenticación contra Firebase real sería un falso positivo silencioso.
 */
export function getAuth(): never {
  throw new Error(
    'getAuth() de firebase-admin está stubbeado en los tests e2e. ' +
      'Si un test necesita autenticación real, el diseño está mal: ' +
      'el guard se reemplaza en setup-e2e.ts.',
  );
}
