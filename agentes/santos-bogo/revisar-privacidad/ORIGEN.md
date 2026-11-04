# Origen: revisar-privacidad

- **Tipo:** agente
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, sobre los endpoints de partidos, usuarios y solicitudes de SportMatch (rama
  `dev`, solo lectura). Como no hay reglas de visibilidad escritas, usó "mínimo necesario". Encontró 8
  exposiciones: la alta es `POST /users`, que devuelve la fila completa de otra cuenta y permite saber si
  un mail está registrado. También las coordenadas exactas en el endpoint público y las faltas por
  no-show visibles para cualquiera. Revisó logs, IA, fotos, metadatos y seeds, y dejó 4 preguntas para
  el PO.
- **Cambios por la prueba:** prioridad separada entre la ubicación de una persona y la de un evento
  público; la etiqueta `cruza con seguridad`; el aviso del `include` sin `select` en el modelo
  principal; listar los endpoints que el front no llama; columna de endpoint y sección "revisado y ok".

## Notas

Sale de RNF-03 (Privacidad), que en el charter es una sola palabra. Distinta de `security-agent` (Tomás),
que prueba si se puede acceder a lo ajeno: esta mira lo que la API entrega legítimamente y no debería.
