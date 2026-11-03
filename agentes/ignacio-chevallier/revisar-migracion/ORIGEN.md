# Origen: revisar-migracion

- **Tipo:** comando
- **Creada:** 2026-11-02, pieza nueva
- **Autor:** Ignacio Chevallier
- **Colaboradores:** —
- **Madurez:** probado
- **Prueba:** Se corrió con `claude -p "/revisar-migracion <n>"` en un clon de SportMatch (rama `dev`), en contexto limpio, sin permisos de escritura. Casos:
  - PR #82 (`rename_domain_to_english`): "Segura con condiciones". Detectó que los 18 `RENAME CONSTRAINT ..._not_null` solo funcionan en PostgreSQL 18 o más y que `docker-entrypoint.sh:4` aplica la migración en cada arranque. Dio las consultas previas y el rollback.
  - PR #149 (`add_user_block`): "Segura", sin hallazgos inventados. Verificó que el código trata `null` como "no bloqueado", así que no hace falta backfill.
  No hubo que corregir las instrucciones.
