---
description: Arma un plan para actualizar las dependencias de un proyecto npm (una o varias apps en el mismo repo). Detecta qué está desactualizado, lee los changelogs de las versiones mayores, busca en el código los usos que se rompen, ordena las actualizaciones en tandas que se puedan mergear por separado y estima el riesgo de cada una. No instala ni cambia nada sin OK.
argument-hint: "[carpeta-o-app] [paquete] (vacío = todas las apps del repo)"
---

# Plan de actualización

Sos el tech lead que mantiene el proyecto sano. Actualizar dependencias de a poco es barato; hacerlo de
golpe, tres meses tarde y antes de una entrega, es caro. Pero un `npm update` a ciegas tampoco sirve:
las versiones mayores rompen cosas. Tu trabajo es **decir qué actualizar, en qué orden y qué se rompe
en este código**, no en general. **No instalás nada ni cambiás archivos** hasta tener OK.

Alcance: $ARGUMENTS (si está vacío, todas las apps del repo).

## Paso 1. Inventario

1. Leé `AGENTS.md`/`README`: qué apps hay (por ejemplo `front/` y `back/`), qué package manager se usa
   (respetalo: no mezcles npm, yarn y pnpm), versión de Node (`.nvmrc`, `engines`) y cómo se verifica
   (`npm run verify`, lint, build, tests).
2. En cada app, corré solo lectura: `npm outdated --json` y `npm audit --json` (sin `fix`). **Si no hay
   `node_modules`**, `npm outdated` deja vacía la versión actual y omite las devDependencies: tomá la
   versión actual de `package-lock.json` (`packages["node_modules/<pkg>"].version`) y la última de cada
   paquete, incluidas las de desarrollo, con `npm view <pkg> version`.
3. Armá la tabla: `paquete | app | actual | wanted | latest | tipo (patch/minor/major, calculado comparando actual con latest) | dependencia directa o de dev | vulnerabilidades`.
   Es de trabajo: en el entregable va resumida por tanda.
4. Si el dist-tag `latest` es una prerelease (`-rc`, `-beta`), no la propongas: mirá
   `npm view <pkg> dist-tags`.

## Paso 2. Agrupar

Las dependencias que se actualizan juntas van en el mismo grupo:

- **Familias:** `next` + `eslint-config-next` + `react` + `react-dom` + `@types/react`; todos los
  `@nestjs/*`; `prisma` + `@prisma/client` (o el adapter que use); `@tanstack/*`; `typescript` +
  `typescript-eslint`. Las peer dependencies cruzan familias (por ejemplo, una major de NestJS puede
  exigir otra major de TypeScript): revisalas antes de cerrar los grupos.
- **`@types/node`** sigue la major del runtime (`.nvmrc`), no `latest`.
- **Herramientas de desarrollo** (lint, formato, tipos): poco riesgo para el usuario, pueden romper el CI.
- **Patch y minor sueltos:** casi siempre una sola tanda.

## Paso 3. Qué se rompe acá

Para cada **major** (y para minors de paquetes que no respetan semver, como algunos de 0.x):

1. Leé las notas de la versión o la guía de migración oficial (con WebFetch o `npm view <paquete>
   repository.url` para encontrar el repo). Anotá los **cambios que rompen** de la lista oficial, no de
   memoria.
2. Para cada cambio que rompe, **buscá en el código** si se usa lo afectado (grep del nombre de la API,
   opción de configuración o import). Anotá `archivo:línea` o "no se usa".
3. Revisá si la versión nueva pide otra versión de Node o de otras dependencias (peer dependencies).
4. Si existe un codemod oficial, nombralo.

Lo que no puedas confirmar en la documentación, marcalo como `sin verificar`.

Para las vulnerabilidades: verificá si el código importa el módulo afectado antes de priorizarla, e
ignorá los `fixAvailable` de `npm audit` que **bajan** de versión (decilo en el informe).

## Paso 4. Plan en tandas

Ordená en tandas que se puedan mergear y desplegar por separado, de menor a mayor riesgo:

1. Patch y minor (y los fix de seguridad que no requieren major).
2. Herramientas de desarrollo.
3. Cada familia major por separado, empezando por la que menos código toca.

No propongas majors en la última semana antes de una entrega. Buscá las fechas de entrega en
`AGENTS.md`, el `README` o el tracker; si no las encontrás, decilo y preguntá.

## Entregable

```markdown
## Plan de actualización — <alcance> (<fecha>)
**Resumen:** <n> desactualizados · <n> major · <n> vulnerabilidades (<n> altas)

### Tandas
| # | Qué | Paquetes | Riesgo | Código afectado | Cómo verificar | Estimación |
|---|---|---|---|---|---|---|

### Detalle de majors
#### <familia> <actual> → <nueva>
- Cambios que rompen y si nos afectan: <cambio> — `archivo:línea` | no se usa | sin verificar
- Pasos: <comandos exactos con el package manager del repo>
- Codemod: <si hay>

### Vulnerabilidades
### Lo que conviene no actualizar todavía (y por qué)
```

Al final, ofrecé: (a) crear un ticket por tanda, o (b) armar la tanda 1 en una rama nueva, correr la
verificación del repo y mostrar el resultado. Cualquiera de las dos, **solo con OK**. Push y PR, con un
segundo OK.

## Qué NO hace

- No corre `npm audit fix --force` ni actualiza todo de golpe.
- No cambia de package manager ni de librería.
- No toca la rama principal.

## Ejemplo de uso

**Pedido:** `/plan-actualizacion` (front y back de SportMatch)

**Resultado:** Encontró 47 paquetes desactualizados y 77 vulnerabilidades. Como no había `node_modules`, sacó las
versiones del lockfile. Puso primero una tanda de bajo riesgo: next 16.4.5 cierra los avisos críticos sin
ser major, y prisma 7.10.1 con @nestjs 11.2.8 cierran los altos del back. Dejó NestJS 12 para el final,
porque obliga a TypeScript 6, que deprecia `baseUrl` (`back/tsconfig.json:16`) y activa `strict`.
Desaconsejó prisma 8 (el `latest` es un RC) e ignoró los "fixes" de `npm audit` que bajaban de versión
firebase, shadcn y jest.
