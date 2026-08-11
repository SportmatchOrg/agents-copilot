---
name: pr-review-sportmatch
description: Checklist de revisión de PRs de SportMatch. Copilot code review la invoca durante la revisión para aplicar los estándares del equipo (bugs, seguridad, cumplimiento de RF, DoD).
---

# Skill: Revisión de PR — SportMatch

Cuando revises un Pull Request de SportMatch, aplicá este checklist además del análisis estándar. Reportá cada hallazgo con `archivo:línea`, severidad (`BLOCKER / MAJOR / MINOR / NIT`) y una sugerencia concreta.

## 1. Bugs y lógica
- Casos borde no manejados, condiciones invertidas, off-by-one, manejo de nulos, promesas sin `await`, recursos sin cerrar.

## 2. Cumplimiento del requerimiento
- Identificá el RF asociado (RF-01…RF-06, ver AGENTS.md §2) desde el título/rama del PR.
- Verificá los criterios de aceptación uno por uno. **Marcá explícitamente cualquier AC que el PR no cubra.**
- Si el PR no mapea a ningún RF → `MAJOR`: posible trabajo fuera de backlog (problema de trazabilidad).

## 3. Seguridad
- Credenciales/API keys hardcodeadas → `BLOCKER`.
- Inputs de usuario sin validar; queries sin parametrizar (inyección) → `BLOCKER/MAJOR`.
- Datos personales expuestos sin control (viola RNF-03 Privacidad) → `MAJOR`.

## 4. Resiliencia (RNF-04)
- Errores no capturados que puedan tumbar toda la app en vez de degradar la función afectada.

## 5. Mantenibilidad (RNF-05)
- Funciones largas, duplicación, nombres poco claros, código comentado/muerto, falta de tipos, TODOs sin ticket.

## 6. Convenciones del equipo
- Formato de commits `tipo(RF-xx): ...`, nombre de rama, un PR por historia (AGENTS.md §6).

## Regla de oro
No mergees ni apliques cambios de forma autónoma. Comentá con evidencia y, si un `BLOCKER` amerita seguimiento, sugerí el texto de una tarjeta para Linear. La decisión es humana ("Lab4 no codifica").

## Salida
Cerrá siempre con:
- **Resumen del PR** (2-3 líneas, qué hace).
- **Veredicto:** Aprobar / Aprobar con cambios menores / Solicitar cambios.
