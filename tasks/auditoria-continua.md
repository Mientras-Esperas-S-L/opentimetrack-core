# Auditoría continua — cuaderno

Vueltas dadas: 80 · Vueltas seguidas sin hallazgos: 0

**Parada el 14/08/2026, retomada el 25/08/2026.**

*Los trece hallazgos de la prueba de convergencia están cerrados* (vueltas 43 a
55), más los dos de aislamiento que se arreglaron el mismo 14/08. La lista de
«pendiente de arreglar» está vacía desde la vuelta 55.

**Y sigue sin converger, que es lo que importa.** Desde entonces se han probado
**ocho lentes nuevas y siete han dado hallazgos**: la empresa recién creada (56),
el administrador único (57), la persona dada de baja (58), los formularios
reabiertos (59), el manual contrastado contra el producto (60), el esquema de la
puerta de integración (61) y el coste en consultas de esa puerta (62), que es la
única que no encontró un defecto --- solo un hueco de vigilancia.

El criterio propuesto ---cinco lentes seguidas sin nada alto ni medio--- volvió
a cero en la vuelta 64, que encontró una inyección de fórmulas en el CSV que se
entrega. La lección de la vuelta 42 se repite: la etiqueta «limpia» de las 35
áreas mide qué lentes se pasaron, no la salud del código.

Las tres últimas vueltas han ido por las **tres piezas que salen del sistema**
---CSV (64), nombre de fichero (65) y PDF (66)--- y las tres han encontrado algo.
La 66 además encontró un defecto **debajo de un arreglo anterior**: la vuelta 39
hizo que la discrepancia del art. 4.b llegara al informe, y hasta ahora se
imprimía fuera de la hoja. La prueba de la 39 pasaba porque preguntaba si el
texto estaba en el fichero, no si caía dentro de la página.

El 14/08 Francisco cerró las cinco decisiones que estaban esperándole. Cuatro
están hechas y la quinta ---la capa de i18n del frontend--- está en marcha.

El estado de cada área no es una opinión: «limpia» significa que se ejercitó
entera en una pasada y no salió nada. Mientras quede una «sin tocar», no se
vuelve a una limpia.

## Áreas

### Pantallas

| Área | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Fichar (`/`) | limpia | 13/08 v1 | **doble pulsación = jornada en cero** |
| Resumen (`/panel`) | limpia | 13/08 v2 | **decía 2 de 57 esperando decisión** |
| Mi jornada (`/mi-jornada`) | limpia | 14/08 v16 | **«la hora no es la real» fallaba siempre**; descarga del propio registro (v10) |
| Mis ausencias (`/mis-ausencias`) | limpia | 14/08 v17 | **el justificante no se podía adjuntar nunca**, y el diálogo prometía que sí |
| Personas | limpia | 13/08 | filtros, selección múltiple, `?department=` roto |
| Departamentos | limpia | 13/08 | miembros desde el diálogo |
| Centros | limpia | 13/08 | zona horaria de texto libre |
| Calendario del equipo | limpia | 13/08 | filtros; cuatro manos |
| Cuadrante | limpia | 13/08 | formulario no enviable; días vacíos = todos |
| Turnos | limpia | 13/08 | — |
| Permisos (`/panel/permisos`) | limpia | 14/08 v23 | **no existía**: el catálogo no se podía editar desde ninguna pantalla |
| Fichajes | limpia | 13/08 | filtros de tipo y origen |
| Por decidir | limpia | 13/08 v2 | resolver en bloque; **contadores truncados a 50** |
| Informes | limpia | 13/08 | zip con nombre de PDF; CSV con CRLF |
| Aplicaciones | limpia | 13/08 | — |
| Ajustes | limpia | 13/08 | límites legales sin aviso; cambios sin guardar |
| Registro de actividad | limpia | 14/08 v42 | IP de un compañero; **6 escrituras sin rastro**, entre ellas vaciar el cuadrante |
| Entrar / recuperar contraseña | limpia | 13/08 v3 | **el aviso de demasiados intentos, traducido a máquina** |

### API sin pantalla

| Área | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Fichaje delegado (terminal, lector) | limpia | 13/08 v4 | **evidencia sin tope de tamaño** |
| `applications/people` (integración Geosian) | limpia | 13/08 v5 | **lectura truncada a 500 en silencio**; el cursor se rompía con el `+` del huso |
| `applications/attendance` | limpia | 13/08 v6 | **el día salía del reloj del contenedor, no de la empresa** |
| Avisos push y correo | limpia | 13/08 v7 | — en el área; salió **una plural sin traducir que se veía en blanco** |
| Importación de datos (festivos) | limpia | 13/08 v9 | **solo leía un país**; no comprobaba el fichero; el resumen contaba días que no escribía |

### Ley

| Punto | Estado | Última pasada | Hallazgos |
|---|---|---|---|
| Art. 34.9 — registro objetivo, fiable, conservado | limpia | 13/08 v10 | **el informe de empresa borraba a quien se fue**; nadie podía descargar el suyo desde la interfaz |
| Art. 34.2 — distribución irregular | limpia | 13/08 v12 | **el preaviso de 5 días no lo leía nadie**; el 10 % anual, descartado a propósito |
| Art. 34.3/34.4 — jornada, descansos | limpia | 13/08 | avisos con cita |
| Art. 35 — horas extra y su tope | limpia | 13/08 | — |
| Art. 36 — nocturno y turnos | limpia | 14/08 v15 | **el turno de noche no cerraba la jornada**; el veto de horas extra del 36.1 no se comprobaba |
| Art. 37.1/37.2 — descanso semanal y festivos | limpia | 13/08 | — |
| Art. 37.3 — permisos retribuidos | limpia | 13/08 v11 | **una empresa nueva se quedaba sin un solo permiso**; el catálogo cuadra con el articulado |
| Art. 38 — vacaciones y recuperación | limpia | 13/08 | — |
| Art. 4.b — consentimiento de las dos partes | limpia | 13/08 | — |
| Constancia de la consulta a la RLT | limpia | 14/08 v13 | **no había dónde declararlo**; ahora consta la vía, cuál, desde cuándo y la consulta |
| Calendario con dos meses de antelación (38.3) | limpia | 13/08 v9 | **estaba solo citado**; ahora se avisa, y solo cuando las pone la empresa |
| RGPD / art. 88 LOPDGDD | limpia | 14/08 v14 | **una empresa de baja guardaba las IP para siempre**; y el rastro había dejado de ser inmutable |

## Prueba de convergencia (14/08/2026) --- NO ha convergido

Seis lentes que las 42 vueltas no habían usado, cada hallazgo pasado por un
escéptico que partía de que era falso. **15 sobrevivieron, 2 fueron refutados,
y ninguna de las seis lentes volvió de vacío.** Diez de gravedad alta.

Lo que mide esto: la etiqueta «limpia» de las 35 áreas dice qué lentes se
pasaron, no la salud del código. Cambiar de lente sigue dando hallazgos graves,
así que el trabajo no está terminado --- está sin empezar por ese lado.

### Arreglado el mismo día

Los dos de aislamiento entre empresas, porque una fuga de datos de un cliente a
otro no se deja para la vuelta siguiente. Los dos eran míos, escritos el 12/08
en la vuelta de cobertura de turnos, y encadenaban: el primero repartía los
identificadores que el segundo necesitaba.

- `apps/shifts/coverage.py` --- el panel de cobertura ofrecía como candidatos a
  la plantilla de **todos los clientes de la plataforma**, con nombre y UUID. Y
  salían marcados viables y ordenados delante, porque los dos bloqueos que
  podrían frenarlos (turnos y ausencias) sí filtran por empresa y para alguien
  de fuera venían vacíos: cuanto más ajena la persona, mejor candidata parecía.
- `apps/shifts/views.py` --- `reassign` aceptaba uno de esos UUID, enlazaba el
  turno y escribía el nombre de esa persona en el rastro append-only de la
  empresa equivocada. Sus vecinas `assign` y `clear` sí llevaban el filtro.

Con sonda permanente en `apps/common/tests/test_nadie_ve_la_empresa_de_al_lado.py`,
que recorre todos los `User.objects` del proyecto y exige `tenant=` o un motivo
escrito. La primera versión de esa sonda tenía la exención por nombre de fichero
(`views.py`) en vez de por ruta, con lo que eximía a `shifts/views.py`: habría
pasado en verde sin ver el fallo que la motivó.

### Pendiente de arreglar --- ninguno

Ordenados por gravedad. Cada uno viene con su escenario reproducido; el detalle
completo (evidencia y refutación) está en el registro del workflow.


## Hallazgos abiertos

- **`record_retention_years` no borra nada.** El ajuste existe, tiene su valor
  por defecto de cuatro años, se valida contra el suelo del art. 34.9 ---no deja
  bajar de cuatro--- se publica en la API y lleva un `help_text` explicando la
  razón legal. Y **no hay ninguna tarea que lo aplique**: los fichajes se
  conservan indefinidamente.

  Su hermano de al lado, `security_metadata_retention_days`, sí tiene su purga
  (`purge_security_metadata`, con su tarea en Celery). La diferencia no parece
  deliberada.

  Conservar de más no incumple el art. 34.9, que fija un mínimo. Choca con el
  art. 5.1.e del RGPD, y eso lo dice el propio `help_text` del campo: «keeping
  data because it might be useful is not a basis».

  **No se ha implementado a propósito**: borrar fichajes es destructivo sobre el
  registro legal, hay que decidir qué pasa con los informes ya emitidos y con las
  correcciones que apuntan a un fichaje borrado, y esa decisión no se toma de
  madrugada. El campo ahora dice en su ayuda que declara la política y no la
  aplica, para que nadie crea que hay una purga en marcha.

- **¿Quien ya no trabaja aquí puede consultar su propio registro?** Hoy no: al
  darle de baja, su sesión deja de valer entera y no puede entrar. Los fichajes
  se conservan cuatro años y salen en el informe que la empresa entrega, así que
  el dato existe --- lo que no hay es forma de que lo mire quien lo generó.

  El art. 34.9 obliga a tener el registro «a disposición de las personas
  trabajadoras» y a conservarlo cuatro años, y no dice «mientras dure la
  relación». Se defiende en los dos sentidos: la empresa custodia el registro y
  puede entregar una copia a quien la pida, que es como funciona todo lo demás
  del expediente laboral. Pero el producto presume de que el registro es un
  derecho de la persona y aquí lo trata como un dato de la empresa.

  **Es decisión de producto, no arreglo.** Preguntarlo antes de tocar nada. El
  manual dice ya lo que pasa hoy (§2), que antes describía otra cosa.

- **Los catálogos de catalán y gallego, con 31 huecos nuevos cada uno.** 460 en
  total. Los dejó la vuelta 43 al vaciar traducciones falsas y al extraer cadenas
  que llevaban tiempo sin recogerse. Van con las ~460 del frontend en el paquete
  del traductor nativo. **El castellano sí está completo**: cero sin traducir.

- **La capa de i18n del frontend: DECIDIDO QUE SÍ (14/08), en marcha.** Las
  cadenas están escritas en castellano dentro del JSX. Con catalán elegido, una
  persona recibe en catalán los correos y los errores de la API, y sigue viendo
  «Fichar» y «Mi jornada» en castellano.

  Medido el 14/08, y es menos de lo que decía esta nota: **~460 cadenas**, no
  más de mil. Son 305 literales entrecomillados, 116 nodos de texto suelto en el
  JSX y 37 plantillas con interpolación, repartidas sobre todo en Ajustes (62),
  Personas (53) y Decisiones (37).

  Dos cosas que condicionan el montaje y ya están comprobadas:

  - MUI trae `caES` pero **no** `glES` ni `euES`. Para gallego hay que dejarle
    `esES`, o sus textos internos ---paginación, tablas--- saldrían en inglés,
    que es exactamente el fallo que ya se cazó en el backend.
  - La resolución del idioma **ya existe y es correcta**: `api.js` calcula
    `user.locale || tenant.language || navigator.language` y la manda en
    `Accept-Language`. Lo que falta no es decidir el idioma, es que las cadenas
    de React lo usen.

  Traducir bien 460 cadenas de prosa cuidada a catalán y gallego es trabajo de
  traductor, no mío. Lo que se entrega es la maquinaria montada de punta a
  punta y el catálogo extraído listo para pasárselo a alguien.

- **Los tres catálogos nuevos piden revisión nativa.** Catalán y gallego están
  completos en los 188 mensajes que llegan a las personas. El euskera va con 148
  y le faltan 35 párrafos largos de derecho laboral, que caen al castellano a
  propósito. La cabecera de cada `.po` lo dice en su idioma.

- **Tres exportaciones del cliente que nadie llama, y son decisiones abiertas.**
  El barrido al revés de la vuelta 18 dejó estas: `signUp` ---no hay pantalla de
  alta de empresa, así que un cliente nuevo solo se da de alta por API---,
  `createLeaveType` y `updateLeaveType` ---el catálogo no se puede editar, que ya
  estaba anotado--- y `getEmployee`, que probablemente sobra. Ninguna es un fallo
  por sí sola; las tres son «¿esto tenía que existir?».

- **Ejecutar las pruebas con ventana de vez en cuando.** El favicon ausente
  llevaba ahí desde siempre con la suite entera en verde: Chrome sin ventana no
  lo pide. Lo mismo puede pasar con tipografías, impresión o consultas de medios.

- **Fichar no ofrece pausa ni modo de trabajo.** El modelo los soporta
  ---`PunchInterval.BREAK`, `work_mode`--- y la pantalla solo tiene un botón.
  Puede ser deliberado (un toque, sin decisiones) pero entonces el descanso del
  art. 34.4 no se puede registrar desde el sitio donde se ficha. **Por decidir,
  no por arreglar**: preguntarlo antes de tocar nada.

  Mirado el `timetrack/` de Geosian el 13/08: **allí tampoco existe**. Su regla
  es «una entrada y una salida por día» y su guía de migración dice literalmente
  que «pausas y ausencias llegarán en OpenTimeTrack, no aquí». Así que no hay
  nada que copiar: el hueco es de OTT desde el principio.

## Cerrado

### Vuelta 80 --- Dos peticiones donde solo cabe una (26/08)

**Lente:** seguir el barrido de concurrencia por los sitios que quedaban, con el
método ya calibrado en la 79 --- doce rondas y **el solape medido**, porque un
verde sin solape no dice nada.

#### Primer hallazgo: dos solicitudes de la misma ausencia

La comprobación de solapamiento lee la cola sin bloquear, así que dos peticiones
simultáneas ven la misma cola y las dos escriben.

| | Rondas con dos solicitudes | Solape real |
|---|---|---|
| Antes | **12 de 12** | 37 ms |
| Después | 0 de 12 | 34 ms |

Y lo que pasa después ya estaba escrito en el docstring de `_overlapping`: «quien
apruebe la segunda crea una contradicción que nadie caza». Si se aprueban las
dos, el saldo de vacaciones se descuenta dos veces y el cuadrante ve el día
doblemente ocupado.

**Arreglo:** `hold()` sobre la persona antes de mirar la cola, la misma pieza que
la vuelta 79 añadió para fichar.

#### Segundo hallazgo, y **sin concurrencia de por medio**

Al comprobar si dos correcciones simultáneas sobre el mismo fichaje se colaban
---12 de 12--- resultó que **dos seguidas también**: 201 y 201. Eso no es una
carrera, es el comportamiento normal, y es deliberado: te deniegan una corrección
y pides otra con mejor motivo.

Lo que no puede pasar es que se apliquen las dos. Y se aplicaban:

| | Fichajes de esa persona |
|---|---|
| Antes | 3: `IN` activo, `IN` activo, `IN` anulado |
| Después | 2: `IN` activo, `IN` anulado |

**Dos entradas activas donde había una.** El registro decía que la persona entró
dos veces sin salir: la jornada no cierra, el cuadrante no cuadra y el informe
que se entrega lleva un asiento que no ocurrió. El motivo era mecánico --- la
segunda aprobación anulaba un fichaje **ya anulado** ---o sea, nada--- y creaba
otro sustituto encima.

**Arreglo:** aprobar exige que el fichaje siga vigente, con 409
`target_already_changed`. La segunda solicitud se queda **pendiente** en vez de
resolverse sola, para que quien la pidió vea qué pasó, y la vía correcta sigue
abierta: pedir una nueva sobre el fichaje tal y como está ahora.

#### Lo que salió limpio

Las correcciones no necesitan bloqueo: que haya dos pendientes sobre el mismo
asiento es correcto, y lo que había que impedir era la aplicación, no la
solicitud. Buscar la carrera llevó al defecto de verdad, que estaba en otro
sitio.

**Pruebas.** `apps/absences/tests/test_dos_solicitudes_a_la_vez.py` (3) y
`apps/punches/tests/test_dos_correcciones_sobre_el_mismo_fichaje.py` (6). Las de
concurrencia, **sin hilos** y por lo mismo que explica
`apps/common/tests/test_dos_a_la_vez.py`: `transaction=True` vacía las tablas con
TRUNCATE y el rastro de auditoría lo rechaza. Se comprueba que el `FOR UPDATE`
sobre la persona va **antes** de leer la cola. **Validadas contra el fallo**:
neutralizado cada arreglo, cae solo lo suyo y los cinco controles aguantan.

**Estado:** áreas «Ausencias» y «Correcciones», limpias con una lente más.
Cerrada con **1057 pruebas de backend y 271 de navegador en verde**, linters
limpios, castellano sin huecos, cero `fuzzy` y sin migraciones pendientes.

### Vuelta 79 --- Dos fichajes en el mismo instante (26/08)

**Lente:** el barrido de transiciones de estado sin bloqueo, siguiendo el método
que rindió en las vueltas 72 y 76.

#### Lo que salió limpio

- Correcciones, ausencias y recuperación de horas usan `claim`, que bloquea la
  fila y exige el estado de partida.
- **Las horas extra a propósito no.** Usan `update_or_create` con
  `UniqueConstraint(employee, day)`: una decisión sobre horas extra no toca los
  fichajes, así que rectificarla es legítimo y el rastro guarda las dos ---
  probado, `OVERTIME_AUTHORISED` y luego `OVERTIME_REJECTED`. La carrera real con
  dos hilos da 200 y 200, una sola fila y coherente. Y
  `apps/common/tests/test_dos_a_la_vez.py` ya lo tenía escrito como decisión
  tomada, así que ni hallazgo ni cambio.

#### El hallazgo: fichar no bloquea nada

`test_double_tap` cubre el doble toque **secuencial**, y su propio docstring
nombra lo que quedaba fuera ---«ni dos pestañas, ni un terminal, ni un
conector»---: todos ésos son **simultáneos**. La protección compara con el último
fichaje leído de la base, sin bloquear, así que dos peticiones a la vez leen el
mismo «último» y las dos pasan.

Medido con dos hilos y una barrera:

| | Rondas con dos fichajes | Solape real |
|---|---|---|
| Antes | **14 de 15** | 35 ms |
| Después | 0 de 15 | 32 ms |

Lo que deja en el registro es lo del doble toque secuencial y peor, porque no se
detecta: una entrada y una salida en el mismo instante, un día de cero segundos
trabajados y la persona en estado «fuera». Deshacerlo exige el procedimiento del
art. 4.b, de uno en uno.

**La primera medición fue de una sola ronda y salió limpia.** Era la ronda
afortunada, la única de quince que no se cuela --- y parecía suficiente para
cerrar la lente como buena.

**Arreglo.** `hold()` en `apps/common/transitions.py`, junto a `claim`: bloquea
una fila cuando no hay estado que exigir. Se bloquea **a la persona**, porque un
fichaje no modifica al anterior y no hay fila de estado que tomar; serializa solo
sus propias pulsaciones y funciona también en el primer fichaje del día.

**Prueba.** `apps/punches/tests/test_dos_fichajes_a_la_vez.py`, y **sin hilos**
por lo mismo que explica `test_dos_a_la_vez.py`: `transaction=True` vacía las
tablas con TRUNCATE en el desmontaje y el rastro de auditoría lo rechaza --- es
uno de los tres disparadores que lo hacen inmutable. Lo que se comprueba es
determinista: que fichar emite un `FOR UPDATE` sobre la persona **antes** de leer
su último fichaje, más el control de que el fichaje sigue saliendo bien y con su
sello. **Validada contra el fallo**: quitado el bloqueo, cae la primera y el
control aguanta.

**Estado:** área «Fichar» limpia, con una lente más. Cerrada con **1048 pruebas
de backend y 271 de navegador en verde**, linters limpios, castellano sin huecos,
cero `fuzzy` y sin migraciones pendientes.

### Vuelta 78 --- El aviso existía y le faltaban los suelos (26/08)

**Lente:** el barrido de salvaguardas que se apagan por configuración, siguiendo
el hilo que la 77 dejó a medias.

**El cuadro completo:** de los **catorce** campos con cita legal, solo **cuatro**
tenían `floor` o `ceiling` declarado. El aviso que añadí en la 77 lee justo esos
dos valores, así que los otros diez pasaban sin que nadie dijera nada. Probados
por API, ocho de ocho aceptados con cero avisos.

Y no era información que hubiera que averiguar: **la nota de cada cita ya la
explica en prosa**, al lado del campo que debía llevarla como número. «Quince
minutos cuando la jornada continuada excede de seis horas.» «Hasta el 30 %, y el
convenio puede subirlo al 60 %.» «Cinco días de preaviso.» «Cuatro años como
mínimo.»

**Arreglo.** Declarados los que la propia nota justifica: `break_minutes` suelo
15, `break_after_hours` techo 6, `complementary_hours_share` techo 60,
`roster_notice_days` suelo 5, `record_retention_years` suelo 4. El mecanismo de
aviso ya existía --- solo le faltaban los datos.

**Y el plazo del art. 4.b, aparte.** Un `correction_consent_days` de cero no es un
plazo corto: es ninguno. La empresa propone y aplica en el mismo segundo, sin dar
ocasión de aceptar ni de discrepar, y pedir el consentimiento sin esperarlo es no
pedirlo. Lleva su propio aviso y **no** un `floor` en el marco: el artículo no
fija plazo, y declararle un número sería atribuirle algo que no dice --- el mismo
error de procedencia que arregló la vuelta 76, en la dirección contraria.

**Lo que no se declara, con su motivo.** Está en el apartado de descartes.

**Un falso positivo mío.** La sonda decía que `record_retention_years = 1` se
aceptaba. Mentira: en su endpoint ---`/api/company/`--- da 400 citando el art.
34.9 y no admite pacto a la baja. Yo lo mandaba a `/api/working-time-rules/`,
donde ese campo no existe y DRF lo ignora devolviendo un 200 limpio. El propio
`test_entrada_malformada` ya tiene escrito ese aviso: «lo que medía era que DRF
ignora lo desconocido».

**Prueba.** `apps/shifts/tests/test_los_suelos_que_no_estaban_declarados.py`,
doce casos: cada suelo avisa con su artículo (cuatro parametrizados); dentro de la
ley no se dice nada (cuatro controles); el plazo de cero días; un plazo normal
que calla; las vacaciones sin suelo a propósito; y la conservación rechazada en
su endpoint, para que quede dicho por qué ese campo no está con los demás.
**Validada contra el fallo**: quitados los cuatro suelos nuevos, caen exactamente
esos cuatro y los ocho controles aguantan.

**Y una prueba mía frágil, cazada al compilar.** Comprobaba «agree» en el mensaje
del aviso, y en cuanto se compilaron los catálogos el mensaje salió en
castellano. Ahora comprueba el campo y el artículo, que es lo que no depende del
idioma.

**Estado:** área «Ajustes» limpia, con una lente más. Cerrada con **1046 pruebas
de backend y 271 de navegador en verde**, linters limpios, castellano sin huecos,
cero `fuzzy` y sin migraciones pendientes.

### Vuelta 77 --- Un cero que apaga una salvaguarda (26/08)

**Lente de partida:** los truncados silenciosos. Se agotó rápido y sin hallazgo:
los `[:300]` y `[:160]` coinciden exactamente con el `max_length` de su campo, y
la discrepancia completa vive en `PunchCorrection.employee_dissent` y viaja al
informe --- lo que se corta es el extracto del rastro, no el documento.

De ahí salió otro hilo, también sin hallazgo: el frontend no pone ningún
`maxLength`, así que se puede escribir una discrepancia de 1562 caracteres y
recibir el 400 al enviar. Pero el mensaje es claro ---«no tenga más de 1000
caracteres»--- está traducido, y `ErrorNote` pinta el detalle por campo desde el
13/08. Es una mejora de usabilidad, no un defecto, y decirlo así es más honesto
que forzarlo.

#### El hallazgo, por el otro extremo: valores absurdos que sí se aceptan

`test_entrada_malformada` cubre que nada devuelva un 500 con basura. No cubre que
un valor **del tipo correcto y fuera de toda razón** se acepte. Probado:

| | Respuesta |
|---|---|
| Horas contratadas 999999, y 0 | 400, validado |
| Jornada semanal de 200 h, y de 0 | **200, guardado** |
| Descanso entre jornadas de 0 h | **200, guardado** |
| Plazo de consentimiento de 0 días | **200, guardado** |

Y lo que importa no es el número: **es lo que apaga**. Con el suelo de descanso
en doce horas, un cuadrante con ocho horas produce `short_daily_rest`; con el
suelo a cero, ese aviso **desaparece**. Una salvaguarda del art. 34.3 se
desactiva escribiendo un número.

**Lo que ya estaba bien**, y hay bastante: el cambio deja rastro `RULES_CHANGED`
con `{'daily_rest_hours': [12, 0]}` y con quién; la pantalla de ajustes avisa en
amarillo porque tiene las `citations` con su `floor`; y la validación de fichas
de convenio también avisa. El hueco era **la API**: por ahí entran los
conectores y los scripts de migración, y no recibían ninguna señal.

**Arreglo, sin impedir.** La respuesta del PATCH lleva `warnings` con el campo,
el artículo y el mensaje, y la cifra del límite sale del marco del país --- no del
código, por lo mismo que explica `Citation`. No se bloquea: el RD 1561/1995 baja
algunos de estos suelos para sectores concretos, así que un valor por debajo
puede ser correcto y quien lo sabe es la empresa. La validación de fichas hace
exactamente esto con `fatal=False`.

Y en el rastro: «12 → 0» no dice por sí solo que ese cero esté bajo un mínimo
legal, y quien lo lea dentro de dos años no tiene por qué saberse el artículo.
Ahora la nota lo dice.

**Un falso «está bien» que casi cuela.** La primera medición dijo que el cero
**no** apagaba el aviso. Era la caché: `WorkingTimeRules.for_company` recuerda
las reglas en el objeto `Tenant` mientras dure la petición ---está escrito en su
propio comentario--- y mi sonda reutilizaba la misma instancia después del PATCH.
Recargando la empresa, el aviso desaparece.

**Prueba.** `apps/shifts/tests/test_un_cero_apaga_una_salvaguarda.py`, seis
casos: el cuadrante avisa con el suelo legal ---el control---; un cero apaga el
aviso y la API lo dice; el rastro dice por qué ese número importa; un valor
dentro de la ley no avisa de nada ---un aviso que sale siempre no lo lee
nadie---; solo se avisa de lo que acaba de cambiar; y el descanso semanal lleva
su propio artículo, para que no sea una regla escrita para un solo campo.
**Validada contra el fallo**: neutralizado el cálculo, caen tres y los tres
controles aguantan.

**Estado:** área «Ajustes» limpia, con una lente más. Cerrada con **1034 pruebas
de backend y 271 de navegador en verde**, linters limpios, castellano sin huecos,
cero `fuzzy` y sin migraciones pendientes.

### Vuelta 76 --- La cifra del convenio citando el Estatuto (26/08)

**Lente:** el barrido **sistemático** de piezas hechas y desconectadas. Esa
pregunta ---«¿existe la llamada?»--- había rendido por casualidad en las vueltas
68, 74 y 75, así que esta vez se hizo entero, con un script que recorre el árbol
de sintaxis y busca métodos públicos sin uso fuera de su propio fichero.

**La primera pasada dio treinta candidatos, y eran ruido**: los `@action` de los
ViewSet los llama el enrutador, las propiedades se usan sin paréntesis, los
filtros los conduce django-filter. «Muchos fallos a la vez no son muchos
fallos.» Refinado ---excluyendo decoradores del framework y clases que este
conduce, y buscando el uso con y sin paréntesis--- quedaron **diez**, y de esos,
tres que no eran del framework: `Ficha.basis_for`, `Ficha.note_for` y
`LegalFramework.citation`.

#### Lo que salió limpio

- `LegalFramework.citation(key)` no se llama, pero **la información sí viaja**:
  el endpoint de reglas construye el diccionario `citations` directamente y el
  frontend lo pinta campo por campo con `legalField`. Es un método de
  conveniencia sin usar, no funcionalidad perdida.
- `finding_citation` sí está conectado: los avisos del cuadrante reciben su
  artículo.

#### El hallazgo: `basis_for` y `note_for`

`apply_to_rules` copiaba los **valores** de una ficha de convenio a las reglas de
la empresa y **descartaba el artículo y la nota** de cada uno. Medido con la
ficha de jardinería, que está en el repositorio:

| | El convenio dice | La pantalla decía |
|---|---|---|
| Descanso entre jornadas | 12 h, **Art. 16** | 12 h, Art. 34.3 ET |
| Descanso en jornada continuada | 15 min, **Art. 16** | 15 min, Art. 34.4 ET |

La cifra coincide y el problema no es la cifra: es la **procedencia**. Cuando el
convenio se renueve, nadie sabrá que ese valor venía de él; y ante una
inspección, la empresa tiene que poder decir qué norma aplica, no una parecida.
La `note` del YAML ---donde la asesoría deja la cita textual y el razonamiento de
la conversión--- no se veía en ninguna parte, y el docstring de
`WorkingTimeRules` prometía «la cifra con el artículo del que viene».

**Arreglo.** Campo `from_agreement` en las reglas con la procedencia por campo, y
el endpoint fusiona: **la cita del convenio gana** sobre la del marco del país, y
se conserva `framework_basis` y el suelo legal para no perder la referencia
---ningún convenio puede bajarlo, así que sigue sirviendo para avisar---. El
frontend no se toca: `cite()` ya junta `basis` y `note`.

**El detalle que casi se cuela.** La primera versión anotaba la procedencia solo
de los campos que **cambiaban** de valor, y jardinería confirma lo que ya decía
el Estatuto: los doce campos que interesan quedaban fuera. Salió al medir, no al
razonar. Ahora se anota siempre que la ficha declare el artículo.

**Y el guard de entradas malformadas hizo su trabajo**: `from_agreement` salió
escribible por defecto y contestaba un 500 a cualquier basura.
`test_ningun_campo_de_la_api_contesta_un_500` lo cazó en la misma tanda. De solo
lectura: lo pone la ficha, y dejarlo escribible permitiría declarar que un número
viene de un artículo que nadie ha comprobado.

**Prueba.**
`apps/tenants/tests/test_la_cifra_del_convenio_dice_de_donde_sale.py`, seis
casos: sin convenio manda el marco ---el control---; con el convenio aplicado la
cita es la suya; se anota aunque el valor no cambie; lo que el convenio no fija
sigue citando la ley; la nota de la asesoría llega a la pantalla; y el suelo del
país no se pierde. **Validada contra el fallo**: neutralizado el registro, caen
cuatro y los dos controles aguantan.

**Estado:** área «Convenios» limpia, con una lente más. Cerrada con **1028
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos, cero `fuzzy` y sin migraciones pendientes.

### Vuelta 75 --- Un sello que nadie mira (26/08)

**Lente:** la integridad del registro, siguiendo la pregunta que rindió en la
74: hay un campo que promete algo, ¿existe la llamada que lo cumple?

Cada fichaje guarda un `hash_integrity` desde el principio, `verify_hash`
funciona y detecta un cambio en la hora, en el tipo o en el origen. **No había
una sola llamada desde el producto**: el método solo aparecía en las pruebas.

#### Lo que sí estaba bien

- El **rastro de auditoría** es append-only a nivel de base de datos, con tres
  triggers, un comando que los repone y `/api/health/` devolviendo 503 si
  faltan. Esa parte está mejor cuidada que en la mayoría de los productos.
- La **huella del informe** hace lo suyo: certifica que el papel entregado es el
  que se generó, y excluye la hora de generación para que dos copias del mismo
  periodo se puedan comparar.

#### El hallazgo, medido

Adelantando dos horas un fichaje por SQL directo ---la API no deja editar uno:
una corrección crea otro y anula el viejo, así que manipularlo de verdad exige
entrar por debajo---:

| | Antes | Después |
|---|---|---|
| Horas en el informe | 8,0 | **10,0** |
| El sello del fichaje cuadra | sí | **no** |
| El informe se genera | sí | **sí, sin una queja** |

La huella del documento no cubre esto: certifica el papel, no que lo generado
refleje lo que se fichó. Con el fichaje alterado, el informe sale con huella
perfectamente válida y dos horas que nadie trabajó. **La pieza que detecta el
fraude estaba hecha, probada y desconectada.**

**Arreglo.** `build_report` comprueba el sello de cada fichaje del periodo. Es el
momento en que el registro sale del sistema como prueba, y sale gratis: los
fichajes ya están cargados y es un sha256 por fila ---con su prueba de que no
añade consultas---.

**Y se dice, no se enmienda.** La cifra sigue siendo la del registro y la
jornada sigue en el informe: corregirla por nuestra cuenta sería inventar un
dato distinto del que hay, y quien recibe el documento necesita ver el registro
tal como está para poder actuar. El aviso entra por `row.incidents`, así que
viaja al PDF y al CSV por el mismo sitio que la discrepancia del art. 4.b.

**Prueba.** `apps/reports/tests/test_el_sello_del_registro_se_comprueba.py`, seis
casos: un día intacto no dice nada ---el control---; uno tocado por debajo sale
avisado; el aviso viaja a lo que se entrega; la huella cambia cuando aparece el
aviso; la cifra no se toca; y comprobarlo no cuesta consultas.

**Una prueba mía pasaba con el fallo delante.** La de la huella alteraba la hora,
y la huella cambia por eso aunque el aviso esté desconectado. Reescrita tocando
el **origen**, que rompe el sello del fichaje y no entra en la huella del
documento: así la única diferencia entre las dos huellas es el aviso. Salió al
validar contra el fallo, que es exactamente para lo que sirve ese paso.

**Estado:** área «Informes» limpia, con una lente más. Cerrada con **1022
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos, cero `fuzzy` y sin migraciones pendientes.

### Vuelta 74 --- Anotar que se informó no es informar (26/08)

**Lente:** el correo que sale. Cuatro plantillas, y nunca se había mirado qué
lleva, a quién y qué delata.

#### Lo que salió limpio

- **Los asuntos no llevan datos.** «Restablecer tu contraseña en X», «Tu
  registro de jornada ha cambiado». Nada de nombres ni de horas en lo que se ve
  en la pantalla de bloqueo de un móvil.
- **El «he olvidado la contraseña» no delata quién tiene cuenta**: 204 tanto si
  la dirección existe como si no, y también para alguien dado de baja. El 400
  solo aparece con una cadena que no es un correo, que no dice nada de nadie.
- **La inyección de cabeceras se rechaza**: `existe@…\nBcc: espia@…` da 400.
- **Límite de tasa de 5/min** en esa ruta.

**Y un falso hallazgo mío, con moraleja.** La primera medición dio **142 ms**
cuando la dirección existía y **2 ms** cuando no: un canal temporal de libro.
Repitiendo con una llamada de calentamiento antes y la cubeta del límite vaciada
entre medidas, la diferencia real es **2 ms contra 1**. Los 142 eran la primera
petición del proceso cargando plantillas y conexiones.

#### El hallazgo: la representación legal no recibía nada

`_inform_representatives` guardaba la hora y una nota con nombre y apellidos
---«Informados: Fulana»--- y **no enviaba ningún correo**. Ese texto viaja al
informe de inspección, y el `help_text` que la empresa lee al marcar la casilla
promete «informado cuando alguien discrepa de un cambio en su registro (art.
4.b)».

Medido en el flujo real, con control para que el cero significara algo:

| Paso | Correos | A quién |
|---|---|---|
| La empresa propone el cambio | 1 | la persona |
| **La persona discrepa** | **0** | --- |
| La empresa lo aplica sin acuerdo | 1 | la persona |

Es el «solo citado» en su forma peor: hay campo, hay marca de tiempo, hay nombre
propio y viaja al documento. Todo parece cubierto y nadie recibió nada.

**Arreglo.** `_mail_the_representatives`, con plantilla propia y el mismo
`fail_silently` que el aviso a la persona --- que no salga un correo no puede
tumbar la discrepancia, que es justo lo que el artículo protege.

**Qué se manda y qué no.** Que hay una discrepancia, de quién y de qué día. El
texto que la persona escribió **no** se reproduce: puede contar por qué faltó a
una hora ---en la prueba, que estuvo en el médico--- y eso es suyo. Quien recibe
el aviso tiene acceso al registro por el art. 6.2 y puede consultarlo, que es la
diferencia entre informar y difundir.

**Prueba.** `apps/punches/tests/test_a_los_representantes_se_les_avisa.py`, cinco
casos: el representante recibe el aviso; no se le reenvía lo que la persona
escribió; sin representantes se anota el hueco y no se manda nada; la persona
sigue recibiendo lo suyo ---el control, porque sin él un cero no dice nada---; y
que falle el correo no tumba la discrepancia. **Validada contra el fallo**:
quitado el envío, caen exactamente las dos primeras.

**Las traducciones, otra vez.** `makemessages` prestó traducciones a las dos
cadenas nuevas: el asunto del aviso salía como «un cambio en el registro de
jornada». Corregidas en castellano; en catalán y gallego se **vació** la
prestada en vez de dejarla sin la marca `fuzzy`, porque una traducción
equivocada sin marca es peor que un hueco.

**Estado:** área «Avisos» limpia, con una lente más. Cerrada con **1016 pruebas
de backend y 271 de navegador en verde**, linters limpios, castellano sin huecos,
cero `fuzzy` y sin migraciones pendientes.

### Vuelta 73 --- Reorganizar no es repartir permisos (26/08)

**Lente:** qué se lleva por delante un borrado. El registro vive cuatro años y
no puede perderse porque alguien retire un departamento o un centro.

#### El registro aguanta todo lo que la API ofrece

Probado sobre datos reales, con tres fichajes de por medio:

| Borrado | Respuesta | Fichajes |
|---|---|---|
| Departamento donde trabaja | 204, su `department` a `None` | intactos |
| Centro de trabajo con gente | 409 `workplace_in_use` | intactos |
| Baja de la persona | 200, `is_active=False` | intactos |
| La empresa entera | 404 --- esa puerta no existe | intactos |

`Punch.employee` es `PROTECT` y dar de baja **desactiva** en vez de borrar. Por
ese lado no hay nada que arreglar.

#### El hallazgo: el borrado no pierde datos, reparte permisos

`visible_people` estrecha a un responsable a los departamentos que le pusieron
al mando, y lee «al mando de nada» como «nada le estrecha». Es deliberado y está
razonado: la alternativa dejaría a un responsable sin ver a nadie el día del
alta.

Retirar el único departamento que alguien dirigía lo deja en ese mismo estado
por otro camino, y ahí el efecto es el contrario del prudente. Medido sobre una
empresa viva:

| | Antes | Después de retirar su departamento |
|---|---|---|
| Alcance | 2 personas | **todas** |
| Personas que ve | 2 | 4 |
| Fichajes que ve | 1 | 2 |
| Justificante de otro departamento | 404 | **200** |

Ese justificante puede ser un parte médico ---art. 9 del RGPD--- de alguien de
quien nunca respondió. **Nadie tocó sus permisos**, y el rastro de auditoría
dice «departamento borrado», no «pasa a leer toda la empresa».

**Por qué era fácil pasarlo por alto.** Para la gente **del** departamento,
perderlo es ordenado: conservan todo y pierden una etiqueta. Para quien
**responde** de él es lo contrario. El comentario de `WorkplaceViewSet` dice
exactamente eso ---que para un departamento `SET_NULL` «es una respuesta
ordenada»--- pensando en los miembros.

**Arreglo.** `DepartmentViewSet.perform_destroy` lo rechaza mientras alguien
responda de él, con el mismo patrón que ya usaba el centro de trabajo: 409
`department_has_managers` y un mensaje que dice qué hacer. La vía correcta
---mover primero a los responsables--- sigue abierta y es una decisión que
alguien toma a propósito y que deja su propio rastro.

**Prueba.** `apps/users/tests/test_retirar_un_departamento_no_amplia_a_nadie.py`,
seis casos: no se retira uno que alguien dirige; su alcance sigue siendo el suyo
---dicho en lo que puede leer, incluido el justificante ajeno en 404---; uno sin
responsables se retira sin problema; tener miembros no lo bloquea, porque ahí
`SET_NULL` sí vale; la vía correcta sigue abierta; y una responsable dada de baja
no bloquea nada, porque ya no lee. **Validada contra el fallo**: neutralizada la
comprobación, caen exactamente las dos primeras y los cuatro controles aguantan.

**Y la trampa de siempre con las traducciones.** `makemessages` rellenó la
cadena nueva copiando la del centro de trabajo por parecido y la marcó `fuzzy`:
el mensaje del departamento decía «sin centro pierden sus festivos locales».
Corregida a mano, y los tres catálogos vuelven a cero `fuzzy`.

#### Lo que arrastró en el frontend

La suite de navegador dio un rojo en `/panel/departamentos`, y detrás había dos
cosas del producto:

- **La pantalla ofrecía un borrado que el servidor va a rechazar.** El botón
  aparecía con `people_count === 0`, que cuenta quién está **dentro** y no quién
  **responde**: un departamento sin gente y con jefa mostraba «Eliminar» y un
  texto que prometía que no afectaba a nadie. Ahora exige las dos condiciones, y
  el texto lo dice.
- **Siete botones «Eliminar» sonaban igual** con lector de pantalla. `aria-label`
  con el nombre del departamento, como se hizo con «Revocar» en la vuelta 67.

Y una prueba que probaba lo contrario de lo que ahora es correcto: la 11 se
llamaba «alta con responsable, y no se borra si tiene gente» y comprobaba que
**sí** se borraba teniendo responsable. Reescrita: mientras lo tenga no se
ofrece, y tras retirarle el mando se borra. Es la lección 115 otra vez --- la
prueba tomaba el mismo atajo que el arreglo cierra.

De paso, la demo tenía tres departamentos de pruebas viejas (`Colado …`,
`Depto p…`), todos sin gente dentro. Retirados; quedan los cuatro reales.

**Estado:** área «Organización» limpia, con una lente más. Cerrada con **1011
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos, cero `fuzzy` y sin migraciones pendientes.

### Vuelta 72 --- No cambiar nada también es decidir (26/08)

**Lente de partida:** las demás entradas de fichero, después de lo de la 71.
Duró un `grep`: en todo el producto hay **una sola** ---el justificante--- y ya
estaba cubierta. Sin material, cambio de eje a la separación de las cuatro
manos, que el guion nombra expresamente.

#### Lo que salió limpio

Ejercitado por la API, con sesiones de verdad y sin montar estados a mano:

- Quien pide una corrección **no la aprueba**: 409 `cannot_decide_your_own`,
  para responsable y para administrador. La jefa sí aprueba la de un obrero.
- El **consentimiento del art. 4.b solo lo da la persona**: la jefa por el
  obrero 409, un compañero 404, el administrador 409, la propia persona 200 con
  `employee_agreed=True`.
- Nadie pone una **discrepancia en boca de otro**: 409.
- No se puede aplicar sin acuerdo mientras la persona está **en plazo**
  (`still_within_the_window`), ni resolver dos veces, ni dos responsables a la
  vez: la segunda mano rebota con 409.
- El camino entero del art. 4.b, por la puerta: propone → discrepa → la empresa
  aplica igual. Queda `applied_without_agreement`, la discrepancia se conserva y
  **los representantes quedan avisados**.

Por el camino monté mal un escenario ---puse `status=DISPUTED` a mano, cuando ese
es el estado **final** y no el intermedio--- y el 409 resultante parecía un
defecto. Lo era de la sonda. Probado por la puerta, funciona.

#### El hallazgo: la puerta estaba cerrada en un sentido y abierta en el otro

Aplicando la lección 105 ---«un módulo bien escrito no protege a quien no lo
llama»--- al mecanismo transversal `apps/common/four_eyes.py`: lo importan
cuatro sitios, y al enumerar todas las decisiones del producto,
**`reject_correction` no estaba entre ellos**.

Medido, con el control de que sí había otra persona que podía decidir:

| La misma responsable, sobre su propio fichaje | Respuesta |
|---|---|
| Aprobar el cambio | 409 `cannot_decide_your_own` |
| **Rechazarlo** | **200, `REJECTED`, resuelto por ella misma** |

No cambiar nada también es decidir. Si la empresa propone corregir el fichaje de
un responsable ---quitarle una hora que no trabajó, por ejemplo--- archivar esa
propuesta es exactamente la decisión que el art. 4.b quiere que pase por una
segunda persona. Y `reject` cierra la corrección: quien la propuso vuelve a
empezar, y el rastro dice que la resolvió la propia persona afectada.

**Arreglo.** `reject_correction` pasa por `refuse_self_decision` igual que
`approve_correction`, con la misma marca en la nota. Ninguna prueba existente se
rompió, lo que confirma que nada dependía del comportamiento anterior.

**La excepción se mantiene y se prueba.** En una empresa con una sola persona al
mando no hay segunda, y negarlo dejaría a un autónomo sin poder tocar su
registro. Va adelante, y la nota que viaja al informe dice que se resolvió a
solas --- permitirlo en silencio borraría justo la diferencia que el
procedimiento existe para dejar ver.

**Prueba.** `apps/punches/tests/test_no_cambiar_nada_tambien_es_decidir.py`,
cuatro casos: no archiva sola un cambio sobre su fichaje; tampoco lo aprueba
---la simetría queda fijada, no solo el arreglo---; el administrador sigue
rechazando la de otra persona; y quien está sola al mando sigue pudiendo y queda
dicho en la nota. **Validada contra el fallo**: neutralizada la llamada, caen
exactamente esas dos y los controles aguantan.

#### Lo que confirmó la suite de navegador

Dos rojos, y los dos por el mismo motivo: **la prueba 22 usaba justo el atajo
que este arreglo cierra**. Entra como administradora, pide una corrección de su
propio fichaje y al terminar la limpiaba **rechazándosela ella misma**. Ahora
eso contesta 409 `cannot_decide_your_own`, que es lo correcto.

El segundo rojo ---`/mi-jornada` en la prueba de contraste--- era colateral: con
la limpieza rota, la 22 dejaba correcciones pendientes que cambiaban el render
de esa pantalla. En aislado pasaba. Es la lección de «limpia antes de crear»
vista del revés: **la limpieza rota de una prueba tumbó otra**.

La limpieza la hace ahora una segunda sesión, la del responsable, que es
exactamente lo que el procedimiento pide.

**Estado:** área «Correcciones» limpia, con una lente más. Cerrada con **1005
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos y sin migraciones pendientes.

### Vuelta 71 --- Un justificante que dice `.pdf` y no lo es (26/08)

**Lente:** los justificantes de ausencia. Son ficheros que sube la persona y a
menudo un dato del art. 9 del RGPD, así que la pasada mira dos cosas: quién
llega a ellos, y qué se acepta como fichero.

#### Lo que salió limpio, y dos falsos hallazgos míos

El control de acceso es impecable, ejercitado con seis sesiones distintas contra
el endpoint real:

| Quién | Respuesta | Rastro |
|---|---|---|
| La dueña del justificante | 200 | ninguno, a propósito |
| Una compañera del mismo departamento | 404 | — |
| Un responsable de **otro** departamento | 404 | — |
| Su responsable | 200 | sí |
| Un administrador | 200 | sí |
| Un administrador de **otra empresa** | 404 | — |

Por el camino me equivoqué dos veces, y las dos habrían acabado en el cuaderno
como hallazgos si no llego a validarlas:

1. **«No queda rastro de ninguna descarga.»** Filtré el registro por
   `"document_downloaded"` y la acción es `DOCUMENT_DOWNLOADED`. El contador
   daba cero porque contaba mal, no porque el producto callara.
2. **«Un responsable de otro departamento entra.»** Le había puesto
   `department=oficina`, que es **dónde trabaja**, no qué dirige. Lo que dirige
   va en `Department.managers`, y sin departamentos al mando el alcance es todo
   por diseño ---está razonado en `scope.py`: la alternativa es un responsable
   que no ve a nadie el día que la empresa se da de alta---. Con los
   responsables puestos de verdad, da 404.

También sale bien lo que el RD 1060/2022 obliga: adjuntar un parte a una baja
médica se rechaza con `no_medical_certificate`.

#### El hallazgo: la extensión la elige quien sube el fichero

Contra el endpoint real, antes de tocar nada:

- Un **zip** llamado `parte.pdf`: **201, aceptado**.
- Un **HTML con un `<script>`** llamado `foto.png`: **201, aceptado**.

Sí se rechazaban el fichero vacío, la doble extensión `.pdf.html` y el nombre
con comillas.

Dos consecuencias, y la segunda se ve menos:

- **La defensa en profundidad que el módulo creía tener no existía.** El
  docstring de `uploads.py` dice que son dos ---la lista de extensiones y el
  `Content-Disposition: attachment` del almacenamiento--- y que «el par es lo
  que sobrevive a que alguien cambie la otra más tarde». Contra este caso solo
  había una: una lista de extensiones no filtra a quien elige la extensión.
- **Y sin nadie atacando:** un justificante que dice `.pdf` y es otra cosa llega
  a la gestoría o a la Inspección y no se abre. El registro se queda con un
  documento inservible y no se sabe hasta el día en que hace falta.

**Arreglo.** `validate_content` en `uploads.py`: comprueba la marca de los
primeros bytes contra el formato que anuncia el nombre. WEBP y HEIC la llevan
dentro de un contenedor, así que la tabla guarda el desplazamiento y la cabecera
que se lee se calcula de la propia tabla, para que añadir un formato más adentro
no la deje corta. Conectado en el modelo y en el serializer, como los otros dos
validadores, con su migración.

**Lo que no hace, a propósito:** validar el formato entero. Un PDF roto por la
mitad sigue pasando --- se trata de que nadie cuele un tipo distinto, no de
rechazar el escaneo de una fotocopiadora vieja.

**Prueba.** `apps/absences/tests/test_el_justificante_es_lo_que_dice.py`, siete
casos: los dos disfraces se rechazan; un parte de verdad sigue entrando;
**ninguna foto de móvil se queda fuera** ---PNG, JPEG y WEBP generadas de
verdad, y la caja `ftyp` de HEIC, que es lo que sale de un iPhone---; el fichero
queda con el puntero devuelto para quien lo guarde después; un PDF a medias
vale; y una extensión no admitida la rechaza el otro validador, no este.
**Validada contra el fallo**: neutralizada la comprobación, caen exactamente las
dos de los disfraces y los cinco controles aguantan.

**Estado:** área «Ausencias» limpia, con una lente más. Cerrada con **1001
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos y sin migraciones pendientes.

### Vuelta 70 --- El huso viaja con el fichaje (26/08)

**Lente:** el hallazgo que la 69 dejó medido y marcado para esta vuelta.
`Timesheet`, `Decisions` y `Overview` pintaban con `session.tenant.time_zone`.

**Qué faltaba de verdad.** La 69 puso la zona de cada cual en su sesión, que
arregla las pantallas donde uno mira lo suyo. Las de gestión enseñan a **varias**
personas a la vez, y el frontend solo tenía la de la empresa: en una empresa de
Madrid con delegación en Las Palmas, todas las filas salían en el huso de la
central.

Inventariado sobre la respuesta real, no sobre lo que yo suponía: `/api/employees/`
**ya** traía `effective_time_zone` ---efecto de la 69--- y el fichaje **ninguna**
clave con «zone».

**Dónde ponerlo.** Se podía sacar del `EmployeePicker`, que ya recibe la persona
entera, pero eso solo cubre el caso con filtro y se pierde al recargar. El huso
va **en el fichaje**: un volcado mezcla delegaciones, y una hora sin su huso no
dice a qué hora se fichó. Quien lo lee por la API ---una pantalla o un
conector--- no tiene otra forma de saberlo.

- `time_zone` en `PunchSerializer`, con lo que `target_detail` y `result_detail`
  de una corrección lo heredan gratis.
- `time_zone` en `CorrectionSerializer`, porque `proposed_timestamp` va suelto:
  es la hora que se propone poner, y se leía con una hora de más.
- En el frontend, `punch.time_zone ?? zone` y `correction.time_zone ?? zone`. La
  de la empresa queda de respaldo, no de respuesta.

`byDay` también: con la zona de la central, un fichaje de las 23:30 en Las
Palmas caía bajo el día siguiente.

**El N+1, medido antes y después.** Un campo derivado por fila es un N+1
esperando, y la lección 108 es de la vuelta pasada. Cuarenta fichajes de veinte
personas ---la mitad con centro propio y la mitad sin, que son los dos
caminos--- costaban **46 consultas**; con `select_related` hasta el centro y
hasta la empresa, **6**. La prueba de plantilla que existía no lo habría cazado:
mide crecer con la gente, no con las filas.

**Prueba.** `apps/punches/tests/test_cada_fichaje_dice_su_huso.py`, tres casos:
el fichaje dice su huso ---y el control de que quien no tiene centro se queda con
el de la empresa, sin el cual un arreglo que devolviera siempre lo mismo
pasaría---; la corrección lleva el de quien la sufre, y el fichaje que cuelga
también; y decirlo no cuesta una consulta por fila. **Validadas contra el
fallo**, cada una por su motivo: quitando el `select_related` cae solo la del
coste, y revirtiendo el campo caen solo las otras dos.

**Estado:** área «Fichajes» y «Decisiones», limpias con una lente más. Cerrada
con **994 pruebas de backend y 271 de navegador en verde**, linters limpios y sin
migraciones pendientes.

### Vuelta 69 --- La delegación que va una hora por detrás (26/08)

**Lente:** la misma pregunta que rindió en la 68 ---«¿quién importa este
módulo?»--- aplicada a `apps/common/clock.py`, que avisa de que la trampa de
`date.today()` «se coló cuatro veces antes de que este módulo existiera».

**Lo que salió limpio, y se comprueba porque hacía falta comprobarlo.** No queda
ninguna `date.today()` viva: las siete apariciones son comentarios que la citan.
Los `.date()` sueltos son todos correctos ---`agreements.py` es YAML sin husos y
el resto ya venía convertido---. El resumen semanal del responsable coloca un
fichaje de las 00:30 en el día que la persona vivió, no en el de UTC, y el
informe de una persona de Las Palmas dentro de una empresa de Madrid pone su
fichaje de las 23:30 en **su** día y no en el de la central.

Es decir: **donde se cuenta, estaba bien.**

**El hallazgo está donde se enseña.** La sesión (`/api/auth/me/`) daba
`tenant.time_zone` y ninguna zona más ---comprobado sobre la respuesta real: la
clave `user` trae `workplace` y `workplace_name`, y ni una sola clave con
«zone»---, así que las pantallas no tenían otra cosa que usar. Y
`/api/punches/today/` devolvía también la de la empresa.

Para una delegación en Las Palmas dentro de una empresa de Madrid eso son
sesenta minutos:

- El **reloj de la pantalla de fichar** iba una hora adelantado. Quien ficha a
  las 09:00 de su reloj leía las 10:00.
- Quien fichaba a las **23:30** lo veía como las **00:30 del día siguiente**, y
  su jornada aparecía empezada un día después.
- Mientras el informe que se entrega ponía ese mismo fichaje en el día correcto.

**La pantalla y el documento decían días distintos para el mismo fichaje**, y de
eso va justo el art. 34.9: el registro que la persona consulta es el suyo.

**Arreglo.** `effective_time_zone` en el usuario de la sesión ---el patrón ya
existía en `WorkplaceSerializer`, resuelto con el mismo `get_`--- y
`str(request.user.tzinfo)` en `/today/`. En el frontend, `MyTime` pasa a usar la
de la persona con la de la empresa de respaldo.

**Un N+1 que me pilló la casa.** El campo nuevo toca `workplace` y, para quien
no tiene centro, `tenant`: `/api/employees/` pasó de 10 consultas con tres
personas a 19 con doce. Lo cazó `test_no_crece_con_la_plantilla` en la misma
tanda, sin que yo lo buscara. Resuelto con `select_related("department",
"workplace", "tenant")` --- los dos, porque con solo `workplace` seguía en 19.

**Prueba.** `apps/punches/tests/test_el_reloj_de_su_centro.py`, cuatro casos: la
sesión dice el huso de quien la abre; **quien no tiene centro se queda con el de
la empresa** (el control, porque un arreglo que exigiera centro dejaría sin hora
a la mayoría de las plantillas); el reloj de fichar es el suyo; y el caso de
punta a punta, que además comprueba que con la zona de la empresa saldría el día
siguiente --- si eso dejara de cumplirse, el caso ya no separaría los dos husos y
la prueba no demostraría nada. **Validada contra el fallo**: revertidos los dos
sitios, caen tres y aguanta el control.

**Estado:** área «Fichar» sigue limpia, con una lente más. Cerrada con **991
pruebas de backend y 271 de navegador en verde**, linters limpios y sin
migraciones pendientes.

### Vuelta 68 --- Las doce horas que eran once (26/08)

**Lente:** el cambio de hora, comprobado en el código que se ejecuta y no donde
está citado. `apps/common/dst.py` existe desde hace vueltas, está bien escrito y
tiene sus pruebas --- y **solo lo usaba `overtime.py`**. La pregunta de la vuelta
fue cuál de las demás cuentas del producto debería saber del cambio de hora y no
lo sabía.

**El hallazgo.** Un turno guarda horas de reloj de pared: «acaba a las 22:00,
empieza a las 10:00». `_check_daily_rest` restaba esos dos `datetime`, que son
**naive**, así que daba doce horas los 365 días del año. La madrugada del último
domingo de marzo, entre esas dos horas de pared solo pasan **once**.

El suelo del art. 34.3 son doce horas de descanso entre jornadas. Un cuadrante
que programe esas doce de pared la noche del cambio deja a la persona con once
reales, **y no avisaba**: el aviso se calculaba con la misma aritmética que
producía el error. Es un falso negativo justo en la noche en la que hace falta.

La de octubre va al revés ---trece horas--- y no incumple nada. Importa porque un
arreglo que empezara a avisar ahí sería peor que el defecto: una advertencia
falsa cada octubre, para toda la plantilla de noche a la vez.

**Cómo se confirmó, y contra qué.** `review_roster` con el fin de semana del
cambio daba los mismos dos hallazgos que una semana normal: ninguno de descanso.
Un vacío no es prueba, así que se validó con un caso conocido ---ocho horas de
descanso sin cambio de hora de por medio--- y ahí sí salía `short_daily_rest`.
La comprobación funcionaba; lo que fallaba era la aritmética.

**Los tres sitios.** La lección 101 dice enumerarlos antes de tocar nada:

- `services.py` `_check_daily_rest` --- el art. 34.3, con el falso negativo
  confirmado.
- `services.py` `_check_weekly_rest` --- las 36 horas del art. 37.1, incluidos
  los bordes de la ventana, que se construían con `datetime.combine` naive.
- `coverage.py` `who_can_cover` --- los avisos de descanso al cubrir una baja,
  que es donde el responsable decide a quién llama.

El cuarto sitio que resta turnos, en el cálculo de horas extra, ya localizaba la
zona: es el que usa `change_across`.

**Arreglo.** `real_gap(desde, hasta, where)` en `apps/common/dst.py`, junto al
resto de este conocimiento. Acepta naive ---como salen de un turno--- y aware
---como salen de la base--- y pasa por UTC antes de restar, que es la trampa
que ese módulo ya documentaba: dos `datetime` con el **mismo** `tzinfo` se restan
como reloj de pared.

**Y la explicación, no solo la cifra.** El propio módulo lo defiende: esas horas
son reales y la ley va por el tiempo efectivamente trabajado, así que no hay
cifra que corregir --- hay que decir de dónde sale. Quien lee el cuadrante ve
22:00 y 10:00 y cuenta doce; sin la frase, el aviso parece una cuenta mal hecha
del programa y se ignora justo esa noche. El mensaje añade ahora «esa noche los
relojes se adelantaron», traducida al castellano.

**Prueba.** `apps/shifts/tests/test_el_descanso_la_noche_del_cambio.py`, cinco
casos: la noche de marzo avisa con once horas y dice por qué; una semana normal
con las mismas horas de pared calla; la noche de octubre no inventa un
incumplimiento; un descanso corto de los de siempre sigue avisando; y `real_gap`
por separado da 11, 13 y 12 donde la aritmética de pared daría doce las tres
veces. **Validada contra el fallo**: revertida la línea, cae exactamente la
primera y las otras cuatro aguantan.

**Estado:** área «Cuadrante» sigue limpia, con una lente más. Cerrada con **987
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos y sin migraciones pendientes.

### Vuelta 67 --- El día que salía dos veces (26/08)

**Lente:** el hallazgo que la 66 dejó anotado y medido. Se coge primero, como
decía el cuaderno.

**Lo que pasaba.** `Timesheet` pedía cincuenta fichajes por página y luego los
agrupaba por día. Cuando el corte caía dentro de un día ---con una persona
activa cae casi siempre--- ese día salía **dos veces**, una en cada página y con
la mitad de sus horas cada vez. Medido en la demo: el último fichaje de la
página 1 era una entrada y quedaban **34 fichajes de esa misma persona y ese
mismo día** en la siguiente.

Nada lo decía. Quien miraba el día 26 en la primera página creía que había visto
el día 26.

**Lo que no era.** Antes de mirar el render escribí que la pantalla mostraría
una jornada abierta que sí se cerró. Falso: `Timesheet` no calcula jornadas ni
saldos, solo lista eventos bajo un encabezado de día. El defecto es el día
partido y repetido. Queda corregido arriba, en el hallazgo.

**Por qué no valía ninguna de las dos salidas fáciles.** Traer el periodo entero
como en `MyTime` no sirve para el volcado sin filtrar: el rango por defecto es
del uno de mes a hoy y **de toda la empresa**, que en la demo son unos dos mil
fichajes. Y paginar por día en el servidor cambia el contrato de `/punches/`,
que también usa la puerta de integración.

**Arreglo: dos vistas, porque son dos preguntas.**

- **Con una persona elegida** se mira su jornada, y ahí el día es la unidad: se
  trae el periodo entero con `getAllPunches`, sin paginador. Si no cabe ---medio
  año, por ejemplo--- la pantalla lo dice y pide acortar las fechas.
- **Sin persona** esto es un volcado de auditoría: se pagina por fichaje, que es
  la unidad que se lista, y **cada fila lleva su fecha**. Agrupar por día encima
  de una paginación por fichaje era justo lo que producía el día repetido.

La tabla se extrajo a `TablaDeFichajes` para no duplicarla, con `conFecha` como
única diferencia. Al montar la columna nueva quedó desalineada un momento ---la
cabecera la ponía tras «Tipo» y el cuerpo tras «Hora»---; ahora la fecha va la
primera en las dos.

**Prueba.** `e2e/44-el-dia-no-se-parte.spec.js`. Busca por API la persona con
más fichajes en un solo día, **exige que pase de cincuenta** ---si no, dice que
no puede demostrar nada en vez de dar un verde vacío--- y comprueba que el
encabezado de ese día aparece **una sola vez** y con todas sus filas. La segunda
comprueba que el volcado sin persona lleva las columnas Fecha y Persona.
**Validada contra el fallo**: forzando `porDia` a falso, se pone roja.

**Estado:** área «Fichajes» limpia, con una lente más. Cerrada con **982 pruebas
de backend y 271 de navegador en verde**, linters limpios y sin migraciones
pendientes.

### Vuelta 66 --- El PDF que se imprime fuera de la hoja (26/08)

**Lente:** la tercera pieza de lo que sale del sistema. El CSV se revisó en la
64 y el nombre del fichero en la 65; queda el PDF, que es el que se lleva en
papel a una inspección.

**Cómo se buscó.** Datos hostiles por las tres vías que llegan al PDF: marcado
(`<b>`, `<font color=white>`), texto sin cerrar, y longitud. Las dos primeras
salieron bien. Las de longitud descubrieron primero un **falso positivo mío**:
un apellido de 320 caracteres no llega al PDF porque `last_name` es de 100 y lo
rechaza PostgreSQL antes. Con los máximos reales el documento se generaba sin
quejarse.

**El hallazgo.** La discrepancia del art. 4.b admite **mil caracteres**, y va a
una celda de `Table` como cadena suelta. ReportLab no parte las cadenas de las
celdas: las dibuja seguidas. Medido con las posiciones del flujo de contenido,
en un A4 de 595 puntos de ancho el texto llegaba hasta el **5102**. Nueve veces
la hoja.

Estaba en el fichero y no se leía en el documento. Y eso vacía justo lo que el
artículo protege: que el registro lleve la versión de la persona junto a la de
la empresa para que quien lo lee pueda comparar las dos. Afectaba igual al
nombre de la persona (100 caracteres), al de la empresa y al motivo de una
ausencia.

**Por qué no lo vio la vuelta 39.** Esa vuelta fue la que hizo llegar la
discrepancia al informe, y la fijó con `assert "Yo entré antes." in texto`. Un
extractor devuelve lo que hay en el flujo de contenido, no lo que cae dentro de
los márgenes: la comprobación pasaba con el texto colgando fuera de la página.

**Arreglo.** Las celdas de longitud libre pasan por `_celda()`, que envuelve el
texto en un `Paragraph` ---que sí ajusta líneas--- y lo **escapa**, porque
`Paragraph` interpreta marcado: sin escapar, un `<` tumbaría el documento y
`<font color=white>` escondería texto dentro de una prueba legal. Medido otra
vez: 500 puntos de 595.

**Prueba.** `apps/reports/tests/test_el_pdf_se_lee_en_la_hoja.py`, cinco casos.
El primero es `test_la_medicion_sabe_ver_el_desbordamiento`: construye a mano
una tabla con la cadena suelta y exige que el medidor diga «se sale». Sin él,
los otros cuatro podrían estar pasando porque el medidor no mide.

Al pasar las celdas por `Paragraph` el texto se parte en renglones, así que el
helper `_texto_del_pdf` de `test_lo_que_pone_el_informe.py` colapsa los saltos
antes de buscar: una frase corta salía cortada por la mitad y la búsqueda
literal fallaba sin que faltara nada. Queda anotado ahí lo que ese helper mide y
lo que no.

**Estado:** área «Informes» sigue limpia, con una lente más. Cerrada con **982
pruebas de backend y 269 de navegador en verde**, linters limpios y sin
migraciones pendientes.

#### Lo que destapó la suite al cerrar la vuelta

La tanda de navegador dejó un rojo que no venía del PDF, y tiró de un hilo más
largo. **La aplicación recién autorizada no aparecía en la pantalla.**

La causa no era la prueba. El listado se sirve de cincuenta en cincuenta y
`Applications.jsx` pintaba `rows` sin paginar: con más de cincuenta
aplicaciones, las que sobraban no se veían **ni se podían revocar**, que es lo
que corta el acceso de un conector a los registros. Y estaban ordenadas por
nombre, así que una recién autorizada caía donde le tocara alfabéticamente.

Al buscar el mismo patrón en el resto del panel salió una segunda pantalla, y
peor: **`MyTime`, el registro de la propia persona.** Pide el mes entero y
pintaba las cincuenta primeras filas. Medido con los datos de la demo:
`operario@demo.local` tiene **209 fichajes en agosto** y la pantalla enseñaba
50 --- las más recientes, así que los primeros días del mes salían en blanco,
como si no se hubiera trabajado. Un mes laborable con pausas son ochenta y ocho
fichajes: no es un caso extremo.

El subtítulo de esa pantalla dice «Tu registro completo». Es el art. 34.9: la
persona tiene derecho a consultar su registro, y enseñarle un trozo llamándolo
completo no es consultarlo.

El comentario de `api.js` ya nombraba este agujero de una vuelta anterior
---«the clock events, the people and the audit trail all showed the first fifty
rows»--- y se arregló en People y en el rastro de auditoría. Los fichajes de la
persona se quedaron fuera. Segundo arreglo incompleto de la misma vuelta, con
el del PDF.

**Arreglos.**

- `periodoEntero()` en `api.js`, con `getAllPunches` y `getAllCorrections`:
  recorre las páginas del periodo. Un `Pager` no vale aquí porque los fichajes
  se pintan agrupados por jornada, y cortar cada cincuenta filas dejaría la
  entrada de un día en una página y su salida en la siguiente. Tope de veinte
  páginas, y si se alcanza la pantalla **lo dice** en vez de hacer pasar por
  completo lo que no lo está.
- `Pager` en `Applications.jsx`, el que ya usaban People, Timesheet, Decisions,
  AuditTrail y MyLeave.
- Orden del listado de aplicaciones: **activas primero y las más recientes
  arriba**, en vez de alfabético. Lo revocado baja pero no desaparece, porque
  los fichajes que registró siguen siendo suyos.
- Dos botones de la misma tarjeta se llamaban «Revocar» ---uno tumba la
  aplicación entera, el otro un token---. Ahora tienen `aria-label` distinto:
  con lector de pantalla sonaban igual y no había forma de distinguirlos.

**Pruebas.** `e2e/43-el-mes-entero.spec.js` pregunta al servidor cuál es el mes
más cargado de esa persona, exige que pase de cincuenta ---si no, dice que no
puede demostrar nada en vez de dar un verde vacío--- y comprueba que el día más
antiguo se ve. **Validada contra el fallo**: revertido `getAllPunches` a
`getPunches`, la prueba se pone roja. Tres pruebas más en
`test_applications_api.py` para el orden, para que lo revocado baje sin
desaparecer, y para que `count` y `next` digan que hay más.

La prueba de las aplicaciones no revocaba la aplicación pese a decirlo en el
título: dejaba una activa cada vez que se corría. De ahí las 59 acumuladas que
destaparon todo esto. Ahora revoca.

### Vuelta 65 --- El nombre de un fichero es una ruta (26/08)

Sigue la lente de la 64 ---lo que sale del sistema, visto por quien lo recibe---
y da **tres hallazgos** en la misma zona: el apellido de una persona acaba en la
cabecera `Content-Disposition` y en la entrada de un zip, y los dos lo leen como
camino. El apellido es texto libre que escribe la administración de la empresa,
o un conector por `/api/app/people/`.

- **Zip Slip.** Con el apellido `../../../evil`, la entrada del zip sale como
  `'../../../evil_Nombre.pdf'`. Quien lo descomprima con una herramienta que no
  valide rutas ---`extractall` de Python, sin ir más lejos--- escribe tres
  niveles por encima del destino. Y quien descomprime ese zip es la gestoría o
  la Inspección.

- **Dos personas que se llaman igual se pisan.** Una empresa con dos Ana García
  producía dos entradas `García_Ana.pdf`: al descomprimir, la segunda machaca a
  la primera. **Se entrega un informe menos de los que dice la carátula y nada
  avisa.** El manual promete «un zip con un PDF por persona».

- **Sin apellido, el separador queda colgando**: `_Jefa.pdf`. El respaldo que el
  código tenía previsto (`or str(person.id)`) no llegaba a saltar, porque la
  cadena no estaba vacía.

Los tres se arreglan con `apps/common/descargas.py`: `nombre_seguro` quita todo
lo que se lea como ruta y translitera los acentos ---«Garc_a» no lo reconoce
nadie, «Garcia» sí--- y `nombre_de_persona` añade el número de empleado, o el
principio del identificador si no lo tiene. Los cuatro sitios que componían
nombres pasan por ahí, incluida la cabecera de descarga, que llevaba el apellido
entre comillas sin escapar.

Trece pruebas nuevas, dos rojas sin el arreglo. Y tres pruebas existentes de
`test_quien_se_fue.py` fijaban el nombre exacto de las entradas: comprobaban
«García_Ana.pdf» cuando lo que les importa es **quién** está en el zip. Ajustadas
a eso, que es más robusto y dice mejor lo que buscan.

974 pruebas de backend en verde.

### Vuelta 64 --- El CSV que se abre en Excel (26/08)

Lente nueva, y de las que cambian el color de la vuelta: **el fichero que se
entrega, abierto por quien lo recibe**. Excel y LibreOffice evalúan como fórmula
cualquier celda que empiece por `=`, `+`, `-` o `@`, y el informe de jornada
salía sin neutralizar.

Comprobado de punta a punta: una persona con el nombre
`=HYPERLINK("http://…","pincha")` produce un CSV donde esa celda **es** un
enlace ejecutable. Las comillas del CSV no protegen ---son sintaxis del fichero,
el programa las quita al leer y evalúa lo de dentro---.

Aquí pesa más que en un CSV cualquiera, por dos motivos:

- **El destinatario es la Inspección o la gestoría.** No es un fichero que uno se
  baja para sí: es el documento con el que la empresa responde.
- **Parte del texto lo escribe la persona trabajadora.** La discrepancia del art.
  4.b viaja al informe **por diseño**, que es el derecho que ese artículo
  protege, así que no se puede sanear quitándola. Y la exportación de auditoría
  lleva `actor_label`, que en una integración lo pone el conector.

Los **dos** exportadores del producto pasan ahora por `EscritorSeguro`
(`apps/common/csv_export.py`), que antepone un apóstrofo solo a las celdas que
empiezan como una fórmula: un nombre corriente sale intacto. Nueve pruebas,
incluida una de punta a punta con su contraste ---que el nombre llegue al
fichero, porque si no llegara la comprobación pasaría sin mirar nada---.

961 pruebas de backend en verde.

### Vuelta 63 --- Una carrera en la prueba del vaciado (26/08)

Segunda vuelta seguida sin defecto del producto. La suite completa falló una vez
en «asignar un turno, verlo, y vaciar el mes»: el vaciado dejaba veintitrés
turnos. **Aislada pasaba siempre**, que es la firma de una carrera y no de un
defecto.

El diálogo de confirmación se cierra en cuanto se pulsa «Vaciar», y el borrado
sigue viajando. La prueba esperaba a que el diálogo desapareciera y consultaba la
API **una vez**: en una tanda cargada, esa consulta llegaba antes que el DELETE y
veía los turnos que estaban a punto de irse. Ahora espera a que quede vacío, como
ya hacía el spec del Resumen por el mismo motivo.

Queda dicho como matiz de la interfaz, no como arreglo: el diálogo se cierra
antes de que la acción termine. Para «Vaciar el mes» ---que es de las pocas cosas
que no se pueden deshacer--- no es evidente que esté bien, pero cambiarlo es
decisión de producto y no la toma una prueba en rojo.

### Vuelta 62 --- La puerta de integración, vigilada (26/08)

**Primera vuelta sin un defecto del producto desde la 42.** Lo que había era un
hueco de vigilancia.

`test_no_crece_con_la_plantilla.py` mide catorce rutas del panel y comprueba una
propiedad, no un número: que ninguna consulte más por haber más gente. Es la
sonda que en su día cazó los dos N+1 de `/api/shifts/review/` (40 consultas con
tres personas, 130 con doce).

**No cubría `/api/app/…`**, que es justo lo que un conector golpea cada pocos
minutos y con la plantilla entera. Y `_attendance_of` lleva un comentario largo
explicando cómo se evitó ahí una consulta por cabeza ---«en una plantilla de
doscientas eso eran seiscientas consultas»--- sin nada que vigilara que siguiera
siendo verdad.

Añadidas las dos, con su propia credencial de aplicación: sin ella contestaban
403 y la sonda las habría dado por planas, que es el falso negativo contra el
que este mismo fichero se protege más abajo. Medido: **7 consultas con tres
personas y 7 con doce** en `/api/app/attendance/`, 5 y 5 en `/api/app/people/`.
La optimización funciona, y ahora se entera alguien si deja de funcionar.

### Vuelta 61 --- El esquema de la puerta de integración (26/08)

Retoma uno de los «pendiente al parar» del 14/08: los endpoints de integración
publicaban su respuesta como **objeto libre** ---`responses={200: dict}`--- y el
esquema es la documentación del protocolo abierto. Quien escribe un conector
tiene que deducir la forma probando, o descubrirla el día que cambia.

- `/api/app/attendance/` no tenía serializer de respuesta y ahora lo tiene, con
  los tramos, el estado y el aviso de que `day` es el día **en la zona de la
  empresa** y no en UTC.
- `/api/app/people/{ref}/` en sus tres métodos declaraba `dict` teniendo
  `PersonInTheAnswerSerializer` escrito justo encima, sin usar. El listado sí lo
  usaba: se quedó a medio camino.

Sonda en `tenants/tests/test_el_esquema_dice_que_devuelve.py`: recorre las seis
operaciones de la puerta ---`/api/app/…` y el fichaje delegado--- y exige que
cada respuesta 2xx apunte a un esquema con campos. Lleva su propio contraste
---que las rutas sigan existiendo--- y se ha comprobado que se pone roja al
devolver una de ellas a `dict`.

Solo la puerta de integración: las pantallas propias van con el frontend en el
mismo repositorio y se enteran de un cambio al momento. Quedan otros doce
`responses={…: dict}` en endpoints internos, anotados y sin tocar.

952 pruebas de backend en verde.

**Y un tropiezo propio, por reincidencia.** Edité el backend mientras corría la
suite de navegador, que es exactamente lo que la lección de la vuelta 49 dice que
no se haga: el recargador de Django reinició el servidor y la tanda murió a los
tres minutos con dos fallos que no existían. Relanzada con el backend quieto.

### Vuelta 60 --- El manual contra el producto (26/08)

Lente nueva: coger las afirmaciones **comprobables** del manual y verificarlas
una a una contra el código. Salió de la vuelta 58, donde una discrepancia
apareció por casualidad.

Lo que se comprobó y **está bien**: el enlace de acceso caduca a las 24 h y vale
una vez; la contraseña pide doce caracteres (`min_length=12` en los tres sitios);
el justificante admite hasta 10 MB y solo PDF o imagen (`MAX_BYTES`); el informe
corta en 200 personas por petición (`MAX_PEOPLE_PER_EXPORT`); el plazo para
contestar a un cambio propuesto son siete días por defecto
(`correction_consent_days`).

Lo que **no**: «se conserva cuatro años». Se conserva, pero porque no se borra
nunca, no porque haya una política que se cumpla. Ver «Hallazgos abiertos».

La lente rinde y es barata: el manual está escrito con cifras concretas, y cada
cifra es una pregunta con respuesta en el código.

### Vuelta 59 --- El formulario que proponía ayer (26/08)

Lente: **abrir un formulario, escribir, cancelar y reabrirlo**, que es de las que
el propio prompt pide y no se había hecho nunca. Departamentos y Personas están
limpios: ni el borrador sobrevive al cancelar, ni «Nuevo» hereda lo que se estaba
editando, ni editar una fila enseña la anterior.

**Lo que salió fue otra cosa, y por mirar a la hora rara.** Eran la 01:28 de un
miércoles y el diálogo de solicitar una ausencia proponía el **martes**.

`new Date().toISOString().slice(0, 10)` da la fecha en **UTC**, que no es la de
nadie salvo en Greenwich: al este devuelve el día anterior durante toda la
madrugada, al oeste el siguiente durante la tarde. En España, cada noche entre
las 00:00 y las 02:00 en verano, quien pedía un permiso sin fijarse lo pedía para
ayer.

Y lo llamativo: **`format.js` ya tenía el helper correcto, con un comentario que
describe este fallo palabra por palabra** ---«anybody west of Greenwich gets
yesterday for most of the evening and anybody east gets tomorrow in the small
hours»---. Quedaban tres sitios con el patrón viejo: el diálogo de ausencias y
las dos fechas del periodo de Informes, que es el documento que se entrega a la
Inspección.

Prueba en `e2e/42-la-fecha-de-hoy.spec.js`, **con el reloj movido a las 00:30**:
a media mañana las dos formas coinciden y la prueba pasaría con el fallo delante.
Dos de sus comprobaciones se ponen rojas con el código de antes.

### Vuelta 58 --- Cuando te dan de baja (26/08)

Lente: **la persona dada de baja**, ejercitada de verdad --- alta, fichaje, baja
con la sesión abierta, y a ver qué pasa.

**El manual describía algo que no ocurre.** Decía «aunque tu sesión siga abierta,
el fichaje se rechaza», que suena a un aviso explicando tu situación. Lo que pasa
es que **la autenticación entera deja de valer**: 401 en la siguiente petición,
sea la que sea, y la pantalla de entrada, donde ya no se puede entrar. No es solo
el fichaje: tampoco puede consultar su registro.

Y de ahí sale una consecuencia que no estaba escrita: `register_punch` tiene su
propio rechazo con código, `employee_inactive`, **y por esta vía no se alcanza
nunca**. Solo lo ve un fichaje delegado, donde quien autentica es la aplicación y
no la persona. Se descubrió porque la primera versión de la prueba usaba
`force_authenticate` y salía 409 en vez de 401: ese helper salta justo la capa
que rechaza, así que estaba probando un camino que ninguna persona recorre.

Manual corregido, y el comportamiento fijado en
`users/tests/test_al_darte_de_baja.py` con testigos de verdad --- para que
cambiarlo sea una decisión y no un descuido. La pregunta de si debería conservar
el acceso a su propio registro queda en «Hallazgos abiertos»: es de producto.

### Vuelta 57 --- Lo que el informe le cuenta a la Inspección sobre el origen (26/08)

Lente: **la excepción del administrador único**, ejercitada de verdad con la
empresa que se creó en la vuelta 56. Elena, sola en su empresa, ficha, pide
corregir su propio fichaje y lo aprueba ella misma.

**La regla de las cuatro manos funciona como promete**: se aplica porque no hay
nadie más, y la resolución lo dice con todas las letras --- «Resuelto por la
misma persona a la que afecta: no hay ningún otro responsable ni administrador en
la empresa». Eso está bien y no se toca.

**Lo que no llegaba era al informe.** Al generar el documento que se entrega, la
observación del día decía: «entrada sin salida; **registrado por una
aplicación**». No lo había registrado ninguna aplicación: lo había corregido la
administración de la empresa tras el procedimiento del art. 4.b.

La causa: `day_notes` escribía una sola frase a partir de `row.delegated`, que
sale de `Punch.was_delegated` --- y ese agrupa **tres orígenes**: `DELEGATED`,
`ADMIN` e `IMPORT`. Para el modelo está bien agrupado, porque los tres significan
«no lo hizo la persona». Para el informe no: una aplicación fichando en nombre de
alguien, la empresa corrigiendo, y una importación son tres pruebas distintas, y
la que salía era la más benigna para la empresa.

El manual lo promete en dos sitios ---«los dos que no hizo la persona van
destacados» y «quien lee el informe tiene derecho a distinguirlos»--- y el
informe no los distinguía.

Ahora dice cuál de los tres, y **un día corregido lleva marca aunque no haya
discrepancia**, que es lo que el manual promete en «los días con eventos
corregidos van señalados» y antes solo pasaba si además se había impuesto sin
acuerdo. Los tres estados entran en la huella del documento.

De paso, `makemessages` volvió a rellenar por parecido: «imported from another
system» salió como «Según el cuadrante». Corregidas las cuatro en castellano y
vaciadas las de catalán y gallego.

943 pruebas de backend en verde.

### Vuelta 56 --- La empresa del primer día (26/08)

Primera vuelta desde que se vació la lista de pendientes, y con **lente nueva**:
una empresa recién creada, sin nadie, sin turnos, sin permisos, sin centros. Es
la primera pantalla que ve un cliente y la que nadie mira, porque `seed_demo`
siempre trae datos. Se creó un inquilino aparte ---sin tocar nada de lo que ya
había en la base--- y se recorrieron las diecisiete pantallas.

**Los vacíos están cuidados, y eso también es un resultado.** Cada pantalla dice
qué falta y dónde crearlo: «Todavía no hay turnos definidos. Créalos en Turnos
antes de montar el cuadrante», «Esta empresa no tiene permisos configurados, así
que nadie puede pedir ninguno» con su botón de cargar, «Sin centros no se
puede…». Ajustes avisa por su cuenta de que no hay representante legal y cita el
art. 4.b. Nada de pantallas en blanco.

**Lo que sí salió: la concordancia con uno.** El Resumen decía «1 **personas** de
alta». Solo se ve cuando hay exactamente una, o sea justo en una empresa nueva.

El barrido del árbol encontró doce sitios con un número seguido de un sustantivo
en plural fijo; **cinco se rompen de verdad** y siete ya condicionaban. Los cinco
usan ahora un `plural()` compartido en `format.js`:

- el recuento de personas del Resumen,
- «N permisos configurados» en Ajustes,
- los días de antelación del aviso del art. 38.3, en Decisiones y en el
  Calendario ---y ahí un día de antelación no es raro, es el caso que dispara el
  aviso---,
- y los días de más por desplazamiento del permiso del art. 37.3.b.

Prueba en `e2e/41-la-empresa-recien-creada.spec.js`: comprueba el helper y
recorre seis pantallas buscando «1» seguido de un plural. No crea la empresa,
porque montar un inquilino desde la suite exigiría un endpoint de alta que el
producto no tiene; queda dicho en su cabecera.

### Vuelta 55 --- La descarga que no decía nada, y el último de los trece (26/08)

`deploy/cabeceras.md` y `pages/me/MyLeave.jsx`. Dos mitades del mismo hallazgo.

**La CSP publicada no nombraba el almacén de objetos.** `STORAGE_BACKEND=s3` es
el valor por defecto en producción, y con él la descarga de un justificante no la
sirve la API: responde un 302 al almacén con una URL firmada. El navegador vuelve
a evaluar la CSP **sobre el destino de la redirección**, así que sin ese origen en
`connect-src` la descarga se bloquea. En la configuración que documenta el propio
producto, ni la persona ni quien aprueba podían recuperar el fichero que la
aplicación les pidió subir. Documentado, con el porqué y con la nota de que con
`filesystem` no hace falta.

**Y el fallo era mudo.** El `onClick` llamaba a una función `async` sin recoger
el rechazo, así que no pasaba nada de nada: ni aviso, ni fichero. Quien lo sufre
lee «la aplicación no responde», que apunta a cualquier sitio menos a una
cabecera de despliegue. Ahora hay `catch` y el aviso sale por `ErrorNote`, que la
pantalla ya tenía montado.

Un barrido por el árbol de sintaxis confirmó que era **el único** `onClick` que
llama a una función `async` exportada sin capturar, de 42 candidatas.

**Sin prueba de navegador, y es el segundo caso.** Tres intentos: la sesión del
operario no siempre tiene una ausencia con justificante ---y saltarse la prueba
por falta de datos es peor que no tenerla---, y crear una desde el formulario no
llegó a cuajar. El arreglo es un `.catch` sobre una llamada, así que el riesgo de
que se rompa sin que nadie lo note es bajo; queda dicho por si alguien lo toca.

---

**Con esto se cierran los trece hallazgos** que la prueba de convergencia del
14/08 dejó pendientes. La lista de «pendiente de arreglar» queda vacía por
primera vez desde entonces.

### Vuelta 54 --- Un filtro publicado que no filtraba (26/08)

No salió de buscar, salió de **perseguir una prueba en rojo**. La suite del
calendario falló con «la ausencia no llegó al servidor», y la ausencia sí había
llegado: el POST devolvía 201 y la fila estaba en la base. Lo que fallaba era la
comprobación siguiente.

`AbsenceViewSet` no declaraba `search_fields`. El backend de búsqueda viene en
los de por defecto, así que **el parámetro `?search=` se publica en el esquema** y
DRF, sin campos, lo ignora y devuelve la lista entera. Un cliente que lo use se
queda con la primera página creyendo que es su resultado --- y en una lista
paginada, la diferencia entre «no hay» y «no cabe en la página» no se ve.

La prueba llevaba un comentario largo explicando que **ya la habían arreglado
antes** por este mismo síntoma: buscaba `search=Prueba`, se le llenaba la página
y cambiaron a buscar por su marca propia. El arreglo no podía funcionar, porque
la búsqueda no buscaba. Solo movió el umbral: esta noche, con 55 ausencias de
prueba acumuladas y fecha posterior, se volvió a cruzar.

Ahora busca por nombre, apellido y motivo, con el buscador sin acentos que el
proyecto ya tenía. Dos pruebas de backend, una de ellas roja sin el arreglo.

La interfaz no se veía afectada: filtra en el cliente. Quien lo sufría era quien
leyera el esquema --- o sea, un integrador.

**Y queda una deuda de la suite anotada**: `limpiarAusenciasDePrueba` no se lleva
las que quedaron aprobadas, porque una aprobada no se puede cancelar. Por eso se
acumulan tanda tras tanda. Con la búsqueda arreglada ya no rompe nada, pero la
base de desarrollo sigue engordando.

942 pruebas de backend en verde.

### Vuelta 53 --- Una identidad, dos empresas (25/08)

`users/models.py`. `oidc_sub` llevaba `unique=True` a secas, y eso contradice lo
que la propia clase declara dos campos más arriba para el correo: único **por
empresa**, «porque una persona puede trabajar para dos empresas, y en un sistema
pensado para integradores multiempresa eso deja de ser un caso raro».

Un grupo con dos sociedades en el mismo OTT y un solo proveedor de identidad: la
primera da de alta a Rosa con `azure|abc123` y la segunda ya no puede. Y lo que
recibía su conector no era un rechazo, era un **500** --- exactamente lo que el
docstring de `_refuse_collisions` dice que hay que evitar, porque un conector no
puede reaccionar a eso. Ahora la restricción lleva la empresa, y el choque dentro
de una misma empresa sale como `identity_taken`, que sí se puede leer.

**Y el campo pasa de `NULL` a cadena vacía**, que es la convención de esta clase
---`employee_id` ya lo hacía--- y lo que la restricción parcial necesita para
excluir a quien no tiene identidad federada. Ruff lo pedía en cuanto se quitó el
`unique`, y coincidía con lo que el propio proyecto ya hacía.

**La migración va en tres pasos, y el orden no es un detalle.** Vaciar los nulos
con el índice único todavía puesto choca en la segunda fila, porque todas pasan a
valer lo mismo. Primero se quita la unicidad global, después se rellenan, y solo
entonces el campo pasa a NOT NULL. Comprobado contra la base de desarrollo, que
tenía **279 filas con NULL sobre 280**: la primera versión se caía ahí.

940 pruebas de backend en verde.

### Vuelta 52 --- Diez segundos para diez megas (25/08)

`services/api.js`. El plazo de axios era de diez segundos para todo, y la
pantalla de ausencias anuncia «PDF o foto, hasta 10 MB». Ese límite solo se
cumplía si la subida iba a más de 8 Mb/s sostenidos; por debajo ---o sea, en un
móvil en la calle--- axios abortaba **con el cuerpo ya enviado**. El servidor
creaba la solicitud con su justificante y en pantalla salía «No hay conexión con
el servidor», con el diálogo relleno como si no se hubiera mandado nada. La
persona se iba creyendo que no había pedido el permiso mientras su responsable lo
veía en la cola.

Ahora el plazo sale del peso: diez segundos más un segundo por cada 128 KB, que
es una subida de 4G **mala** y no una buena, porque el plazo tiene que aguantar el
peor caso razonable. Ocho megas dan 74 s y diez dan 90; una petición de solo
texto sigue en diez.

Y como este es el tercer sitio donde lo mismo mordía, el aviso compartido
`ErrorNote` dice ahora, cuando el código es `timeout`, que puede haberse
guardado y que se compruebe antes de reenviar. Es la misma idea de la vuelta 50 y
aprovecha el código que se separó allí.

**Sin prueba propia, y queda dicho.** El plazo sí la tiene ---comprueba que ocho
megas pasan de sesenta segundos y que sin fichero no se alarga---. El añadido a
`ErrorNote` no: todas las pantallas que lo usan exigen rellenar un formulario
entero con la red interceptada, y tras tres intentos por caminos distintos
---diálogo de ausencias, Ajustes, pantalla de fichar, que tiene aviso propio y no
usa `ErrorNote`--- no compensaba seguir. Si alguien lo retoca, no hay red debajo.

### Vuelta 51 --- La jornada de quien no trabaja la entera (25/08)

`absences/usage.py`. Cuando no hay turno en el cuadrante, la jornada de
referencia salía de la **semana de la empresa entre cinco**, sin preguntar qué
tiene pactado esa persona. Para quien trabaja veinte horas a la semana ---cuatro
al día--- eso son ocho, y el error se movía en las dos direcciones a la vez:

- **Le negaba horas que le corresponden.** Seis horas de búsqueda de empleo
  (art. 53.2): se ausenta un día suyo, cuatro horas, y el producto contaba ocho.
  `used=8`, `allowance=6`, `over=True`. Quien aprueba ve que se ha pasado de un
  permiso legal habiéndose ausentado 4 de las 6 horas a las que tiene derecho ---
  durante un preaviso de despido objetivo, que es justo cuando hacen falta.
- **Y le concedía de más a la empresa sin que se entere.** Cuatro días laborables
  de fuerza mayor familiar (art. 37.9), que el artículo cuenta en horas: cinco
  ausencias de cuatro horas ---cinco jornadas suyas, una de más--- salían como
  2,5 días. El doble de lo que el artículo obliga.

Ahora sale de `agreed_hours`, con el matiz que ese método ya documenta: solo una
cifra **semanal** se convierte en día dividiendo entre cinco. Una anual no es una
semanal por 52, así que ahí sigue valiendo la semana de la empresa como mejor
suposición disponible, y el `estimated=True` sigue diciendo que lo es.

Tres pruebas, dos rojas sin el arreglo, y la tercera es el contraste: a jornada
completa la referencia sigue siendo la empresa.

938 pruebas de backend en verde.

### Vuelta 50 --- Los dos de la red, que eran el mismo error (25/08)

Los dos hallazgos altos que quedaban, los dos de la lente «pérdida de trabajo», y
al arreglarlos resultó que son la misma equivocación en dos sitios: **tratar «no
me han contestado» como si fuera un hecho conocido.**

- **El refresco que tropieza** (`services/api.js`). Un `catch { tokens.clear() }`
  trataba cualquier fallo de la renovación como sesión caducada. Un 502 del
  balanceador a medio desplegar, un 429 de la cubeta que comparte una oficina
  detrás del mismo NAT o el wifi parpadeando no dicen nada sobre el refresco, que
  dura siete días. Quien llevaba cinco minutos rellenando un alta se iba a la
  calle con el formulario perdido, y encima se destruía un testigo bueno: ni
  recargando volvía dentro. Ahora solo se cierra si el servidor lo rechaza.

  **Y ahí saltó un detalle que solo se ve probando**: la prueba que ya existía
  ---«una sesión rechazada de verdad sí lleva a entrar»--- se puso roja. Este
  servidor **no contesta 401 a un refresco malo**: lo trata como regla de
  negocio y sale con **409 `session_expired`**. Mirar solo el estado dejaba fuera
  el caso legítimo. Se comprueba por código, que es explícito.

- **El aviso de la pantalla de fichar** (`pages/Clock.jsx`). Decía en negrita «No
  se ha registrado nada. Vuelve a pulsar cuando tengas cobertura.» ante cualquier
  fallo sin respuesta. Pero sin respuesta hay dos casos y axios los distingue: la
  petición que **no salió** ---y ahí la frase es verdad y hace falta--- y la que
  salió y cuyo plazo se agotó a los diez segundos, donde el servidor ha podido
  registrarla perfectamente.

  Afirmar lo segundo era, además, lo que provocaba el daño: la persona vuelve a
  pulsar, han pasado más de diez segundos, la guarda del doble toque cubre cinco,
  y entra una **salida** encima de la entrada. La jornada legal queda en unos
  segundos y deshacerlo exige el art. 4.b con el acuerdo de las dos partes.

  Ahora el plazo agotado tiene código propio y su propio aviso: «Puede que sí
  haya quedado registrado. Mira abajo antes de volver a pulsar.» Y la pantalla
  pregunta sola por el día, así que si quedó registrado la respuesta aparece en
  un segundo sin que nadie toque nada.

Dos pruebas nuevas en los ficheros que ya cubrían cada zona, las dos contrastadas
contra el código sin arreglar.

### Vuelta 49 --- La marca que no se movía (25/08)

`common/models.py`. `auto_now` promete que `updated_at` se pone al guardar, y
con `update_fields` no lo cumple: Django la fija en la instancia y **no la
escribe**, porque no está en la lista. La fila queda cambiada con la marca de
antes, en silencio, y leyendo el código no se ve ---
`save(update_fields=["is_active"])` parece completo.

Aquí decide si una integración funciona. `/api/app/people/?since=` avanza por
`updated_at`, así que una baja hecha desde el panel no la veía nunca un conector:
seguía teniendo por activa a alguien que ya no lo está, la mantenía en sus
cuadrantes y le mandaba fichajes que OTT rechaza con `employee_inactive` sin que
nadie mire esos errores.

**Arreglado en la raíz y no en el sitio.** El barrido encontró **siete**
`save(update_fields=…)` sin la marca, en cinco ficheros. Parchear el del hallazgo
habría dejado los otros seis y el octavo se escribe igual de fácil, así que
`BaseModel.save` la añade siempre. Tres pruebas, dos de ellas rojas sin el
arreglo, más una sonda que vigila que ese método siga existiendo.

**Y una prueba que pasaba con el fallo delante.** La primera versión comprobaba
la baja pidiendo `?since=<cursor>` y buscando a Rosa en la respuesta. Aparecía
igual: el cursor filtra con `>=` para no perder dos cambios del mismo instante,
así que reenvía la última tanda entera. Verde, y sin comprobar nada. Ahora mira
la marca en la fila.

**Observación, no arreglo**: la respuesta de `/api/app/people/` no trae el
`updated_at` de cada persona, solo el `next_since` global. Basta para avanzar el
cursor y no basta para diagnosticar por qué una persona no llega. Sin tocar.

**Y la comprobación de formato, que no podía dar limpia.** No había
`.prettierignore`, así que `prettier --check` revisaba las sesiones que genera
Playwright ---fuera del control de versiones--- y salía en rojo pasara lo que
pasara. Seis vueltas anotándolo como «deuda previa» sin mirar por qué. Con el
fichero puesto, los once ficheros de código que quedaban sin formatear se
formatean y la comprobación queda limpia de verdad.

935 pruebas de backend en verde.

### Vuelta 48 --- Lo que la sonda de móvil no miraba (25/08)

Encadenada con la 47 y en la misma lente. Empezó buscando dónde estaba la sonda
de desbordamiento antes de escribir otra, y ahí salió lo primero:
`29-en-el-movil.spec.js` **ya existía**, medía a 390 px y su cabecera decía que
«ninguna otra pantalla se sale». Miraba once de diecisiete.

De las seis que faltaban, **una estaba rota**: el Calendario del equipo se salía
22 px. La rejilla estaba bien resuelta ---`overflowX: auto` con `minWidth`, que
es lo correcto--- y el culpable era la barra de meses: un `Stack direction="row"`
**sin `flexWrap`** con tres botones, el nombre del mes con sus 190 px y dos
filtros de 160. Más de 630 px de ancho mínimo en una fila que no se parte y no se
encoge. Ahora se parte en tres líneas.

Las diecisiete están en la sonda.

**Y de mirar la pantalla arreglada salió otra**: el rótulo decía «Agosto **De**
2026». `text-transform: capitalize` sube cada palabra, que en inglés es lo que se
quiere y en castellano no. Estaba en tres pantallas (Calendario, Cuadrante y Mi
jornada, esta última con «Lunes, 25 **Ago**»). Resuelto en el idioma y no en la
hoja de estilos, con `capitalised()` en `format.js`: en catalán y gallego pasa lo
mismo y los meses ingleses ya vienen en mayúscula de fábrica. Cero
`textTransform: 'capitalize'` en el proyecto.

De propina, dos pantallas reimplementaban `monthName`, que también estaba ya en
`format.js`. Ahora lo usan.

Tres pruebas nuevas en el mismo fichero, que es donde tenían que ir.

### Vuelta 47 --- Con el navegador de verdad, y en un teléfono (25/08)

Primera vuelta con la extensión de Chrome en vez de Playwright. La diferencia
salta a la vista: **la suite mira el `h1`, y los dos fallos de esta vuelta
estaban en lo que la suite no mira.**

- **La cabecera decía «Resumen» en las trece pantallas de gestión.**
  `AppShell.jsx`. `currentLabel` hacía un `find` sobre las rutas del menú, y
  `/panel` es prefijo de todas las demás, así que ganaba siempre la primera que
  casa. Es **el mismo fallo que `navigation.jsx` documenta y resuelve** con
  `end: true` para el resaltado del menú; un piso más arriba se ignoraba. Ahora
  respeta `end` y se queda con la coincidencia más larga.

- **Diez de las doce pantallas de gestión no se podían alcanzar desde un
  teléfono.** La barra lateral solo existe de `md` para arriba, la de abajo
  lleva a las cuatro pantallas propias más «Resumen», y no había botón de menú.
  Las rutas funcionaban tecleadas; desde el Resumen solo se enlazan dos
  (`/panel/personas` y `/panel/decisiones`). Un responsable un lunes no podía
  abrir «Por decidir» ni el cuadrante.

  Lo llamativo: **media pieza ya estaba escrita.** `NavSection` acepta un
  `onNavigate` que usa en el `onClick` de cada entrada, y nadie se lo pasaba
  nunca --- solo tiene sentido en un cajón que se cierra al elegir. Faltaba el
  cajón. Ahora hay botón de menú fuera de escritorio, cajón temporal con el
  mismo menú, y `onNavigate` haciendo lo que esperaba.

  El `BottomNav` se queda como estaba: sigue valiendo como acceso rápido. Su
  docstring dice que gestión colapsa a una entrada «que es a donde va quien
  gestiona desde el móvil», y eso era cierto salvo por las diez pantallas que
  dejaba fuera.

Prueba en `e2e/40-desde-el-movil.spec.js`: recorre las trece pantallas desde el
menú en 390×844, comprueba que el cajón se cierra al elegir, que a un operario no
se le ofrece, y que la cabecera dice el rótulo de cada pantalla. Contrastada
contra `HEAD`: dos de sus comprobaciones se ponen rojas.

**Y una petición de Francisco atendida por el camino**: la opción seleccionada
del menú se veía como una píldora. `borderRadius: 1.5` se multiplica por el
`shape.borderRadius: 10` del tema, o sea 15 px sobre una fila de 40. Bajado a
0.6. De propina, el redondeo se comía los extremos de la regla izquierda, que es
justo lo que el comentario de al lado dice que tiene que verse a pleno sol.

**Lo que enseñó el método**: los rótulos del menú y los títulos de pantalla no
coinciden en tres casos (Centros / Centros de trabajo, Calendario / Calendario
del equipo, Ajustes / Ajustes de la empresa). Escribí la prueba dándolos por
iguales y falló. El inventario real del DOM no es un paso opcional.

252 pruebas de navegador y 932 de backend en verde.

### Vuelta 46 --- Lo que hace un conector, escrito (25/08)

`tenants/people_api.py`. Una aplicación integrada daba de alta a una persona, le
cambiaba el correo ---que es su identificador de acceso--- y la daba de baja
---y desde ese momento `register_punch` la rechaza---, y en la pantalla de
auditoría no había ni una línea. Ni quién, ni cuándo, ni qué había antes. El
`changes={"before": ..., "after": ...}` que el propio código construye para saber
qué pisó el conector se tiraba a la basura.

La causa no estaba en la vista sino en el encaje: `record()` deduce la empresa
del actor, y aquí no hay actor **a propósito**, porque quien escribe es una
aplicación y no tiene fila en `users`. Sin empresa, la entrada no se puede
acotar, así que `record()` la descarta con un `log.warning`. Todo sale bien, la
respuesta es 200, y el rastro se queda vacío. Es la peor forma de fallar que
tiene esta tabla: lo que se pierde solo se echa de menos el día que alguien
pregunta quién cambió algo.

Arreglo de una línea en cada sitio ---`company=company`, que es el caso para el
que existe el parámetro--- con dos pruebas de comportamiento. La segunda hubo
que reescribirla: comprobaba el aislamiento preguntándole al manager, y
`AuditLog` **no** es un `TenantOwnedModel` a propósito (su docstring lo dice: el
acotado lo hace el ViewSet). Preguntar al manager no demostraba nada. Ahora va
por `/api/audit/`, que es por donde se lee de verdad, y comprueba primero el caso
que sí debe traer algo: sin eso, un cero en la empresa de al lado no distingue
«bien acotado» de «la entrada nunca se escribió».

**Y una sonda permanente**, en `audit/tests/test_toda_entrada_sabe_de_quien_es.py`.
Lee el árbol de sintaxis de las 40 llamadas a `record()` del código de producción
y exige que las que pasan `actor=None` lleven `company=`. Lleva su propio
contraste ---que encuentre más de veinte llamadas--- porque una sonda que no ve
nada pasa siempre. Validada contra la versión de `HEAD`: señala las dos líneas
exactas, 313 y 345.

El barrido dice que eran las dos únicas del proyecto.

932 pruebas de backend y 249 de navegador en verde.

### Vuelta 45 --- El fichero se va con su fila, y los puertos que nadie seguía (25/08)

**El justificante huérfano** (`absences/models.py`). Retirar una solicitud
borraba la fila y dejaba el fichero en el almacén para siempre, sin nada que lo
apuntara: ni fila, ni pantalla, ni comando. Un justificante es a menudo un dato
del art. 9 del RGPD, y quien retira su solicitud está diciendo justamente que no
quiere que se quede; la empresa no podía atender una supresión (art. 17) ni
cumplir su plazo de conservación (art. 5.1.e) porque no sabía que existía.

Dos decisiones del arreglo, y ninguna es de estilo:

- **`post_delete`, no `Absence.delete()`.** `QuerySet.delete()` no llama al
  método del modelo, así que el borrado en masa ---una purga por retención, una
  empresa que se va--- se saltaría la limpieza justo cuando más ficheros hay en
  juego. La señal la reciben las dos vías, y hay prueba de las dos.
- **Dentro de `on_commit`.** Borrar antes de confirmar deja, si algo revierte la
  transacción, una fila viva apuntando a un fichero que ya no está: la pantalla
  ofrece una descarga que falla y nadie sabe por qué. Eso es peor que el problema
  que arregla.

Cuatro pruebas, contrastadas con la señal neutralizada: tres se ponen rojas. El
contraste hizo falta de verdad, porque las pruebas necesitan
`django_capture_on_commit_callbacks` ---dentro de un test nada confirma nunca---
y sin él habrían estado comprobando lo contrario de lo que buscan.

**Y un hallazgo que salió al mover los puertos, que es como se encuentran estas
cosas.** Francisco levantó la pila en 3010/8100 para que no chocara con Geosian,
usando las variables que el compose declara para eso mismo. No se podía entrar.
La pantalla decía **«No hay conexión con el servidor»**, que apunta a cualquier
sitio menos al culpable:

- `CORS_ALLOWED_ORIGINS` estaba escrito a mano con el 3000. El compose se
  parametrizó expresamente para convivir con otra pila y CORS no seguía esa
  parametrización, así que usar la opción documentada dejaba la aplicación
  inservible. Ahora el valor por defecto de desarrollo sale de `OTT_PORT_WEB`, y
  el `.env.example` documenta las cuatro variables de puerto y lo que cuelga de
  cada una.
- **La suite de navegador tenía la API a fuego en el 8000, en cinco sitios.**
  `baseURL` sí era parametrizable; la API no. Y el síntoma no era «no encuentro
  la API»: era un `null` en el almacén durante el arranque de sesión, con los 244
  tests restantes sin correr. Ahora sale de `OTT_API_URL`, junto a `OTT_URL`.

Los dos son el mismo defecto: **una opción de configuración que el propio
repositorio ofrece y que, al usarse, rompe el sistema con un mensaje que engaña.**

**Nota de entorno, no del producto.** Al recrear la API para que releyera el
`.env` ---se lee al **crear** el contenedor, no al reiniciarlo--- desapareció
`pypdf` y la recogida de pruebas se interrumpió entera. Estaba declarado en
`requirements/dev.txt`; lo desfasado era la **imagen**, construida antes de esa
línea. Con `podman compose build api` vuelve. Merece la pena saberlo porque el
síntoma es un `ModuleNotFoundError` en un fichero que nadie ha tocado, y porque
significa que la suite llevaba tiempo corriendo sobre dependencias que no eran
las declaradas.

249 pruebas de navegador en verde en 3010/8100, 928 de backend en verde.

### Vuelta 44 --- La clave de idempotencia, obligatoria (25/08)

Cierra el hallazgo abierto que dejó la 43. Se decidió mirando el dato en vez de
sopesando: **no hay contrato que romper.** Cero llamadas a
`/api/punches/delegated/` en todo `~/Projects/geosian` fuera del propio OTT, el
`ott_client` es la pieza 6 del plan de integración y estamos en la fase 1, y el
propio plan describe esa pieza como «cliente HTTP con la credencial de
aplicación, **reintentos y cola local** para cortes». O sea que el único conector
previsto va a reintentar por diseño contra una puerta que no lo toleraba.

- `Idempotency-Key` pasa a ser obligatoria. Sin ella, `400
  idempotency_key_required`, que es un código sobre el que una máquina puede
  ramificar. Una cabecera en blanco cuenta como ausente: parece que el conector
  hizo su parte y no la hizo.
- Excepción nueva `IncompleteRequest` en `common/exceptions.py`, hermana de
  `BusinessRuleError` y con su misma interfaz. La distinción que ya documentaba
  aquélla pedía la otra mitad: 409 es «está bien formado y no se puede hacer»,
  400 es «le falta algo». Y lo que falta no tiene por qué ser un campo ---aquí es
  una cabecera---, así que la validación por campos de DRF no servía.
- Al actualizar las pruebas, el helper `as_application` genera una clave distinta
  por llamada. Tres pruebas hacían varios fichajes con el mismo cliente y había
  que darles clave por evento; la de pasar la tarjeta dos veces la lleva
  **distinta a propósito**, porque son dos pasadas y no un reintento: lo que
  tiene que frenar la segunda es la guarda del doble toque, que es lo que esa
  prueba comprueba.
- Documentado donde lo va a leer quien programe: el esquema OpenAPI, el manual
  (§14, «Lo que hay que decirle a quien programe el terminal») y la pieza 6 del
  plan de integración, con el detalle que se olvida: **si el conector encola, la
  clave se genera al entrar en la cola, no al desencolar**, o cada reintento
  traería una nueva y no protegería de nada.

Y de propina, el instrumento con el que la 43 dio por buenos los catálogos estaba
roto: contaba como vacía toda traducción de varias líneas, porque un `msgstr`
multilínea empieza siempre por `msgstr ""`. Con el detector arreglado, el
castellano tenía 2 huecos de verdad ---no 128--- y son de la vuelta 13. Cerrados.

924 pruebas de backend en verde.

### Vuelta 43 --- Lo que falsea el asiento (25/08)

Pasada de arreglo, no de búsqueda: con trece hallazgos abiertos, seguir mirando
con lentes nuevas acumula en vez de converger. Los cuatro elegidos son los que
hacen que **lo guardado no diga lo que pasó**, que es lo único que este producto
promete.

- **La pausa descontada contra el convenio** --- `reports/services.py:279`.
  `build_day_status` preguntaba por `break_counts_as_work` y `build_report` no,
  así que el mismo día se leía 8 h en pantalla y 7 h 45 en el PDF, el CSV y el
  resumen de nómina. Los tres salen de `build_report`, así que el arreglo los
  cubre a la vez. Dos pruebas: la del convenio que sí lo cuenta y la del valor
  por defecto que no, y las dos comparan contra la cifra de la pantalla en lugar
  de contra una constante ---que es lo que fija la promesa: **las dos lecturas
  del mismo día tienen que coincidir**---.

- **La corrección que corrompía lo que corregía** --- `punches/corrections.py`.
  `_create` levantaba el sustituto con siete campos, así que un MODIFY perdía
  `interval`, `work_mode`, `hours_nature`, `overtime_settlement`,
  `force_majeure` y `flexibility_measure`. Corregir el final de una pausa la
  convertía en trabajo: el día quedaba `ON_BREAK` para siempre y con 0 h. Ahora
  hereda del fichaje al que sustituye. En un ADD no hereda nada, a propósito:
  nadie declaró esos hechos nunca.

- **`proposed_type` sin validar** --- `punches/correction_views.py`. `CharField`
  sin `choices`, columna sin CHECK y `save()` sin `full_clean()`: `"in"` en
  minúsculas entraba con 201, se aprobaba con 200, mandaba los dos correos de
  conformidad y dejaba el día en cero, porque ningún lector reconoce ese valor.
  Comprobado en `request_correction`, que es **la puerta única** ---
  `propose_correction` pasa por ella---, y en el serializer para que el cliente
  reciba un 400 con el campo señalado en vez de un rechazo genérico.

- **El fichaje delegado sin clave de idempotencia** --- `punches/delegated.py`.
  Un conector cuyo 201 se pierde reintenta, y como el tipo se deduce del estado,
  el reintento no repetía la entrada: grababa una **salida**. Nueve horas de
  jornada quedaban en treinta segundos, y deshacerlo exige el art. 4.b con el
  acuerdo de las dos partes. Ahora acepta `Idempotency-Key`: el reintento
  devuelve el mismo fichaje con 200 y no graba nada. La clave se reserva
  **antes** de escribir, así que dos reintentos simultáneos no pasan los dos.
  Vive en `DelegatedPunchReceipt`, fuera del fichaje: es un dato de la
  integración, no de la jornada, y nada que invente un integrador debe llegar al
  informe de Inspección.

  **La clave es opcional, y eso es una decisión a medias que hay que cerrar.**
  Exigirla rompería cualquier integración escrita contra el contrato de hoy ---
  el plan de Geosian entre ellas--- y eso es decisión de producto. Pero un
  conector que no la mande sigue expuesto al mismo fallo. Sin release publicada,
  éste es el momento barato de hacerla obligatoria; después es incompatible.
  **Preguntarlo antes de tocar nada.**

Y tres que salieron al dejar la suite de navegador en verde, ninguno buscado:

- **`06-correcciones` fallaba solo en paralelo.** El helper daba por hecho que su
  segundo fichaje sería una salida, y otro spec dejaba al operario con la jornada
  ya cerrada. En serie pasa. No se ha tocado: es fragilidad de la prueba ante el
  estado compartido, anotada aquí para que la siguiente vuelta no la persiga como
  si fuera del producto.
- **El contador de las pestañas de «Por decidir» mentía por encima de 99.** El
  `Badge` de MUI corta ahí por defecto, así que una cola de 125 se pintaba «99+»
  mientras el Resumen decía 125: dos pantallas de la misma aplicación contando lo
  mismo y diciendo cosas distintas. Es el mismo pecado que ya documentaba
  `cuantasHay` un piso más abajo ---«redondear a la baja es peor que no
  ponerlo»--- solo que un piso más arriba. `max={999}` en las cinco.
- **Cuatro botones «Corregir» que se oían idénticos.** El rótulo accesible
  llegaba hasta el minuto, y una persona puede tener cuatro fichajes dentro del
  mismo minuto. Ahora dice si es entrada o salida y la hora al segundo, que
  distingue siempre porque la guarda del doble toque no deja dos eventos a menos
  de cinco segundos.

**Deuda que esta pasada destapó y no cerró:** `makemessages` llevaba sin correrse
lo suficiente como para que 21 cadenas del código no estuvieran en ningún
catálogo. Al extraerlas, rellenó 14 por parecido y las marcó dudosas: ninguna
decía lo que dice su original ---«Changed what a leave grants» salió como
«Cambiar la hora de un fichaje»---. En castellano se han traducido las 16 que
faltaban y corregido las 14; en catalán y gallego se han **vaciado** las 10 de
cada uno, porque una traducción falsa marcada dudosa es una trampa para quien
limpie los marcadores después, y medio idioma en un producto que explica
obligaciones legales es la decisión que ya se tomó con el euskera. Quedan para
traductor nativo, 31 huecos nuevos y 477 en total. El castellano quedó sin
ninguno en la vuelta 44. Y `prettier` señala 16 ficheros del frontend sin formatear,
quince de ellos anteriores a esta pasada.

Estado al cerrar: **923 pruebas de backend y 249 de navegador en verde**, ruff,
eslint y prettier limpios sobre lo tocado, sin migraciones pendientes, catálogos
compilando.

### Vuelta 42 --- Lo que cambia datos sin decir quién (14/08)

El rastro de actividad es de lo que este producto vende, y estaba lleno para
unas cosas y vacío para otras. Barrido de las 58 operaciones de escritura: 25
con `record()`, 33 sin.

La mayoría de las 33 están bien así, y conviene dejarlo escrito para que nadie
las «arregle» luego: entrar, salir, renovar sesión y recuperar contraseña son
mecánica de sesión; el fichaje **es** el registro y auditarlo duplicaría la
tabla; las preferencias del móvil son del móvil. Seis gaps de verdad, todos del
mismo tipo --- **cosas que se configuran una vez, nadie mira, y el día que los
números no cuadran hay que reconstruir por qué**:

- **El cuadrante.** `assign`, `paint` y `clear` podían repintar o **vaciar** un
  mes entero de toda la plantilla sin que constara nadie. Y el cuadrante es
  contra lo que se comparan los fichajes.
- **El catálogo de permisos.** Bajar el de matrimonio de 15 días a 10 cambia el
  derecho de todo el mundo. Se anota **desde qué cifra**, que es la mitad que
  importa: el convenio puede haber mejorado la legal, y bajarla después no se
  distingue de corregir una errata.
- **Centros, departamentos, turnos-tipo y festivos.** El armazón contra el que
  se mide el registro. Un centro lleva la **zona horaria**: cambiarla mueve el
  límite del día de toda su gente sin tocar ni un fichaje. Un festivo decide qué
  cuenta como laborable, y de ahí sale el saldo de vacaciones.

Una entrada por operación y no por turno: pintar un mes a veinte personas son
seiscientas filas, y seiscientas entradas idénticas no son un rastro, son ruido
que entierra el resto. Y solo si cambió algo de la lista: un rastro que anota
cada pulsación de «Guardar» es uno que nadie lee.

**La parte que va a durar es la sonda.** Un endpoint que cambia datos y no deja
constancia no rompe ninguna prueba ni se ve en la pantalla: solo se nota el día
que alguien pregunta quién lo hizo. Así que
`test_ninguna_escritura_nueva_nace_sin_rastro` recorre las escrituras del
proyecto y exige, para cada una, o un `record()` o una entrada en
`SIN_RASTRO_A_PROPOSITO` **con su motivo escrito**. Encontró las cuatro del
armazón después de que yo diera por cerradas las dos primeras.

**Y de camino, la tanda E2E completa.** El resumen entero decía 243 de 249, no
las «245 pasadas» que había leído en un `tail -4` truncado. Cuatro de
`06-correcciones` caían por agotamiento de la semilla: el ayudante tomaba
prestado un fichaje existente y la prueba de aplicar la anulación lo dejaba en
`is_active=false`, así que el fichero **pasaba una vez por base de datos**.
Ahora la prueba crea el fichaje que va a anular ---dos pulsaciones, que dejan a
la persona como estaba--- y aguanta dos pasadas seguidas. Las otras dos eran un
`ERR_CONNECTION_RESET` del contenedor, no del producto.

### Vuelta 41 --- Auditar la auditoría (14/08)

Después de encontrar dos pruebas que nunca se ejecutaban, la pregunta era cuánto
del verde es real.

**Tranquilizador, y conviene decirlo así: 166 pruebas E2E, cero sin aserción.
865 de backend, dos con la aserción implícita y una condicional.** Las suites
están sanas.

Lo que había: una aserción vacía de verdad ---`count() >= 0`, cierto siempre---
en la prueba del aviso de tope, cuyo propio comentario admitía que «no siempre
hay una que se pase» sin fabricar ninguna. Dos del backend apoyadas en «no
lanzar excepción», que es defendible pero pasaría igual si se quitara la
restricción que dicen probar. Y una condicional mía de esa misma mañana, cuyo
`if` era falso siempre.

Para la condicional la salida no fue escribir mejor el `if`: fue **traducir los
dos mensajes** al catalán y al gallego, que era lo que el producto necesitaba.

**Lo que más enseñó fue el método.** Cuatro instrumentos seguidos me dieron
resultados falsos: un regex que cortaba los cuerpos por la llave equivocada
(166 falsos positivos), otro que enganchaba el `({ page })` en vez del cuerpo,
un patrón que no veía `expect.poll(`, y una aserción mía que daba por hecho que
`User.objects` filtra por empresa. Los cuatro se cazaron igual: validando el
instrumento contra un caso que ya se sabía la respuesta, **antes** de creerse el
resultado.

### Vuelta 40 --- Qué hace la interfaz con los errores de la API (14/08)

El interceptor está bien hecho: normaliza a `{code, message, details, status}`,
renueva la sesión en un 401 y saca el `non_field_errors`. Y las pantallas
enseñan el mensaje, que **es lo correcto**: los mensajes están escritos con
cuidado y traducidos, y ramificar sobre los ochenta códigos del backend sería
peor producto. Eso no es un hallazgo por mucho que el número asuste.

Lo que sí lo es: hay una clase de error donde enseñar el mensaje no basta,
porque significa que **lo que hay en pantalla ya no es verdad**. Las treinta y
cuatro mutaciones hacían `onError: setError` y ninguna refrescaba.

El caso lo trajo el bloqueo de decisiones concurrentes de esa misma mañana: dos
responsables, uno resuelve, el otro pulsa y lee «ya está resuelta» con la fila
todavía en la lista. Vuelve a pulsar, mismo error, y la cola le miente hasta que
recarga. El propio código reconocía el escenario en el camino en lote.

Cuatro códigos, no todos los 409: refrescar en cualquier error traería la lista
entera cada vez que falta un campo, que es la mayoría de las veces. Hay prueba
de contraste.

**Nota de método**: la prueba finge la respuesta del servidor. Lo que cambió es
del navegador, y montar el caso de verdad dejaría una ausencia aprobada por
ejecución ---no se pueden borrar, a propósito---. Como la mutación va
interceptada, el servidor nunca la ve y el dato de prueba se retira limpio.

### Vuelta 39 --- Qué pone el informe que se entrega (14/08)

Había pruebas del PDF y comprobaban que empieza por `%PDF-` y que pesa más de
mil bytes. Nada leía su contenido, y es el documento de más peso del producto:
lo que el art. 34.9 obliga a poner a disposición de la Inspección.

El grueso estaba bien ---la cita del artículo, empresa, CIF, persona, periodo,
zona horaria, la tabla con el turno de noche en su día, el total y una huella---.
Faltaban tres cosas que el código **calculaba** y ningún renderizador imprimía:

**La discrepancia del art. 4.b.** `row.disputed` y `row.dissent` se calculaban y
los dos formatos los ignoraban: una corrección impuesta sobre la objeción de la
persona salía **exactamente igual** que una aceptada. El código lo tenía escrito
en dos sitios ---«it travels to the inspection report»--- y no viajaba.

**Las pausas y las esperas**, que el art. 3.d y el 3.g piden registrar
precisamente porque no computan como jornada. Se sumaban y no se imprimían.

**La huella no cubría nada de eso.** Su comentario ya decía el principio ---«están
en el documento, así que están en la huella»--- y se aplicaba a la mitad. Dos
informes del mismo periodo, uno con corrección impuesta y otro sin ella, daban
la misma huella.

Se añade `pypdf` a las dependencias de prueba: sin poder leer el PDF no había
forma de comprobar qué pone, y esa era la razón de que llevara así desde
siempre.

### Vuelta 38 --- Los correos (14/08)

Un correo no tiene petición detrás, así que no hereda idioma de ningún sitio
sensato. De los cuatro que manda el producto **solo uno lo activaba**: los
recordatorios de fichaje, cuyo comentario ya explicaba por qué. Los otros tres
fallaban de dos maneras distintas.

La invitación y los dos de correcciones los dispara otra persona desde su
sesión, así que salían **en el idioma de quien actuó**: una empresa castellana
pidiéndole conformidad a alguien que eligió catalán se la pedía en castellano, y
de eso va justo el art. 4.b. El restablecimiento de contraseña llega sin sesión,
así que caía a `LANGUAGE_CODE` dijera lo que dijera esa persona.

**Y el que más se nota: la invitación saludaba «Hola :».** `{% blocktranslate %}`
no resuelve accesos a atributos, así que `{{ user.first_name }}` dentro del
bloque se renderiza vacío. Las otras tres plantillas pasan un `first_name` plano
y salen bien; esta era la única con la forma que no funciona, y es el primer
mensaje que recibe cualquier empleado nuevo.

Llevaba así desde siempre porque **nada renderizaba estas plantillas**: las
pruebas comprobaban que el correo se manda y a quién, nunca qué pone.

La cuarta prueba es la que aguanta: comparar textos no sirve mientras los
catálogos estén a medias, pero sí se puede exigir que todo sitio que mande
correo active un idioma.

### Vuelta 37 --- Instalación desde cero (14/08)

Base de datos vacía de verdad, migrada de cero, y los primeros cinco minutos de
un cliente nuevo.

**Casi todo bien, y una parte con historia.** Los tres disparadores del rastro y
la extensión `unaccent` los pone la migración: aquel incidente en que faltaban
era del entorno, no del código. Sin deriva entre modelos y migraciones, y CI ya
lo comprueba.

El primer día funciona: se da de alta la empresa, recibe sus 32 permisos
sembrados y sus reglas con valores, `record-arrangement` dice honestamente que
no consta nada, y se puede fichar al momento. Ninguna pantalla revienta con cero
datos. Los festivos vienen vacíos y la pantalla lo dice con el camino para
traerlos.

**El hallazgo, pequeño y con causa interesante.** El catálogo de turnos paginaba
sin orden, y no por olvido: su modelo declara `ordering = ["name"]`. Lo que pasa
es que `annotate` con un agregado mete un `GROUP BY` y Django descarta la
ordenación por defecto en las consultas agregadas. La anotación se añadió para
decir cuántos días usan un turno antes de borrarlo y se llevó el orden por
delante. Sin orden, la página 2 puede repetir filas de la 1 y saltarse otras.

La prueba mira **el aviso de DRF** y no el código: buscar `order_by` en los
`get_queryset` habría dado limpio, porque el problema es lo que Django hace
después. Una de doce listas.

### Vuelta 36 --- Cómo escala con el tamaño de la plantilla (14/08)

Solo dos ficheros del proyecto medían consultas, y eran los dos arreglados esa
misma mañana. El resto de la API no tenía ninguna cobertura de esto, y un N+1 no
se ve nunca en desarrollo: con tres personas de prueba son doce consultas y con
doscientas son dos mil, sin ningún aviso entre medias.

Barrido de catorce endpoints con 3 personas y con 12. Trece planos y uno que
crecía: **`/api/shifts/review/`, de 40 consultas a 130**. Es la pantalla que un
responsable abre para ver qué incumple su cuadrante, así que la empresa grande
es justo la que más la necesita.

Dos N+1 en el mismo endpoint. Los festivos, preguntados por persona cuando
dependen solo del centro. Y las reducciones de jornada, preguntadas por persona
**y por semana**.

Queda en 11 consultas, con tres personas y con doce.

La prueba compara en vez de fijar un tope: un número máximo se sube cada vez que
molesta, y «no puede crecer con la plantilla» o se cumple o no.

### Vuelta 35 --- El contrato publicado contra la realidad (14/08)

El producto vende su API de integración como funcionalidad, así que el esquema
OpenAPI **es** contrato. Primera vuelta hecha con un abanico de agentes: siete
dimensiones en paralelo, cada hallazgo con un refutador que intentaba tumbarlo.
57 propuestos, 39 sostenidos. Lo mío por mi cuenta coincidió con una dimensión
entera; las otras seis encontraron cosas que yo no vi.

**Solo contaba el camino feliz.** 200, 201, 204 y poco más: ni un 400, ni un
403, ni un 409 en 119 operaciones, y ningún componente que dijera qué forma
tiene un error. El peor hueco es el 409, que es como este producto rechaza por
regla de negocio: sin documentarlo, un cliente razonable lo trata como fallo
transitorio y reintenta en bucle algo que nunca va a salir. Tampoco se decía que
hay un `code` estable con el que ramificar, así que la alternativa era comparar
mensajes traducidos.

Va como gancho de posprocesado: los códigos se derivan de la operación, así que
la vista 120 nace documentada. Me equivoqué leyendo `security` al revés y el
esquema salió declarando un 401 en la pantalla de entrar; hay prueba que lo fija.

**Cinco operaciones decían no llevar cuerpo y lo leían.** La grave: cerrar
sesión. Sin cuerpo no invalidaba nada **y devolvía 204**, así que un cliente
escrito leyendo el contrato daba la sesión por cerrada mientras el token de
refresco seguía valiendo una semana. Su propio docstring dice «signing out
actually signs out».

**Cinco decían devolver una cosa y devolvían otra.** Entrar, alta y poner
contraseña se publicaban «sin cuerpo» y devuelven los tokens ---la primera
llamada de cualquier integración, y el contrato ni nombraba `access`---.
`auth/me` decía `User` y devuelve `{user, tenant}`. Y `roster`, `calendar` y
`pending` prometían el sobre paginado devolviendo un array, más filtros
heredados que nunca aplican: pedir el cuadrante de una persona devolvía el de la
plantilla entera, en silencio y con la forma correcta.

**Los ámbitos, la parte que existe para integrar.** Los seis se publicaban sin
tipo ni valores, y ninguna operación decía cuál pide. Ahora salen del enrutador
y **por método**: leer una ficha pide `read:people` y borrarla `write:people`, y
publicar el atributo de la clase habría dicho que con permiso de lectura se
puede dar de baja a alguien.

Quedan sostenidos y sin hacer unos veinte hallazgos más, casi todos respuestas
declaradas como objeto libre (`/api/app/attendance/`, `/api/punches/today/`,
`/api/absences/balance/`, la emisión de credencial) y filtros sin documentar en
auditoría. Ninguno rompe nada hoy; todos hacen que quien integre tenga que leer
el código.

### Vuelta 34 --- Responsable contra administración (14/08) · SIN HALLAZGOS

El cuarto corte de permisos, y el único que no estaba barrido. El de aislamiento
cubría sin sesión, entre empresas, y operario contra responsable; faltaba
responsable contra administración, que es una distinción real y con
consecuencias ---emitir la credencial de una aplicación es repartir una llave a
los registros de la empresa entera---.

**Salió limpio.** Veintidós operaciones de administración correctamente negadas
a un responsable y catorce de las suyas que sigue pudiendo hacer.

Lo que queda no es un arreglo, es la guarda. Una vista nueva con la clase de
permiso equivocada no se ve mirando la pantalla, porque el menú ya oculta lo que
no toca ---y ocultar un enlace no es un permiso---. La tercera prueba deriva del
código las rutas con control de rol y exige que cada una esté nombrada, así que
olvidarse rompe la construcción en vez de pasar en silencio. Ya cazó una:
`applications/scopes/`.

Validada saboteando un permiso a propósito: cambiando `IsAdmin` por
`IsManagerOrAdmin` en las aplicaciones, el barrido lo canta al instante.

### Vuelta 33 --- Lo que pasa cuando la entrada no es la esperada (14/08)

Tres ejes en una vuelta, porque los tres preguntan lo mismo: qué hace el
producto cuando lo que llega no es lo que esperaba.

**Rutas de error.** Sonda con basura en cada campo real de cada serializador,
1296 peticiones. Tres 500, y los tres del mismo tipo: código que asume una
cadena y corre **antes** de que valide nadie.

El peor es `POST /api/auth/token/` con `{"email": 12}`: sin sesión, alcanzable
desde Internet, y dentro de la función que existe para registrar los intentos
fallidos ---la forma de un ataque---. En vez de la línea del registro salía una
traza, justo con la entrada que más se parece a uno.

Los otros dos: `source_for` en los fichajes, y `reassign` en los turnos, escrito
ese mismo día.

Método: la primera versión mandaba diccionarios genéricos y dio 71 «basuras
aceptadas» que no eran nada, porque casi ninguna clave coincidía con un campo
real. Sacar los campos del propio serializador es lo que la hizo encontrar algo,
y además la hace crecer sola.

**Datos extremos.** Nombres en su longitud máxima ---100 en un departamento, 120
en un centro, 255 en una empresa--- y sin espacios. Rompían **tres** pantallas:
Departamentos se salía 719 px en el móvil, Centros 675, y Ajustes 1435. Una
línea en el tema las arregla las tres, y la novena pantalla que se añada nace
arreglada.

**Concurrencia.** Ninguna transición de estado estaba protegida: todas miraban
la copia en memoria. Dos responsables a la vez dejaban una ausencia en
`REJECTED` **con `approved_by` puesto**, y el rastro con una aprobación y un
rechazo de la misma solicitud. Vivía en ausencias, correcciones y
recuperaciones. Las horas extra se dejan como están: se pueden redecidir por
diseño.

### Vuelta 32 --- Las cinco decisiones de Francisco (14/08)

Cuatro hechas en el día. La quinta, la capa de i18n, sigue en «Hallazgos
abiertos» porque está en marcha.

**Las horas de un turno de noche cuentan en el día en que empieza.** La otra
mitad del turno de noche: las marcas ya salían bien y la atribución seguía
partiendo por la medianoche, así que esas ocho horas no aparecían en ningún
día. Ni en el estado, ni en el informe, ni en las extras, ni en la
conciliación. La regla y sus artículos, en `apps/punches/workday.py`. Lo que
**no** sigue la regla y queda separado: la nocturnidad, que se cuenta por la
franja 22:00-06:00 vaya al día que vaya.

De regalo: sin día, «la jornada de ahora» ya no es «hoy». A las tres de la
madrugada, quien entró a las 22:00 veía «sin empezar» en su propia pantalla.

**El tope de horas abiertas pasa a ser de cada empresa.** `max_open_hours` en
`WorkingTimeRules`, dieciséis por defecto, con su campo en Ajustes y su prueba
de punta a punta. Lo pidió Francisco por las guardias de veinticuatro horas
---bomberos, residencias, vigilancia---, donde dieciséis parte la guardia por
la mitad.

**La IP sale del rastro de auditoría.** Chocaba con la inmutabilidad de la
tabla: los tres disparadores rechazan UPDATE y DELETE, así que no había forma
de borrarla ni para atender una solicitud del art. 17. Se va la columna, se va
la lógica que decidía a quién enseñársela, y se va el parámetro `request` de
`record()`, que solo estaba para sacarla ---33 llamadas dejan de pasarlo---.

**Los topes de cuota salen del Core.** Y aquí me equivoqué al levantarlos:
`max_employees` **no** estaba muerto, se comprobaba de verdad al dar de alta.
Eso empeora el caso: una instalación propia podía negarse a añadir empleados
con un mensaje que no venía de ningún contrato.

### Vuelta 31 --- El idioma no se activaba en ninguna petición (14/08)

Salió al ir a montar el i18n del frontend y preguntarme cómo se resuelve hoy el
idioma. `LocaleAndTimeZoneMiddleware` colgaba todo su cuerpo de
`request.user.is_authenticated`, y la API autentica por JWT, que DRF resuelve
dentro de la vista. El middleware ve `AnonymousUser` **siempre**: ni idioma ni
zona horaria se activaron nunca.

La clase de dos más arriba tiene el diagnóstico escrito ---«for those the tenant
is set again by the permission class»--- y esta, escrita justo debajo con la
misma forma, nunca recibió el mismo trato.

Debajo había un segundo fallo independiente: la mitad de la empresa leía
`company.settings["language"]`, clave de un JSON que nada escribe nunca, cuando
el idioma vive en `Tenant.language`.

No saltó antes porque la web manda `Accept-Language` por su cuenta. Se rompía
donde no hay navegador: correos, tareas de fondo, integraciones.

**El aviso metodológico vale más que el fallo.** Escribí la prueba con
`force_authenticate`, que deja el `request.user` de Django sin tocar. Fallaron
las dos mitades, también la que yo daba por buena, y eso fue lo que destapó el
problema de fondo. Una prueba hecha desde la interfaz habría dado verde.

### Vuelta 30 --- El zoom del navegador (14/08)

Al 200 % en un portátil de 1280 la página cree que mide 640: por encima de los
600 en que MUI pasa las filas a horizontal, y por debajo de lo que hace falta
para que quepan. Personas se salía 60 px por la derecha y el interruptor de
«ver también las bajas» quedaba fuera de la pantalla.

Se fabricaba su propia fila de filtros en vez de usar `FilterBar`, y la suya no
llevaba `flexWrap`. Es la segunda mitad de un fallo ya conocido: esa misma
pantalla también se fabricaba su propio buscador, y por eso se quedó sin nombre
accesible cuando el común lo recibió.

### Fuera de vuelta --- La baja sin fecha (14/08)

De una pregunta de Francisco: ¿qué pasa si alguien deja la empresa con el
cuadrante ya hecho? Sondeado antes de contestar: **nada**. Los turnos futuros
seguían asignados y la revisión no decía una palabra.

La baja ponía `is_active = False` y nada más. La comprobación del contrato se
salta a quien no tiene fechas, que es toda la plantilla indefinida. Y el
cuadrante es contra lo que se comparan los fichajes, así que quien se fue iba a
salir como ausencia sin justificar todos los días.

Lo que faltaba no era una comprobación sino **una fecha**: `is_active` es un sí
o un no sin día. Ahora la baja escribe el último día que la relación cubre y la
comprobación que ya existía funciona sola.

**Vuelta 29 — El teclado. Nada roto, y una lección de método.**

El eje que quedaba de accesibilidad. Foco visible, diálogos que lo atrapan y lo
devuelven al botón que los abrió, y se llega al botón de fichar tabulando. **La
primera vuelta sin hallazgos.**

Lo que costó fue medirlo. Tres sondas seguidas dijeron que el foco era invisible
---no hay `outline`, no hay `box-shadow`, y añadir `Mui-focusVisible` a mano no
cambia el fondo--- y las tres se equivocaban. Comparando **píxeles** se acabó en
un intento. Van cuatro falsos positivos en dos días, todos por mirar el DOM en
vez de mirar lo que se ve.

**Vuelta 28 — Fichar sin cobertura.**

El escenario de campo del producto. El service worker no guarda cola a propósito
---la hora de un fichaje no se decide en el navegador, y está escrito en él---,
así que sin red no se ficha: eso está bien decidido. Lo que estaba mal era lo
que se decía. El aviso salía **en inglés** y no decía lo único que hace falta
saber: que **no ha quedado nada**. Sin esa frase, quien está en una obra ve un
aviso genérico y se va convencido de haber fichado.

De rebote, **la inicial del avatar era casi invisible en tema claro**: 1.75 de
contraste. No lo vio el barrido de la vuelta 26 y no es culpa del barrido ---
depende del dato: con nadie fichado la lista está vacía y el avatar no existe.
Salió al repetir la prueba con otra gente en pantalla, que es el argumento para
dejarlas puestas en vez de pasarlas una vez.

Y una prueba que se había quedado vieja sin que nadie lo notara: comprobaba el
aviso que el paginador sustituyó en la vuelta 22, y pasaba porque con menos de
cincuenta propuestas tomaba la rama del «no debe aparecer».

**Vuelta 27 — El idioma, y la tercera promesa imposible.**

Dos hallazgos, y el segundo ya es un patrón.

**Los ajustes ofrecían ocho idiomas** y solo hay catálogo de castellano. Elegir
«Catalán» dejaba el producto en castellano sin decir nada. Lo que sí conviene
saber ---y que la sonda aclaró--- es que **no caen en inglés sino en castellano**,
porque `LANGUAGE_CODE` es `es`: o sea que el daño era la promesa, no el
resultado. Quedan los dos que funcionan.

Y la misma pantalla decía **«cada persona puede usar otro distinto»** con el
campo en el modelo, en la API, y sin ningún sitio donde elegirlo. Es la tercera
vez: antes fueron «se puede adjuntar después» (v17) y «usa los filtros de arriba
para llegar al resto» (v22). Tres textos escritos describiendo lo que el
producto *debería* poder hacer en vez de lo que hace.

**Vuelta 26 — El tema oscuro, que nadie había mirado.**

Otro eje sin recorrer, de los que quedaron nombrados en la vuelta anterior. El
conmutador lleva semanas puesto y el oscuro no lo había visto nadie.

Dos colores de estado por debajo del mínimo: el verde de «Aprobada» en **3.26**
de contraste y el terracota de «Aplicada sin acuerdo» en **3.24**, contra el 4.5
que pide la norma. Y justo en los distintivos que dicen en qué estado está algo,
que es para lo que se miran.

La causa es de una línea: `primary` se aclaraba en oscuro y los otros dos se
habían quedado con el color del claro.

Lo que más enseña: **el del terracota no lo vio el barrido**. Su estado no
aparecía en ninguna de las pantallas recorridas; lo vio la cuenta, al mirar por
qué fallaba el otro. Un barrido encuentra lo que se cruza en el camino; el resto
lo encuentra entender la causa y preguntarse quién más está en el mismo caso.

Comprobado además que el modo claro no empeoró, que es lo fácil de romper al
tocar una paleta.

**Vuelta 25 — El móvil, que es donde se ficha y donde nadie miraba.**

Toda la suite corría a ancho de escritorio. Fichar se hace con el teléfono en la
mano, en una obra o en un portal, y esa anchura no la ejercitaba nadie: la misma
forma que el favicon que solo se veía con ventana.

**El producto aguanta bien**, y conviene dejarlo escrito porque no era evidente:
ninguna pantalla se sale, los diálogos caben con sus botones dentro (326 de 390)
y el botón de fichar mide 255×64 en la mitad inferior, donde llega el pulgar. Los
mandos pequeños que salieron ---30 px el conmutador de tema, 26 el paginador---
están por encima del mínimo de 24 que pide la norma, aunque por debajo de lo
cómodo; cambiarlos es una decisión de diseño y no un arreglo.

El único fallo era **mío y de la vuelta anterior**: el buscador de Personas pasó
al componente compartido, que fijaba el ancho en vez de ponerle un tope. 380 px
más el borde en una pantalla de 390. Un día de vida.

Y de rebote, la razón de que la suite entera saliera en rojo dos veces esta
semana: con doscientas pruebas a cinco peticiones cada una, **la suite agota el
cupo por hora de la cuenta que usan todas**, y lo que se ve no es un límite sino
la pantalla de entrar en mitad de otra prueba. `dev.py` ya resolvía esto para
pytest y dejaba fuera el caso del navegador.

**Vuelta 24 — Barrido de nombres accesibles: cinco sitios.**

Salió del tropiezo de ayer: la prueba de Permisos clicaba el conmutador de tema
porque los dos botones se llamaban «Cambiar». Lo que confunde a un localizador
confunde igual a quien navega con lector de pantalla, así que se barrieron las
catorce pantallas.

**47 botones «Corregir»** en Fichajes, 19 «Editar» en Personas, 7 en Turnos, 6
en Departamentos, y 7 «Eliminar» --- donde peor sienta equivocarse. Ninguno decía
de qué fila era.

Y el **buscador compartido no tenía nombre**: un `placeholder` no es una
etiqueta, desaparece al escribir y hay lectores que no lo anuncian. Con dos
detalles que costaron: el `aria-label` va en `slotProps.htmlInput` ---puesto en
el `TextField`, MUI lo reenvía al div de fuera y la sonda lo seguía marcando
después de «arreglarlo»--- y **Personas se fabricaba su propio buscador**, así
que se quedó fuera del arreglo del componente común. Ahora usa el compartido y
hereda el botón de vaciar, que allí tampoco había.

Ningún mando estaba mudo, que era lo que más miedo daba.

La sonda se queda como prueba de las catorce pantallas, contrastada quitando el
`aria-label`: tres pantallas en rojo.

**Vuelta 23 — La pantalla de permisos, y el diseño que no servía sin ella.**

Existía todo lo demás: el modelo con sus unidades y periodos, la siembra por
país, el endpoint completo, y hasta `createLeaveType` y `updateLeaveType`
exportados en el cliente. No había pantalla --- así que la mejora que trae un
convenio solo se podía aplicar por API, y **la decisión de copiar el catálogo en
vez de leerlo del marco legal, tomada justo para permitir esa mejora, no servía
para nada**.

Es la cuarta de la familia «la pieza existe y nadie la llama», y la más cara:
las otras tres eran un hueco; esta dejaba sin efecto una decisión de diseño
entera.

Se edita cuánto da, no de qué artículo sale. Vacío en «cuánto da» significa sin
tope ---«el tiempo indispensable»--- porque mandar 0 sería inventarse un límite
de cero. Y retirar un permiso solo lo quita de las solicitudes nuevas: uno cuyo
motivo deja de renderizarse es un registro que perdió algo.

De paso, un fallo de accesibilidad de cosecha propia: el botón decía «Cambiar» a
secas, y treinta y dos «Cambiar» seguidos no le dicen nada a quien navega con
lector de pantalla. Salió porque la prueba clicaba el «Cambiar entre claro y
oscuro» de la cabecera --- `name` en Playwright casa por subcadena.

**Vuelta 22 — El paginador de «Por decidir», y era peor de lo anotado.**

El cuaderno decía «a las que faltan solo se llega filtrando». Mirándolo: **los
filtros son en cliente sobre lo ya cargado**, así que el aviso ---«se muestran 50
de 137, usa los filtros de arriba para llegar al resto»--- proponía algo que no
podía funcionar. A las 87 restantes no se llegaba desde ninguna parte, y el
mensaje hacía creer que sí. Peor que no decir nada.

Y son **dos** colas, no tres: las ausencias pendientes, las horas extra y las
recuperaciones son acciones que devuelven la cola entera. Eso salió de mirar el
backend en vez de fiarse de la nota de hace nueve vueltas.

La selección se vacía al cambiar de página, porque las acciones en bloque actúan
sobre lo que se ve y arrastrar marcas de una página que ya no está delante es
cómo se aprueba algo sin haberlo mirado.

De paso, la prueba del Resumen que me había mordido dos veces: comparaba una
foto de la API contra la pantalla de después, en una base donde otra prueba
resuelve colas en bloque. Ahora relee las dos cifras juntas hasta que coincidan
--- lo que busca es un truncado, y un truncado no se arregla mirando otra vez.

**Vuelta 21 — Las horas extra: de 1449 consultas a 5, y el número que faltaba.**

Medio segundo en una empresa de veinte, y esto lo pide la pantalla de decisiones
cada vez que se abre. Ahora 48 ms.

Tres causas, y la primera es la que enseña algo. **482 consultas pedían las
mismas reglas de la empresa**: `for_company` hace un `get_or_create` cada vez y
se llama desde dentro de los bucles. Es una función que parece barata ---devuelve
una fila--- y aparece en todas partes; ahí es donde se esconden estas cosas.
**243 volvían a pedir un turno que el bucle ya tenía en la mano.** Y **241
traían los fichajes de un día**, que ahora salen de una vez.

Con el cuidado de siempre: el día es el de **su** centro y no el de la empresa.

Y lo que se abre al arreglarlo: el Resumen ya cuenta las horas extra con número.
Iban aparte y sin cifra justo porque contarlas era caro, y quedarse fuera de la
cifra grande era el fallo de la vuelta 2 en pequeño. Debajo se dice cuántas de
ellas son horas extra, con su plazo de cuatro meses, porque no es lo mismo una
solicitud que espera respuesta que unas horas que caducan.

**Vuelta 20 — La asistencia, de 73 consultas a 2.**

Las dos familias de barrido de la vuelta 19 no dejaron nada más, y las de
seguridad ya estaban cubiertas ---la suite adversarial cubre escribir *y* leer lo
ajeno dentro de la empresa---, así que esta vuelta va al hallazgo de rendimiento
que quedaba abierto desde la 6.

Medido en la empresa de desarrollo, 19 personas: **73 consultas y 27 ms**, casi
cuatro por cabeza. Ahora **2 y 3 ms**, y ya no crece con la plantilla.

Tres cosas, y la tercera solo se ve contando el SQL. `build_day_status` cuesta
dos consultas y ahora se le pueden pasar hechas. Los fichajes del día salen en
una sola para todo el mundo. Y `person.tzinfo` mira el centro, pero **el centro
sin zona propia cae en su empresa**: con `select_related("workplace")` seguía
habiendo una consulta por persona, la de la empresa del centro. La cadena tenía
un eslabón más de los que parece, y eso no se lee, se cuenta.

Lo que más costó fue la prueba. La primera versión medía el ayudante con una
lista que ella misma se traía bien, así que el `select_related` de la vista ---lo
que se estaba arreglando--- no lo tocaba nadie: pasaba igual antes y después.
Medida por el endpoint sí se pone roja con el código de antes.

**Vuelta 19 — Segunda pasada, barriendo las dos clases que ya dieron fallos.**

Dos barridos, uno por cada familia con antecedentes.

**Ajustes que nadie lee.** El de `roster_notice_days` en la vuelta 12 hacía
sospechar de más. No los hay: los veintinueve ajustes de empresa y de reglas
tienen lector. Solo quedan tres campos de cuota ---`max_employees`,
`max_admins`, `max_storage_mb`--- que nada aplica, y que ni siquiera están
expuestos: esquema muerto, arriba anotado.

La primera versión del barrido dio **todos muertos**, incluidos `weekly_hours` y
`daily_rest_hours`, que evidentemente se leen. Era un `grep -oP` sobre varios
ficheros, que antepone el nombre del fichero a cada resultado. Un barrido que
acusa a todo el mundo no es un barrido: se calibra mirando que lo conocido salga
donde debe.

**Cálculos que no sobreviven a la medianoche.** Aquí sí había uno, y es el mismo
supuesto que dejó el turno de noche sin cerrar: **la guarda del doble toque
miraba «los fichajes de hoy»**, así que pulsar a las 23:59:58 y otra vez a las
00:00:01 daba dos fichajes --- el día nuevo estaba vacío. Tres segundos entre uno
y otro, que es justo lo que esa guarda existe para evitar, y un turno que empieza
a las 00:00 es corriente donde se trabaja de noche.

Los demás sitios que acotan por día están bien, y conviene dejarlo escrito:
`timestamp__date` con USE_TZ convierte a la zona activa, que el middleware fija a
la de la empresa; y el gráfico del Resumen cuenta **eventos** y lo dice en su
propia documentación, así que partir una noche en dos días es correcto ahí.

**Vuelta 18 — Segunda pasada, con la comprobación al revés.**

Sin áreas sin tocar ni a medias, la vuelta se hace por técnica en vez de por
pantalla: coger lo que el backend ofrece y buscar **quién lo llama**. Es la que
salió de la vuelta 17 y cuesta dos minutos.

**Las setenta y dos rutas de la API tienen cliente**, salvo las tres de
integración externa, que es como debe ser. Ahí no había nada.

Al revés sí: seis funciones exportadas en `services/api.js` que ninguna pantalla
usa. Una era un fallo de producto --- **el resumen que acompaña a la nómina**.
Estaba entero en el servidor, con su periodo, sus cifras, su huella y su descarga
en PDF; su documentación dice «read for the person concerned»; y ninguna pantalla
se lo daba a esa persona. Quien lleva la nómina podía generarlos desde Informes y
quien trabaja no podía verlos --- con `generatePayrollSummaries` usada y
`getPayrollSummary` muerta, la una al lado de la otra.

Van tres fallos encontrados con la misma técnica en dos vueltas.

Y una prueba que **solo funcionaba la primera vez**: fijaba el tope de horas
extra en 72, y si una tanda anterior se cortó antes de restaurarlo, ya valía 72
--- nada que guardar, botón desactivado, treinta segundos de espera. Ahora elige
un valor distinto del que hay.

**Vuelta 17 — «Solicitar», y el tramo que faltaba. Última área a medias.**

**El justificante no se podía adjuntar.** La API lo aceptaba desde el principio,
el modelo lo guarda con sus validadores ---PDF o imagen, hasta 10 MB---, la lista
enseñaba un distintivo de «tiene justificante» y hay un endpoint para
descargarlo con su control de acceso probado. Y ninguna pantalla lo subía nunca.

Peor que el hueco: el propio diálogo prometía que «se puede adjuntar después», y
no se podía ni antes ni después. Todo el camino de vuelta montado menos la ida.

Es la misma forma que el catálogo de permisos de la vuelta 11 y que
`roster_notice_days` de la 12: **la pieza existe, está bien hecha, y nadie la
llama**. Tres veces en siete vueltas. Merece buscarse a propósito.

Con dos cuidados que no son cosméticos: nunca en una baja ---desde el RD
1060/2022 el parte no se le entrega a la empresa y el servidor rechaza el
fichero, así que ofrecerlo sería invitar a subir un dato de salud que no debe
estar--- y el fichero se olvida al cerrar el diálogo, porque adjuntar el
justificante de un permiso a la solicitud siguiente sería peor que no tenerlo.

**Vuelta 16 — «Pedir una corrección», y una lección cara sobre la base compartida.**

**La opción «la hora registrada no es la real» fallaba siempre.** El servidor
exige decir qué fichaje se corrige ---sin eso el consentimiento del art. 4.b no
significa nada--- y el diálogo no ofrecía dónde indicarlo: se recibía «Indica qué
fichaje se corrige» y ningún sitio donde hacerlo. La otra mitad, «olvidé
fichar», sí funcionaba, y por eso llevaba ahí sin verse.

Y un fallo de sesión que salió **de sufrirlo**: de tanto correr la suite en un
día se agotó el límite de peticiones por persona, y la pantalla de Ajustes se
volvió el formulario de entrada con la sesión buena guardada al lado. Media hora
buscando una regresión que no existía. En la vuelta 6 se arregló que el testigo
dejara de borrarse con un 429; lo que veía la persona seguía siendo lo mismo,
porque sin sesión en memoria la aplicación cae al formulario. Ahora distingue
«no vale» de «no he podido comprobarla».

Lo que más me ha costado de esta vuelta no fue encontrar nada: fue **el estropicio
que hice yo**. Mi primera versión de la prueba creaba fichajes con dos POST
seguidos, la protección del doble toque rechazaba el segundo, y Ana se quedó
fichada: dieciséis pruebas de otros ficheros en rojo. Y varios sondeos por
consola dejaron ocho empresas de mentira donde debía haber tres, que tumbaron
setenta y cuatro. Ambas cosas estaban en `lessons.md` desde ayer.

**Vuelta 15 — El art. 36, y el fallo más grave de toda la auditoría.**

Empezó como una vuelta pequeña. El hueco que el cuaderno traía ---«falta la
fecha de la evaluación de salud»--- **no es un hueco**: `docs/cobertura-legal.md`
lo excluye a propósito, «nosotros avisamos de que esa condición existe; el
reconocimiento lo lleva el servicio de prevención». Anotado, y a mirar lo que sí
nos toca.

**El veto de horas extra del art. 36.1 no se comprobaba.** El aviso del
cuadrante lo nombraba ---«trae una media de ocho horas, una prohibición de horas
extra y una evaluación de salud»--- y luego la cola de «Por decidir» las
autorizaba sin mencionarlo. `holds_night_worker_status` existía y se usaba en un
solo sitio. Al lado están sus dos hermanas, que sí se comprobaban desde hacía
tiempo: el veto a los menores (art. 6.3) y el de jornada parcial (art. 12.4.c).
Faltaba la tercera.

Y escribiendo la prueba de eso salió lo gordo: **un turno de noche daba dos
entradas y ninguna salida**. La deducción del tipo miraba solo los fichajes del
día local, así que al salir a las 06:00 el día nuevo no tenía ninguno y decía
«entrada». La jornada no se cerraba nunca, el día quedaba en cero horas y la
persona figuraba trabajando indefinidamente. En vigilancia, limpieza o
residencias eso es el registro entero mal, todos los días, para toda la
plantilla de noche --- y es justo la gente sobre la que el producto más avisa.

La misma raíz mordía en otro sitio: quien entró a las diez no podía empezar una
pausa a las tres de la mañana, porque la guarda preguntaba «¿está abierta la
jornada?» por días locales.

Las dos arregladas. La tercera capa ---a qué día pertenecen esas horas--- queda
arriba, en los hallazgos abiertos, porque es una decisión y no un arreglo.

**Vuelta 14 — La purga de metadatos, y una garantía que se había evaporado.**

El área estaba bien cuidada de partida: doce pruebas, cron documentado, tarea de
Celery, y el purgado de `evidence` razonado por escrito ---no entra en el hash
justo para que se pueda borrar, que es el error que `_hash_v1` cometió con la
IP---. Aun así salieron dos cosas.

**Una empresa de baja conservaba las IP para siempre.** El bucle recorría solo
las activas, y el comando terminaba diciendo «Purged 0 events»: todo iba bien.
El plazo no deja de correr porque una empresa deje de usar el producto, y esos
son justo los datos que ya no mira nadie.

Y lo gordo, que salió de intentar arreglar otra cosa: **el rastro había dejado
de ser inmutable**. La migración que crea los tres triggers figuraba aplicada y
su función existía, pero los triggers no estaban en la base de desarrollo. Se
podía editar y borrar el rastro sin que nada chistara --- lo contrario de lo que
esa misma migración declara: «un rastro que puede editar aquel a quien incrimina
no es prueba».

Lo descubrí porque la **prueba** rechazaba el UPDATE y la base no. Ahí está lo
que hay que quedarse: las pruebas corren sus migraciones enteras y siempre ven
los triggers, o sea que son el único sitio donde este fallo **no podía** salir.
Por eso la comprobación vive ahora en `/api/health/`, que le pregunta a la base
que está sirviendo, con `ensure_append_only` para reponerlos --- una sonda que
avisa sin dar salida deja al operador leyendo migraciones.

De rebote, `seed_demo --reset` estaba roto y nadie lo sabía: borraba entradas
del rastro, y solo funcionaba porque los triggers faltaban.

**Vuelta 13 — La constancia de cómo se organizó el registro. Última área.**

El art. 34.9 pide dos cosas y el producto hacía una. Llevar el registro, sí.
**Documentar con qué amparo se organizó ese registro**, no: no había dónde
escribirlo. Es lo primero que una inspección pide después de los propios
registros, antes que ningún fichaje, porque decide si el sistema tiene respaldo.

Las tres vías son excluyentes y están ordenadas ---la decisión del empresario es
la de «en su defecto» y solo esa arrastra la consulta previa---, así que se
guardan como opciones y no como texto libre: esa diferencia es justo la que
decide si faltaba una consulta. Una decisión de empresa sin fecha de consulta se
señala; un convenio **con** fecha de consulta se rechaza, porque un acuerdo es
la negociación y sugerir un trámite que no existe confunde a quien lo lea
después.

Se guarda la constancia, no el acta: que exista un documento, de qué fecha y con
qué referencia es el hecho comprobable. Un almacén de documentos traería su
propia decisión de conservación ---esto no es registro de jornada, así que los
cuatro años no le aplican--- y esa no se toma de pasada.

Tres cosas más salieron por el camino, todas de comprobaciones que ya estaban:

- **El barrido de aislamiento cazó la ruta nueva** antes de que se me olvidara
  meterla, que es exactamente para lo que está.
- **El registro de actividad imprimía «null»** donde el campo estaba vacío
  ---«consulted_on: null → 2024-01-10»---. Le pasaba a cualquier entrada con un
  campo opcional; no había salido porque ninguna de las que había guardaba un
  nulo. Lo vio la prueba que vigila `undefined`, `NaN` y `null` en todas las
  pantallas.
- **Cinco entradas del catálogo estaban marcadas `fuzzy`**, o sea saliendo en
  inglés. Una la metí yo en la vuelta 10 y se fue a `main`: al cambiar el texto
  de un error, `makemessages` lo marcó fuzzy con la traducción vieja. Ya lo mira
  una prueba.

Y tres pruebas que **caducaban a medianoche**: congelaban el reloj para fichar y
preguntaban por «hoy» fuera del bloque congelado. La tercera, que no era mía,
usaba `date.today()` ---la fecha UTC del contenedor--- mientras el producto mira
el día de la empresa: entre las doce y las dos de la madrugada en Madrid no
coinciden. La trampa de `apps/common/clock.py`, esta vez dentro de una prueba,
donde el aviso del módulo no lo lee nadie.

**Vuelta 12 — El art. 34.2: un ajuste que no leía nadie.**

`roster_notice_days` vivía en el modelo, en el marco legal con su cita, y en la
pantalla de ajustes para que la empresa lo subiera si su convenio lo mejora.
**Y no lo miraba ni una línea de código.** Es la misma familia que los
`search_fields` declarados sin el filtro puesto: un ajuste que no lee nadie es
peor que no tenerlo, porque quien lo configura se queda convencido de que el
producto lo vigila.

Ahora el cuadrante avisa con su cita, como los otros nueve. Tres decisiones que
salieron de **medir** y no de suponer:

- El plazo se cuenta desde que el turno se puso o se cambió, no desde hoy.
  Contra hoy, uno planificado en enero para julio se volvería «de última hora»
  solo por acercarse la fecha.
- `updated_at` y no `created_at`: mover un turno de las siete a las quince es un
  dato nuevo, y el artículo pide el día **y la hora**.
- Un turno anotado **después** del día no cuenta. Eso no es poco preaviso, es
  rellenar el cuadrante de la semana pasada --- y eran **94 de los 128** avisos
  que salían en un mes de datos reales. Sin medirlo, el aviso habría nacido
  siendo ruido.

Y un falso positivo de cosecha propia: la comprobación de plurales de la vuelta
7 daba por vacía toda traducción larga, porque gettext las parte y la primera
línea es siempre `msgstr[N] ""` con el texto debajo. Ladrar sin motivo hace el
mismo daño que callarse, porque a la segunda vez se desactiva; lleva ya su
contraste para que siga cazando el fallo que la trajo.

**Vuelta 11 — El art. 37.3, y un fallo que solo se veía fuera de desarrollo.**

Lo que cuadraba, y merece decirse porque es donde más fácil habría sido
equivocarse: **el catálogo está bien contra el articulado**. El RDL 5/2023
partió la antigua letra b en dos, subió la hospitalización de dos días a cinco y
sacó el fallecimiento a una letra nueva, «b bis», sin correr las demás --- y el
catálogo cita b, b bis, c, d, e, f exactamente así. Los quince días del
matrimonio son naturales, el fallecimiento guarda dos más dos de desplazamiento
en vez de un cuatro que no distinguiría los casos, y los del «tiempo
indispensable» no llevan tope inventado.

Y el fallo: **una empresa recién dada de alta se quedaba con cero permisos**. Se
creaba la empresa, se creaba su administradora, y el catálogo no se sembraba. El
desplegable de «Qué pides» salía vacío y nadie podía pedir un matrimonio, un
fallecimiento ni una hospitalización.

Lo interesante es por qué no se había visto: el endpoint que siembra el catálogo
existía, `seedLeaveTypes` estaba exportado en el frontend, y **no lo llamaba
ninguna pantalla**. Lo único que lo usaba era el comando de datos de
demostración --- o sea que funcionaba en desarrollo y en ningún sitio más, que es
la forma más cara de que algo esté roto, porque parece que está bien. Todas las
pruebas, las de backend y las de navegador, corren sobre la base sembrada.

**Vuelta 10 — El art. 34.9, que es el producto entero.**

Lo que aguantó, y conviene decirlo porque marca dónde no volver: el fichaje está
protegido contra el borrado ---`PROTECT` en la persona, «a person with clock
events is never deleted»---, la retención de cuatro años no se puede bajar por
ajuste, y la purga de metadatos se lleva la IP y el dispositivo sin tocar el
fichaje ni su hash.

**El informe de toda la empresa borraba a quien se había ido.** Filtraba por
`is_active`, así que el de marzo salía sin la persona que se marchó en abril, y
no lo decía: un zip con doscientos documentos y uno menos. Lo que el artículo
pone a disposición de la Inspección es el registro **del periodo**, no el de
quien siga en plantilla el día que se pide --- y en una empresa con rotación esto
pasa todos los meses, porque una inspección se pide justo del periodo en el que
alguien se fue. Ahora entra quien está de alta más quien fichó en el rango; dos
de las seis pruebas son el contraste que impide que el arreglo sea «meter a todo
el mundo».

**Y «a disposición de las personas trabajadoras» no se cumplía.** La API dejaba
a cualquiera pedir el suyo desde el principio, pero la única pantalla que lo
ofrecía estaba detrás del panel de gestión: a su disposición lo tenía quien
administra, y no la persona de la que habla el artículo. Poder mirarlo en
pantalla no es poder llevárselo --- lo que se enseña a un juzgado es el documento
con su huella. Ahora hay un botón en «Mi jornada», y baja el mes que se está
mirando, no el corriente.

Dos fallos míos, los dos cazados por pruebas que acababa de escribir: el rótulo
del botón decía «Invalid Date» ---`monthName` toma un objeto, no dos números---
y la comprobación de que un operario no puede pedir el informe de otro **pasaba
sin comprobar nada**, porque con una URL relativa la petición se la queda el
servidor de desarrollo del frontend y devuelve el `index.html` con un 200.

**Vuelta 9 — La importación de festivos, y los dos meses del art. 38.3.**

El comando escribe días en todas las empresas del país de un tirón y **no tenía
ni una prueba**. Lo que escribe no es un dato cualquiera: un festivo dentro de
un permiso no gasta día de vacaciones, y decide si el cuadrante señala trabajo
en fiesta.

Tres fallos. **Solo se podía importar un país**: se quedaba con el primer
directorio por orden alfabético, así que con `es/` y `pt/` publicando el mismo
año, las empresas portuguesas no recibían nada y el comando decía que había
terminado --- mientras la cabecera del módulo presumía de que añadir un país es
un fichero y no un cambio de código. **No comprobaba nada de lo que leía**, y
`HOLIDAYS_DIR` existe justo para que un despliegue traiga el suyo: sin país daba
un `KeyError` pelado, y una fecha del año equivocado ---la errata natural al
copiar el fichero del año anterior--- se escribía y **no se podía deshacer
reimportando**, porque la limpieza va por el rango del año que pides. Y **el
resumen contaba días que no se escribían**, porque `ignore_conflicts` se traga
en silencio lo que choque.

Diecinueve pruebas donde no había ninguna; nueve se ponen rojas con el comando
de antes.

Y el punto legal de la misma área, que llevaba desde el 13/08 como «solo
citado»: el art. 38.3 pide que las vacaciones se conozcan con dos meses. Ahora
se avisa ---no se impide, como con el resto de los mínimos--- y **solo cuando
las pone la empresa**: quien pide las suyas conoce las fechas por definición, y
un aviso que saltara también ahí saldría en la mitad de las solicitudes y en dos
semanas nadie lo miraría. Para distinguirlo hacía falta un dato que la fila no
tenía: quién la metió. Decía de quién son las vacaciones y quién las aprobó, y
se callaba lo del medio.

**Vuelta 8 — La CI, que llevaba roja, y una intermitente que era un fallo.**

Dos cosas, y las dos salieron de correr las comprobaciones enteras antes de
empujar en vez de dar por hecho el estado.

**El paso del esquema fallaba desde que entró la API de integración.** Dos
avisos, y `--fail-on-warn` los convierte en error. Comprobado que venían de
antes poniendo el fichero de entonces y viéndolos salir igual. Uno era una
colisión de nombres de operación ---las dos lecturas de personas se llamaban
igual y el generador las desempataba con un número, así que qué método era cuál
en un cliente generado dependía del orden en que se recorrieran las rutas---; el
otro, un juego de valores con dos nombres, el mismo caso ya resuelto dos veces
ahí al lado.

**Y `npm run lint` daba 739 errores en local**, todos del informe HTML de
Playwright, que eslint entraba a leer. En la CI no se veía porque el checkout es
limpio y ese directorio no existe: se rompía solo en local, y justo para quien
acababa de correr las pruebas.

Lo gordo salió de una prueba que fallaba **una de cada tantas** y pasaba al
ejecutarla sola. La tentación era llamarla frágil. Era un fallo del producto:
**la búsqueda del servidor no ignoraba los acentos**, así que `garcia` devolvía
cero y `ibanez` no daba con Rocío Ibáñez. Con una plantilla española eso es la
mitad de los apellidos, y vale igual para los centros («Almacén») y los
departamentos («Jardinería»).

Lo tapaba el recorte que hace el navegador sobre la lista ya cargada, que sí los
ignora: mientras la respuesta anterior siguiera en pantalla, la encontraba
igual. Solo se veía cuando la lista llegaba antes de teclear. **En cuanto la
plantilla no cabe en una página deja de ser intermitente y pasa siempre**, que
es lo que lo hace serio.

Y el comentario de esa misma prueba, escrito por mí, afirmaba que el servidor
también los ignoraba. No lo comprobé al escribirlo.

**Vuelta 7 — Avisos push y correo. Nada en el área, y un fallo mío al salir.**

El área aguantó: los recordatorios de fichar, el aviso de jornada abierta y los
correos de decisión ya estaban bien montados. Faltaban tres casos por cubrir y
ahora están: que la ventana de silencio se mida en el reloj de cada persona ---a
las 21:30 de Madrid en Las Palmas son las 20:30, y callarse ahí es perder
justo el aviso que sirve---, que una jornada de noche todavía abierta pertenezca
a ayer y se recuerde por la mañana, y que el correo salga en el idioma de quien
lo recibe, que sale de cron y allí no hay idioma activo. Cada uno con su
contraste, porque un vacío sin caso conocido no prueba nada.

El hallazgo salió **releyendo el diff para comitear**, no probando: la plural
del aviso de demasiados intentos ---el que traduje en la vuelta 3--- tenía la
tercera forma vacía. El catálogo declara la regla de CLDR, `nplurals=3`, donde
la forma 1 es la de los millones y **la 2 es la corriente**: 1 usa la 0, un
millón la 1, y todo lo demás la 2. Rellené la 0 y la 1. Y gettext con una forma
vacía no cae al inglés: devuelve la cadena vacía. O sea que el mensaje se veía
en «1 minuto» y en blanco en «5 minutos», que es por donde se pasa al agotar el
cupo por hora.

Dos cosas que apuntar de aquí. Una, `msgfmt --statistics` **no lo ve**: contaba
615 mensajes traducidos con esa forma vacía dentro, así que la comprobación
limpia no valía. Dos, arreglar la entrada no impide que la siguiente plural
nazca igual, así que la prueba que queda lee las tres formas de cada plural del
catálogo entero.

**Vuelta 6 — La asistencia para integraciones, y dos de regalo.**

En el área: **el día salía de `date.today()`**, que es la fecha UTC del
contenedor. A las 00:30 de Madrid decía que era ayer mientras los tramos ya eran
de hoy --- la aplicación que pinta esto ponía la fecha de un día y los fichajes
de otro, y quien más lo cruza es el turno de noche, todas las madrugadas.
`apps/common/clock.py` existe justo por esta trampa y avisa de que ya se había
colado cuatro veces; esta era la quinta, y el último `date.today()` del código.
Había otro en el inspector de convenios, con menos daño (un convenio verificado
hoy se marcaba «con fecha futura» durante dos horas), corregido también.

**Fuera del área, de un uso real:** con la aplicación abierta y la sesión
caducada, `tokens.clear()` vaciaba el almacén y **React no se enteraba**. La
pantalla seguía puesta, su consulta seguía pidiendo cada minuto y cada una daba
401. Un 401 por minuto para siempre, sin arreglarse ni llevar a entrar. Ninguna
prueba lo cubría porque todas **navegaban**, y al navegar se revisa la sesión y
todo funciona: lo roto era quedarse quieto dentro. Validado revirtiendo el
arreglo.

**Y mirando una tanda con ventana:** dos pruebas fallaban solo así. Era un
**404 del favicon** --- que no existía. Chrome sin ventana no lo pide, de modo
que la suite entera estaba en verde mientras cada visita real se llevaba un 404
y una pestaña con el globo genérico. Hay `service worker`, así que además la
aplicación se podía instalar sin nombre y con un cuadrado en blanco. Añadidos
icono SVG, `.ico`, versiones con margen para Android y manifiesto, con pruebas
de que el manifiesto no promete ficheros que no están.

**Vuelta 5 — La integración de personas.** Dos fallos encadenados, y el segundo
solo aparece si se prueba el primero de verdad.

**La lectura masiva devolvía quinientas personas y no decía que hubiera más.**
Un conector de una empresa de seiscientas daba la plantilla por leída: las otras
cien no existían para él, ni sus altas ni sus bajas. Un recorte callado en una
integración es peor que en una pantalla, porque no hay nadie mirando que
sospeche. Ahora la respuesta trae `count`, `has_more` y `next_since`, y el
cursor es `updated_at`, que ya hacía falta para la lectura incremental.

**Y el cursor no funcionaba.** `next_since` sale con el huso pegado
---«…123456+00:00»--- y en una URL el `+` significa espacio: llegaba
«…123456 00:00», no parseaba, y la respuesta era un 409. Cualquier conector que
siguiera el cursor de la forma más obvia se quedaba con la primera tanda. Lo
cazó la prueba que recorre hasta el final en vez de comprobar solo que
`has_more` era cierto --- esa habría pasado con el cursor roto.

De paso: el endpoint salía en el esquema con la respuesta descrita como «un
objeto cualquiera». Quien escribiera el conector tenía que leerse el código o
adivinar, y adivinando no se descubre `has_more`. Ahora el esquema dice los
cuatro campos y explica cómo seguir el cursor, con el aviso de codificar el
`+`.

**Vuelta 4 — Fichaje delegado.** El área mejor construida de las cuatro
revisadas, y conviene decirlo: ya estaban cubiertos el aislamiento entre
empresas, los permisos, las credenciales revocadas, las referencias
desconocidas, que la delegación llegue al informe y que las credenciales no se
guarden en claro. El servidor sigue poniendo la hora aunque delegue el botón.

Un hallazgo: **`evidence` no tenía tope de tamaño**. Lo escribe una integración
desde fuera, con seis mil peticiones por hora de cupo, y esos fichajes viven
cuatro años y salen en cada informe. Un conector honesto que vuelque la traza
GPS entera en cada fichaje llena la base sin hacer nada prohibido. Ahora caben
cuatro mil caracteres, que es de sobra para lo que el campo existe ---unas
coordenadas, una red, el identificador de un evento--- con una prueba del
rechazo y otra de que lo normal sigue pasando: validar solo el rechazo dejaría
pasar un tope de cero.

Y siete casos que faltaban por cubrir, ahora en verde: pasar la tarjeta dos
veces en un lector ---el caso más común de una puerta, y el que antes dejaba la
jornada en cero---, el turno entero fichando en el mismo minuto sin estorbarse,
una referencia que señala a dos personas, quien está de baja, y que lo que
detectó el sensor llegue al registro con su prueba.

Un susto que no era: la línea `except User.DoesNotExist, ValidationError, ...`
sin paréntesis parece sintaxis de Python 2, y es válida en 3.14 (PEP 758).
Comprobado antes de «arreglarla».

**Vuelta 3 — La puerta.** Lo importante estaba bien y conviene decirlo, porque
marca dónde no volver: **no hay enumeración**. Recuperar la contraseña de una
cuenta que existe y de una que no da el mismo 204 con el mismo cuerpo, y entrar
da el mismo error se equivoque uno en el correo o en la contraseña. El backend
de autenticación además cifra una contraseña de mentira cuando la cuenta no
existe, para que el tiempo de respuesta tampoco lo delate, y está comentado. El
enlace de recuperación es de un solo uso por construcción ---sale del hash de la
contraseña--- y caduca en veinticuatro horas.

Lo que sí salió: **el aviso al agotar los cinco intentos por minuto era la
traducción automática de DRF**. «Solicitud fue regulada (throttled). Se espera
que esté disponible en 58 segundos.» Sin artículo, con una palabra en inglés
entre paréntesis, y lo lee quien acaba de fallar cinco veces la contraseña ---el
peor momento para pedirle que descifre nada---. Ahora dice «Demasiados intentos.
Vuelve a probar en 58 segundos», en minutos cuando pasa del minuto, y conserva
el plazo, que era lo único accionable del mensaje viejo.

Y uno pequeño de la misma familia que los de ayer: **el correo del enlace
prometía «24 horas» escritas a mano** mientras el plazo se configura por
entorno. Coincidían hoy; bajarlo a cuatro habría dejado el correo mintiendo.
Ahora sale del ajuste.

De paso, un fallo del banco de pruebas que un bucle destapa y una tanda suelta
no: **dos tandas seguidas se estrellaban**, porque la última prueba agota a
propósito el cupo de intentos y el arranque de sesiones lo comparte ---va por
IP---. Ahora el arranque espera lo que el propio aviso dice que falta. Validado
agotando el cupo a mano y lanzando la suite acto seguido: entra al minuto.

**Vuelta 2 — Resumen.** La tarjeta «esperando decisión» contaba dos de las
cinco colas ---ausencias y correcciones pendientes--- y se dejaba fuera las
propuestas sin contestar, que era la más grande: decía **2** habiendo **57**. No
es un número de adorno: es lo que decide si alguien entra en «Por decidir», y
entre lo que no contaba estaban las horas extra, con cuatro meses de plazo para
compensarse con descanso (art. 35.1).

Ahora suma las cuatro colas que se pueden contar barato y dice aparte que hay
horas extra, sin número: calcularlas cuesta medio segundo y esto se refresca
cada minuto. Un «hay» honesto antes que un número caro o un cero falso.

Contrastando la portada con las pestañas salió el segundo: **los contadores de
«Por decidir» venían de las filas recibidas, no del total**, y las colas de
correcciones llegan de cincuenta en cincuenta. La pestaña decía 50 habiendo 55,
y a las cinco que faltaban no se llegaba desde ninguna parte. Ahora el número
sale de `count` y una lista recortada lo dice. Cinco pruebas en
`e2e/16-resumen.spec.js`, todas comparando pantalla contra servidor y no contra
cifras escritas a mano.

De camino, y a raíz de mirar el `timetrack/` de Geosian: **la pantalla de fichar
tiraba el estado que el POST ya devuelve** y pedía un segundo GET. La guía de
Geosian lo dice con todas las letras ---«reutilizar `today_status` del 201, sin
segundo GET»--- y es el peor sitio para un viaje de más: la persona está delante
del botón esperando a ver si el fichaje entró.

**Vuelta 1 — Fichar.** Dos pulsaciones seguidas no creaban dos entradas: creaban
**una entrada y una salida**. Medido con milisegundo y medio entre ellas, el día
quedaba con cero segundos trabajados y en estado «fuera», y quien había pulsado
se iba convencido de haber fichado. Un doble toque en un móvil, una pantalla que
tarda y se vuelve a pulsar, o un cliente que reintenta: en una obra, con
guantes, es un martes.

Arreglado en `register_punch`, que es por donde entran también el terminal, la
aplicación y el conector --- el botón ya se desactivaba mientras la petición
viajaba, y eso no cubre ninguno de esos tres. Se rechaza en vez de ignorarse:
tragarse el segundo dejaría el registro bien y a la persona sin saber qué pasó.
Cinco segundos, y la ventana es por persona y por tipo de intervalo, así que un
terminal compartido con la plantilla entera en el mismo minuto sigue
funcionando. Cinco pruebas en `apps/punches/tests/test_double_tap.py`.

De paso: tres pruebas existentes se apoyaban en fichar dos veces seguidas y
ahora mueven el reloj con `freeze_time`, que es lo que pasa de verdad; y la
prueba de decidir en bloque estrena personas en cada pasada, porque aprobaba
ausencias que ya no se pueden cancelar e iba llenando el calendario hasta
chocar consigo misma.

Lo del 13/08/2026, antes de arrancar el bucle, está en
`tasks/revision-ux-2026-08-13.md` y `tasks/revision-legal-2026-08-13.md`.

## Descartado a propósito

- **Un suelo legal para `annual_leave_days`.** El mínimo del art. 38.1 son
  treinta días **naturales**, que en jornada de cinco días a la semana son
  veintidós laborables. La unidad depende de cómo lo lleve la empresa, así que un
  suelo de treinta avisaría en falso a quien lo tenga en laborables --- y un aviso
  falso que sale cada vez que se toca el campo vale menos que ninguno. La nota de
  la cita explica la conversión, que es lo que sí se puede decir sin equivocarse.

- **Suelos para `max_open_hours` y las tolerancias de entrada y salida.** No hay
  artículo detrás: son decisiones de la empresa sobre su propio funcionamiento.
  La frontera de la jornada abierta además tiene plantillas legítimas de
  veinticuatro horas ---bomberos, residencias--- así que cualquier techo que se
  pusiera sería nuestro y no de la ley.


- **Los cuatro ojos en `cancel_absence`.** Salió en el barrido de decisiones de
  la vuelta 72 como el otro sitio que no llama a `refuse_self_decision`, y ahí
  no aplica: `_must_be_open` solo deja cancelar una solicitud **sin resolver**.
  Retirar una petición propia que nadie ha decidido todavía no es decidir sobre
  el registro de jornada --- es dejar de pedirlo, y no toca ningún fichaje.
  Exigir una segunda persona para eso convertiría en trámite lo que hoy es
  arrepentirse de pedir un día libre.


- **El 10 % anual del art. 34.2.** «En defecto de pacto, la empresa podrá
  distribuir de manera irregular a lo largo del año el diez por ciento de la
  jornada.» No se calcula, y es una decisión, no un olvido.

  Dos motivos. Uno: el tope solo rige **en defecto de pacto**, y el producto no
  sabe si hay convenio o acuerdo de empresa que regule la distribución --- que es
  el caso normal. Enseñar «has usado el 40 % de tu margen» a una empresa cuyo
  convenio lo tiene pactado es decir algo falso con aire de dato.

  Dos: para medirlo haría falta la distribución **ordinaria** de la jornada
  contra la que comparar, y eso no está en el modelo: el cuadrante *es* la
  distribución. Habría que inventarse la referencia, y un porcentaje construido
  sobre una referencia inventada se lee como un hecho.

  Lo que sí se hace es la otra mitad del artículo, que es la comprobable: el
  preaviso. Si algún día se aborda, hace falta antes un sitio donde la empresa
  declare si tiene pacto, y ese sitio es el mismo que el de la consulta a la
  RLT.

- **Selección múltiple en Fichajes.** Un asiento del registro se corrige de uno
  en uno (art. 4.b). Hay una prueba que se pone roja si aparece una casilla.
- **«Aplicar sin acuerdo» en bloque.** Es la excepción del art. 4.b: en bloque
  dejaría de ser excepción. Retirar sí, aplicar no.
- **Impedir un descanso entre jornadas menor de 12 h.** El RD 1561/1995 lo baja
  en sectores concretos. Se avisa citando el artículo; no se impide.
- **Cancelar una ausencia ya aprobada.** El producto responde
  `already_resolved`. Queda anotado como pregunta de diseño en la revisión de
  UX, no como fallo.
