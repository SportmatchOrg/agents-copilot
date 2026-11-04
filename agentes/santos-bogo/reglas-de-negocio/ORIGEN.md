# Origen: reglas-de-negocio

- **Tipo:** skill
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, "partidos y solicitudes" sobre SportMatch (rama `dev`, solo lectura; el
  documento se entregó en el chat). Documentó 27 reglas con referencias en el back y en el front, más las
  tablas de estados. Encontró un título que el wizard pide y no se guarda, un borrado de partidos sin
  restricción que la UI no muestra, una penalización por salida tardía que el front no avisa y
  solicitudes pendientes que nunca expiran. Dejó 9 preguntas para el PO.
- **Cambios por la prueba:** se agregó el estado `detalle` (15 de 27 caían en "sin acordar" solo porque
  el charter es general), los endpoints sin uso y los estados derivados como fuentes de reglas, el
  criterio para incluir reglas de otras entidades, el caso del front más restrictivo que el back y los
  IDs con prefijo por entidad.

## Notas

Pieza de PO: responde "¿qué pasa si…?" con el código como evidencia y deja las decisiones implícitas
como preguntas. Distinta de `dor-checker` y `dod-checker`, que miran un ticket, y de `ticket` (Tomás),
que redacta tickets: esta documenta cómo funciona hoy el producto.
