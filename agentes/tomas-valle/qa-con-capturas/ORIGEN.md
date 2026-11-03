# Origen: qa-con-capturas

- **Tipo:** agente
- **Creada:** 2026-11-02, pieza nueva
- **Autor:** Tomás Valle
- **Colaboradores:** —
- **Madurez:** experimental
- **Prueba:** 2026-11-02, SPO-303 sobre el preview de dev: 5 de 6 criterios `pasa`; C6 `falla` por falta de evidencia en el ticket. Encontró al pasar un desborde en el detalle del partido. Corrió sin las variables de credenciales cargadas y registró cuentas de prueba.
- **Cambios por la prueba:** si faltan las credenciales fuera de producción, registra cuentas descartables y las lista, en vez de marcar todo lo privado como `no verificable`.
