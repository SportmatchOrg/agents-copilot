# Origen: revisar-ia-app

- **Tipo:** skill
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, sobre `back/src/ai` de SportMatch y su uso en el front (solo lectura, sin llamar
  a los proveedores). Inventarió el borrador de partido y la generación de imágenes. Dio 9 hallazgos
  (3 medios: imágenes públicas sin moderación, sin `max_tokens`, hasta 38 s sin timeout en el front),
  una lista de lo que está bien hecho y 8 entradas de prueba con el resultado esperado.
- **Cambios por la prueba:** seguir la salida hasta el endpoint donde se guarda, sumar los timeouts de la
  cadena de respaldo, la cuota devuelta aunque el proveedor cobre, el dictado del navegador como dato
  que sale a terceros, inyección y moderación separadas para imágenes, bajar un nivel si el riesgo ya
  existe sin IA y la sección "lo que está bien".

## Notas

Sale de SPO-295 (borrador de partido y fotos generadas con IA). En el grupo y en el catálogo hay piezas
que *usan* IA, pero ninguna que audite las funciones de IA que la app le ofrece a sus usuarios.
`security-agent` (Tomás) prueba accesos a la API y no mira prompts, costo ni moderación.
