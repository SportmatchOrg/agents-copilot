---
name: revisar-react-query
description: Revisa cómo un frontend React/Next.js usa TanStack Query (React Query) — claves de query, qué se invalida después de cada mutación, datos viejos en pantalla, optimistic updates, precarga y staleTime — y arma el mapa mutación → queries afectadas con los huecos marcados. Usar en PRs que agregan hooks de datos o cuando una pantalla no se actualiza después de una acción. No edita código.
---

# Revisar React Query

Sos un dev de frontend con experiencia en estado de servidor. El bug típico es "acepté la solicitud y la
lista sigue igual hasta que recargo": una mutación que no invalida todas las queries que dependen de
ese dato. Tu trabajo es **armar el mapa completo de qué datos cambia cada acción y qué pantallas los
muestran**, y marcar los huecos. **No editás código.**

Te pueden pasar: un número de PR, una rama, una pantalla ("Mis partidos no se actualiza") o nada (todo
el front).

## Paso 1. Cómo está armado

1. Buscá el `QueryClient` (provider, opciones por defecto: `staleTime`, `gcTime`, `retry`,
   `refetchOnWindowFocus`) y si hay una fábrica de claves (`queryKeys`, `keys.ts`) o claves escritas a
   mano en cada hook.
2. Listá todos los `useQuery`, `useInfiniteQuery`, `useSuspenseQuery`, `prefetchQuery` y
   `ensureQueryData` con su **clave**, la función que llama a la API y su `staleTime`.
3. Listá todas las `useMutation` y cualquier escritura que no pase por mutaciones (llamadas directas a
   la API en un `onClick`) con lo que hacen en `onSuccess`, `onSettled` y `onMutate`.
   Marcá las escrituras que quedan fuera de los guards `isMutating`/`mutationKey` que use el proyecto.
4. Buscá helpers de invalidación (`useInvalidateX`) y qué invalidan.
5. Listá los hooks que traen datos del servidor **sin** React Query (`fetch` en `useEffect` + `useState`):
   ninguna invalidación los alcanza.

## Paso 2. Mapa mutación → datos afectados

Para cada mutación, pensá **qué datos del servidor cambian de verdad** (mirá el endpoint del back si hace
falta) y qué queries los muestran. Por ejemplo, aceptar una solicitud cambia la solicitud, el cupo del
partido y la lista de participantes. Solo cuentan los datos que ve **en esta sesión** quien hizo la
acción; lo que ven otros usuarios lo cubren el polling o el refetch al montar.

Después compará con lo que la mutación invalida o actualiza. Marcá:

- **Hueco:** una query que muestra un dato que cambió y no se invalida ni se actualiza.
- **Clave que no matchea:** se invalida `['match', id]` pero la query usa `['matches', id]`, o se
  invalida con `exact: true` algo que tiene variantes por filtro.
- **Invalidación de más:** se invalida todo (`invalidateQueries()` sin clave) en una acción chica.

En el síntoma, distinguí **pantalla montada** (no se actualiza hasta recargar o hasta el próximo polling)
de **al volver** (se ve el dato viejo un instante hasta el refetch al montar). Lo primero es más grave.

## Paso 3. Otros problemas comunes

- **Claves incompletas:** la función usa un filtro, página o usuario que no está en la clave → dos
  pantallas comparten caché por error, o al cambiar de usuario se ven datos del anterior.
- **Caché entre sesiones:** al cerrar sesión, ¿se limpia el `QueryClient` (`clear()`) o se recrea (por
  ejemplo, `key={uid}` en el provider)?
- **Optimistic updates** sin `onError` que revierta, o sin `cancelQueries` antes.
- **Estado duplicado:** datos del servidor copiados a `useState`/contexto que dejan de actualizarse.
- **`staleTime` y `refetchInterval` sin criterio:** 0 en datos que casi no cambian (deportes), muy alto
  en datos que cambian seguido (cupos, solicitudes), o polling muy seguido sobre endpoints pesados (es
  configuración, no hace falta medir).
- **Precarga:** `prefetchQuery` con clave distinta de la del `useQuery` que la consume (no sirve).
- **Errores y carga:** queries sin manejo de `isError` en la pantalla, `enabled` mal puesto que deja la
  pantalla cargando para siempre.

## Paso 4. Confirmar (opcional)

Si hay un entorno local o de preview, podés reproducir un hueco en el navegador (hacer la acción y ver
si la otra pantalla se actualiza sin recargar). Si no, la conclusión sale del código: decilo.

## Entregable

```markdown
## React Query — <alcance> (<fecha>)
**Configuración:** staleTime por defecto <x> · fábrica de claves: sí/no · limpieza al logout: sí/no

### Queries
| Clave | Hook (`archivo:línea`) | staleTime | Polling |

### Mapa
| Mutación (`archivo:línea`) | Cambia en el servidor | Invalida/actualiza hoy | Falta | Síntoma |
|---|---|---|---|---|

### Otros hallazgos
- <título> — `archivo:línea` — <qué pasa> — <propuesta concreta, con la clave correcta>

### Propuesta (si conviene)
<fábrica de claves o helper de invalidación por entidad, en pocas líneas>
```

Ofrecé, y hacé **solo con OK**: comentario en la PR o un ticket por hueco.

## Qué NO hace

- No migra el proyecto a otra librería ni propone cambiar de enfoque.
- No revisa el diseño visual de los estados de carga y error: solo que existan.
- No mide rendimiento del front.

## Ejemplo de uso

**Pedido:** "Usá revisar-react-query sobre todo el front de SportMatch"

**Resultado:** Encontró una fábrica de claves que se usa en todas las queries, la precarga alineada con las queries que
la consumen y la caché separada por usuario (`key={uid}` en el provider). Mapeó 13 escrituras y marcó 3
huecos. El swipe invalida solo "mis partidos", así que el mapa sigue mostrando como disponible un partido
ya pedido. El onboarding no actualiza el usuario en caché y lo tapa con un parche en `sessionStorage`. Y
calificar no invalida el chip "Calificar". También señaló un polling de 2 s sobre `/matches/mine` y tres
hooks (invitaciones, ratings, notificaciones) que traen datos por fuera de React Query, así que ninguna
invalidación los alcanza.
