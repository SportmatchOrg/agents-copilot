# Origen: partir-pr

- **Tipo:** comando
- **Creada:** 2026-11-02, pieza nueva
- **Autor:** Ignacio Chevallier
- **Colaboradores:** —
- **Madurez:** probado
- **Prueba:** Se corrió con `claude -p` en un clon de SportMatch, en contexto limpio, sin permisos para crear ramas ni PRs:
  - PR #145 (+1261, 22 archivos): 4 PRs (gesto de las hojas, componentes de UI, datos, pantalla). Aisló el cambio a `bottom-sheet.tsx`, que afecta a todas las hojas de la app, y detectó que la PR anunciaba unificar el timer de toast pero no migró ningún uso.
  - PR #159 (SPO-301, 33 archivos): 4 PRs (back emite la cookie → guard + Origin → front → sincronización entre pestañas). Coincide con los 4 commits que el equipo hizo dentro del ticket. Marcó que `FRONT_URL` pasa a ser obligatoria y que la PR del front cierra la sesión de todos los usuarios una vez.
  No hubo que corregir las instrucciones.
