# Instrucciones de Copilot — SportMatch

> Este archivo lo lee **GitHub Copilot** automáticamente en todo el repo: chat, autocompletado y **code review de PRs**.
> Complementa a `AGENTS.md` (raíz), que Copilot code review también usa como contexto.

## Sobre el proyecto

SportMatch es una plataforma web responsiva que conecta personas para practicar deportes. Ver `AGENTS.md` para requerimientos (RF-01…RF-06), modelo de datos, stack y convenciones. **Respetá siempre el alcance**: no propongas ni implementes nada listado como "Fuera de alcance" en AGENTS.md §1 (app nativa, pagos, chat en tiempo real, torneos, etc.).

## Regla rectora: "Lab4 no codifica"

Los agentes de IA **revisan, verifican y reportan**; no mergean código de forma autónoma. Cuando detectan algo accionable, la salida es (a) un comentario/sugerencia en el PR o (b) una propuesta de tarjeta para Linear. La decisión final es siempre humana.

## Convenciones que Copilot debe respetar y hacer respetar

- **Trazabilidad:** todo trabajo se asocia a un RF (RF-01…RF-06). Commits: `tipo(RF-xx): mensaje`. Ramas: `feature/RF-xx-desc`, `fix/desc`. PRs con el ID en el título.
- **Branches:** `main` = entrega, `dev` = integración. Un PR por historia.
- **Definition of Done:** PR mergeada a `dev`, CI verde (build/lint/typecheck), doc actualizada, deploy a staging, todos los AC del RF cumplidos.

## Guía para el code review de Copilot (agente "Code Reviewer")

Al revisar un PR, priorizá en este orden y señalá con severidad `BLOCKER / MAJOR / MINOR / NIT`:

1. **Bugs y lógica** — casos borde, nulos, condiciones invertidas, promesas sin await.
2. **Cumplimiento del RF** — ¿el cambio cubre los criterios de aceptación del RF asociado (AGENTS.md §2)? Marcá AC sin cubrir.
3. **Seguridad** — credenciales hardcodeadas, inputs sin validar, SQL sin parametrizar, datos personales expuestos (RNF-03).
4. **Resiliencia (RNF-04)** — errores que tiran toda la app en vez de degradarse.
5. **Mantenibilidad (RNF-05)** — funciones largas, duplicación, nombres poco claros, código muerto.
6. **Convenciones del equipo** — las de arriba.

Sé específico (archivo:línea), constructivo y no ahogues al dev en NITs. Cerrá con un resumen del PR en 2-3 líneas y un veredicto.

## Stack (contexto para revisar y sugerir)

Front **Next.js + TypeScript + Tailwind**, back **NestJS + TypeScript**, DB **PostgreSQL + Prisma**, infra **Docker + Azure**, CI **GitHub Actions**. Front y back son servicios independientes que hablan por **API REST**.

## Estilo de código

- TypeScript en todo; evitá `any` sin justificar. Aprovechá los tipos de Prisma.
- ESLint + Prettier en front y back; el CI corre lint + typecheck (no aprobar PRs en rojo).
- **NestJS:** módulos por feature (controller + service + DTO). Validá la entrada con DTOs + `class-validator`. No metas lógica de negocio en los controllers.
- **Next.js:** App Router; componentes tipados; estilos con utilidades de Tailwind (evitá CSS suelto salvo necesidad).
- **Prisma:** todo cambio de esquema va por migración; nunca edites la DB a mano. Ojo con queries N+1 (usá `include`/`select` con criterio).
- **API REST:** contratos claros y consistentes; valida y maneja errores devolviendo códigos HTTP correctos (RNF-04 Resiliencia).
