# Origen: contrato-api

- **Tipo:** skill
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, sobre SportMatch (rama `dev`, solo lectura), con alcance `join-requests`. Comparó
  7 endpoints, ninguno roto. Encontró 3 frágiles (errores que caen en la rama equivocada del front,
  mapeo por partes de mensajes en inglés) y 2 de limpieza (el mismo estado con 400 en un endpoint y 409
  en otro; un DTO que acepta `PENDING` y después lo rechaza a mano).
- **Cambios por la prueba:** se incluyen los campos del recurso que viajan dentro de otros endpoints; el
  chequeo de errores pide seguir cada excepción hasta su rama del front, incluido el default; se
  redefinieron `rompe` (flujo normal) y `frágil` (carreras o casos que la UI impide); el "de qué lado
  arreglarlo" ahora vale también para `frágil`.

## Notas

Sale de que en SportMatch el front (`front/src/lib`, `types`) y el back (`back/src/*/dto`) no comparten
tipos. Se apoya en `auditar-errores`: esta solo verifica que cada error del back tenga su rama en el
front; la auditoría a fondo de errores es de la otra pieza. Distinta de `pr-review` y `qa-review`, que
revisan un diff en general; esta compara los dos lados de la API.
