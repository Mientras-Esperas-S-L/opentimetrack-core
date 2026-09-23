# Cuaderno del bucle: la consola de Instalación

Estado entre pasadas. El prompt está en `consola-instalacion-loop.md`.

| # | Trozo | Estado |
|---|---|---|
| T1 | Registro de lo que hacen las cuentas de instalación | **hecho** (PR core 26) |
| T2 | Editar y desactivar una empresa | **hecho** (PR core 27 y 28) |
| T3 | Los administradores de cada empresa y su contraseña | **hecho** (PR core 29) |
| T4 | El estado de cada empresa de un vistazo | **hecho** (PR core 30) |

## Qué toca ahora

Nada: los cuatro trozos están hechos. Lo que queda son las decisiones de abajo.

## Qué se hizo en la última pasada

**T4**, 23/09/2026.

En la lista de empresas: «Actividad» con el día del último fichaje y cuándo habló
cada aplicación, el último acceso con la identidad en «Cómo entran», y las personas
activas. Lo que lleva un día laborable entero sin nada sale en negrita y con
palabras («sin fichajes desde», «callada desde»). Cuatro consultas para todas las
empresas.

**Solo días y recuentos**: ni la hora del fichaje ni quién. En una empresa de una
persona, la hora ya sería su dato.

Medido en devel: GreenCity Pruebas sale «Sin fichajes desde el 21 sept» (hoy es
miércoles 23: el martes entero sin nada) y su aplicación «usada el 22 sept».

**Tres cosas que salieron midiendo:**

- **«Nadie ha entrado todavía con ella»** en GreenCity Pruebas, donde 16 personas
  entran con la identidad. La fecha no se anotaba hasta hoy (ver T3). Ahora se
  cuenta quién ha entrado alguna vez, que sí se sabe. Y «No ha entrado nunca» de
  la ficha pasa a «No consta ningún acceso».
- **A 1280 px la tabla no cabía**: 994 px en una caja de 934, con los botones
  cortados. «Con qué se conectan» va dentro de «Actividad», el CIF bajo el nombre
  y los botones apilados. Medido después: 934 de 934.
- Sin festivos en «callado»: un festivo da un aviso de más. Es un aviso para
  mirar, no un cómputo.

### Antes: T3
23/09/2026.

En la ficha de cada empresa, «Quién la administra»: solo administradores, con su
último acceso y si entran con la cuenta de su empresa. «Mandar enlace» les envía
a su correo el enlace para poner contraseña; la consola no lo ve nunca.

**Dos fallos de fondo que salieron midiendo:**

- **`last_login` no se guardaba nunca.** La cuenta de instalación recién entrada
  seguía con él vacío, así que la columna nueva habría dicho «No ha entrado nunca»
  de todo el mundo. Y el enlace de contraseña firma con ese campo para morir
  cuando la persona entra: seguía valiendo. Arreglado en `issue_tokens`, salvo
  para las sesiones que pide una aplicación en nombre de alguien. Comprobado en
  devel después.
- **El relé rechaza la dirección y la pantalla pedía reintentar.** Con
  `alcaldia@bucle.test` el relé contesta 554; ahora se nombra la dirección y se
  pide comprobarla.

**Sin medir en devel: un envío que llegue.** Las direcciones de las empresas de
prueba son `.test` y el relé las rechaza; las demás son buzones de verdad y no
quise escribir a nadie. El envío correcto lo cubre la prueba con `mail.outbox`.

**Y el rojo del PR 27**: la prueba de la vuelta del proveedor dependía de
`SSO_WEB_URL`, que el contenedor trae y el CI no. Arreglada en el PR 28, y
`como-el-ci.sh` corre ya las pruebas sin esa variable.

### Antes: T2
23/09/2026.

`PATCH /api/platform/companies/<id>/` para la ficha y el estado, y el botón
«Ficha» en cada fila. Desactivar pide el nombre escrito, también en el servidor.

**El arreglo de verdad era otro, como avisaba el prompt.** `is_active` solo
frenaba la entrada con contraseña. Medido con una prueba antes del cambio: con la
empresa desactivada, la sesión abierta seguía, el refresco la renovaba una semana
y el proveedor de identidad abría sesión nueva. Ahora las tres puertas lo miran
(`TenantJWTAuthentication`, el refresco y la vuelta del proveedor), cada una con su
prueba calibrada.

**Y un fallo de antes, más gordo de lo que parecía**: los diálogos de Instalación
nunca enseñaban el motivo de un rechazo. Leían el error de axios crudo y el
interceptor ya lo entrega normalizado. Medido: correo repetido, servidor «Ya hay
una cuenta de la instalación con esa dirección», pantalla «No se ha podido crear la
cuenta». Eso incluye **el aviso del PR 25, que en producción no se ve** hasta que
llegue este PR. Arreglado en el interceptor (lee también `{"detail"}`) y en los
seis diálogos.

Medido en devel a 1280 y 360, con «Ayuntamiento del Bucle»: el CIF repetido sale
bajo su casilla, «Desactivar» está bloqueado sin el nombre, desactivar pone la
marca «Desactivada» en la fila y reactivar la quita. Diálogo sin desborde, ventana
en el ancho pedido. El único error de consola es el propio 400 del CIF repetido,
que la pantalla explica.

**Sin medir en devel**: que una sesión real de una empresa muera al desactivarla.
No tenía contraseña de ninguna cuenta de dentro de una empresa de prueba; lo
cubren las pruebas. T3 da la forma de conseguirla.

**GreenCity y el CIF**: solo lo usa al dar de alta, para el nombre del cliente de
identidad (`opentimetrack-<cif>`) y el de la conexión. Cambiarlo después no rompe
el enlace; el nombre del cliente se queda con el CIF viejo, que es cosmético.

### Antes: T1
23/09/2026.

Tabla propia, `PlatformAuditEntry`, con los tres disparadores de `AuditLog`.
La sonda de salud y `ensure_append_only` vigilan ya las dos tablas. Once acciones
de la consola anotan ahí; las que tocan a una empresa siguen yendo también a su
rastro. Sección «Registro» al final de la consola, paginada.

Medido en devel, entrando por la pantalla de acceso: crear una cuenta desde la
consola la pone arriba del registro **sin recargar**; a 1280 y a 360 px, ventana
en el ancho pedido, sin desborde, sin errores de consola ni respuestas 4xx/5xx.

**De paso**, visto en la captura: el correo salía pegado al nombre en la lista de
cuentas («Administración de la instalacióninstalacion@…») y la zona horaria al
nombre de la empresa. Era `display="block"` suelto, que MUI ya no aplica.
Arreglado en el mismo PR.

La cuenta que creé para medir (`medida-registro-…@mientrasesperas.es`) quedó
desactivada en devel.

**Trampa para las pruebas**: `TRUNCATE` no se puede probar dentro de la
transacción de pytest, porque hay eventos de clave foránea pendientes y la base
lo rechaza por eso y no por el guardián. Se prueba por la sonda de salud.

## Decisiones tomadas sin preguntar

- **El último fichaje, por día y no por hora**, y sin quién.
- **«Callado» es un día laborable entero sin nada**, de lunes a viernes y sin
  festivos. Una empresa sin ningún fichaje todavía no avisa.

- **El CIF se puede cambiar**, con aviso. El caso real es corregir un error del
  alta. Un CIF que cambia de verdad suele ser otra empresa, y eso es darla de alta
  aparte; la consola no lo impide, pero el cambio queda con su antes y después en
  los dos rastros.
- **Desactivar no revoca credenciales ni desactiva personas**: solo cambia el
  estado. Así reactivar la deja exactamente igual, que es lo que pedía el prompt.

- **Tabla propia para la instalación** y no `tenant` nulo en `AuditLog`: esa tabla
  va por empresa para que ninguna lea la de otra, y un nulo ahí es una fila que
  cada consulta tendría que acordarse de excluir.
- **La pista de la credencial sí se guarda** (los últimos caracteres, `…abcd`), que
  es lo que la pantalla ya enseña de cada una. El testigo entero, nunca.
- **Crear una empresa no se anota en el rastro de la empresa**, solo en el de la
  instalación: antes de existir no tiene rastro, y su administrador ya sabe que se
  creó.

## Lo que espera decisión del usuario

- **`main` de opentimetrack-core no tiene ninguna protección**: ni PR obligatorio
  ni comprobaciones. El PR 27 entró con el backend en rojo por eso. Protegerla es
  un cambio de configuración del repositorio y lo decides tú.

- **Producción, cuando se despliegue, trae cuatro migraciones** (`audit/0021` a
  `0024`): copia previa de la base antes. Y hasta entonces, en producción los
  rechazos de la consola salen con el mensaje genérico.
