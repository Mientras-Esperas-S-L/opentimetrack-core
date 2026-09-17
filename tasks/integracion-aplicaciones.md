# Lo que le falta al Core para que otra aplicación lo use entero

**Estado:** plan aceptado, sin empezar · **Fecha:** 17/09/2026.

La puerta de integración existe desde el 13/08/2026: una aplicación tiene su
credencial y sus permisos, empuja personas, ficha en nombre de alguien y lee la
asistencia del día. Con eso una aplicación puede **fichar**, pero no puede sustituir
del todo a su propio módulo de recursos humanos, y esa es la promesa del producto.

Este plan recoge las piezas que faltan para cerrarla. El primer integrador es
GreenCity, pero ninguna pieza es suya: todas son mecanismo general.

## A1. Entrada por un proveedor de identidad (OIDC) ✔ hecho el 17/09/2026

`SsoProvider` (el mismo de A4) más `SsoDomain`, y cuatro puertas: `discover` por dominio
de correo, `start` con PKCE y estado de un solo uso, `callback` que canjea, verifica y
resuelve, y `logout` para que el proveedor cierre sesiones. El sujeto ancla y el correo
solo engancha la primera vez. El secreto se guarda cifrado con `FIELD_ENCRYPTION_KEY`,
que no se deriva de `SECRET_KEY` a propósito. 12 pruebas.

Hoy el Core solo sabe autenticar con su contraseña. Los campos `oidc_sub` y
`oidc_issuer` del usuario están desde el principio, y `is_federated` ya niega la
contraseña a quien tiene proveedor, pero **no hay flujo**: nadie puede entrar por
su proveedor porque no existe el camino.

Qué hace falta:

- `SsoProvider` por empresa (emisor, cliente, secreto cifrado, ámbitos, qué
  reclamación lleva el correo) y `SsoDomain` para descubrir el proveedor desde el
  dominio del correo. El modelo de geosian-backend es la referencia: multi-IdP,
  multiempresa, y ya probado en producción.
- Código de autorización con PKCE, validación del `id_token` (firma, `iss`, `aud`,
  `exp`, `nonce`), solo RS256. Nunca dejar que el proveedor elija el algoritmo.
- Resolución de la persona por `oidc_sub` primero, y por correo dentro de la empresa
  solo la primera vez, para enganchar a quien ya existía.
- Alta al vuelo opcional, sin permisos, cuando la empresa lo active.
- Pantalla de entrada: botón por proveedor, y modo «solo proveedor» cuando la
  empresa lo exija.

Esto es lo que quita la segunda contraseña. Sirve igual para el proveedor propio de
un cliente (Entra) que para la aplicación de gestión que hace de proveedor.

Dos cosas más que van con la federación y que no son opcionales:

- **Cerrar la sesión cuando el proveedor lo pida.** Un cambio de contraseña o una
  desactivación en el proveedor tiene que llegar aquí: OIDC Back-Channel Logout
  (el proveedor envía un `logout_token`, se invalidan los refresh de esa persona).
  Sin eso, la sesión federada vive los siete días del refresco aunque la cuenta de
  origen esté comprometida. Mientras no esté, refresco corto para cuentas federadas.
- **Que un inactivo no refresque.** El empuje de personas desactiva; la
  autenticación JWT debe rechazar al inactivo en el siguiente refresco. La librería
  lo hace por defecto; que una prueba lo fije para que nadie lo cambie sin verlo.

## A2. Asistencia por rango, no solo el día en curso ✔ hecho el 17/09/2026

`GET /api/app/attendance/range/?from=&to=`, con `employee_ref` para una persona y
paginación por persona (`page`) para la plantilla. Tope de 62 días. Por persona y día:
estado, segundos trabajados, tramos, `scheduled` (con `null` cuando no hay cuadrante,
que no es lo mismo que «no le tocaba»), el festivo de **su** centro y la ausencia que
cubre el día. Quien causó baja conserva su calendario. 8 pruebas.

`GET /api/app/attendance/` responde **hoy**, para una persona o para la plantilla.
Una pantalla de recursos humanos pinta un mes entero, así que con esto no se puede
sustituir: haría treinta llamadas y aun así no sabría de ausencias ni de festivos.

`GET /api/app/attendance/?from=&to=` con, por persona y día: estado, minutos
trabajados, tramos, si era laborable según su cuadrante, la ausencia si la hubo
(tipo y si estaba aprobada) y el festivo si lo era. Sin metadatos de captura, como
ya se decidió: la IP y el dispositivo no salen hacia otra aplicación.

Con tope de días por llamada y paginación por persona, porque esto lo va a llamar
un conector que pinta calendarios.

Los **tramos** no son adorno: la aplicación integrada puede necesitar repartir el día
según su propio contexto (qué proyecto, qué obra), y sin los tramos solo puede
repartir a ojo o duplicar el día entero en dos sitios.

## A3. Leer ausencias, cuadrante y festivos desde una aplicación

`read:attendance` se queda con lo que mide la jornada. Lo demás son permisos nuevos
y separados, que es la regla de la casa: se conceden uno a uno.

- `read:absences`: ausencias de un rango, con su tipo del catálogo legal.
- `read:roster`: turnos planificados de un rango.
- `read:calendar`: festivos por centro de trabajo.

**No** se abre escritura de horas por esta puerta. Lo que cambia el registro entra
por donde ya entra: fichar, o el flujo de corrección del art. 4.b. Una aplicación
integrada que pudiera escribir horas convertiría las garantías en opcionales.

La escritura de **ausencias** sí tiene sentido (`write:absences`), porque es una
solicitud, no una medición, y quien la pide suele estar en la otra aplicación.
Pasa por las mismas validaciones y topes que si se pidiera aquí.

## A4. Fichar con la identidad de la persona desde una aplicación ✔ hecho el 17/09/2026

`POST /api/app/sessions/` canjea una aserción firmada (RFC 7523) por una sesión de la
persona que nombra. Los emisores de confianza son filas de la empresa (`SsoProvider`,
que A1 ampliará para el flujo de navegador) y actuar por las personas es un permiso
aparte, desactivado por defecto. La aserción exige `iss`, `aud`, `exp`, `iat` y `jti`,
vive un minuto y sirve una vez. Lo que ficha esa sesión sale `APPLICATION` con el
nombre de la aplicación, y la marca viaja **dentro del token**, no en el cuerpo, así
que el origen no lo elige quien llama. El canje deja rastro en la auditoría.
La referencia opaca de contexto no hizo falta: `evidence` ya la lleva. 13 pruebas.

El ADR-0010 lo da por decidido y solo está la mitad: el fichaje delegado. Falta la
vía preferente, la persona fichando con su identidad desde otra aplicación.

Con A1 resuelto es corto: la aplicación obtiene un testigo de la persona en su
proveedor común, lo presenta, y el fichaje entra por `POST /api/punches/` con
`source = APPLICATION` y el nombre de la aplicación. El no repudio se mantiene:
quien ficha es la persona, y el registro lo distingue del delegado.

**El mecanismo concreto es una aserción, no un flujo de navegador.** El servidor de la
aplicación no tiene el navegador de la persona delante cuando ficha por ella (o
reenvía su cola). Con A1 configurado, la aplicación, que es también el proveedor de
identidad o está registrada como emisor de confianza, firma un JWT corto (emisor,
audiencia este Core, la referencia externa de la persona, 60 segundos) y lo presenta
al canje con `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer` (RFC 7523).
El Core lo valida contra el JWKS del emisor, resuelve a la persona **por su
referencia externa** (`employee_id`), no por `oidc_sub`, para que sirva aunque la
persona entre por otro proveedor en el navegador, y emite una sesión corta. Un
emisor de confianza puede así actuar por cualquiera de sus personas: es lo que
significa ser proveedor de identidad, y por eso el fichaje lleva `source =
APPLICATION` y el nombre de la aplicación a la vista.

Un añadido pequeño y útil: que la aplicación pueda adjuntar una **referencia opaca de
contexto** (lo que para ella significa «dónde»), que el Core guarda y devuelve sin
interpretar, como ya hace con la evidencia del fichaje delegado. No convierte ese
concepto en concepto del Core, y le ahorra a la aplicación depender solo de su propio
índice para saber dónde ocurrió cada fichaje.

## A5. Hora declarada y hora de recepción

Decidido el 13/08/2026 y pendiente desde entonces. Quien ficha en campo sin
cobertura se queda en la cola del dispositivo y llega tarde.

Se guardan **las dos horas**, la declarada por el dispositivo y la de recepción, con
el origen marcado y visibles en el informe de Inspección. Por debajo de un plazo de
gracia (ajuste de la empresa, 24 h por defecto) entra con la declarada; por encima,
pasa por el flujo de corrección.

Lo que la norma exige es fiabilidad, objetividad y trazabilidad, no simultaneidad:
se conserva la procedencia entera y nada es editable después.

## A6. Disponibilidad, para quien planifica

Una aplicación que asigna trabajo pregunta antes de asignar: quién puede trabajar
tal día. Es la regla del ADR-0011: el Core dice cuándo se puede trabajar, la
aplicación dice qué se hace en ese tiempo.

`GET /api/app/availability/?from=&to=` con, por persona y día: si tiene turno, si
está de ausencia, y si el día es festivo en su centro. Sin decir por qué falta
cuando la causa es médica: la disponibilidad no necesita el diagnóstico.

No bloquea el fichaje. Bloquea que una aplicación retire su módulo propio sin
perder la planificación.

## A7. El centro de trabajo, con fechas

**No la pide ningún integrador: la pide el traslado.** Salió mirando a una persona que
trabaja en varios sitios, y ahí resultó no hacer falta: quien se desplaza un día al
municipio de al lado no cambia de centro, y sus festivos siguen siendo los de su
centro de adscripción (art. 34.6 ET, el calendario laboral es del centro). El caso que
sí la necesita es el **traslado**: alguien que cambia de centro para quedarse.

Hoy el centro (`Workplace`) es una columna del usuario, y de él salen los **dos
festivos locales** y la zona horaria. Sin historial, el día que alguien se traslada se
le reescriben los festivos de todos los meses anteriores, y el informe de un mes ya
cerrado deja de decir lo que decía. Ocurre pocas veces y en silencio, que es la peor
combinación.

El departamento ya resolvió esto: `DepartmentAssignment` guarda quién estaba dónde y
desde cuándo, y el informe de un periodo lee la adscripción **de ese periodo**. Falta
lo mismo para el centro:

- `WorkplaceAssignment` con `starts_on` / `ends_on`, la primera sin fecha de inicio
  («no consta desde cuándo»), igual que en la adscripción de departamento.
- Los festivos de una persona en un día se resuelven por el centro **de ese día**.
- La zona horaria, igual.
- El informe del art. 34.9 por centro lee la adscripción del periodo pedido.
- La aplicación de gestión puede empujar el cambio con la fecha en que ocurrió, no
  con la de hoy.

Prioridad: baja mientras nadie traslade a nadie, y alta el primer traslado, porque
antes del traslado se arregla en un rato y después hay que decidir qué hacer con lo
que ya se reescribió.

## A2 bis. Tres huecos pequeños de la API de personas ✔ hecho el 17/09/2026

`oidc_issuer` se guarda; `role` se respeta **solo al crear**; y `GET /api/app/me/`
dice qué aplicación es, con qué permisos y de qué empresa. 6 pruebas. Lo de abajo es
el razonamiento de por qué hacían falta.

Al capturar el contrato real desde el primer integrador aparecieron tres cosas que la
API de aplicaciones no dice y el integrador necesita. Son cortas y van juntas:

- **`oidc_issuer` en el alta.** `PUT /api/app/people/{ref}/` acepta `oidc_sub` pero no el
  emisor, y el sujeto sin emisor no identifica a nadie cuando la empresa tiene dos
  proveedores (el suyo y el de la aplicación). Hoy la clave se ignora en silencio.
- **`role` en el alta.** La persona se crea siempre `EMPLOYEE`; la aplicación de gestión
  sabe quién es responsable y hoy no puede decirlo. Solo al **crear**: el rol de quien
  ya existe lo manda quien administra aquí, no el conector.
- **`GET /api/app/me/`: quién soy.** Una aplicación no puede saber a qué empresa apunta
  su credencial ni qué permisos lleva. «Probar conexión» del integrador tiene que
  tirar de `/api/app/people/` para adivinarlo, y distingue 401 de 403 a mano.

Y una cosa que no es hueco pero conviene dejar escrita: «no existe» es **409**
`person_not_found`, no 404, porque todos los errores de negocio van con 409. El
integrador lo trata así; si algún día se cambia, es un cambio de contrato.

## A8. Por dónde se ficha, cuando hay una aplicación integrada ✔ hecho el 17/09/2026

`Tenant.punch_entry` con tres valores. En `APPLICATION`, el fichaje por esta interfaz
pide un motivo de al menos diez caracteres, que se guarda en la evidencia y sale en el
informe; no se cierra la puerta. Una sesión obtenida por una aplicación no explica
nada, porque es la puerta esperada. 5 pruebas.

Sale de la misma conversación que A7. Si la aplicación integrada es la que sabe el
contexto del fichaje (para su propio uso: en qué proyecto, en qué obra, en qué
municipio), un fichaje hecho por la interfaz del Core llega sin ese contexto, y allí
le falta a la aplicación. La tentación es cerrar la interfaz del Core y dejar una
sola puerta.

**No se cierra: se declara cuál es la puerta normal.** Un ajuste de empresa, «las
entradas vienen de la aplicación», que hace que la interfaz del Core no ofrezca el
botón de fichar como primera opción, y deje en su sitio todo lo demás: ver la
jornada, pedir una corrección, solicitar ausencias, mirar el cuadrante.

Detrás del ajuste queda siempre una salida, **fichar igualmente**, que pide motivo y
marca el fichaje como excepción. Es innegociable por una razón: si la única puerta
fuera la aplicación, el día que la aplicación no esté disponible habría gente
trabajando sin poder registrar su jornada, y el que responde ante la inspección es
este sistema, no la aplicación. Un registro cuya disponibilidad depende de un
tercero no es un registro fiable.

Piezas:

- Ajuste de empresa con tres valores: interfaz y aplicación (hoy), aplicación
  preferente (el de arriba), y solo terminal, para instalaciones sin sesión
  personal.
- La excepción se marca en el fichaje y se ve en el informe, como ya se distingue el
  delegado del propio.
- Ausencias, correcciones y cuadrante no se tocan: no son fichajes.

## Orden

A1, A2 y A2 bis son las que desbloquean a un integrador (entrar sin segunda contraseña y
pintar un mes). A3 va detrás porque sin ella el mes se pinta con huecos. A4 mejora
la calidad de la prueba pero no bloquea, porque el delegado ya funciona. A5 es la
que evita perder jornadas en campo. A8 va con la primera integración real, porque es
cuando aparece la puerta de más. A7 no bloquea a nadie hoy y conviene tenerla antes
del primer traslado de centro. A6 es la última y es de otra conversación.

## Pruebas que van con estas piezas

- Un **fixture capturado** de cada respuesta de aplicación (`people`, `attendance`
  por rango, fichaje delegado, canje de la aserción), para que el integrador pruebe su
  conector contra lo que el Core responde de verdad y no contra lo que recuerda.
- El límite de **6000 llamadas por hora y aplicación** es una decisión, no un
  accidente: una prueba que lo fije y una respuesta `429` que diga cuánto esperar.

## Al terminar cada pieza

- Una pantalla o un campo nuevo → el manual.
- Una situación legal que pasa a estar cubierta → mover su fila en
  `docs/cobertura-legal.md`.
- Y cuando A1 a A4 estén, escribir `docs/integracion.md`: cómo se integra otra
  aplicación, escrito para publicarse. Hoy no existe, y documentar lo que aún no
  está engaña más que no documentarlo.
