# Manual de OpenTimeTrack

Cómo se usa, pantalla por pantalla.

Está escrito también para que de aquí salga después el sistema de ayuda y los
recorridos guiados, como en Geosian. Por eso cada sección lleva un `slug` y
cada paso nombra el elemento concreto de la interfaz: quien monte el tour
tendrá que poner un `data-tour` en cada uno, y la lista está al final.

---

## Índice

**Para quien trabaja**
1. [Entrar por primera vez](#1-entrar-por-primera-vez) · `ott.primer-acceso`
2. [Fichar](#2-fichar) · `ott.fichar`
3. [Mi jornada](#3-mi-jornada) · `ott.mi-jornada`
4. [Pedir una corrección](#4-pedir-una-corrección) · `ott.corregir`
5. [Cuando la empresa propone un cambio](#5-cuando-la-empresa-propone-un-cambio) · `ott.cambio-propuesto`
6. [Mis ausencias](#6-mis-ausencias) · `ott.mis-ausencias`
7. [Actividad: quién ha mirado mi registro](#7-actividad) · `ott.actividad`

**Para quien gestiona**
8. [Dar de alta a una persona](#8-dar-de-alta-a-una-persona) · `ott.alta-persona`
9. [Departamentos](#9-departamentos) · `ott.departamentos`
10. [Turnos y cuadrante](#10-turnos-y-cuadrante) · `ott.cuadrante`
11. [Fichajes de la plantilla](#11-fichajes-de-la-plantilla) · `ott.fichajes`
12. [Por decidir](#12-por-decidir) · `ott.por-decidir`
13. [Informes para la Inspección](#13-informes-para-la-inspección) · `ott.informes`
14. [Aplicaciones y terminales](#14-aplicaciones-y-terminales) · `ott.aplicaciones`
15. [Ajustes de la empresa](#15-ajustes-de-la-empresa) · `ott.ajustes`

**Conceptos**
- [Qué no se puede hacer, y por qué](#qué-no-se-puede-hacer-y-por-qué) · `ott.limites`
- [Glosario](#glosario) · `ott.glosario`

---

# Para quien trabaja

## 1. Entrar por primera vez

`slug: ott.primer-acceso`

Cuando alguien te da de alta, recibes un correo con un enlace. **El enlace vale
una sola vez y caduca a las 24 horas.**

1. Abre el enlace del correo. Te lleva a una pantalla que pide una contraseña.
2. Escríbela dos veces. Mínimo doce caracteres.
3. Pulsa **Guardar y entrar**. No hace falta volver a escribirla: entras
   directamente.

**Si el enlace ha caducado o ya lo usaste**, en la pantalla de acceso hay
*He olvidado mi contraseña*. Escribe tu correo y recibirás otro. Esa pantalla
responde lo mismo exista o no la dirección: es a propósito, para que no se
pueda usar para averiguar quién trabaja dónde.

**Si tu correo está en más de una empresa**, al entrar te pedirá además el
CIF. Solo aparece en ese caso.

---

## 2. Fichar

`slug: ott.fichar`

Es la pantalla de inicio. Un botón grande, y arriba las horas que llevas hoy.

| Estado | Qué ves | Qué hace el botón |
|---|---|---|
| Jornada cerrada | `00:00` | **Fichar entrada** |
| Trabajando | El tiempo corriendo | **Fichar salida** |

**La hora la pone el servidor, no tu móvil.** Aparece dicho debajo del panel de
hoy. No se puede cambiar la hora del dispositivo para fichar antes o después, y
tampoco se pierde nada si tu reloj va mal.

Debajo, **Hoy** muestra los tramos del día: cada entrada con su salida, y el
total. Un tramo abierto se ve como *sin cerrar* hasta que fiches la salida; el
sistema no se inventa una hora de fin.

### Cosas que pueden pasar

- **«La jornada tiene que estar abierta primero.»** Estás intentando empezar un
  descanso sin haber fichado entrada.
- **No te deja fichar entrada.** Tienes una ausencia aprobada para hoy. Sí te
  deja cerrar una jornada que ya habías abierto.
- **Te han dado de baja.** Aunque tu sesión siga abierta, el fichaje se
  rechaza.

---

## 3. Mi jornada

`slug: ott.mi-jornada`

Tu registro completo. Tienes derecho a consultarlo y se conserva cuatro años.

Arriba, las flechas cambian de mes. La derecha se apaga en el mes actual
—adelante no hay nada— y aparece **Volver a este mes** cuando te has ido atrás.

Cada día es una tarjeta con sus tramos y el total. Un día con una corrección
aplicada lleva la etiqueta **Corrección**.

---

## 4. Pedir una corrección

`slug: ott.corregir`

Cuando el registro no coincide con lo que pasó: se te olvidó fichar, se quedó
el móvil sin batería, la hora que consta no es la real.

1. En **Mi jornada**, botón **Pedir una corrección**.
2. **Qué pasó**: *Olvidé fichar* o *La hora registrada no es la real*.
3. Si olvidaste fichar, di si falta **la entrada** o **la salida**.
4. **Hora real**. No puede ser una hora futura.
5. **Motivo**. Es obligatorio, y no es burocracia: una corrección sin motivo
   declarado no se distingue de una manipulación.
6. **Enviar solicitud**.

No se cambia nada todavía. La resuelve un responsable, y **el fichaje original
nunca se borra**: si se aprueba, queda anulado y legible, apuntando al nuevo.

En la misma pantalla, bajo **Mis solicitudes de corrección**, ves en qué estado
está cada una.

---

## 5. Cuando la empresa propone un cambio

`slug: ott.cambio-propuesto`

Al revés que lo anterior: la empresa quiere cambiar algo de tu registro.
Aparece en **Mi jornada**, arriba del todo, bajo **Un cambio en tu registro**.

Verás qué proponen, para qué día y con qué motivo. Dos botones:

- **Aceptar.** Se aplica.
- **No estoy de acuerdo.** Se abre un cuadro donde cuentas qué pasó según tú.
  Es obligatorio: un «no» sin contenido deja el registro con un desacuerdo y
  nada que sopesar frente al cambio, y quien sale perdiendo eres tú, porque tu
  versión es la que faltaría.

Si discrepas, tu versión queda guardada junto a la de la empresa y **se informa
a la representación legal de las personas trabajadoras**.

**La empresa puede seguir adelante sin tu conformidad.** Lo permite el artículo
4.b del real decreto de registro de jornada, y a cambio obliga a que conste: el
registro dirá *aplicada sin acuerdo* y llevará tu versión al lado, y las dos
cosas viajan al informe de Inspección.

**Si no contestas**, pasado el plazo que fije la empresa (siete días por
defecto) puede aplicarlo igualmente. El registro dirá que fue sin tu
conformidad, no que estuvieras de acuerdo.

---

## 6. Mis ausencias

`slug: ott.mis-ausencias`

Vacaciones, permisos y bajas. Arriba, los días que te quedan.

Para pedir: **Solicitar**, tipo, fechas y motivo. Puedes adjuntar un
justificante en PDF o foto, hasta 10 MB.

**No se sube el parte médico.** Desde el RD 1060/2022 la persona trabajadora ya
no se lo entrega a la empresa: el INSS manda los datos directamente. El sistema
lo rechaza a propósito.

Mientras está **Pendiente** puedes **Retirar** la solicitud. Una vez aprobada
ya no: ha bloqueado días y probablemente los planes de otra gente.

Una ausencia aprobada impide fichar entrada esos días.

---

## 7. Actividad

`slug: ott.actividad`

Quién ha consultado tu registro y qué se ha cambiado sobre ti.

Las lecturas llevan marca al margen: son las que nadie anuncia. Que un
responsable abra tu historial es legítimo, pero queda anotado.

**Consultar tu propio registro no deja entrada.** Es un derecho, y anotarlo
enterraría lo que sí importa.

Nadie puede borrar de aquí. Lo impide la base de datos, también para la
administración.

---

# Para quien gestiona

## 8. Dar de alta a una persona

`slug: ott.alta-persona`

**Personas → Dar de alta.** Solo administración.

**Datos básicos**: nombre, apellidos, correo (con él entra, y es único dentro
de la empresa), número de empleado y perfil.

| Perfil | Qué puede |
|---|---|
| Persona trabajadora | Fichar, ver lo suyo, pedir correcciones y ausencias |
| Responsable | Además: ver a todo el mundo, resolver solicitudes, cuadrante e informes |
| Administración | Además: alta y baja de personas, ajustes de la empresa, auditoría completa |

**Contrato** es la sección que más se olvida y la que más consecuencias tiene:

- **Fecha de nacimiento.** Es lo único que enciende las protecciones de menores
  de 18: ocho horas al día, descanso de treinta minutos a partir de cuatro y
  media, dos días de descanso semanal, y prohibición de nocturnidad y horas
  extra. **Sin ella no se aplican**, y el sistema lo dice en vez de suponer que
  la persona es adulta.
- **Horario contratado.** Va en el informe de Inspección: es contenido
  obligatorio del registro.
- **Jornada parcial** y su porcentaje. Activarla impide horas extra (art. 12.4.c
  del Estatuto), que en parcial son horas complementarias y se cuentan aparte.
- **Representante legal.** A quien se avisa cuando alguien discrepa de un
  cambio en su registro. Si no hay nadie marcado, Ajustes lo avisa.

Al guardar se envía automáticamente el correo con el enlace de acceso.

### Después

En el menú de cada fila (⋮):

- **Enviar enlace de acceso**, cuando el anterior caducó o no llegó.
- **Dar de baja**. Deja de poder fichar y de entrar; sus registros se conservan.
  Pide confirmación.
- Con **Ver también las bajas** activado, **Volver a dar de alta**.

---

## 8 bis. Calendario del equipo

`slug: ott.calendario`

Quién está fuera y cuándo, un mes por pantalla. El color es por tipo de
ausencia, no por persona: la pregunta que responde esta pantalla es «¿puedo
aprobar agosto?», y para eso importa cuánta gente falta y por qué.

Las solicitudes **sin resolver aparecen rayadas**: cuentan para decidir, pero
todavía no son un hecho.

**Pinchando en una banda** se abre la ausencia, y si está pendiente se puede
aprobar o rechazar ahí mismo.

---

## 9. Departamentos

`slug: ott.departamentos`

Agrupan a la gente para el cuadrante y los informes. Un departamento con gente
asignada no se puede eliminar: primero hay que moverla.

---

## 10. Turnos y cuadrante

`slug: ott.cuadrante`

**Turnos** define las formas de jornada: nombre, tramos horarios y color.
**Cuadrante** las pinta sobre el calendario.

Para asignar: **Asignar turno**, elige el turno, escribe para buscar a las
personas, el rango de fechas y los días de la semana.

**El cuadrante no es el registro.** Es lo previsto; lo fichado se guarda aparte
y es lo que vale como prueba.

Debajo aparecen los avisos: dónde el cuadrante se aparta de las reglas
configuradas, con el artículo del que sale cada una. **Ninguno bloquea.** El RD
1561/1995 modifica varias reglas en sectores concretos, y un sistema que se
negara a guardar sería inservible en transporte o en guardias; avisa y decide
la empresa.

**Vaciar el mes** borra los turnos del mes de todo el mundo. Pide confirmación
diciendo cuántos turnos y de cuántas personas. No se puede deshacer. Los
fichajes no se tocan.

---

## 11. Fichajes de la plantilla

`slug: ott.fichajes`

El registro tal y como está guardado, con filtros de persona y fechas. Por
defecto, el mes en curso.

Abajo verás cuántos hay en total: **«1–50 de 90 fichajes»**. Si hay más de una
página, se navega con el paginador. El total sale también cuando cabe en una
sola.

Un fichaje anulado sigue apareciendo, tachado. **No se borra nada.** Un informe
que ocultara las correcciones no serviría de prueba.

**Corregir** en cualquier fila abre la corrección. Si el fichaje es de otra
persona, no se aplica sola: pasa a esperar su conformidad (ver
[Por decidir](#12-por-decidir)).

---

## 12. Por decidir

`slug: ott.por-decidir`

Tres pestañas con el número de pendientes en cada una.

**Ausencias.** Aprobar es un clic; rechazar abre un cuadro para el motivo. La
asimetría es deliberada: un rechazo es lo que la persona va a leer y preguntar,
y no debería costar lo mismo que un sí.

**Fichajes.** Correcciones que ha pedido la propia persona. Se aprueban o se
rechazan con motivo.

**Sin acuerdo.** Cambios que ha propuesto la empresa sobre el registro de otra
persona y que esperan su autorización (art. 4.b). Primero los que ya han
contestado.

- **No está de acuerdo** / **Sin contestar todavía** en el distintivo.
- Si discrepó, se ve su versión.
- Si no hay representación legal registrada, aparece dicho: el artículo obliga
  a informarla.
- **Aplicar sin acuerdo** lo aplica dejando constancia. Dice antes qué va a
  constar.
- **Retirar la propuesta** la cancela.

> **Nadie resuelve su propio caso.** Un responsable no puede aprobar una
> corrección sobre su propio registro ni sus propias vacaciones: tiene que
> hacerlo otra persona. La única excepción es una empresa con un solo
> administrador, donde no hay segunda persona; entonces se aplica y **queda
> escrito en la resolución** que se resolvió en solitario.

---

## 13. Informes para la Inspección

`slug: ott.informes`

El documento que se entrega. **De quién**: una persona, un departamento o toda
la empresa.

| Formato | Qué sale |
|---|---|
| PDF, una persona | Un documento |
| PDF, varias | Un zip con un PDF por persona |
| CSV, varias | Un fichero con todo el mundo |

Cada PDF lleva su propia huella SHA-256, por eso no se funden en uno.

La huella permite comprobar que el documento no se ha alterado después de
descargarlo. **No acredita por sí sola que el registro nunca se tocara**: para
eso harían falta garantías adicionales.

Máximo 200 personas por petición. Por encima, acota por departamento.

Exportar el registro de otra persona deja entrada en la auditoría, con su
nombre. Una sola entrada que dijera «se exportó la empresa» no diría de quién,
que es justo lo que la traza sirve para responder.

### El resumen para la nómina

El art. 6.1 obliga a entregar un resumen junto al recibo de salarios. **El
periodo lo fija el ciclo de pago de la empresa**, no esta pantalla: el artículo
lo ata al «periodo fijado para el abono», y dejar elegir fechas produciría
resúmenes que no cuadran con ninguna nómina. Se indica un día cualquiera dentro
del periodo y el sistema deduce cuál es.

**Generar los de toda la plantilla** los produce de una vez, que es como ocurre
la nómina. Al terminar dice cuántos salieron y **quién se queda fuera por no
tener horas en el periodo**: es la pregunta que se hace quien cierra la nómina,
así que se dice en vez de callarla. Un resumen de ceros invitaría a preguntar si
falló el registro o si la persona no trabajó.

---

## 14. Aplicaciones y terminales

`slug: ott.aplicaciones`

Solo administración. Para cuando quien ficha no puede hacerlo con su propia
sesión: un terminal en la entrada, un lector NFC, una tableta compartida en
obra.

1. **Autorizar**, nombre y para qué es.
2. **Qué puede hacer**: los permisos se conceden uno a uno. Una aplicación con
   todos es una llave a la empresa entera.
3. **Emitir token.** Sale una vez y no se puede recuperar: se guarda cifrado.
   Si se pierde, se emite otro.

El token va en la cabecera `Authorization: Bearer …` de cada petición.

**Se pueden tener varios tokens a la vez**, y es lo que permite cambiarlos sin
cortar el servicio: emites el nuevo, lo pones en el terminal, revocas el viejo.

Lo que registre una aplicación va marcado como **En su nombre** o **Terminal**,
nunca como si lo hubiera hecho la persona. Son pruebas distintas y quien lea el
registro tiene derecho a distinguirlas.

**Revocar no borra.** La aplicación deja de funcionar con todos sus tokens,
pero sigue en la lista: lo que grabó es suyo, y quitarla dejaría esos fichajes
sin autor.

---

## 15. Ajustes de la empresa

`slug: ott.ajustes`

**Identificación.** El CIF no se puede cambiar: identifica a la empresa en cada
informe ya emitido.

**Zona horaria e idioma.** Las horas se guardan siempre en UTC; la zona solo
decide cómo se muestran. Cada persona puede usar otro idioma.

**Vacaciones.** Días al año y mes en que empieza el periodo de cómputo. **Estos
valores salen del convenio**: el sistema no los conoce, los aplica.

**Reglas de jornada.** Con qué se compara el cuadrante. Cada valor lleva el
artículo del que sale y **ninguno bloquea**.

Una en particular: **el descanso computa como trabajo efectivo** está apagado
por defecto, porque el art. 34.4 del Estatuto solo lo cuenta como trabajo
cuando lo dice el convenio. El convenio de jardinería sí lo dice. Con el valor
por defecto, una empresa de ese sector registraría unos quince minutos de menos
al día por persona: unas 55 horas al año.

Los valores del convenio se pueden cargar desde una ficha; ver
`agreements/README.md`.

---

# Conceptos

## Qué no se puede hacer, y por qué

`slug: ott.limites`

Cosas que el sistema rechaza a propósito. Están aquí porque en el momento
parecen fallos.

| No se puede | Por qué |
|---|---|
| Poner la hora de un fichaje | La pone el servidor. Si el cliente pudiera elegirla, el registro dejaría de probar cuándo pasaron las cosas |
| Fichar por otra persona desde la web | Existe una vía aparte para terminales y lectores, y lo que entra por ahí va marcado como tal |
| Editar o borrar un fichaje | El registro solo admite añadir. Un cambio se hace con una corrección, que exige motivo y deja autor |
| Aprobar tu propia corrección | Tiene que pasar por una segunda persona. Excepción: administrador único, y entonces consta |
| Adjuntar el parte médico de una baja | Desde el RD 1060/2022 no se entrega a la empresa |
| Subir cualquier fichero como justificante | Solo PDF o imagen, hasta 10 MB |
| Borrar algo de la auditoría | Lo impide la base de datos, también para la administración |
| Quedarse sin ningún administrador | Una empresa así no se puede reparar desde dentro |

## Glosario

`slug: ott.glosario`

**Fichaje.** Un evento: una entrada o una salida, con su hora y su origen.

**Origen.** Cómo llegó al sistema: Web, Móvil, App externa, En su nombre,
Terminal, Corrección, Importado. Los dos que no hizo la persona van
destacados.

**Corrección.** El procedimiento para cambiar el registro. Nunca sobrescribe:
anula y sustituye, dejando lo anterior legible.

**Aplicada sin acuerdo.** Un cambio que la empresa aplicó sin la conformidad de
la persona, con la versión de esta registrada al lado (art. 4.b).

**Huella.** El SHA-256 de un informe. Sirve para comprobar que el documento no
cambió después de emitirse.

**Ficha de convenio.** Un fichero con los parámetros de tiempo de trabajo de un
convenio y el artículo del que sale cada cifra.

---

# Para montar el tour

Anclas que hará falta poner en el frontend. La convención es la de Geosian:
`data-tour="…"` en el elemento, y el recorrido se referencia por su `slug`.

| slug | Pasos y su ancla |
|---|---|
| `ott.fichar` | `clock-button`, `clock-today`, `clock-server-time` |
| `ott.mi-jornada` | `mytime-month-nav`, `mytime-day-card`, `mytime-ask-correction` |
| `ott.cambio-propuesto` | `mytime-proposed-panel`, `mytime-accept`, `mytime-dispute` |
| `ott.mis-ausencias` | `leave-balance`, `leave-request`, `leave-justification` |
| `ott.alta-persona` | `people-add`, `person-basics`, `person-contract`, `person-birthdate`, `person-representative`, `people-row-menu` |
| `ott.cuadrante` | `roster-assign`, `roster-grid`, `roster-findings`, `roster-clear-month` |
| `ott.fichajes` | `timesheet-filters`, `timesheet-pager`, `timesheet-correct` |
| `ott.por-decidir` | `decisions-tabs`, `decisions-disagreement-tab`, `decisions-apply-anyway` |
| `ott.informes` | `reports-scope`, `reports-range`, `reports-download`, `reports-fingerprint`, `reports-payroll` |
| `ott.calendario` | `calendar-month-nav`, `calendar-legend`, `calendar-span`, `calendar-pending-hatch` |
| `ott.aplicaciones` | `apps-authorise`, `apps-scopes`, `apps-issue`, `apps-token-once`, `apps-revoke` |
| `ott.ajustes` | `settings-timezone`, `settings-leave`, `settings-rules`, `settings-break-counts` |

Dos notas para quien lo monte:

- **`ott.cambio-propuesto` solo tiene sentido si hay uno.** El panel no existe
  cuando no hay nada esperando respuesta, y un tour que apunta a un elemento
  ausente se cae. En Geosian eso se resuelve con la detección de panel cerrado;
  aquí hará falta lo mismo, o marcar el tour como condicional.
- **Los pasos de gestión no aplican a una persona trabajadora.** El menú ya los
  oculta, así que el tour debería filtrarse por perfil antes de ofrecerse.
