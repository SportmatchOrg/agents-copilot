# Origen: revisar-despliegue

- **Tipo:** agente
- **Creada:** 2026-11-04, pieza nueva
- **Autor:** Santos Bogo
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-04, sobre toda la configuración de despliegue de SportMatch (rama `dev`, solo
  lectura, sin leer valores de secretos ni hacer requests a los entornos). Veredicto "listo con pasos
  manuales". Encontró: migraciones en cada arranque, health con timeout de 2 s contra el arranque en
  frío de Neon, `GIT_SHA` sin exponer, imagen como root, PAT para GHCR y las `VAPID_*` exigidas sin
  documentar. Armó la tabla de 25 variables y 5 pasos manuales.
- **Cambios por la prueba:** se agregaron qué hacer con la configuración que no está en el repo, la
  definición de bloqueante y de riesgo, el health contra una base serverless, los crons con varias
  réplicas, el tag para volver atrás, variables de build contra runtime y la prohibición explícita de
  hacer requests a los entornos.

## Notas

Distinta de `triage-incidente` (Tomás), que investiga un incidente en curso, y de `antes-despues-release`
(Tomás), que compara pantallas entre entornos: esta lee la configuración antes del deploy.
