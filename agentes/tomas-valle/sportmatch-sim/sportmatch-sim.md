---
name: sportmatch-sim
description: Agente que corre Claude Code en modo headless para simular usuarios de SportMatch (unirse, organizar, aceptar solicitudes, calificar) según su arquetipo, y así generar actividad realista para los KPIs. Usar para poblar y hacer evolucionar un entorno de dev o prod con datos creíbles.
---

# sportmatch-sim

Las instrucciones del agente están en [`CLAUDE.md`](CLAUDE.md), sin cambios. **No renombrar ese
archivo:** el workflow [`.github/workflows/simular.yml`](.github/workflows/simular.yml) corre
`claude -p "Hacé una corrida según CLAUDE.md"`, y Claude Code lo carga por ese nombre.

Este archivo es la ficha de la pieza para el catálogo.

- **Cómo corre:** el workflow se dispara por `repository_dispatch` (corrida programada) o a mano,
  con el entorno (`dev`, `prod` o los dos).
- **Qué usa:** el CLI de `src/` (`node src/cli.ts ...`) para operar contra la API, y `personas/`
  (arquetipos, lugares y pool de personas).
- **Configuración:** `.env.example` lista las variables (URL de la API por entorno, clave de
  Firebase y contraseña de los bots).

## Ejemplo de uso

**Pedido:** Correr el workflow `simular.yml` a mano con entorno `dev` (equivale a `claude -p "Hacé una corrida según CLAUDE.md"`).

**Resultado:** Claude hace de cada persona simulada que entra ese día: revisa y acepta o rechaza solicitudes, cancela o califica partidos, se une a uno que encaje con sus deportes y su zona u organiza uno nuevo, anota una línea en su diario y cierra con un resumen de 3 a 5 líneas de la corrida.
