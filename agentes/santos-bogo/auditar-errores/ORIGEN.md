# Origen: auditar-errores

- **Tipo:** comando
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, `/auditar-errores join-requests` sobre SportMatch (rama `dev`, solo lectura).
  Armó la política actual (helper `toPrismaHttpException`, sin filtro global, `apiFetch` en el front) y
  una matriz de 10 situaciones. Encontró: mensaje falso de "partido lleno" ante cualquier 409 al
  aceptar, 500 por P2025 sin mapear si el jugador cancela mientras lo aceptan, y "ya se jugó" con 400 en
  un endpoint y 409 en el otro. También listó lo que está bien.
- **Cambios por la prueba:** la prioridad ahora pesa la gravedad (un 500 o un mensaje falso va antes que
  uno genérico); se agregaron la categoría "mensaje incorrecto", las carreras entre lectura y escritura,
  chequear si la UI deja llegar al error, los códigos inconsistentes entre endpoints hermanos y la
  sección "lo que está bien".

## Notas

Sale del triage de Tomás (`triage-incidente`), que encontró de casualidad un 500 por P2025 sin
traducir. Distinta de `security-agent` (Tomás), que busca accesos indebidos, y de `qa-review`
(Ignacio), que revisa el diff de una PR: esta recorre un módulo entero siguiendo cada error hasta la
pantalla.
