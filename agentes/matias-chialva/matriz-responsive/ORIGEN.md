# Origen: matriz-responsive

- **Tipo:** skill
- **Creada:** 2026-11-03, pieza nueva
- **Autor:** Matías Chialva
- **Colaboradores:** —
- **Madurez:** experimental

## Notas

Pieza de QA (rol de Matías en el sprint actual) para validar el requisito no funcional de
responsividad (RNF-01 en SportMatch), que hoy no verifica ninguna pieza de forma exhaustiva.

- `auditoria-bugs` (Ignacio) audita flujos y requisitos y mira 3 anchos como parte del recorrido; esta
  no prueba funcionalidad y cubre toda la matriz de tamaños, zoom y fuente grande.
- `revisar-diseno` (Ignacio) lee el diff de una PR y anticipa en el código qué puede romperse; esta
  mira la app real renderizada, en todas las pantallas.
- `alternativas-pantalla` (Matías) trabaja sobre una pantalla y su consistencia con el design system;
  esta solo mira layout, en todas.

Archivo de apoyo: `chequeos-layout.js`, las mediciones que se corren en la página. El script mide; la IA
mira las capturas, agrupa, encuentra la causa en el código y propone el arreglo.
