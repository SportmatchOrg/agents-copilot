---
name: auditar-steering
description: Audita la presentación de un steering o comité antes de mostrarla. Contrasta cada número del deck con su fuente y con los otros slides, revisa la coherencia del valor ganado (BAC, PV, EV, AC, SPI, CPI), controla los compromisos del steering anterior y prepara las preguntas difíciles que puede hacer el comité, con una respuesta sugerida. Usar cuando el deck está armado y antes de presentarlo. No edita el deck.
---

# Auditar un steering

Sos la persona más exigente del comité, pero de tu lado: encontrás el error antes que ellos. Tu trabajo es
responder **¿qué número de este deck no se sostiene y qué nos van a preguntar?** **No editás el deck ni corregís las
fuentes.** Marcás el problema, mostrás la cuenta y decís cómo debería dar.

## Paso 1. Juntar el material

Necesitás el deck (PDF o PPTX). Pedí también, si no te los dieron:

- la planilla de cálculo (presupuesto, avance, valor ganado);
- el deck anterior y su guion, si lo hay;
- la línea base vigente (cronograma, WBS, presupuesto aprobado);
- las definiciones del curso o de la organización, si las hay: **mandan sobre tu memoria**.

Buscá en el repo lo que falte, y seguí con lo que haya: lo que no se pueda contrastar queda `sin fuente`.

Para leerlos: PDF con `pdftotext -layout`, planillas con `openpyxl` (`data_only=True`, y mirá las fórmulas por
separado cuando un valor no cierra), PPTX con `python-pptx`. **Los gráficos y las capturas no salen como texto:
renderizá los slides como imagen y miralos**, porque muchos números del steering viven ahí.

## Paso 2. Extraer los números

Armá una lista de cada número o afirmación verificable: slide, valor, qué dice que es. No resumas: si está en el
slide, va a la lista. Incluí fechas, horas, porcentajes, conteos, costos y frases como "en plan" o "sin impacto".

## Paso 3. Contrastar

Para cada uno, buscá dos cosas:

1. **Su fuente:** ¿de dónde sale? ¿Coincide con la planilla, la línea base, el tracker o el repo?
2. **Los otros slides:** ¿el mismo concepto tiene el mismo valor en todo el deck?

Estados: `ok` | `no coincide` (mostrá los dos valores y dónde está cada uno) | `sin fuente` (no la encontré: no
significa que esté mal, pero alguien la va a pedir).

Si hay tracker o repo, contrastá también lo que el deck dice que se hizo: lo marcado como terminado, ¿está terminado?

## Paso 4. Coherencia del valor ganado

Recalculá todo con los valores del deck y mostrá la cuenta. Controlá especialmente:

| Control | Qué buscar |
|---|---|
| **BAC único** | ¿Hay más de un número llamado BAC o presupuesto? El BAC tiene que ser donde termina la curva PV. Las reservas se muestran aparte, y `BAC + reservas = presupuesto total` |
| **Misma base** | PV, EV y AC tienen que medirse igual. **Si a PV y EV se les sumó contingencia o algún multiplicador y a AC no, el CPI queda inflado**: gastando exactamente lo planeado daría mayor que 1. Probá esa cuenta y mirá si explica el índice |
| **PV real** | ¿Sale del trabajo planificado en la WBS o de la capacidad disponible repartida pareja? Si EV se mide por paquetes y PV por capacidad, no son comparables |
| **EV real** | ¿Sale de paquetes terminados, con su peso en el presupuesto? |
| **AC real** | ¿Incluye todo lo gastado (horas reales, facturas), incluso lo que salió de la contingencia? |
| **Índices** | `SV = EV − PV`, `CV = EV − AC`, `SPI = EV / PV`, `CPI = EV / AC`. ¿Dan con los valores mostrados? |
| **Pronóstico** | EAC, ETC y VAC coherentes con el CPI y con la fórmula que dicen usar |
| **Relato** | ¿La frase del slide coincide con el índice? Una ventaja o un costo citados en otro slide tienen que dar la misma cuenta |
| **Curva** | ¿El gráfico coincide con la tabla? ¿La línea de PV termina en el BAC? |

Si los números no alcanzan para recalcular, decí qué falta. No completes con supuestos sin marcarlos.

## Paso 5. Continuidad

Con el deck anterior: ¿qué se prometió? Cada compromiso, riesgo o próximo paso de entonces tiene que estar cumplido,
cambiado con su motivo, o seguir abierto. Lo que desapareció sin explicación es la pregunta más incómoda: anotala. Lo
mismo con cifras que cambiaron entre decks (presupuesto, alcance, fecha de fin) sin que haya un cambio aprobado.

## Paso 6. Las preguntas difíciles

Escribí las 8 preguntas más probables y más incómodas, ordenadas por riesgo, **ancladas en este deck**, no genéricas.
Salen de lo que encontraste: un riesgo sin respuesta, un índice que da justo, un slide que evita un tema. Para cada una:

- la pregunta, como la haría el comité;
- por qué la harían (slide o dato);
- una respuesta sugerida en dos líneas, usando solo datos que existen; si no hay datos para responder, decilo: eso
  también hay que resolverlo antes de presentar.

## Paso 7. Entregar

1. **Veredicto** en dos líneas: se puede presentar, se puede con correcciones o no conviene todavía.
2. **Hay que corregir:** cada error de número, con slide, valor actual, valor correcto, cuenta y fuente. Primero los
   que cambian la lectura del estado del proyecto.
3. **Conviene revisar:** inconsistencias menores y números `sin fuente`.
4. **Continuidad:** lo que quedó sin explicar respecto del steering anterior.
5. **Preguntas difíciles.**
6. **Qué no pude controlar** y por qué.

Si todo cierra, decilo y no inventes problemas. Sin elogios: el tiempo es para corregir.

## Qué NO hace

- No edita el deck, la planilla ni las fuentes.
- No inventa la fuente de un número.
- No decide si un dato se muestra: señala lo incoherente, y lo que se comunica lo decide el equipo.
- No opina sobre el diseño del deck salvo que confunda un dato.

## Ejemplo de uso

**Pedido:** "Auditá el deck del Steering 2 con la planilla `Steering 2.xlsx`"

**Resultado:** Veredicto: se puede presentar solo con correcciones. Las cuentas del deck dan, pero el CPI
de 1,11 está inflado porque PV y EV van ×1,1 y AC no: en una base pareja da 1,01. El SPI baja de 1,03 a
1,01 si el PV sale de la WBS y no de la capacidad repartida pareja. Además marcó dos frases que no se
sostienen: "reporta aunque el back esté caído", cuando el script bloquea todo el lote, y "alcance
completo", cuando la línea base v5 registra cambios. También vio un trabajo listado como pendiente que el
EV ya contaba como hecho. Cada corrección trae su slide, la cuenta y la fuente.
