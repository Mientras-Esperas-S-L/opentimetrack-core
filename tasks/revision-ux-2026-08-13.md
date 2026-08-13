# Revisión de interfaz, pantalla por pantalla — 13/08/2026

Recorrido de las dieciséis pantallas con sus opciones abiertas, mirando qué se
puede hacer en cada una y qué falta. No es una lista de deseos: cada punto dice
qué tarea concreta se atasca hoy.

Tres estados:

- **Hecho hoy** — arreglado en esta sesión.
- **Por hacer** — con su sitio en el orden de abajo.
- **Está bien** — se mira y se deja. Decirlo importa: marca dónde **no** gastar.

---

## Lo que atraviesa toda la aplicación

### Ninguna pantalla deja operar sobre más de una fila

Ni una casilla de selección en las dieciséis. Cualquier reorganización es abrir
y cerrar diálogos: meter quince personas en un departamento son quince
diálogos, y resolver veintidós horas extra son veintidós.

Detalle que lo confirma: **«Por decidir» ya tiene un «Seleccionar todo»** en una
de sus colas. O sea que el patrón existe, se escribió una vez y no se extendió.

Ver `tasks/ux-acciones-masivas.md`. **Por hacer, es lo primero.**

### Los mandos de MUI hablaban inglés — hecho hoy

«Go to next page», «page 3», «Clear», «Open». Son `aria-label`: no se ven, y por
eso aguantaron sin que nadie los reportara. Los lee quien navega con lector de
pantalla o deja el ratón encima, que es justo la persona a la que peor le viene
encontrarse otro idioma.

Arreglado con el paquete `esES` aplicado al tema, para que lo que se añada
mañana nazca traducido. Con una corrección encima: MUI traduce «open» por
«Abierto», que es lo que el desplegable está, no lo que el botón hace.

### Las listas no eran listas — hecho hoy

Turnos, Centros, Aplicaciones y Departamentos pintaban cajas sueltas. Un lector
de pantalla las leía del tirón, sin decir cuántas hay ni cuándo se acaba.
Ahora son `ul`/`li` de verdad.

### La IP de un compañero en el registro de actividad — hecho hoy

Quien miraba su propio registro veía las líneas de lo que le hicieron, y con
ellas **la dirección IP del responsable que se lo hizo**. Para saber quién le
tocó el fichaje ya está el nombre. Ahora la IP solo la ve quien actuó desde
ella, o la administración.

---

## Pantalla por pantalla

### Resumen (`/panel`)

**Está bien.** Seis tarjetas, cada una con su número y su enlace. Se lee de un
vistazo, que es lo único que se le pide.

### Personas (`/panel/personas`)

La que más trabajo necesita. Veintiuna filas, y para acotarlas solo hay un
buscador de texto y un «Ver también las bajas».

- **Por hacer:** filtrar por departamento, centro y perfil. Hoy no hay forma de
  responder «¿quién no tiene departamento?», que es la primera pregunta de
  cualquier reorganización.
- **Por hacer:** selección múltiple con «Mover a departamento», «Cambiar de
  centro» y «Dar de baja».
- **Está bien:** el menú por fila se llama «Más acciones para Ana García», con
  el nombre dentro. Eso está cuidado y no se toca.

### Departamentos (`/panel/departamentos`)

- **Por hacer:** un selector «Quién está dentro» en el diálogo. Es la pantalla
  que se llama Departamentos y es justo donde no se puede componer uno; los
  miembros se asignan desde Personas, de uno en uno.
- **Está bien:** el que tiene gente dentro no ofrece borrarse. El botón no
  está, en vez de estar y fallar.

### Centros de trabajo (`/panel/centros`)

- **Hecho hoy:** la zona horaria era un campo de texto libre para un
  identificador IANA exacto. Se escribía «Madrid» o «Canarias» y el servidor lo
  rechazaba sin decir cuál era el bueno. Ahora es un desplegable con las del
  país delante y su nombre en cristiano.
- **Por hacer:** mover personas de un centro a otro. Hoy es la ficha de cada
  una.
- **Está bien:** el aviso de que un centro con gente no se puede eliminar
  explica **por qué** —se quedarían sin festivos locales— en vez de solo
  negarse.

### Calendario del equipo (`/panel/calendario`)

- **Está bien:** las solicitudes sin resolver salen rayadas y el mes lleva su
  contador de «N sin resolver». La diferencia entre lo pedido y lo concedido se
  ve sin leer nada.
- **Por revisar:** filtrar por tipo de ausencia o por estado. Con una plantilla
  grande el mes se llena y no hay forma de mirar solo las vacaciones.

### Cuadrante (`/panel/cuadrante`)

- **Hecho hoy:** «Asignar turno» **no se podía enviar nunca** —el formulario
  era inválido para el navegador hiciera lo que hiciera la persona—, y
  desmarcar todos los días asignaba los siete en vez de ninguno.
- **Está bien:** el pintado por arrastre ya es la acción masiva de esta
  pantalla, y «Vaciar el mes» dice cuántos turnos y de cuánta gente antes de
  hacerlo.

### Turnos (`/panel/turnos`)

**Está bien.** Once turnos, alta, edición y borrado con confirmación. Una
pantalla que se usa dos veces al año no necesita filtros.

### Fichajes (`/panel/fichajes`)

- **Está bien, y a propósito:** no hay selección múltiple y no debe haberla. Un
  asiento del registro se corrige de uno en uno, con el consentimiento de las
  dos partes del art. 4.b. Hay una prueba que se pondrá roja si aparece una
  casilla de «seleccionar todo».
- **Está bien:** al filtrar por una persona, la columna «Persona» desaparece.
  Repetir el mismo nombre cincuenta veces no informa de nada.
- **Por revisar:** falta filtrar por tipo (entrada, salida, pausa) y por origen
  (web, móvil, terminal). El origen es una columna que se enseña y no se puede
  usar para buscar.

### Por decidir (`/panel/decisiones`)

Cinco colas con su contador: Ausencias, Fichajes, Sin acuerdo (25), Horas extra
(22), Vacaciones por recuperar.

- **Por hacer:** resolver varias a la vez en las colas donde sea legítimo. Con
  veinticinco pendientes, de una en una no se vacía nunca. **Con la condición
  de que cada decisión guarde su propio rastro**: en el histórico tienen que
  seguir siendo veinticinco decisiones, no una.
- **Está bien:** el contador en cada pestaña. Es lo que decide si alguien entra
  a mirar.
- **Está bien:** las colas vacías se explican en vez de quedarse en blanco.

### Informes (`/panel/informes`)

- **Hecho hoy:** el informe de **toda la empresa** bajaba un `informe.pdf` que
  no abría ningún visor. No estaba roto el documento: la entrega de toda la
  empresa es un **zip** con un PDF por persona, y se guardaba con nombre de PDF.
  La causa estaba en CORS ---`Content-Disposition` no se expone salvo que el
  servidor lo diga, y sin ella la pantalla inventaba el nombre--- que es la
  misma familia que el desfase del reloj de la semana pasada. De paso vuelven
  los nombres buenos: `working-time_B00000001_2026-06-29_2026-08-13.zip` en vez
  de «informe.pdf», que no decía ni de quién ni de cuándo.
- **Hecho hoy:** el CSV salía con finales de línea de Windows. Lo que importa
  no es el «^M» del editor: es que el «\r» se queda pegado a la última columna,
  así que un `split(";")` devuelve «05:00\r» y nadie lo nota hasta que las
  horas no cuadran.
- **Está bien:** es la única pantalla que ya pensaba en volumen. «Generar los de
  toda la plantilla» existe, y los botones se desactivan con el periodo al revés
  diciendo por qué.

### Aplicaciones (`/panel/aplicaciones`)

**Está bien.** El testigo se enseña una vez y lo dice antes de que nadie cierre.
Los permisos se marcan uno a uno, sin un «dar todos».

### Ajustes de la empresa (`/panel/ajustes`)

- **Hecho hoy:** salirse de un límite legal no avisaba. Se podían poner ocho
  horas de descanso entre jornadas en silencio, aunque el validador de convenios
  sí lo comprueba. Ahora avisa citando el artículo —avisa, no impide, porque el
  RD 1561/1995 lo baja de verdad en algunos sectores.
- **Por revisar:** diecinueve campos y un solo «Guardar cambios». Funciona,
  pero no hay ni rastro de qué se ha tocado antes de guardar.

### Fichar (`/`)

**Está bien.** Un botón grande, el reloj vivo y el tiempo trabajado corriendo.
Es la pantalla que más se usa y la más simple, que es como debe ser.

### Mi jornada (`/mi-jornada`)

**Está bien.** El mes, los recordatorios con su explicación al pasar por encima,
y «Pedir una corrección» sin enterrar.

### Mis ausencias (`/mis-ausencias`)

**Por revisar:** solo tiene «Solicitar». No hay forma de filtrar el histórico
por año ni por tipo, y con tres años de antigüedad eso es una lista larga.

### Registro de actividad (`/actividad`)

- **Hecho hoy:** la IP ajena (arriba).
- **Por revisar:** se filtra por fechas y nada más. Con paginación de cinco
  páginas ya, falta filtrar por quién y por qué acción.

---

## El orden

1. ~~**Departamentos: miembros desde el diálogo.**~~ **Hecho.** Un selector
   «Quién está dentro», con la lista completa: quitar a alguien lo deja sin
   departamento, no lo da de baja. Cada movimiento deja su apunte con nombre y
   apellidos, porque cambiar de departamento decide quién lee el registro de
   quién.
2. ~~**Personas: filtros y selección múltiple.**~~ **Hecho.** Filtros por
   departamento ---con «Sin departamento» como opción propia---, centro y
   perfil. Casillas por fila, «todas» limitado a la página que se ve, y una
   barra con «Mover a», «Cambiar de centro» y «Dar de baja». El lote va persona
   a persona a propósito: reutiliza el camino que ya comprueba permisos y deja
   rastro individual.
3. ~~**Por decidir: resolver en bloque.**~~ **Hecho.** Ya lo tenían dos de las
   cinco colas; ahora lo tienen las cinco, con dos matices que no son
   cosméticos. En «Sin acuerdo» solo se puede **retirar** en bloque, nunca
   aplicar: aplicar sin acuerdo es la excepción del art. 4.b, y veinticinco de
   esas con un clic la convertirían en la costumbre. En horas extra, «con
   descanso» y «pagadas» van separadas, porque son dos consecuencias distintas
   del art. 35.1 y las de descanso no cuentan para el tope anual --- un botón
   único obligaría a un valor por defecto, y ese sería el que se aplicara sin
   pensar.
4. ~~**Los filtros que faltan.**~~ **Hecho.** Tipo y origen en Fichajes, quién
   en Actividad, año y estado en Mis ausencias, tipo y estado en el Calendario.
   Con un detalle que se olvida siempre: el mensaje de lista vacía cambia
   cuando hay un filtro puesto, porque «todavía no has solicitado ninguna»
   sería mentira, y una mentira que se cree.
5. ~~**Ajustes: enseñar lo que se ha tocado.**~~ **Hecho.** Un aviso con cada
   campo cambiado y de qué a qué, y el botón desactivado cuando no hay nada que
   guardar.

## Lo que queda

- **Personas y Centros:** mover gente de un centro a otro desde la pantalla del
  centro, igual que ahora se hace con los departamentos.
- **Una ausencia aprobada no se puede deshacer.** El producto responde
  `already_resolved`, y para la baja que pisa las vacaciones ya está el flujo
  del art. 38.3. Pero unas vacaciones aprobadas que hay que mover no tienen
  camino: hoy la única salida es que no existan. Merece una decisión, no un
  parche.
- **`?search=` en `/absences/` se ignora en silencio.** No es un fallo de DRF
  ---un parámetro desconocido no es un error--- pero invita a escribir código
  que cree estar filtrando. O se implementa o se documenta.

Lo que no entra en esta lista, entra en la de «está bien» de arriba, y eso
también es una decisión.
