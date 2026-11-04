# Origen: revisar-react-query

- **Tipo:** skill
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, sobre todo el front de SportMatch (rama `dev`, solo lectura). Mapeó 13
  escrituras contra las queries que afectan. Encontró 3 huecos de invalidación (swipe → mapa,
  onboarding → usuario en caché, calificar → chip "Calificar"), un polling de 2 s sobre un endpoint de
  5 consultas, tres hooks con datos fuera de React Query y escrituras fuera de los guards `isMutating`.
- **Cambios por la prueba:** se agregaron la lista de hooks sin React Query, las escrituras fuera de los
  guards, el polling como criterio, la limpieza de caché recreando el client, distinguir "pantalla
  montada" de "al volver", contar solo los datos de la sesión que hizo la acción y una tabla de queries
  en el entregable.

## Notas

Sale de SPO-296, que migró deportes y partidos a TanStack Query. Ninguna pieza del grupo revisa el estado
de servidor del front: `revisar-diseno` (Ignacio) y `matriz-responsive` (Matías) miran lo visual.
