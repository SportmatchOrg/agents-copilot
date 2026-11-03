# Origen: revisar-diseno

- **Tipo:** agente
- **Creada:** 2026-11-02, pieza nueva
- **Autor:** Ignacio Chevallier
- **Colaboradores:** —
- **Madurez:** probado
- **Prueba:** Revisión retroactiva con `claude -p` en contexto limpio, sin permisos de escritura, parada en el commit de merge de cada PR de SportMatch:
  - PR #102 (pantalla del mapa): 11 hallazgos. El Alto es `mapa/page.tsx:21-22`: el mapa le resta el alto de la navegación en lugar de pasar por debajo del chrome (DESIGN.md §4). Es SPO-305, arreglado cinco semanas después en la #162. Encontró además la causa raíz, el `pb-28` global de `layout.tsx:41`.
  - PR #129 (filtros del mapa): 9 hallazgos introducidos (safe area del sheet, sheet mobile en desktop, CTA "Ver 0 partidos"). El bug de SPO-305 aparece en "Ya estaba antes" como Alto.
- **Cambios por la prueba:** una primera corrida manual sobre la #129 mostró que, mirando solo las líneas del diff, el bug de SPO-305 pasaba de largo. Se agregó la sección "Ya estaba antes" (problemas previos en los archivos tocados, confirmados con `git blame`), y en la corrida limpia funcionó. También se delimitó en "Qué NO hace" contra `alternativas-pantalla` y `matriz-responsive` (de Matías).
