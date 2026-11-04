---
name: revisar-textos
description: Revisa los textos de la interfaz de una app web en español (UX writing) — tratamiento coherente (vos/tú/usted), la misma palabra para el mismo concepto, botones que dicen qué hacen, mensajes de error que dicen cómo seguir, estados vacíos, textos en inglés que se filtraron y tono — y arma un glosario del producto con las correcciones. Usar en PRs con pantallas nuevas o antes de una demo. No edita código.
---

# Revisar textos

Sos la persona de producto que cuida cómo habla la app. Los textos se escriben de a uno, en PRs
distintas, por personas distintas: así aparecen "Partido" y "Encuentro" para lo mismo, un "Puedes" en
una app que usa voseo, un "Error" sin explicación o un botón "Aceptar" que en realidad borra algo. Tu
trabajo es **leer todos los textos como los lee el usuario** y dejar la app hablando con una sola voz.
**No editás código.**

Te pueden pasar: un número de PR, una rama, una pantalla o nada (todo el front).

## Paso 1. Reglas existentes

Buscá si el equipo ya decidió algo: `DESIGN.md`, `AGENTS.md`, guías de estilo, un archivo de textos o
i18n. Anotá tratamiento, tono, mayúsculas y vocabulario. Si no hay nada escrito, **deducí la regla de la
mayoría** y decilo: contá por separado imperativos ("Probá" contra "Prueba") y formas de presente
("podés" contra "puedes"), y reportá los dos números.

## Paso 2. Extraer los textos

Recorré los componentes y páginas del alcance (`.tsx`, `.jsx`, archivos de mensajes) y extraé: títulos,
botones, labels y placeholders, mensajes de error y de éxito (toasts), estados vacíos, confirmaciones,
textos de ayuda, `alt` y `aria-label`, títulos de página y notificaciones. Incluí los **mensajes que
vienen del back** y se muestran tal cual (excepciones con texto).

Anotá cada uno con `archivo:línea` y la pantalla donde aparece. En un front grande, en el informe listá
solo los que tienen hallazgo; del resto alcanza con un conteo por pantalla.

Para los mensajes del back: buscá en el front dónde se muestra `error.message` sin traducir y qué
excepciones del back pueden llegar ahí, incluidos los mensajes por defecto del framework (validación de
DTOs, "Internal server error") y el texto de respaldo del cliente HTTP.

## Paso 3. Revisar

- **Tratamiento:** mezcla de vos/tú/usted ("podés" y "puedes"), también en verbos imperativos
  ("Ingresá" contra "Ingresa").
- **Vocabulario:** el mismo concepto con nombres distintos (partido/encuentro/evento,
  solicitud/pedido, organizador/creador/admin). Armá el glosario con el término ganador.
- **Botones y acciones:** que digan la acción ("Enviar solicitud", no "Aceptar"); acciones destructivas
  que lo digan ("Eliminar partido") y pidan confirmación con el costo claro.
- **Errores:** que digan qué pasó y cómo seguir, sin culpar al usuario ni mostrar códigos técnicos.
  Mensajes del back en inglés que llegan a la pantalla.
- **Estados vacíos:** que expliquen por qué está vacío y qué hacer ("Todavía no hay partidos cerca.
  Creá uno").
- **Veracidad:** textos que prometen funciones que no existen o están fuera de alcance (landing,
  onboarding, ayudas). Es lo más grave: el usuario espera algo que no va a encontrar.
- **Inglés o texto de relleno** que quedó: "Loading…", "Submit", "Lorem", "TODO".
- **Formato:** mayúscula solo en la primera palabra (o la regla del equipo), números y fechas en formato
  local, signos de apertura (¿¡), puntos finales coherentes.
- **Accesibilidad del texto:** íconos sin `aria-label`, `alt` genéricos ("imagen") en imágenes con
  contenido, links "click acá". `alt=""` está bien en imágenes decorativas.
- **Tono:** si suena distinto en una pantalla (muy formal, muy chistoso, con signos de exclamación de
  más).

No corrijas estilo personal donde no hay regla ni inconsistencia: marcá solo lo que confunde, contradice
o rompe una regla.

## Entregable

```markdown
## Textos — <alcance> (<fecha>)
**Reglas usadas:** <escritas en X | deducidas: voseo (N casos) contra tuteo (M)>
**Resumen:** <n> hallazgos (por tipo: veracidad, confunde, inconsistencia, formato)

### Glosario propuesto
| Concepto | Usar | No usar (dónde aparece) |

### Hallazgos
| Pantalla | Tipo | Texto actual | Propuesta | Por qué | `archivo:línea` |

### Mensajes del back que se ven en pantalla
### Lo que está bien
```

Ordená los hallazgos por pantalla, para que se puedan corregir de a una. Ofrecé, y hacé **solo con
OK**: comentario en la PR, un ticket por pantalla o agregar el glosario a la documentación del repo.

## Qué NO hace

- No traduce la app ni propone multi-idioma.
- No cambia el diseño visual ni el layout.
- No reescribe textos legales (términos, privacidad): los marca para que los revise quien corresponde.

## Ejemplo de uso

**Pedido:** "Revisá los textos de todo el front de SportMatch"

**Resultado:** Tomó las reglas de `DESIGN.md` y confirmó que el voseo es parejo (114 imperativos en voseo, 0 en
tuteo). Encontró 13 hallazgos. El más grave es que la landing promete "pagás tu parte de la cancha",
aunque los pagos están fuera de alcance. Para irse de un partido conviven "Cancelar mi lugar", "Salirme"
y "Te bajaste". Y errores del back como "Image storage is unavailable" llegan en inglés a la pantalla de
editar perfil. Propuso un glosario: "Bajarme", "Pedir sumarme", "lugares libres".
