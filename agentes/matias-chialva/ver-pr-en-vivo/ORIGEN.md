# Origen: ver-pr-en-vivo

- **Tipo:** skill
- **Creada:** 2026-11-03, pieza nueva
- **Autor:** Matías Chialva
- **Colaboradores:** —
- **Madurez:** experimental

## Notas

Pieza de QA (rol de Matías en el sprint actual). Sale de revisar PRs de SplitIt a mano: levantar cada PR
en local sin tocar el repo, entrar con una cuenta y recorrer el cambio en el navegador para que el autor
y los reviewers lo vean en capturas y GIF. La sección "Cuidados" junta lo que falló en esa corrida
(symlinks de `node_modules` con Turbopack, sesión compartida entre puertos, no escribir sobre un
formulario que está usando el humano).

- `test-agent` (Ignacio) escribe y corre tests e2e de la API en CI; esta no escribe tests, muestra la app
  funcionando en local a una persona.
- `qa-review` (Ignacio) prepara una review a partir del diff; esta mira la app renderizada y deja
  evidencia visual que se puede sumar a esa review.
- `matriz-responsive` (Matías) recorre todas las pantallas en muchos tamaños; esta recorre solo lo que
  cambió la PR, en un tamaño.
