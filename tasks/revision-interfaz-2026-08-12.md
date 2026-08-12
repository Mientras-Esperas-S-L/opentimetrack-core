# Revisión de la interfaz web · 12/08/2026

> **Estado al cierre del 12/08.** Los cuatro bloqueantes están arreglados y
> comprobados en el navegador: commits `49ca2ae`, `26614d4`, `d974c5a` y
> `9ce560f`. Marcado con `[x]` lo hecho. Lo que sigue sin marcar es lo que
> queda, y está en el orden en que lo haría.
>
> Tres cosas aparecieron al arreglarlos y no estaban en esta lista:
>
> - **La búsqueda de Personas nunca ha filtrado.** `DEFAULT_FILTER_BACKENDS`
>   solo tenía `DjangoFilterBackend`, así que todos los `search_fields` y
>   `ordering_fields` de todos los viewsets eran decoración.
> - **El filtro de fechas de fichajes sí existía y estaba mal.** Cortaba el día
>   en UTC, no en la zona de la empresa: en Madrid, todo lo fichado entre
>   medianoche y las 02:00 contaba en el día anterior.
> - **Personas era la única pantalla del panel sin comprobación de perfil.** Un
>   responsable veía tres botones que el API le rechazaba con 403.

Repaso de las 15 pantallas buscando controles que falten, acciones sin
confirmación y desplegables que no aguanten el número de entradas reales.

Lo que sigue está comprobado contra el código y, donde se podía, contra la API
en marcha. Los cuatro primeros no son cuestión de comodidad: impiden usar el
producto o dejan sin efecto algo que ya está construido.

---

## Bloqueantes

### 1. Nadie puede entrar salvo quien se sembró en la base de datos

Tres cosas encadenadas:

- `send_account_email` manda a `{FRONTEND_URL}/set-password/{uid}/{token}/`
  (`apps/users/passwords.py:74`). Esa ruta **no existe** en `App.jsx`: cae en el
  comodín `path="*"` y redirige al reloj de fichar, sin explicar nada.
- El alta de una persona **no envía invitación**. `send_account_email` solo se
  llama desde el endpoint de recuperación (`apps/users/views.py:325`).
- La pantalla de acceso **no tiene enlace de "he olvidado mi contraseña"**.

Resultado: un administrador da de alta a alguien y esa persona no tiene ninguna
forma de conseguir una contraseña.

- [x] Ruta `/set-password/:uid/:token` con su pantalla
- [x] Enlace de recuperación en `SignIn`
- [x] Botón "Enviar invitación" en Personas, y envío automático al crear

### 2. Las listas se cortan en 50 y la pantalla no lo dice

`PAGE_SIZE = 50` en DRF. El helper `rows()` de `api.js:81` se queda con
`results` y **descarta `count` y `next`**.

Comprobado con datos reales: con 90 fichajes en la empresa demo, la API responde
`count: 90`, devuelve 50 y ofrece `next`. La pantalla Fichajes muestra 50 y no
avisa de nada, bajo el subtítulo "El registro tal y como está guardado".

Afecta a Fichajes, Personas, Mis ausencias y **Actividad**, que es el registro de
auditoría. Un inspector pidiendo el histórico vería una lista truncada sin
ninguna señal de que lo está.

- [x] Que `rows()` devuelva también `count` y `next`, o paginar de verdad
- [x] Paginador o scroll infinito en las cuatro pantallas
- [x] Filtro de fechas en Fichajes y en Actividad, que es lo que evita el
      problema de raíz

### 3. El flujo del artículo 4.b no tiene interfaz

Está construido en el backend (ADR-0014) y no se puede usar.

- `accept`, `dispute` y `apply-anyway` no existen en `api.js`.
- "Por decidir" solo consulta `status: 'PENDING'`. Una corrección que la empresa
  propone sobre el registro de otra persona pasa a `AWAITING_EMPLOYEE` y
  **desaparece de la pantalla**.
- En "Mi jornada", la persona ve sus correcciones en una lista de solo lectura
  con un chip de estado (`MyTime.jsx:196-213`). No hay botón de aceptar ni de
  discrepar.

Una propuesta de la empresa queda colgada para siempre y la persona ve un chip
que dice que se espera su respuesta, sin manera de darla.

- [x] Bandeja de correcciones en "Mi jornada" con Aceptar y Discrepar
- [x] Pestaña de "Esperando respuesta" y "En desacuerdo" en Por decidir, con
      aplicar sin acuerdo pasado el plazo
- [x] Marcar en el listado lo aplicado sin acuerdo

### 4. Seis campos de `User` no salen en ningún serializer

`date_of_birth`, `part_time`, `part_time_percentage`, `contracted_schedule`,
`default_work_mode` y `is_worker_representative` están en el modelo, los lee la
lógica de dominio, y no aparecen en `apps/users/serializers.py`. No hay forma de
rellenarlos ni por API ni por pantalla.

Consecuencias, todas silenciosas:

| Campo | Qué deja sin efecto |
|---|---|
| `date_of_birth` | Todas las protecciones de menores. `age_is_known` es siempre falso, así que no salta ninguna |
| `part_time` | La negativa a horas extra del art. 12.4.c |
| `contracted_schedule`, `part_time_percentage` | Contenido obligatorio del art. 3 del proyecto de RD; el informe sale vacío |
| `is_worker_representative` | El aviso a la representación legal del art. 4.b: nunca encuentra a nadie |

- [x] Añadirlos al serializer de lectura y al de escritura
- [x] Sección "Contrato" en la ficha de persona
- [x] Casilla de representante legal, con aviso en Ajustes si no hay ninguno

---

## Controles que faltan

- [x] **Reactivar a quien está de baja.** El botón solo aparece si
      `is_active` (`People.jsx:317`). El API ya lo permite: `is_active` es
      escribible. Ahora dar de baja es un viaje de ida.
- [x] **Confirmar antes de destruir.** Cinco acciones y ninguna pregunta: dar de
      baja, borrar departamento, borrar turno, cancelar ausencia y **vaciar el
      mes** del cuadrante (`Roster.jsx:438`), que borra el mes entero de todo el
      mundo con un clic.
- [x] **Decir a cuántos afecta un borrado.** Departamento y turno son
      `SET_NULL`: no se pierde nada, pero borrar un departamento deja sin
      asignar a su gente y borrar un turno lo despega de días ya publicados.
      Debería decir "3 personas quedarán sin departamento".
- [x] **Actividad**: filtro por fecha y exportación en CSV. Es el
      registro que se enseña en una inspección.
- [x] **Informes**: una persona, un departamento o toda la empresa. Falta "toda la empresa" y "por
      departamento"; hacer 200 PDF de uno en uno no es viable. Y el resumen del
      art. 6.1 se genera para toda la plantilla desde la misma pantalla.
- [x] **Mi jornada**: navegación por meses. Se ven los últimos 50 fichajes,
      unos 25 días, y no hay forma de mirar atrás.
- [x] **Calendario de equipo**: pinchar una banda abre la ausencia, y si está pendiente se decide ahí. Ni ir a la persona
      ni abrir la ausencia ni asignar desde ahí.
- [x] **`punches/delegated/`**: pantalla de Aplicaciones. No tenía ni pantalla ni API: solo shell.

---

## Desplegables

Ni un `Autocomplete` en todo el proyecto. Todos los selectores son `Select`
planos con `MenuItem`.

| Dónde | Estado |
|---|---|
| Cuadrante, "A quién" | **Hecho.** `EmployeePicker` con chips y búsqueda en servidor |
| Fichajes, "Persona" | **Hecho.** Mismo componente, más "toda la empresa" |
| Informes, "Persona" | **Hecho.** Falta añadirle "toda la empresa" y "por departamento" |
| Ajustes, "Zona horaria" | **Hecho.** Autocomplete con todas y el desfase horario a la derecha |
| Personas, "Departamento" | Pendiente y no urgente. Vale mientras sean pocos; pasados 20, buscador |

Los tres primeros salían de la lista paginada, así que además de incómodos
estaban truncados: en una empresa de doscientas, tres cuartas partes de la
plantilla no se podían elegir y nada lo decía. `EmployeePicker` avisa cuando lo
que muestra no es todo.

La zona horaria tiene además un fallo propio: el campo del backend acepta
cualquier zona IANA y el desplegable solo ofrece nueve. Una empresa configurada
por API con `Europe/Berlin` ve el desplegable **en blanco**, y guardar cualquier
otro campo de esa pantalla le cambia la zona sin que se entere.

También conviene añadir a los selectores de persona el filtro por departamento
como paso previo: en una empresa de 200, "primero el departamento, luego la
persona" es más rápido que teclear.

---

## Menor

- [x] La búsqueda de Personas lanzaba una consulta **por tecla**: no hay debounce
      ni `useDeferredValue` en ningún sitio del proyecto.
- [ ] Sin ordenación por columnas en ninguna tabla.
- [ ] Sin acciones en bloque (asignar departamento a varias personas, por
      ejemplo).
- [ ] Sin aviso de confirmación tras guardar. Los formularios cierran el diálogo
      y ya está; en una tabla larga no se ve qué cambió.
- [ ] Los botones deshabilitados no dicen por qué. "Asignar turno" está apagado
      si no hay turnos y eso sí se explica con un `Alert`, pero "Descargar PDF"
      apagado por rango inválido no.

---

## Nota sobre datos de prueba

Para comprobar el punto 2 se crearon 80 fichajes en la empresa demo de
desarrollo (`Jardines Demo S.L.`, `manager@demo.local`). Se dejan puestos: sin
ellos el corte a 50 no se reproduce, y hará falta para verificar el arreglo.
`python manage.py seed_demo --reset` los quita.

---

## Fuera de España

Lo que haría falta para que el producto sirva en otro país está en
[`internacionalizacion.md`](internacionalizacion.md), con las cifras medidas
sobre el código de hoy y los comandos para reproducirlas.

Lo corto: el núcleo ya es neutro, hay 19 citas legales españolas llegando a la
pantalla, siete de los ocho idiomas del desplegable devuelven inglés, y
`Tenant.country` existe desde el principio diciendo que sirve para seleccionar
las reglas aplicables sin que lo lea nadie. Ese campo es el gancho.
