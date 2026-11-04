# Origen: revisar-consultas

- **Tipo:** agente
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, sobre SportMatch (rama `dev`, solo lectura, sin base levantada), con el pedido
  "el mapa tarda ~2 s". Siguió `GET /matches` de punta a punta y encontró 6 hallazgos (2 altos): el
  puntaje de organizadores calculado en Node con todo el historial (coincide con SPO-306, y propuso el
  SQL de reemplazo) y el listado sin límite con filtros de distancia y cupo en memoria. Propuso dos
  índices y marcó como causa probable, fuera de la base, la llamada a Firebase con `checkRevoked` en el
  guard.
- **Cambios por la prueba:** se agregaron guards y services de otros módulos al recorrido, el patrón
  "idas a la base en serie", la sección "fuera de alcance pero relevante", declarar los volúmenes
  supuestos, las reglas que tiene que replicar un cálculo pasado a SQL y comentar en el ticket existente
  en vez de crear otro.

## Notas

Sale de SPO-306: el mapa tardaba ~2 s y la causa estaba en una consulta, no en el front. Distinta de
`revisar-migracion` (Ignacio), que revisa si una migración se puede aplicar sin perder datos; esta
revisa el rendimiento de las consultas y propone índices, sin escribir migraciones.
