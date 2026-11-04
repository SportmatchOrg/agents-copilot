# Origen: plan-actualizacion

- **Tipo:** comando
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, `/plan-actualizacion` sobre front y back de SportMatch (solo `npm outdated`,
  `npm audit`, `npm view` y changelogs oficiales; nada instalado). 47 desactualizados, 18 majors y 77
  vulnerabilidades, en 5 tandas. La primera cierra los críticos sin majors. NestJS 12 queda al final
  porque arrastra TypeScript 6 (`baseUrl`, `strict`). Desaconsejó prisma 8 (RC en `latest`) y descartó
  los "fixes" de audit que bajaban de versión.
- **Cambios por la prueba:** se corrigió el paso de `npm outdated` sin `node_modules` (deja vacía la
  versión actual y omite las devDependencies), se agregaron el cálculo del tipo de cambio, las
  prereleases en `latest`, las peer dependencies que cruzan familias, `@types/node` atado al runtime,
  los fixes de audit que bajan de versión, verificar si el módulo vulnerable se importa y buscar las
  fechas de entrega en lugar de suponerlas.

## Notas

Área que el grupo no tenía: mantenimiento de dependencias. No es un script porque el valor está en leer
los changelogs y buscar en el código lo que se rompe, no en listar versiones.
