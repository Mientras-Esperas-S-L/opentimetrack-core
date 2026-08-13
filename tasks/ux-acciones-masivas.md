# Acciones masivas y composición: qué falta, pantalla por pantalla

Anotado el 13/08/2026, para hacer al terminar las pruebas.

El disparador fue una pregunta concreta —«¿cómo añado personas a un
departamento?»— cuya respuesta resultó ser «desde Personas, de una en una». Pero
el problema no es de Departamentos: es que **ninguna pantalla del producto
permite operar sobre más de una fila**, y eso convierte cualquier tarea de
reorganización en abrir y cerrar diálogos.

## Estado: los dos puntos de Departamentos y Personas, hechos el 13/08/2026

Y de paso salió un fallo que llevaba ahí desde siempre: **`?department=` y
`?workplace=` de la API rechazaban cualquier identificador**, incluso el bueno,
con «Escoja una opción válida». `django-filter` construye la lista de opciones
válidas al importar el módulo, y en ese momento no hay empresa en el contexto:
los gestores de un `TenantOwnedModel` devuelven vacío sin empresa, así que la
lista quedaba vacía para siempre. La API lo anunciaba y no filtraba nada.

Se vio al estrenar el filtro en la pantalla. Ninguna prueba lo habría cazado
pidiendo un identificador inventado ---da 400, sí, pero **siempre** da 400---
así que la que hay ahora lo pide con uno de verdad.

## Lo que había que hacer en Departamentos

1. **Selector «Quién está dentro» en el diálogo del departamento.** El mismo
   componente que ya usa «Quién lo lleva», pero de miembros. Es el arreglo
   pequeño y cubre el caso normal: acabo de crear un departamento y quiero
   meterle su gente sin salir de aquí.

2. **Filtro por departamento y selección múltiple en Personas, con «Mover
   a…».** Es lo que sirve cuando se reorganiza de verdad: filtrar «Sin
   departamento», marcar doce y moverlas de una vez.

Los dos, no uno. El primero resuelve componer; el segundo, reorganizar. Son
tareas distintas y la gente llega a ellas desde sitios distintos.

## El patrón, que es lo que de verdad hay que arreglar

Tres piezas que hoy no existen en ninguna pantalla:

- **Filtrar** por los campos que de verdad separan las filas.
- **Seleccionar** varias, con la casilla de cabecera para «todas las de la
  vista» y un contador visible de cuántas van.
- **Actuar** sobre lo seleccionado, con una barra que aparece al haber
  selección y dice exactamente qué va a pasar y a cuántas filas.

Y una regla que no se salta: **lo irreversible sigue preguntando**, y la
pregunta dice el número. «Se dan de baja 12 personas» no es lo mismo que «¿Estás
seguro?».

## Dónde hace falta, y para qué

Por revisar una a una al implementarlo. Esto es la lista de partida, no la
conclusión: hay que abrir cada pantalla y mirarla entera, no solo buscar dónde
pegar una casilla.

| Pantalla | Filtrar por | Seleccionar y actuar |
|---|---|---|
| Personas | departamento, centro, perfil, con o sin baja | mover de departamento, cambiar de centro, dar de baja |
| Departamentos | — | añadir miembros desde el propio diálogo |
| Centros | — | mover personas de un centro a otro |
| Fichajes | persona, día, estado | por revisar: aquí tocar en masa roza el registro legal |
| Por decidir | tipo, persona, antigüedad | resolver varias a la vez, **si** cada una conserva su rastro |
| Cuadrante | ya tiene pintado por arrastre | revisar si basta |
| Turnos | — | probablemente no hace falta |
| Calendario | tipo de ausencia, estado | por revisar |
| Informes | ya genera para toda la plantilla | revisar si el resto de pantallas puede llegar aquí |
| Aplicaciones | — | probablemente no hace falta |

## Las dos líneas que no se cruzan

- **El registro de jornada no se toca en masa.** Un fichaje se corrige uno a
  uno, con el consentimiento de las dos partes que pide el art. 4.b. Una
  herramienta que deje rectificar cien asientos de una vez es exactamente lo que
  la norma quiere impedir, por muy cómoda que resulte.
- **Resolver en masa solo si cada decisión guarda su rastro.** Aprobar
  veinte ausencias de golpe puede estar bien; lo que no puede es que en el
  histórico aparezcan como una sola cosa, ni que se salte las cuatro manos.

## Cómo abordarlo

La petición es más amplia que la lista de arriba: **revisar cada pantalla
entera, con todas sus opciones, y mejorar lo que se pueda**. Así que el orden es
mirar primero y decidir después --- no ir pantalla por pantalla pegando
casillas de selección donde quepan.
