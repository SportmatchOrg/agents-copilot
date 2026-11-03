# Origen: estimar-ticket

- **Tipo:** skill
- **Creada:** 2026-11-02, pieza nueva
- **Autor:** Ignacio Chevallier
- **Colaboradores:** —
- **Madurez:** probado
- **Prueba:**
  - Backtest con SPO-295 (en la sesión, con el export `linear-issues.csv`): propuso 2 pts sin mirar la estimación; la real era 2.
  - SPO-306 y SPO-307 (abiertos), con `claude -p` en contexto limpio y Linear en vivo (solo lectura). SPO-306: 3 pts (rango 3–5), coincide con la estimación cargada. Usó como referencias tickets del mismo módulo (SPO-253, 234, 231) y marcó que sería el primer `$queryRaw` no trivial del repo. Avisó que el 90 % de los tickets son de 1 o 2 pts y que 3 es, en la práctica, el techo de la escala.
  - Una primera corrida limpia no pudo leer Linear (permisos de la sesión). No inventó el alcance de los tickets: armó la clase de referencia y pidió acceso.
- **Cambios por la prueba:** se agregaron el export del tracker como fuente y el aviso de escala comprimida.
