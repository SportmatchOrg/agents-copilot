# Origen: analizar-cambio-alcance

- **Tipo:** skill
- **Creada:** 2026-11-02, pieza nueva
- **Autor:** Ignacio Chevallier
- **Colaboradores:** —
- **Madurez:** probado
- **Prueba:** Se corrió con `claude -p` en contexto limpio, con Linear en vivo (solo lectura) y el repo de gestión `sportmatch-linktree`:
  - SPO-295 (generar foto con IA, terminado): clase "Aprobado" (WBS v5, paquete 15.2.1). Reportó los desvíos: la decisión del proveedor de IA (Cloudflare, sin respaldo) se cerró en el ticket y no en un acta; Linear (2 SP) y la WBS (3,58 h) no coinciden; tokens de animación agregados sin pasar por el diseño; IDs corridos en `tickets-alcance-v5.md`.
  - SPO-307 (paginar `GET /matches`, abierto): clase "Extensión". SPO-232 había excluido el bounding box, y la carga como bug sin control de cambios no pasó por steering. Recomendó partirlo: compresión ahora y paginado después de la entrega.
- **Cambios por la prueba:** la primera versión solo comparaba contra el charter y habría clasificado SPO-295 como "Nuevo". Se agregaron la búsqueda de cambios ya aprobados (WBS posteriores, actas) y la clase "Aprobado", que reporta solo el desvío.
