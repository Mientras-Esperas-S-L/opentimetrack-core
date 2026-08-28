# Auditoría continua — cuaderno

Vueltas dadas: 148 · La interfaz habla los tres idiomas entera. Ahora **las trece situaciones de cobertura legal** que marcó Francisco el 28/08: **una cubierta, doce por delante**. La auditoría exploratoria queda para después: el contador de vueltas en blanco está en 2 de 3. El contador de vueltas en blanco quedó en 2 de 3 cuando se dejó de buscar: si se vuelve a abrir la auditoría, se retoma ahí

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

**Estado a 26/08/2026 (vuelta 101).** Los dos párrafos de arriba se escribieron
hacia la vuelta 66 y describen aquel momento; se dejan como quedaron. Desde el
25/08 se han dado diecinueve vueltas más (83-101) **con hallazgo en diecisiete**.
El patrón que más ha rendido en esta tanda no es una lente sino una forma:
**la pieza está hecha y desconectada** ---el servicio existe, nadie lo llama---,
seguida de **contar lo que hay sale más barato que forzar el fallo** (la 98
encontró 4.391 justificantes sin dueño con una consulta) y de **medir antes de
concluir**, que ha desmontado unos ocho hallazgos propios antes de escribirlos.
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
| La matriz de permisos entera (51 rutas × 4 roles) | limpia | 26/08 v83 | — **sin hallazgo**; el barrido queda como prueba |
| La persona que se mueve (cambios de departamento) | limpia | 26/08 v84 | **ceder un departamento ampliaba a quien lo cedía** a toda la plantilla |
| El borde del año (Nochevieja a caballo) | limpia | 26/08 v85 | **un 500 por una regla del modelo**; las vacaciones a caballo no salían en el año siguiente |
| Lo que las vueltas anteriores dejaron desfasado | limpia | 26/08 v86 | **una corrección que no podía resolver nadie**; dos textos que decían lo contrario de lo que pasa |
| El texto que escribe la persona (Unicode) | limpia | 26/08 v87 | **un motivo que en pantalla dice otra cosa** que en el registro |
| Dos pestañas del mismo navegador | limpia | 26/08 v88 | **tener dos abiertas costaba una sesión cada cuarto de hora** |
| El volumen (200 personas, un año) | limpia | 26/08 v89 | el tope está calibrado; **pero todo rechazo del informe salía como 5 bytes** |
| Lo que las tandas dejan detrás | limpia | 26/08 v90 | — **sin hallazgo**; la suite limpia bien y el sedimento es histórico |
| El camino de vuelta (deshacer) | limpia | 26/08 v91 | **una propuesta equivocada no se podía retirar**; la otra parte tenía que pararla |
| Lo que se borra de verdad | limpia | 26/08 v92 | **un responsable hacía desaparecer la solicitud de otro**, sin fila y sin rastro |
| Lo que se lleva un borrado (cascadas) | limpia | 26/08 v93 | **el registro cambiaba una hora hacia atrás** al retirar un centro |
| Qué más se relee con las reglas de hoy | limpia | 26/08 v94 | **un turno de noche pasaba a «entrada sin salida»** al bajar un tope |
| La pantalla y el documento dicen lo mismo | limpia | 26/08 v95 | **un cero separaba los dos**: fichar leía 16 y el informe 0 |
| Lo que la prueba de accesibilidad no miraba | limpia | 26/08 v96 | **doce «Asignar» idénticos** en una pantalla fuera de su lista |
| Por qué la tanda falla en un sitio distinto cada vez | limpia | 26/08 v97 | **un fallo dejaba un ajuste de empresa cambiado** y rompía a los siguientes |
| Fallos parciales (qué queda a medias) | limpia | 26/08 v98 | **4.391 justificantes huérfanos**: sustituir uno dejaba el anterior en disco |
| Lo que crece sin techo | limpia | 26/08 v99 | **la lista negra de testigos no la purgaba nadie**: 53 % ya caducados |
| Vigencia de las reglas de cómputo | hecha | 26/08 v100 | **decidido y aplicado**: las dos reglas del registro llevan fecha de efecto |

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

- ~~**4.917 justificantes huérfanos en el disco de desarrollo.**~~ (v98) **CERRADO
  el 27/08.** La causa se arregló en la v122 ---las pruebas escribían en el almacén
  de desarrollo y su borrado va en `on_commit`, que en una prueba no corre--- y los
  que ya estaban se retiraron en la v125 con el visto bueno de Francisco: 4.917
  ficheros, 8,1 MiB, cero fallos, quedan los 12 que alguna ausencia referencia.

- ~~**4.391 justificantes huérfanos en el disco de desarrollo.**~~ (v98) 8,1 MiB de
  ficheros sin ninguna fila que los apunte, acumulados a razón de mil por tanda
  desde el 12/08. La causa está arreglada ---sustituir un justificante ya borra el
  anterior--- pero **lo ya acumulado sigue ahí**, y son datos del art. 9. Se
  limpian comparando `MEDIA_ROOT` con `Absence.objects_all_tenants`, que es como
  se contaron; no se ha hecho porque borrar ficheros de la base de desarrollo lo
  decide su dueño. **Para Francisco.**

- ~~**La tanda de navegador falla en una prueba distinta cada vez.**~~ (v96)
  **CAUSA ENCONTRADA Y CERRADO el 27/08 (v104).** Eran dos cosas, y la sospecha
  de entonces ---el navegador reutilizado once minutos--- no era ninguna de las
  dos:

  1. **Esperas por reloj.** `waitForTimeout(2500)` entre una acción y su
     comprobación. Dos segundos y medio bastan casi siempre; al final de una
     tanda larga, no. Encaja con el síntoma exacto: pasa aislada, pasa con los
     doce primeros ficheros ---124 pruebas--- y cae dentro de las 283. Y el
     mensaje no se parece a la causa: decía «esperaba 3, encontré 0», que suena
     a que no se movió nadie, cuando aún no se había movido. Quedan **41 más**
     repartidas en veinte ficheros, con su propia entrada abajo.
  2. **La hora a la que se corre.** Un fixture que ficha en hora de empresa y
     consulta con la fecha del contenedor solo funciona diecinueve horas de cada
     veinticuatro; las vueltas se dan de madrugada. Su entrada propia también
     está abajo.

  Lo que despistó fue medir la carga y descartarla con razón ---4,3 de media con
  32 núcleos--- y quedarse ahí: la máquina no iba cargada **de media**, pero una
  espera fija no necesita que lo vaya, solo que ese instante lo esté.

- ~~**Las reglas de cómputo no tienen fechas de vigencia.**~~ **DECIDIDO Y HECHO
  el 26/08 (v100):** versionadas por fecha de efecto, solo las dos del cómputo.
  Queda el texto original abajo por lo que explica de la distinción.

- **[cerrado] Las reglas de cómputo no tenían fechas de vigencia.** (v94) Medido sobre un abril terminado: marcar que
  la pausa cuenta como trabajo lo lleva de 7:00 a 8:00 h, y bajar el tope de
  jornada abierta convierte un turno de noche de `22:00;06:00;08:00` en `entrada
  sin salida` con cero horas. Que las reglas cambien es legítimo ---salen del
  convenio---; que el cambio alcance al pasado, no. El arreglo pide reglas
  versionadas por fecha de efecto, y con ello la decisión de **desde cuándo**
  aplica un convenio nuevo y qué pasa con lo ya entregado. **Para Francisco.**
  Mientras tanto el documento imprime con qué reglas se calculó.

- **La demo acumula sedimento entre sesiones.** (v90) 533 personas donde la
  semilla monta catorce, 452 correcciones, 413 turnos. No es un fallo ---el
  producto no borra a propósito y la suite da de baja lo que crea--- pero hace que
  dos mediciones separadas en el tiempo no sean comparables. `seed_demo --reset`
  lo arregla; **no se ejecuta desde una vuelta de auditoría** porque borra datos
  de la base de desarrollo. **Para Francisco**, entre sesiones.

- **`DELETE` de un departamento con responsables contesta 409; `PATCH` con
  `managers` vacío llega al mismo estado y contesta 200.** (v86) Desde la vuelta
  84 ese estado ya no es peligroso ---quien se queda sin departamento lee solo lo
  suyo---, así que la refusal protege de un estorbo, no de una fuga. Que las dos
  vías respondan distinto es incoherente, pero decidir cuál gana es cuestión de
  producto: o el `PATCH` avisa también, o el `DELETE` deja de impedir y avisa.
  **Para Francisco.**


- **Las dependencias son la superficie que la auditoría no ha mirado en 38
  vueltas.** Salió sola: el push del 26/08 devolvió el enlace a Dependabot del
  repositorio, y había **34 alertas abiertas**.

  Miradas, son **una**: las treinta y cuatro son el mismo paquete ---`pypdf`, de
  ámbito `development`--- con avisos acumulados por estar en 6.1.3. Actualizado a
  6.14.2 y suite en verde. Ni una de las 34 afecta a producción: `pypdf` no
  aparece en ningún módulo del producto, solo en las pruebas que leen el PDF que
  genera ReportLab.

  Lo que queda abierto es el **hueco de método**, no el paquete: nadie mira las
  alertas de dependencias, y no hay nada en el bucle que lo haga. `opentimetrack-
  cloud` además las tiene **desactivadas** ---razonable mientras solo lleve
  documentación, y hay que acordarse el día que lleve código---. Pendiente decidir
  si esto entra en la auditoría como lente periódica o se resuelve con alertas
  fuera de ella.


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

- ~~**El lote de informes de toda la plantilla, sin comprobar.**~~ (v109)
  **HECHO en la v110**: genera resúmenes de nómina, contesta 201 y dice cuántos y
  a quién deja fuera. Abrirlo destapó que el CSV y el PDF de ese resumen eran el
  registro del art. 34.9 con otro nombre de fichero.

- **Cuarenta y dos esperas por reloj en la suite de Playwright**, repartidas en
  veintiún ficheros. Una de ellas ---`waitForTimeout(2500)`--- rompía la tanda
  entera al final de una corrida larga, y el mensaje del fallo no se parecía a la
  causa. Se arregló esa; las otras 41 siguen. Entre una acción y su comprobación
  va la condición, no un número de milisegundos: `expect.poll` es más rápido
  cuando todo va bien y no miente cuando la máquina va cargada.

- **El dossier de producto va por la vuelta 83.** (v120) Vive en el repo privado
  ---`opentimetrack-cloud/docs/08-comercial/01-dossier-producto.md`, versión 1.4---
  y no lo toca la auditoría. Dos filas suyas se han vuelto ciertas **por lo que se
  arregló estas vueltas**: los descansos «también las noches del cambio de hora»
  (lo era en pantalla y no en el documento, v106) y la huella de los PDF (cierta,
  pero con 577 fichajes saliendo acusados de alterados, v109). Revisarlo fila a
  fila contra el código es una vuelta; **no se hace sin que Francisco lo pida**,
  porque es material comercial y de otro repositorio.

- **Veintisiete `date.today()` sin arreglar en las pruebas.** El producto barrió
  esa llamada de su propio código y dejó `common/clock.py` explicando por qué; las
  pruebas se quedaron con ella. Nueve ficheros la mezclan con datos creados en
  hora local, que es la combinación que rompe entre medianoche y las dos de la
  madrugada en verano. Hoy no rompe ninguna ---medido con la suite corrida dentro
  de la franja---, pero cada prueba nueva que la copie es una bomba con retardo.
  El plan: prohibirla con ruff (`flake8-tidy-imports.banned-api`) y barrer las
  veintisiete en la misma pasada, que es como se arregló en el producto.

- **La unicidad del número de empleado en la base sigue distinguiendo
  mayúsculas.** (v118) El alta por API ya lo impide, pero por shell o importación
  se pueden crear «EMP-9» y «emp-9», y entonces la puerta de integración resuelve
  una al azar y el fichaje delegado se planta por ambigüedad. El arreglo completo
  es un índice funcional sobre `Lower(employee_id)`, y esa migración **falla si en
  producción ya hay dos que chocan**. En desarrollo hay cero. Decisión de
  producto, no de auditoría.

- **Los catálogos de catalán y gallego, con 501 huecos cada uno** (medido en la
  vuelta 101; eran 460 en la 43). Los dejó la vuelta 43 al vaciar traducciones
  falsas y al extraer cadenas que llevaban tiempo sin recogerse, y **crecen solos**:
  cada vuelta que añade texto de interfaz amplía el hueco, la 100 entre ellas.
  Conviene medirlo al cerrar cada vuelta ---`msgfmt --statistics`--- para que no
  se descubra el bulto de golpe. Van con las ~460 del frontend en el paquete
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

### Vuelta 153 --- El acuerdo de trabajo a distancia, parte B (28/08)

**4 de 13.** Cierra lo que la vuelta anterior dejó abierto: el diálogo del
acuerdo en la ficha de la persona.

**Y empieza corrigiendo lo que escribí ayer.** Puse en el dossier y en el
inventario que el acuerdo «hoy solo se puede registrar por API». Era **falso por
partida doble**: no había serializer, ni ViewSet, ni ruta, ni `admin.py` en la
aplicación. La única forma de crear uno era abrir un shell de Django. Lo di por
hecho porque había escrito el modelo y no comprobé qué había alrededor ---la
misma forma de error que la [[293]], dos días seguidos---.

**El hallazgo de la vuelta no es el diálogo: es que el guard de traducción tenía
un agujero.**

`npm run i18n:check` daba **verde** con trece cadenas nuevas sin traducir. Lo vi
por casualidad, comprobando a mano si mis cadenas estaban en `ca.json`.

La causa está escrita en el propio guard, y era razonable cuando se escribió:

> «No comprueba lo contrario ---que todo lo del código esté traducido--- **a
> propósito**: la conversión va a medias por diseño y lo no traducido cae al
> castellano, que es correcto.»

Eso dejó de ser verdad el 28/08, cuando la interfaz quedó entera en los tres
idiomas. **Nadie rehízo el criterio.** Desde entonces había dos guards: uno que
exige que todo lo visible pase por `t()`, y otro que exige que no sobren
traducciones. Faltaba el tercero, que es el que sostiene la frase «la interfaz
está entera en tres idiomas»: **que no falten**.

Medido antes de arreglarlo, que es lo que evita exagerar: faltaban **trece
cadenas, y las trece eran mías de esta vuelta**. La interfaz sí estaba entera
hasta hoy. Pero el agujero llevaba abierto desde la vuelta 146 y lo que lo tapaba
era la costumbre, no el guard.

Ahora `comprobar-lo-visible.mjs` compara lo que pasa por `t()` con los dos
catálogos y falla con código 1 si falta alguna. Con su contraste, y con el
consejo separado: aconsejar «envuélvelo en `t()`» a quien lo tiene envuelto y sin
traducir manda a mirar donde no es.

**Dos decisiones de la pantalla que el servidor no puede tomar:**

1. **Se ofrece a todo el mundo**, no solo a quien ya teletrabaja. El atajo
   evidente era copiar el criterio de las temporadas del fijo discontinuo ---que
   solo se ofrecen a quien lo es--- y habría sido justo al revés de lo que dice
   el art. 5.1: un acuerdo se firma **antes** de empezar, así que exigir que ya
   conste trabajo a distancia obliga a incumplir el artículo para poder
   cumplirlo. Hay prueba, y comprueba las dos cosas a la vez ---que la acción de
   distancia está y la de temporadas no--- porque si la segunda cayera, la
   primera dejaría de significar nada.
2. **Firmar tarde se avisa y se guarda.** El aviso sale **mientras se escribe**,
   no después: decirlo cuando ya está guardado es tarde para quien todavía puede
   mirar la fecha del papel. Y se guarda igual, porque es un incumplimiento que
   ya ocurrió: negarse a registrarlo no lo deshace, deja el registro sin rastro
   de un acuerdo que existe y empuja a escribir una fecha falsa para que el
   formulario pase.

**Los dos barridos de aislamiento hicieron su trabajo,** como en las tres vueltas
anteriores: la ruta nueva no estaba en ninguno y las dos pruebas de cobertura se
pusieron rojas hasta que la metí ---incluyendo que un responsable no pueda firmar
el acuerdo de nadie, que es de quien lleva los contratos---.

**Un tropiezo con los scripts de edición:** busqué `'    "/api/activity-periods/",'`
con cuatro espacios y el `count` dio 2, porque esa cadena está **contenida** en la
misma línea con ocho. El `assert` paró el script antes de escribir nada ---por
suerte, porque escribe al final--- y se arregla anclando el salto de línea
delante.

**Cifras al cerrar:** 1.369 pruebas de backend y 307 de navegador en verde,
linters limpios, `i18n:check` en verde **y ahora comprobando lo que decía
comprobar**, sin migraciones pendientes.

### Vuelta 152 --- El umbral del trabajo a distancia, parte A (28/08)

**Partida, y se dice.** Esta vuelta trae la cuenta, el acuerdo y los avisos; la
pantalla para registrar el acuerdo queda para la siguiente, como pasó con el fijo
discontinuo. Hoy se puede por API y eso no es «cubierto».

**Lo primero que hay que entender del art. 1:** la Ley 10/2021 no regula «el
teletrabajo». Fija **cuándo se aplica** ---trabajo a distancia de al menos el 30 %
de la jornada en un periodo de referencia de tres meses--- y por debajo de ese
umbral no exige nada. Por encima entra entera: acuerdo por escrito y **previo**
(art. 5.1), con el contenido mínimo del art. 7.

Eso convierte una pregunta jurídica en una cuenta, y la cuenta es de las que este
producto puede hacer porque el dato ya estaba: cada fichaje dice si ese tramo fue
presencial o a distancia (art. 3.e).

**Y aquí la diferencia con la vuelta 150.** Con las horas complementarias resultó
que `hours_nature` no lo mandaba **ninguna** pantalla, así que la cuenta habría
sido cero para siempre y hubo que derivarlas. Con el modo de trabajo no: `Clock.jsx`
lo ofrece al fichar y `api.js` lo manda. Lo comprobé antes de escribir nada,
precisamente por lo de la vuelta anterior.

Lo que sí pasaba es que **la demostración no lo enseñaba**: mil cuarenta y nueve
fichajes, todos presenciales, y las 699 personas con «presencial» por defecto. La
misma forma de hueco que las pausas de la vuelta 149.

**Dos avisos y no uno,** porque son dos incumplimientos que se arreglan distinto:
no tener acuerdo, y tenerlo firmado después de haber empezado. Mandar a quien
tiene el papel con la fecha corrida a que «firme un acuerdo» sería mandarle a
resolver un problema que no es el suyo, y una firma no se puede correr hacia
atrás.

**La ventana es móvil, y es lo contrario de lo que decidí hace dos vueltas.** En
el tope de complementarias razoné que las ventanas naturales son mejores porque
un tope que cambia cada mañana no se puede comprobar en un calendario. Aquí no:
aquel es **un límite que no se puede rebasar** y este es **un umbral que dice si
una ley aplica hoy**. La ley habla de «un periodo de referencia de tres meses»
sin atarlo al calendario, y lo que interesa es si ahora mismo hace falta acuerdo.

**Tres meses no son noventa días.** El 31 de mayo menos tres meses no es el 31 de
febrero: se retrocede al último día del mes que toque. Restar noventa días habría
sido una línea y habría dado el 2 de marzo, que no es tres meses antes de nada.
Hay prueba con el 31 de mayo y con su versión bisiesta.

**Un `0 %` sobre una ventana vacía no se contesta.** Cero de cero no es «esta
persona no teletrabaja», es que no consta nada, y la diferencia importa cuando lo
que se decide es si una ley aplica.

**Un tropiezo mío:** metí la tabla de quién teletrabaja como constante de módulo
**en medio de la clase** de la semilla, lo que corta la clase por ahí. `ruff` no
lo dijo ---el fichero no llegaba a parsearse--- y lo vi al comprobarlo con `ast`.
Y usé `WorkMode` y `RemoteWorkAgreement` sin importarlos, que es la 252 otra vez;
esta vez los importé en el mismo paso, antes de correr nada.

**La demostración ya lo enseña, y enseña las dos caras:** Ana teletrabaja el 41,6 %
con su acuerdo firmado dos semanas antes de empezar ---la ley aplica y está
cumplida--- y Luis el 63,4 % sin ninguno, que es lo que la revisión del cuadrante
saca. Sin el segundo, la demostración enseñaría la ley cumplida y no enseñaría
para qué sirve mirarla.

**Cifras al cerrar:** 1.369 pruebas de backend y 304 de navegador en verde,
linters limpios, `i18n:check` en verde, sin migraciones pendientes, y los tres
catálogos del servidor sin cadena visible pendiente ni dudosa ---el guard de
`fuzzy` cazó cinco hoy---.

### Vuelta 151 --- La reducción por guarda legal, que el producto rechazaba (28/08)

**3 de 13.** Cambié la que había anunciado. Dije que tocaba el tope del contrato
formativo «porque es la misma forma sobre otra cifra», y eso es elegir por
dificultad, que es justo lo que el encargo dice que no haga. Por gente afectada
en un cliente real, la reducción por guarda legal gana de calle.

**Lo que había, que no era lo que decía el enunciado.** El inventario ponía «Hay
régimen; la fracción reducida y las fechas, no». La maquinaria para reducir la
jornada ---una fracción, unas fechas, y el cuadrante midiendo contra lo
reducido--- **existía entera** desde el ERTE. Estaba cerrada con esto:

    if reduction_share is not None and leave_type.initiated_by != "COMPANY":
        raise BusinessRuleError(code="reduction_is_company_recorded", ...)

y el razonamiento escrito al lado era bueno: una excedencia voluntaria «al 40 %»
no existe en la ley, y si se colara, el cuadrante mediría a esa persona contra un
contrato que nadie redujo. Lo que no consideró es que **la reducción más
corriente de todas la pide quien trabaja**: el art. 37.6 es un derecho suyo, no
un acto de la empresa, así que caía del lado prohibido.

Es el mismo patrón que el `?search=` de la vuelta 149: una regla bien razonada
para el caso que tenía delante, que deja fuera un caso real que nadie miró.

Consecuencia práctica: la única forma de apuntar una reducción era escribirla en
el horario contratado. En la demostración estaba literalmente como
**«L-V 09:00-15:00 (guarda legal)»**, donde no hay fracción, no hay fechas y
**el derecho no se acaba nunca**. Cuando el menor cumple doce años no avisa
nadie, y la persona sigue con la jornada reducida para siempre.

**Lo que decide ahora** no es quién lo registra sino si el artículo lo permite, y
eso lo dice el catálogo tipo a tipo: `LeaveType.can_reduce_the_day`. Una
excedencia voluntaria sigue sin poder, que es lo que la regla vieja protegía y
hay prueba que lo fija.

**La horquilla del artículo se avisa, no se impide.** De un octavo a la mitad. El
artículo delimita el derecho, no lo que las partes puedan acordar, y bloquearlo
obligaría a apuntar la reducción en el horario contratado otra vez ---que es de
donde se la ha sacado---.

**Tres tropiezos, y los tres los cazó algo del proyecto:**

1. **Puse `paid=True`** razonando «se cobra lo que se trabaja». Lo paró el guard
   que exige que ninguna suspensión salga de la nómina de la empresa. Tenía razón:
   el campo dice si la empresa paga **la parte que no se trabaja**, y ahí no paga
   nadie ---la reducción de jornada lleva reducción proporcional del salario---.
2. **Escribí la fracción al revés.** `reduction_share` es **cuánto se reduce** ---
   «40 means they work 60 %», dice el modelo sin lugar a dudas--- y yo lo tomé por
   cuánto se trabaja. Lo cazó la prueba del cuadrante, y no era un detalle
   interno: **la nota que lee quien registra la solicitud lo decía así**, o sea que
   una reducción de un cuarto se habría apuntado como del 75 %.
3. **La migración no se podía deshacer.** El `ALTER TABLE` y el `UPDATE` en la
   misma transacción dan «cannot ALTER TABLE because it has pending trigger
   events» al revertir. Partida en dos ---`0014` la columna, `0015` los datos---
   va y viene sin quejarse.

**El sembrado de la migración era obligatorio,** no un adorno: el campo nace en
`False`, así que sin él el ERTE y el mecanismo RED habrían dejado de poder reducir
en cuanto se aplicara, y el cuadrante habría vuelto a medir contra la jornada
entera a quien la tiene reducida. Sin que nadie tocara nada.

**Un contraste que no contrastó, y lo que dijo.** Vacié la lista de la migración
esperando que la prueba del ERTE se pusiera roja, y siguió verde: la fixture
siembra el catálogo desde `apps.legal.es`, no desde el historial de migraciones.
La prueba es correcta pero **fija el catálogo, no la migración**, y su docstring
ahora lo dice en vez de afirmar lo que no cubre.

**La demostración lo enseña.** Elena Prats pasa a tener su contrato entero ---40
h--- con una reducción del 25 % y sus fechas, en vez de 30 h escritas a mano.

**Cifras al cerrar:** 1.354 pruebas de backend y 304 de navegador en verde,
`ruff`, `ruff format`, `eslint` y `prettier` limpios, `i18n:check` en verde, sin
migraciones pendientes, y los tres catálogos del servidor sin cadena visible
pendiente ni dudosa ---el guard de `fuzzy` que se puso ayer cazó las dos de hoy---.

### Vuelta 150 --- El tope de las horas complementarias (28/08)

**2 de 13.** Elegida por lo que más se nota: las complementarias son la única
protección que el trabajo a tiempo parcial tiene de verdad ---el art. 12.4.c
prohíbe las horas extraordinarias en un contrato parcial--- y tocan a media
plantilla en hostelería, comercio o limpieza.

**El enunciado contaba mal dos veces**, y clasificar antes de escribir código
volvió a ser lo que más ahorró.

Decía: «A medias. El cuadrante avisa; el tope **mensual** del 30 % no se
acumula».

1. **No es mensual.** El art. 12.5.c habla del «treinta por ciento de las horas
   ordinarias de trabajo objeto del contrato», y el objeto se pacta por semana,
   por mes o por año (art. 12.1). Un contrato de 800 horas al año tiene 240
   complementarias **al año**, no 20 al mes: repartirlas por meses inventa un
   límite que nadie pactó, y es justo lo que este proyecto ya se negó a hacer en
   `agreed_hours` ---dividir 1700 horas anuales entre 52 da una cifra que no
   está en ningún contrato---. El contrato anual es precisamente el que deja
   concentrar el trabajo en la temporada.

2. **No había nada que acumular.** El campo `hours_nature` existe y la API lo
   acepta, pero **ninguna pantalla lo manda**: nadie escribe esa marca nunca. Y
   la semilla la escribía en el fichaje de **salida**, cuando todo lo descriptivo
   viaja en el que abre el tramo ---`_span` lo dice con todas las letras---, así
   que las siete horas complementarias de la demostración eran invisibles hasta
   para el informe.

**Cómo se ha hecho: derivándolas.** El art. 12.5.a las define por lo que son ---
las realizadas como adición a las ordinarias pactadas---, así que salen de
restar lo trabajado menos lo pactado en el periodo del contrato. Si la cuenta
dependiera de la marca sería cero para siempre y el aviso no llegaría nunca.

**Y cierra una promesa que el producto llevaba tiempo haciendo.** El aviso del
cuadrante dice, desde hace vueltas, que las horas por encima del contrato
«cuentan para su propio límite». Ese límite no lo llevaba nadie.

**Las personas salen del registro, no del cuadrante.** Quien no tiene turnos
planificados es quien más fácilmente se pasa sin que nadie mire, y es el agujero
que `_check_time_actually_worked` existe para tapar: repetirlo aquí habría dejado
fuera al mismo grupo. Hay prueba que lo fija sin crear ni un turno.

**El aviso solo existe donde la figura existe.** Se lee del marco legal: la
directiva europea no conoce las complementarias ---son una construcción del ET---
y emitir allí un aviso con un porcentaje español sería inventarle a otro país un
límite que su ley no tiene.

**El guard de aislamiento volvió a pillarme, y esta vez con razón.** `User.objects`
no acota por empresa ---su propio docstring lo dice--- y mi consulta de personas
a tiempo parcial no llevaba `tenant=`. Ayer el mismo guard me paró en la
renovación de sesión y allí la excepción era legítima; hoy era un fallo. La
diferencia está en si hay empresa de la que tirar, y en el refresco no la hay.

Al escribir la prueba salió un matiz que conviene no confundir: **quitando el
`tenant=` la prueba sigue pasando**, porque `Punch.objects` corta la fuga más
adentro. La defensa explícita se queda, y el docstring dice cuál de las dos hace
hoy el trabajo en vez de afirmar una fuga que no se ha visto.

**Tres cosas que corrigen lo escrito ayer:**

- **El backend sí tiene guard de catálogo.** `test_los_dos_idiomas_van_al_dia.py`
  existe desde el 27/08 y clasifica cada cadena en «visible» o «etiqueta de
  campo» leyendo el AST. Ayer escribí que no existía sin buscarlo.
- **Un `fuzzy` no enseña texto equivocado.** Comprobado con `msgfmt`: la entrada
  se omite del `.mo` y la cadena sale en el idioma de partida. Lo que sí es
  cierto, y es el agujero real, es que **el guard no la ve** ---mira si el
  `msgstr` está vacío, y un `fuzzy` lo tiene lleno---. Cerrado hoy con
  `test_ninguna_cadena_visible_se_queda_en_dudosa`, con contraste sobre un
  catálogo escrito a mano porque los del proyecto no tienen ni una dudosa.
- **Las cifras de deuda de traducción eran mías, no del proyecto.** Mi contador
  de huecos leía el formato multilínea de gettext ---`msgstr ""` seguido del
  texto--- como vacío. Los números reales: **0 sin traducir en castellano** y
  **153 en catalán y gallego**, que son exactamente las etiquetas internas que el
  dossier ya declaraba. Y el ruido tapaba un hueco de verdad: uno, mío, del
  llamamiento del art. 16.3, que ya está traducido.

**Cifras al cerrar:** 1.345 pruebas de backend y 304 de navegador en verde,
`ruff` y `ruff format` limpios, `eslint` y `prettier` limpios, `i18n:check` en
verde, los tres catálogos del servidor sin ninguna cadena visible pendiente ni
dudosa.

### Vuelta 149 --- Lo que salió al limpiar la base (28/08)

Esta vuelta no estaba en la lista: la abrieron cuatro pruebas de navegador que
se pusieron rojas al **resembrar la demostración** para las capturas del
dossier. Ninguna era una regresión. Las cuatro llevaban meses en verde apoyadas
en el poso que dejan las propias ejecuciones, y **una tapaba un defecto de
verdad**.

**El defecto: `?search=` no filtraba y contestaba 200.**

`/punches/?search=Hugo` devolvía 583 fichajes de diez personas. El filtro de
búsqueda está declarado globalmente, así que el parámetro se acepta en los once
listados de la API; pero DRF solo busca donde el listado declara
`search_fields`, y **siete de los once no los declaraban**. Ni error ni aviso:
la tabla entera.

Lo interesante es por qué no salió antes. La prueba lo comprobaba a propósito
---su comentario dice que un filtro que ignora el término contesta 200 con la
empresa entera y que por eso mira lo que trae--- y aun así pasaba: miraba los
primeros resultados y una persona con casi mil fichajes llenaba ella sola la
primera página. La intención estaba bien y la muestra no.

Arreglado en los dos sentidos: los fichajes se buscan por nombre, apellido y
número de empleado ---sin acentos, como el resto---, y **un `search` que el
listado no atiende se rechaza con un 400 que lo dice**, en lugar de ignorarse.
Cuatro listados quedan así a propósito (festivos, tipos de ausencia, turnos y
patrones); si algún día han de buscar, la prueba lo señala sola.

**El segundo: renovar la sesión no miraba a la persona.**

Salió tirando del hilo de por qué siete pruebas de aislamiento fallaban con la
base recién sembrada. Los ficheros de sesión de la suite guardaban tokens de
personas que el resembrado había sustituido, y la comprobación de «¿sigue
valiendo?» ---que renueva contra el servidor **a propósito**, para no fiarse de
la fecha--- contestaba que sí: `/auth/refresh/` devolvía **200 y un acceso
nuevo** para alguien dado de baja, y también para alguien borrado de la base.

Medido antes de arreglarlo, porque cambia lo que es: **con ese token no se entra
a nada**. La autenticación sí comprueba `is_active` y todo responde 401. No era
acceso indebido; era una respuesta que dice «bien». El coste, aun así, fue real:
siete pruebas rojas señalando al producto por algo que no era suyo.

Ahora contesta lo mismo que a un token caducado o falso ---no se distinguen, que
diría si esa cuenta llegó a existir---. Y arregló los siete fallos **solo**: el
arranque pide la renovación, le dicen que no, y vuelve a entrar.

**Lo que le faltaba a la demostración,** que era la causa de dos de los cuatro
fallos y también un hueco del producto enseñado:

- **Ninguna pausa.** El art. 3.d pide anotar el principio y el final de las
  pausas que no son tiempo de trabajo, el producto las registra desde hace
  vueltas y la demostración no tenía **ni una**. Ahora las tiene quien hace
  jornada larga, el 85 % de los días. De paso, un mes pasa de una página ---de
  44 fichajes a unos 70---, que es lo que dos de las pruebas necesitaban y la
  semilla no había dado nunca.
- **Quien administra no fichaba.** Al entrar como administradora, «Mi jornada»
  salía en blanco: la primera pantalla de quien va a probar el producto.

**Y una prueba que pedía un imposible.** `44-el-dia-no-se-parte` buscaba a
alguien con **más de cincuenta fichajes en un solo día**. Nadie ficha cincuenta
veces en un día: eran fichajes que otras pruebas habían ido apilando sobre la
misma persona y el mismo día. Solo podía correr sobre una base sucia. El defecto
que vigila ---que un día no salga partido entre dos páginas--- no necesita ese
disparate: basta con que el periodo pedido pase de una página, y un mes de
alguien que hace pausas lo pasa de sobra.

**Otras dos correcciones de la suite:**

- `11-resto-de-pantallas` daba por bueno el filtro si quedaban **menos filas**.
  Con una persona elegida la pantalla trae el periodo entero en vez de la
  primera página ---la unidad que se lee ahí es la jornada---, así que filtrar
  puede acabar enseñando **más** filas. Contaba el tamaño de la página, no el
  filtro. Ahora se mide contra lo que el servidor dice de esa persona **en el
  rango que la pantalla tiene puesto**, que fue el segundo tropiezo: preguntar
  por todos sus fichajes daba su histórico entero, 106, contra los 66 del mes a
  la vista.
- `02-aislamiento` borraba el departamento que creaba **al final del cuerpo**,
  no en un `finally`. Cuando la prueba falló, el departamento se quedó, y quien
  avisó fue `zz-sin-residuos` doce minutos después sin poder decir quién lo
  había dejado. Es la lección de la vuelta 148 repetida.

**Deuda de traducción que destapó `makemessages`:** doce cadenas mías sin
traducir y **cuatro `fuzzy`** en un proyecto que tenía los tres catálogos a cero.
Los huecos son lo de menos; los `fuzzy` son texto **equivocado que se muestra**
---gettext había emparejado «activity starts» con «Registro de actividad»---.
Traducidas las doce a los tres idiomas y los catálogos vuelven a su estado
exacto de antes: 22, 143 y 142 huecos viejos, cero `fuzzy`.

**El guard de aislamiento hizo su trabajo:** el `User.objects` que añadí al
renovar la sesión no acota por empresa, y me obligó a declararlo con su motivo
---la renovación es anónima: el token trae el identificador y todavía no hay
empresa--- en vez de dejarlo pasar.

**Queda anotado, sin tocar:** otras tres pruebas borran lo que crean fuera de un
`finally` ---`04-personas`, `08-formularios-gestion` y `12-acciones-masivas`---.
Hoy no fallan; el guard de residuos las cazaría igual, tarde y sin nombre.

**Cifras al cerrar:** 1.335 pruebas de backend y 304 de navegador en verde,
`ruff` y `ruff format` limpios, `eslint` y `prettier` limpios, `i18n:check` en
verde con 915 cadenas y 19 exentas.

### Vuelta 148 --- El fijo discontinuo, parte B: la pantalla (28/08)

**Hecho:** el diálogo de temporadas, que se abre desde «Más acciones» en la fila
de la persona y **solo si es fija discontinua**. Tres pruebas de navegador con su
contraste, y las quince cadenas nuevas traducidas a catalán y gallego en el mismo
paso.

**Y la cobertura pendiente decía algo falso.** `uncovered` ya detectaba el turno
fuera de temporada ---`is_engaged_on` se lo daba hecho--- pero lo etiquetaba
`left_the_company`: «dejó la empresa» de alguien que solo está esperando su
campaña. No se resuelven igual, que es justo lo que dice el docstring de esa
función: a quien se fue hay que reasignarle el turno; a quien está fuera de
temporada a lo mejor solo hay que moverlo unos días. Ahora tiene motivo propio.

**Tres tropiezos, y los tres míos:**

1. **Importé un icono que no existe** en MUI 9 ---`DeleteOutline`--- y Vite
   devolvió un 500 que dejó la pantalla en blanco. Es **la lección 252 repetida
   entera**. Se comprueba con un `ls` del paquete y no lo hice.
2. **Leí `.results` de algo que ya venía normalizado.** `page()` devuelve
   `{rows, count, hasMore}`, así que la lista salía vacía con el servidor
   contestando 200 y 201: todo parecía bien y no había nada.
3. **Un contraste que no contrastó.** Saboteé `{person.seasonal && (` con un
   `replace` que no encajaba ---prettier lo había compactado a una línea--- y la
   prueba corrió contra el código bueno. Pasó, y lo leí como «el contraste
   funciona».

### Vuelta 147 --- El fijo discontinuo, parte A (28/08)

**Lo que se buscaba:** empezar por el llamamiento del fijo discontinuo (art. 16),
la primera de las trece.

**Lo que salió al mirarlo**, y cambia el diseño: **lo esperado no sale del
contrato, sale del cuadrante**. `reconcile_day` devuelve `expected_minutes=0` y
estado `NO_SHIFT` cuando no hay turno, así que fuera de temporada, si nadie le
pone turnos, el sistema ya no espera jornada. El enunciado del inventario
---«fuera de temporada el sistema no sabe que no se espera jornada»--- describe
mal el hueco. El hueco real era poder decir **cuándo** es la temporada, que el
cuadrante avise si se asigna fuera, y que quede constancia del llamamiento.

**Hecho:** el modelo `ActivityPeriod` con su fecha de llamamiento, la API en
`/api/activity-periods/`, `is_engaged_on` respetándolo y el aviso
`outside_the_season` en el repaso del cuadrante. Diez pruebas y dos contrastes
---quitar la regla, y aplicarla a quien no es fijo discontinuo---.

**Tres decisiones que no eran obvias:**

- **El fin del periodo es opcional.** Una campaña sabe cuándo empieza y no
  siempre cuándo acaba; obligar a un cierre produciría un dato falso donde hay
  un hueco honesto.
- **El llamamiento es una fecha, no una casilla.** El art. 16.3 lo pide con
  antelación, y «se le llamó» sin decir cuándo no acredita nada. Se rechaza si
  es posterior al inicio.
- **Sin periodos declarados, la relación cubre todo el contrato.** Si no, marcar
  a alguien como fijo discontinuo lo dejaría sin un solo día en activo hasta que
  alguien cargara sus campañas.

**Y el aviso del cuadrante no llegaba a quien más lo necesita.**
`_check_outside_the_contract` se saltaba a quien no tiene ninguna fecha de
contrato, que es **justo** el fijo discontinuo indefinido.

**Lo que encontraron los guards, que es lo que hace que valgan:**

- El barrido de aislamiento vio que **un compañero podía leer la temporada de
  otro**. Lo había dejado como el catálogo de permisos o los centros, que los ve
  toda la empresa porque son su armazón; un periodo de actividad no es armazón,
  es un dato de una persona. Ahora se lee acotado con `visible_people`.
- El barrido de roles pidió decidir si un responsable puede fijar temporadas. No:
  organiza dentro de la temporada, pero decidir cuál es va con el contrato.
- Y el guard de avisos exigió base legal para `outside_the_season`. La tiene
  ---art. 16--- así que va citado y no en la lista de los que no la necesitan. En
  la directiva sí va exento: el fijo discontinuo es una figura del ET.

**Queda la parte B:** la pantalla para cargarlos, en los tres idiomas, y el
efecto en la cobertura pendiente.

**Lo que se buscaba:** empezar por el llamamiento del fijo discontinuo (art. 16),
la primera de las trece.

**Lo que salió al mirarlo**, y cambia el diseño: **lo esperado no sale del
contrato, sale del cuadrante**. `reconcile_day` devuelve `expected_minutes=0` y
estado `NO_SHIFT` cuando no hay turno, así que fuera de temporada, si nadie le
pone turnos, el sistema ya no espera jornada. El enunciado del inventario
---«fuera de temporada el sistema no sabe que no se espera jornada»--- describe
mal el hueco.

**El hueco real es otro, y son tres cosas:**

1. **Nadie puede declarar los periodos de actividad.** El campo `seasonal`
   existe desde hace tiempo y `is_engaged_on` **nombra el hueco en su propio
   docstring**: «the system does not model the call-up yet --- which is a gap
   worth naming rather than a question to answer wrongly».
2. **El cuadrante no avisa si se asigna turno fuera de temporada.**
   `_check_outside_the_contract` sí avisa fuera de las fechas del contrato, pero
   se salta a quien no tiene ni `contract_start` ni `contract_end` --- que es
   justo el caso del fijo discontinuo indefinido.
3. **No queda constancia del llamamiento**, que el art. 16.3 pide por escrito y
   con antelación.

**No cabe en una vuelta**, así que va en dos:

- **A:** el modelo del periodo de actividad con su fecha de llamamiento, la API,
  `is_engaged_on` respetándolo y el aviso del cuadrante. Con pruebas de backend y
  su contraste.
- **B:** la pantalla para declararlos, en los tres idiomas, y el efecto en la
  cobertura pendiente.

### Vuelta 146 --- Turnos, el guard, y la interfaz queda entera (28/08)

**Turnos traducida**, que era la última. El catálogo: 772 → **788 claves**. La
interfaz: **898 de 917 cadenas**, y las 19 que quedan no son huecos.

**El guard**: `scripts/comprobar-lo-visible.mjs`, con `NO_SE_TRADUCE` ---las 19,
una a una, con su motivo--- y tres contrastes, los tres verificados poniéndolo
rojo a propósito:

1. una cadena nueva sin `t()` lo pone rojo (salida 1);
2. una exención que ya no le corresponde a nada también (salida 1), porque una
   decisión vieja que sigue tapando es tan mala como el hueco;
3. y si el lector dejara de encontrar cadenas, sale con 2 en vez de decir que
   está todo bien --- cero pendientes con un lector roto se lee igual que cero
   pendientes de verdad.

Corre en la suite (`54-nada-se-queda-sin-traducir`) además de en `npm run
i18n:check`, porque a mano no lo llama nadie.

**Y `36-interfaz-traducida` se retira.** Comprobaba que lo no traducido cayera
al castellano y no al inglés, con una muestra de pantalla sin traducir que se
movió dos veces ---Personas, Informes--- y al llegar Turnos se quedó sin caso.
Lo dejaba dicho en su propio texto: «cuando no quede ninguna sin traducir, esta
prueba se borra». Una prueba que se queda sin caso y sigue en verde es peor que
no tenerla.

**Lo que sigue faltando, y no lo arregla ninguna vuelta más:** nadie que hable
catalán o gallego ha revisado esto. La cobertura ya no es lo que impide
anunciarlo; la revisión sí.

### Vuelta 145 --- El barrido de lo pequeño (28/08)

**Traducido:** todo lo que quedaba salvo Turnos. Entrar, elegir contraseña,
Centros de trabajo, Mi jornada, Fichajes, Cobertura pendiente, los
recordatorios, el selector de tema, el de persona, el aviso de alcance y los
tres servicios que escriben texto ---`api.js`, `bulk.js`, `avisoDeAlcance.js`---.
El catálogo: 682 → **772 claves**. Van 871 de 917.

**Los módulos que no son componentes** ---`format.js`, `bulk.js`, `api.js`,
`avisoDeAlcance.js`--- llaman a `i18next.t` directamente, porque no hay
componente al que enganchar el hook. El medidor no lo reconocía y los contaba
como huecos: ahora entiende las dos formas.

**Y los `noun` de todos los paginadores y barras de selección** van marcados con
`alCatalogo`. Eran veinte cadenas repartidas por seis pantallas que se traducían
en ejecución pero no aparecían en el catálogo como tales.

**Lo que queda son 46 cadenas y ninguna es un hueco.** Nombres de navegadores
(`push.js`), teclas (`Escape`, `Enter`), la cabecera `Authorization: Bearer`,
un aviso de consola para el equipo, el nombre del producto, dos mensajes de
error de programación en inglés y los símbolos de duración (`{{}} h {{}} min`).
Cada una necesita su motivo escrito, y ese es el trabajo del guard.

### Vuelta 144 --- Resumen, Registro de actividad y Mis ausencias (28/08)

**Traducido:** las tres enteras. El catálogo: 628 → **682 claves**. Van 764 de
921, diecinueve pantallas, y la tabla de la prueba llega a doce.

**Dos muestras hubo que cambiarlas, y las dos por lo mismo**: no comprobaban lo
que decían comprobar.

- «Solicitar» se escribe igual en castellano y en gallego, así que la
  salvaguarda de la vuelta 136 saltó antes de llegar al navegador. Se cambia por
  el filtro del año, que sí cambia en los dos.
- El subtítulo del Registro de actividad **es distinto según quién mire**: quien
  administra lee «la base de datos lo impide, también para la administración» y
  quien no, «nadie puede borrar estas entradas». Elegí el segundo y la prueba
  corre con sesión de administración, así que buscaba un texto que esa sesión no
  ve. Dos textos para la misma pantalla es justo el sitio donde una muestra se
  elige mal.

### Vuelta 143 --- Calendario del equipo, Fichar y Departamentos (28/08)

**Traducido:** las tres enteras. El catálogo: 572 → **628 claves**. Van 698 de
919, dieciséis pantallas.

**Fichar entra en la tabla de la prueba**, y era la que faltaba: es la única que
ve quien no gestiona nada, o sea la mayoría de la plantilla. Su muestra es
«trabajadas hoy», que sale siempre, y el control el botón grande.

Turnos se queda **sin traducir a propósito**: es la muestra de «lo que todavía
no está traducido cae al castellano» de la prueba 36. Cuando le toque, esa
prueba se borra ---su condición habrá dejado de existir--- y lo que la sustituye
es el guard del catálogo completo.

### Vuelta 142 --- Personas e Informes, y la lista que ya había divergido (28/08)

**Traducido:** los 49 que quedaban en Personas ---la vuelta 135 dio la pantalla
por terminada--- e Informes entero. El catálogo: 514 → **572 claves**. Van 623
de 923, trece pantallas.

**El hallazgo, y es de ayer mismo:** la lista de idiomas estaba escrita **dos
veces**, en los ajustes de la empresa y en la ficha de cada persona. Ayer
arreglé el criterio en una ---cada idioma con su propio nombre, «English» y no
«Inglés»--- y la otra se quedó como estaba. Doce horas de divergencia.

Ninguna prueba lo habría visto: las dos listas son correctas por separado y
nadie compara la de Ajustes con la de Personas. Ahora hay una sola, en
`i18n/index.js`, con el razonamiento entero al lado ---por qué son cuatro y no
ocho, por qué el euskera se retiró, por qué van en su idioma---.

**Los cuatro mapas de Personas** ---roles, regímenes de jornada, periodos y
condición de nocturno--- van con `alCatalogo`. El de regímenes lleva además la
pista de cada uno, que es donde viven las citas del Estatuto: art. 12.4.c para
la parcial, art. 37.6 para la reducida, art. 11 para la formativa.

**Y la muestra de «sin traducir» se mueve otra vez.** La prueba 36 usaba
Informes; ahora pasa a Turnos, con su historial en el comentario. Es la segunda
vez que se mueve y está previsto en su propio texto: es un rojo que significa
«se ha avanzado».

**El sedimento, cerrado de raíz.** Volvió a saltar ---segunda vez en dos días---
y esta vez se fue al fondo en vez de barrer y seguir.

- **El guard no podía medir su propio tope.** Dice vigilar que no pase de
  sesenta bajas, pero pedía la lista con `page_size=1000` y comprobaba que no
  hubiera segunda página; el servidor tiene su propio tope y devuelve lo que
  quiere, así que se ponía rojo a las **cincuenta y una**. Un tope que no se
  alcanza nunca no es un tope: es un rojo que llega antes. Ahora recorre las
  páginas, con su propio límite de recorrido para no dar vueltas si algo
  devolviera `next` para siempre.
- **La causa, resuelta.** `14-decidir-en-bloque` creaba dos personas por pasada
  para estrenar calendario, y esas dos no se pueden borrar. Lo que necesitaba no
  era gente nueva sino **días libres**, y eso también se consigue moviéndose de
  fechas: dos personas fijas y unas fechas distintas cada vez.
- **Y el primer intento de eso estaba mal.** Derivaba las fechas del reloj y
  confiaba en no repetirse; **falló a la primera**, con dos pasadas dentro del
  mismo segundo. Ahora **pregunta**: pide unos días y, si el servidor dice que
  están ocupados, prueba los siguientes. Contrastado con tres pasadas seguidas,
  que antes rompían en la segunda.

### Vuelta 141 --- Pedir una ausencia y Ajustes, y dos listas que no había que traducir (28/08)

**Traducido:** `LeaveDialog.jsx` entero ---el fichero con más texto de todo el
frontend, 55 cadenas: el saldo, los avisos de tope, las condiciones del
convenio--- y los 51 que quedaban en Ajustes, de los que la vuelta 136 había
dado por terminada la pantalla. El catálogo: 435 → **514 claves**. Van 556 de
937.

**Dos listas que se resolvieron sin traducir nada:**

- **Los nombres de los idiomas.** Iban a medias ---«Español» e «Inglés» en
  castellano, «Català» y «Galego» en el suyo--- y la salida no era pasarlos por
  `t()`: **cada uno con su propio nombre**, «English» incluido. Quien viene a
  esa lista puede no entender el idioma en el que está la pantalla, que es justo
  por lo que viene, y «Inglés» no le dice nada a quien busca «English».
- **Los doce meses**, escritos a mano en castellano, así que el desplegable del
  periodo de cómputo decía «enero» dentro de una pantalla en catalán. Salen
  ahora del navegador como el resto de fechas: una lista menos que mantener y
  una menos que traducir.

**La prueba del diálogo va aparte de la tabla**, porque no es una pantalla: hay
que abrirlo. Y el botón que lo abre es de `MyLeave`, que todavía no está
traducida, así que acepta los dos rótulos ---`/^(Solicitar|Demanar)$/`--- para
no ponerse roja el día que le toque su tanda.

### Vuelta 140 --- Cuadrante, Permisos y Aplicaciones, y un hueco que me había hecho yo (28/08)

**Traducido:** las tres pantallas enteras, 84 claves nuevas. El catálogo: 351 →
**435**. Con ellas van nueve pantallas de treinta y ocho y la mitad de las
cadenas: 464 de 953.

**El hallazgo:** seis claves llevaban un espacio en el borde ---`t(' · sin
sueldo')`--- y **una era de la vuelta 138**, hecha por mí. El espacio ahí es
separación, no texto: al pasar por la lista de pendientes se recorta, se traduce
sin él, y entonces el código pide « · sin sueldo» mientras el catálogo guarda «·
sin sueldo». i18next no encuentra nada y devuelve la clave, que se lee
perfectamente en castellano.

Lo grave es que `comprobar-catalogos.mjs` **no podía verlo**: busca la clave en
el código con `includes`, y la versión recortada sí es una subcadena de la
entera. La comprobación estaba en verde y el hueco llevaba ahí un día.

Ahora lo mira, con su contraste ---se vuelve a meter una clave con espacio y se
comprueba que salta--- y con un segundo contraste sobre sí misma: si el patrón
dejara de reconocer las llamadas a `t()`, cero claves con espacio parecería un
producto limpio en vez de una comprobación rota.

**Y la tabla de la prueba de idiomas estrena un hueco a propósito:** `control`
pasa a ser opcional. Aplicaciones no tiene ningún control cuyo rótulo cambie en
gallego ---«Autorizar» se escribe igual--- y forzar uno habría sido inventarse
una traducción para que la prueba tuviera qué mirar.

**Y saltó el guard del sedimento**, que llevaba avisando desde la vuelta 128 y
esta vez no por el tope: `/employees/?is_active=false` pasó de sesenta y ya no
cabía en una página, así que la comprobación se negó a dar por limpio lo que no
había visto. Bien hecha.

De las sesenta, cincuenta y dos llevaban marca de prueba: **treinta se
retiraron** y **veintidós no**, porque cada una tiene una ausencia. Ninguna era
de hoy, o sea que el `erase` de la vuelta 134 hace su trabajo y esto es
sedimento de antes.

Las veintidós son de `14-decidir-en-bloque`, y **no es un descuido suyo**: crea
gente nueva cada pasada porque **aprueba** lo que pide, y una ausencia aprobada
ya no se puede cancelar. Con gente de la casa iría llenando el calendario hasta
que una pasada tropieza con lo que dejó otra. Deja dos irrecuperables por tanda,
y la regla que lo impide es correcta: quien tiene una ausencia aprobada no es un
alta equivocada.

Así que se escribió la escoba: **`python manage.py purge_test_people`**, con
ensayo en seco, que se niega fuera de `DEBUG` y aplica la misma regla que la API.
Seis pruebas, y la que sostiene a las demás es la del contraste: si el patrón
encajara con cualquiera, las otras cinco pasarían igual y esto sería una escoba
que se lleva la plantilla. Comprobado sustituyendo la marca por `.` --- se pone
roja.

De paso me pilló **el guard de aislamiento**: el comando consulta `User.objects`
sin empresa. Es a propósito ---barre el entorno entero y no hay petición de la
que sacarla--- y ahora está declarado con su motivo.

**Lo que queda por decidir**, anotado y no hecho: esas dos personas por tanda
siguen acumulándose, así que el guard volverá a saltar en unas quince tandas. La
salida sería que la prueba reutilice dos personas fijas y **derive las fechas**
del instante de la tanda en vez de estrenar gente --- lo que buscaba con las
altas era un calendario libre, y eso también se consigue moviéndose de fechas.

### Vuelta 139 --- Lo que sale en todas las pantallas a la vez (28/08)

**Lo que se buscaba:** traducir los componentes compartidos, que la medida
nueva puso los primeros. Son pocas cadenas ---`common.jsx` tiene nueve--- pero
salen en las treinta y ocho pantallas, así que valen más que cualquier pantalla
suelta.

**Traducido:** `common.jsx` (el paginador, los estados, el aviso de plazo
agotado), `punches.js` (tipo y origen de un fichaje), `selection.jsx`,
`filters.jsx`, `format.js` y `navigation.jsx`. El catálogo: 306 → **351 claves**.

**Y tres cosas que solo se ven al traducir:**

- **Las fechas seguían en castellano.** Nueve sitios formateaban con `'es-ES'`
  fijo, así que una pantalla traducida entera decía «Agosto de 2026» encima.
  Ahora sale del idioma de la sesión (`localeDeFechas()`). **Lo que no cambia se
  ve más que lo que falta**: parece un descuido, no un trabajo a medias.

- **El idioma se fijaba después de pintar.** `ConIdioma` llamaba a
  `changeLanguage` desde un `useEffect`, o sea **después** del primer pintado,
  y `useTranslation` solo repinta a quien lo usa. `format.js` no es un
  componente y no puede usarlo, así que las fechas se quedaban con el idioma de
  arranque. Se fija ahora antes de pintar, y la aplicación se remonta con una
  `key` cuando alguien cambia de idioma en caliente.

- **«1 personas».** `Pager` y `SelectionBar` sacaban el singular quitándole la
  «s» al plural. Funcionaba de casualidad en castellano ---y ni eso: ya había
  una prueba de agosto por «1 personas de alta»--- y en catalán deja «persone»,
  que no es una palabra. `noun` pasa a llevar las dos formas, `{singular,
  plural}`, en los catorce sitios que lo usan. La singularización mecánica no
  sobrevive al cambio de idioma.

**Las dos comprobaciones nuevas**, las dos en `53-la-pantalla-en-tres-idiomas`:
lo compartido se mira aparte de la tabla de pantallas ---por la tabla no se
distingue si lo traducido fue la pantalla o el trozo común--- y las fechas
tienen la suya. Esta última esquiva una trampa de calendario: «abril» y
«octubre» se escriben igual en castellano y en catalán, así que dos meses al año
la prueba no distinguiría nada; si toca uno de esos, avanza al mes siguiente.

### Vuelta 138 --- La medida estaba mal, y con ella tres pantallas dadas por hechas (28/08)

**Lo que se buscaba:** seguir con la tanda de Aplicaciones, Cuadrante y
Permisos, que ya venía extraída y traducida de la vuelta anterior.

**Lo que salió:** al contrastar las cadenas contra el catálogo, tres de las que
había traducido «de más» resultaron estar en el fichero y no en mi lista. Mi
extractor no las veía. Al mirar por qué, no era un caso raro: se dejaba dos
familias enteras.

- **Los párrafos partidos por un `<strong>` o un `<code>`.** El patrón no
  cruzaba el salto de línea, así que una frase de tres líneas con la cifra en
  negrita en medio no existía para él.
- **Los rótulos dentro de un objeto** ---`{label: 'Pendiente'}`---. Ahí viven
  todos los estados de `components/common.jsx`, o sea los que salen en **todas**
  las pantallas a la vez.

Con esa medida venía diciendo «quedan 160 cadenas en 23 ficheros». Rehecha con
el árbol de sintaxis: **719 en 41 ficheros**. Y tres pantallas que había dado
por terminadas ---Decisiones con 66 huecos, Ajustes con 51, Personas con 49---
no lo estaban.

Contar de menos no deja un hueco: deja un hueco **y** la impresión de que no lo
hay. Es el mismo patrón que ya salió cuatro veces en la lista de agosto ---41
esperas que eran 3, 27 fechas que eran 25, 501 huecos que eran 354, 4.917
ficheros de los que 12 sí se usaban--- solo que aquí el recuento sin clasificar
era mío y llevaba tres vueltas gobernando el trabajo.

**Lo hecho:**

- **`frontend/scripts/lo-que-se-ve.mjs`**, la medida de verdad, junto al
  `comprobar-catalogos.mjs` que ya existía. Aquel mira que ninguna traducción se
  haya quedado huérfana; este, que ninguna cadena visible se haya quedado fuera.
  Es la base del guard que falta. `npm run i18n:falta`.
- **`alCatalogo()`** en `src/i18n/index.js`, que es `gettext_noop` con otro
  nombre: marca una cadena de un mapa de constantes para el catálogo sin
  traducirla ahí ---el mapa se evalúa al cargar el módulo, cuando todavía no se
  sabe en qué idioma va a mirarlo nadie--- y deja que `t()` la traduzca en el
  punto de uso.
- **Decisiones al 100 %**: 84 de 84 cadenas. Estrena `<Trans>` para las cuatro
  frases que llevan la cifra en negrita en medio. Partirlas para poder
  envolverlas obligaría a traducir «de antelación, y el» suelto, que no es una
  frase en ningún idioma.
- **Los rótulos que además se buscan.** `KIND_LABELS` alimenta el buscador y la
  pantalla. Traducirlo solo donde se lee dejaría el filtro mirando el
  castellano: escribir «Canviar l'hora» en catalán no habría encontrado nada.
- **El catálogo**: 259 → **306 claves** por idioma.

**La comprobación, y su contraste.** `<Trans>` es nuevo aquí y ninguna de las
cinco pruebas de idioma lo miraba: si estuviera mal montado, todas seguirían en
verde y en pantalla se leería `<destacado>3 días</destacado>`. La cobertura fue
a `05-ausencias`, que es la prueba que ya fabrica el exceso de tope y por tanto
ya tiene el dato sembrado --- se le añadió que la frase aparece en catalán y
que la castellana ya no está. Contrastada quitando las dos claves catalanas a
propósito: se pone roja.

**Lo que queda:** 653 cadenas. Las de `components/common.jsx` y
`components/punches.js` van primero aunque sean pocas, porque salen en todas las
pantallas a la vez.

### Vuelta 137 --- Centros, Por decidir y Fichajes (27/08)

Tercera tanda: `Workplaces.jsx`, `Decisions.jsx` y `Timesheet.jsx`, 87 claves. El
catálogo pasa de 182 a **259**, y con seis pantallas hechas está traducido cerca del
**70 %** de las cadenas de la interfaz.

Son las tres que más texto legal llevan: las citas del art. 4.b sobre el cambio sin
acuerdo, la del art. 35.1 sobre cómo se salda una hora extra, la del art. 36.1 que
prohíbe horas extraordinarias a quien tiene la condición de trabajo nocturno, y la
del art. 38.3 sobre las vacaciones que se comió una baja.

#### El hook va donde hay pantalla, no donde hay texto

El script que envuelve pone `useTranslation` en cada función que parece un
componente, y se equivocó dos veces:

- **`byDay`** agrupa fichajes por día y no pinta nada. Un hook ahí es un error de
  las reglas de React, y `eslint` lo dijo tal cual: «se llama en una función que no
  es ni un componente ni un hook».
- **`ListaRecortada`** sí pinta, pero su único texto lleva dos números dentro
  ---«Se muestran 5 de 40»--- así que el script no lo tocó y el hook quedó sin usar.
  Envuelto a mano con interpolación, `{{mostradas}}` y `{{total}}`, **con los
  números dentro de la frase**: en otro idioma no van necesariamente en ese orden,
  y partir el texto para intercalarlos obliga a traducir trozos que por separado no
  significan nada.

Las dos las cazó `eslint` antes de que llegaran a ninguna parte.

#### Y una muestra que la salvaguarda de ayer habría dejado pasar

Al elegir pantalla para la prueba pensé en «Por decidir», y su título se escribe
**igual en castellano y en gallego**. La comprobación que puse en la vuelta 136
---que la muestra cambie entre idiomas--- lo habría dicho en un rojo claro, pero
esta vez la vi antes: se eligieron Centros de trabajo y Fichajes, cuyos tres textos
sí difieren.

Que una salvaguarda te cambie la forma de elegir **antes** de que salte es
exactamente para lo que está.

#### Verde al cerrar

`1.310` pruebas de backend, linters limpios, la prueba de los tres idiomas
cubriendo ya **cinco pantallas**.

**Quedan 22 ficheros** y unas 79 cadenas, todas en pantallas pequeñas.

### Vuelta 136 --- Ajustes y Mi jornada, y una muestra que no comprobaba nada (27/08)

Segunda tanda: `Settings.jsx` (59 cadenas) y `MyTime.jsx` (39). El catálogo pasa de
89 a **182 claves**, y con estas tres pantallas está traducido el 44 % de lo que
hay: la de gestión de plantilla, la de configuración de la empresa y la que usa la
persona trabajadora para ver su jornada y pedir correcciones.

Los párrafos partidos en varias líneas se envuelven con la clave **en una sola**:
partida no coincidiría con el catálogo, y como la clave es el castellano eso
significa que la traducción no se encontraría nunca ---saldría el original y nadie
lo notaría---.

#### Una muestra que no podía comprobar nada

Al ampliar la prueba de los tres idiomas elegí «Mes anterior» como control de Mi
jornada. **Se escribe igual en castellano, catalán y gallego**, así que la
comprobación que da valor a esta prueba ---que el texto castellano ya no está en
pantalla--- no podía cumplirse: fallaba en catalán y en gallego, y pasaba en
castellano.

El fallo era claro pero el motivo no, así que ahora hay una comprobación previa que
lo dice en un rojo directo: **una muestra que no cambia entre idiomas no distingue
«traducido» de «sin traducir»**. Recorre la tabla y exige que cada texto elegido
sea distinto del castellano en los dos idiomas.

#### Dos roles de MUI que no son los que parecen

`type="number"` en un `TextField` expone rol **`spinbutton`**, no `textbox`. Y
«Pedir una corrección» existe dos veces ---como título de diálogo y como botón---,
así que localizarlo pide decir cuál.

#### Verde al cerrar

`1.310` pruebas de backend, linters limpios, la prueba de los tres idiomas ampliada
a tres pantallas y con su salvaguarda.

**Quedan 25 ficheros** y unas 166 cadenas.

### Vuelta 135 --- La interfaz en tres idiomas: Personas (27/08)

Primera tanda del multiidioma, que Francisco pidió montar «más que nada porque
queremos que sea multiidioma». Y lo primero que salió al abrirlo es que **no hay
que montar nada**.

#### El mecanismo ya estaba, y bien

`src/i18n/index.js`: i18next con `react-i18next`, y una decisión que es
exactamente la correcta ---**la clave es la cadena en castellano**---. Así lo que
falta cae al castellano solo, sin configurar nada, igual que en el backend, donde
lo no traducido cae a `LANGUAGE_CODE` y no al inglés de los `msgid`. Su propio
comentario lo dice: que las dos mitades del producto se degraden igual «no es
casualidad, es la condición para que un catálogo a medias sea utilizable».

`ConIdioma.jsx` ya resuelve el idioma de la persona, de su empresa y del
navegador, en el mismo orden que la cabecera `Accept-Language` ---si se calcularan
por separado, una pantalla en catalán enseñaría un error en castellano---.

Lo que faltaba era **poblarlo**: lo usaban **2 de 38 pantallas**, y el catálogo
tenía 23 claves que eran las del menú.

**Se descartó traer `react-intl`**, que es lo que usa Geosian con ~2.900 claves y
un componente `T` propio. Funciona bien allí, pero aquí obligaría a reescribir el
menú y a cambiar de librería para conseguir con `defaultMessage` lo que la clave
castellana ya da. Y se perdería la simetría con el backend, que es lo que hace
utilizable un catálogo a medias.

#### Personas: 66 claves nuevas

El fichero con más texto de todo el frontend. Envueltas las props y los textos de
una línea con un script, y a mano los tres párrafos largos ---que van en una sola
línea en la clave: partida no coincidiría con el catálogo--- y los cinco textos que
viven dentro de objetos (`title:`, `detail:`, `verb:` de los diálogos de
confirmación), donde no hay JSX que envolver.

El catálogo de catalán y gallego pasa de 23 a 89 claves.

**Un falso positivo de mi propio extractor**, que merece quedar escrito: contaba
`set('email')` como una llamada a `t('email')`, porque `set(` acaba en `t(`. Salían
diecisiete claves inventadas ---`first_name`, `contract_end`, `role`...--- que no
existían en el código. Con `(?<![A-Za-z_$.])t\(` desaparecen. El código nunca se
tocó; lo que estaba mal era la cuenta.

#### La prueba, y por qué esta no puede pasar en falso

`53-la-pantalla-en-tres-idiomas.spec.js` recorre la pantalla en catalán, gallego y
castellano, pidiendo el idioma desde la sesión ---que es de donde lo saca el
producto--- y devolviéndolo en un `finally`.

Y lo que la hace valer: **en catalán y gallego comprueba que el texto castellano ya
no está en pantalla**. Sin eso pasaría con el catálogo vacío, porque la clave *es*
el castellano y `t()` devuelve la clave cuando no encuentra traducción. Comprobado
vaciando `ca.json`: se pone roja.

También comprueba un rótulo de control además del texto largo, y elige texto **de
la propia pantalla** y no del menú: el menú ya estaba traducido y comprobarlo daría
verde sin haber traducido nada.

#### Terminología

Alineada con la traducción oficial del Estatuto: «conveni col·lectiu», «jornada»,
«treball a distància», «treballador nocturn»; «convenio colectivo», «xornada»,
«traballo a distancia», «traballador nocturno». Los avisos que citan artículos
llevan su cita intacta.

#### Y rompí una prueba que ya existía, por no buscarla

La tanda salió con un rojo en `36-interfaz-traducida`, que **existía desde antes** y
yo no había mirado. Comprueba lo mismo que acababa de escribir yo por otro lado, y
usaba como muestra de «algo sin traducir» exactamente el texto que acababa de
traducir: «Ver también las bajas», con el comentario «sin traducir todavía, y por
eso vale como muestra».

Es el patrón de la vuelta 128 al revés: una prueba que **depende de que algo siga
sin hacer**. La muestra se ha movido a Informes, y ahora lleva escrito que va a
volver a romperse cuando se traduzca esa pantalla ---y que eso significa «se ha
avanzado», no «se ha roto algo»---, con el historial de muestras y qué hacer el día
que no quede ninguna: **borrar la prueba**, porque su condición habrá dejado de
existir y lo que la sustituye es el guard del catálogo completo.

Las dos pruebas se quedan porque no se solapan, y así queda dicho en las dos: la
36 entra por el idioma **de la empresa** y recorre la cadena entera hasta el
atributo `lang` del documento; la 53 entra por el de **la persona** y recorre lo ya
traducido.

#### Y el sedimento, resuelto de raíz con lo de la vuelta anterior

La tanda completa también sacó en rojo la prueba del borrado, que sola pasaba: en
una tanda entera la lista de Personas tiene decenas de filas ---las que van dejando
las demás pruebas--- y la recién creada no estaba a la vista. Ahora **se busca por
su correo** antes de operar, que es además lo que haría cualquiera.

Y de ahí salió el cierre: `darDeBajaLasDePrueba`, que es lo que usan las pruebas
para limpiar, **solo podía dar de baja**. Por eso el sedimento crecía tres personas
por tanda y el guard saltaba cada pocas vueltas. Ahora, después de dar de baja,
**intenta retirar del todo**, y el servidor decide: si esa persona tiene fichajes,
ausencias o decisiones sobre otras, se niega y la baja es lo correcto.

Limpiados los 46 que quedaban con el propio endpoint: **36 retiradas y 10 negadas
por el servidor**, que son las que tienen rastro. Que negara diez es la prueba de
que discrimina, no de que falle.

Así se cierra lo que el guard venía avisando desde la vuelta 128: **no era el tope,
era que no se podía borrar**.

#### Verde al cerrar

`1.310` pruebas de backend, `eslint` y `prettier` limpios, tres pruebas de
navegador nuevas.

**Quedan 27 ficheros** y unas 264 cadenas. Los siguientes por tamaño:
`Settings.jsx` (54), `MyTime.jsx` (33), `Workplaces.jsx` (27), `Decisions.jsx` y
`Timesheet.jsx` (24 cada uno).

### Vuelta 134 --- Retirar un alta equivocada (27/08)

Lo que quedó propuesto al cerrar la lista, y que había aparecido **dos veces solo
el mismo día**: 946 personas de basura en la base de demostración por la mañana y
57 más por la tarde, cuando el guard del sedimento saltó. Francisco eligió hacerlo
antes de volver a la auditoría exploratoria.

#### Lo que ya estaba bien, y por qué no se tocó

`DELETE /api/employees/<id>/` **no borra: da de baja**, y está sobreescrito a
propósito con su razón escrita ---«their clock events must survive»---. Eso es
correcto y se queda: los fichajes de quien trabajó aquí viven cuatro años y su
ficha tiene que seguir explicándolos.

Lo que faltaba es el otro caso, que no tenía salida: **el alta equivocada**. El
correo mal escrito, la persona duplicada, la que se creó en la empresa que no era.

Así que verbo propio: `POST /api/employees/<id>/erase/`. Borrar de verdad y dar de
baja son operaciones distintas y no comparten botón.

#### La comprobación, que no es «no tiene fichajes»

Son **tres familias**, y la tercera es la que no se ve:

1. **Lo que la base ya protege** (`PROTECT`): fichajes y correcciones. Sin
   comprobarlo antes, el borrado falla con un `ProtectedError` que no dice de
   quién ni cuántos.
2. **Lo que se iría en cascada** y es historial: ausencias, decisiones de horas
   extra, resúmenes de nómina entregados con el recibo de salarios y vacaciones
   recuperadas. Nada de eso lo tiene un alta equivocada.
3. **Lo que decidió sobre otras personas.** Si aprobó una ausencia, resolvió una
   corrección o autorizó horas extra, esos campos son `SET_NULL`: borrarla **no
   falla, vacía**. La aprobación se queda con «decidido por: nadie», en silencio,
   y el art. 4.b pide que un cambio en el registro lleve nombre y apellidos.

Medido sobre la empresa de demostración: borrar a Marta Ruiz dejaría **53
aprobaciones de ausencias sin nombre**. Ninguna de las dos primeras familias la
habría detenido por esa razón ---sí por sus fichajes--- pero el conteo lo separa
para poder decirlo.

El rastro de auditoría sí sobrevive a la persona, porque guarda `actor_label`, el
nombre tal como se escribió. Una aprobación no tiene esa copia.

#### Una prueba mía que pasaba por el motivo equivocado

`test_no_deja_a_la_empresa_sin_administracion` daba dos perfiles de
administración, borraba uno y comprobaba que el último no se podía borrar. Pasaba
---y seguía pasando con el guard **quitado**--- porque el último borrado lo pedía
esa misma persona sobre sí misma, y eso ya lo impide otra comprobación.

Lo que de verdad lo garantiza es la combinación: borrar es cosa de la
administración y nadie puede borrarse a sí mismo. El guard sigue llamándose
---cuesta una línea y protege si mañana se permite borrar a un responsable--- pero
hoy es defensa en profundidad. Reescrita para que diga eso, y no lo que parecía.

De las cuatro guardas, tres se rompen y ponen una prueba en rojo. La cuarta es la
redundante, y ahora está escrito que lo es.

#### Dos trampas de la prueba de navegador

**El diálogo tapa la tabla.** MUI marca el resto de la página con `aria-hidden`
mientras hay un modal abierto, así que `getByRole('row')` devolvía **cero por el
diálogo** y la comprobación pasaba sin haber borrado nada. Se espera a que el
diálogo se vaya y se pregunta al servidor, que es quien tiene la verdad.

**Y la prueba se saboteaba a sí misma**: comprobar por API que la persona ya no
está pide un 404 a propósito, y el navegador lo apunta como error de red. La
vigilancia de la consola se hace ahora **antes** de esa comprobación, porque lo
que vigila es la pantalla mientras se usa.

Las dos las dio la captura del fallo, que Playwright guarda sin que nadie se la
pida. La lección 252 otra vez.

#### Traducciones: diez `fuzzy` que decían cosas falsas

Los mensajes nuevos se parecen a otros existentes, así que `makemessages` arrastró
traducciones viejas y las marcó dudosas. Entre ellas: «leave they approved»
heredó **«ausencia que las pisó»**, «leave they requested for somebody else» heredó
**«Esa solicitud es de otra persona.»** ---una frase de error--- y «You cannot erase
your own account» heredó **«No puedes dar de baja tu propia cuenta»**, que cambia
borrar por dar de baja, que es justo la distinción de esta función.

Los dieciséis traducidos en los tres idiomas. Y de paso, el aplicador **ya no marca
el castellano** como «traducido sin hablante nativo»: eso decía algo falso, porque
el castellano se escribe con conocimiento. Solo catalán y gallego llevan la marca.

#### Verde al cerrar

`1.310` pruebas de backend (once nuevas), `ruff` limpio, sin migraciones
pendientes, castellano completo con 727 mensajes y los tres catálogos a cero
`fuzzy`.

Y en `docs/cobertura-legal.md`: sale el punto 7 de «Por dónde seguir», que era
esto, y entran tres que no estaban en ninguna lista ---reducciones por cuidados,
el acuerdo de trabajo a distancia y las jornadas especiales por sector---, que
salieron al repasar el dossier con Francisco.

### Vuelta 133 --- Las dependencias, y la lista se agota (27/08)

Tarea **10 de la lista**, la última. Francisco la dejó abierta: «mira las
dependencias (que no sé a qué te refieres, pero ponte con ello)». Lo que había que
mirar eran seis cosas, y cinco dieron algo.

#### Las dos vulnerabilidades, con veredicto

`pypdf` por debajo de 6.15.0 puede consumir memoria sin techo con un PDF preparado
a mano. Suena a que un justificante subido tumba el servidor, y **no era el caso**:

- `pypdf` es de **desarrollo**. La usan cuatro pruebas para leer los PDF que
  genera el propio proyecto.
- El PDF que sube una persona **no se parsea**: la validación mira los bytes de la
  cabecera (`%PDF-`) y el tamaño. Y el informe se **escribe** con `reportlab`, que
  no lee.

Actualizada igual, a 6.16.2: el arreglo es gratis y quita el aviso de cada `push`.

#### Dos que venían de prestado

Importadas y no declaradas, funcionando porque otro paquete las arrastraba:
**`cryptography`** ---que importa `vapid_keys`, un comando **de producción**, y
traían `pywebpush`, `py-vapid` y `http_ece`--- y **`pillow`**, que importa una
prueba y traía `reportlab`.

Eso aguanta hasta que el otro paquete cambia su árbol, y entonces **se rompe en el
despliegue y no en desarrollo**, donde ya estaba instalada.

#### Una que sobraba, y comprobado de la única forma que vale

`factory-boy`: cero importaciones. Las pruebas construyen sus objetos a mano.
Retirada del fichero **y desinstalada del contenedor** antes de correr la suite:
quitarla del fichero y no probar habría dejado la duda para el día del despliegue.
1.299 pruebas sin ella.

#### Y un error mío que la lección se merece

Declaré `cryptography==46.0.5` **de memoria**, y la instalación entera falló con un
conflicto de resolución: `pywebpush 2.4.0` pide una más nueva y la que había puesta
era la **50.0.0**. Igual con `pillow`: puse 12.1.0 y era la 12.3.0.

El número de una versión no se supone. Se lee.

#### Lo que queda vigilado

`test_las_dependencias_estan_declaradas`, con dos comprobaciones y tres contrastes:

- **Todo lo que se importa está declarado**, por `ast` ---este mismo fichero nombra
  media docena de paquetes en comentarios sin importar ninguno, y un `grep` los
  contaría---.
- **Todo lo declarado se usa**, contra el código y la configuración, porque la
  mitad no se importa nunca: `gunicorn` es un ejecutable, `whitenoise` y
  `django-redis` se nombran en los ajustes.
- Y los dos que se usan **por su efecto y no por su nombre** ---`pytest-cov`, que
  invoca el CI, e `ipython`, que usa `manage.py shell` si está--- van exentos **con
  el motivo escrito**, y la exención de la cobertura **se valida** contra la
  configuración de `pyproject.toml`. Una exención que nadie comprueba se queda
  muerta y acaba justificando lo que ya no se usa.

Comprobado rompiéndolo tres veces: sin declarar `cryptography`, con un paquete
declarado que nadie usa, y quitando la configuración de cobertura.

#### Lo que no se ha mirado, dicho

Si una dependencia está **abandonada** ---que exista versión nueva no dice si hay
alguien detrás--- y las licencias del árbol de npm, que es mucho mayor. Las dos en
`docs/dependencias.md`, que además explica cómo repetir la revisión.

#### Y el guard de la vuelta 128 saltó, que es para lo que estaba

La tanda de navegador de esta vuelta salió con **un rojo**: «el sedimento de
personas de prueba dadas de baja no crece sin techo». Había **57**, con el tope en
60 ---la cuenta del guard incluye alguna que la mía no---. Ninguna con un solo
fichaje.

El desglose dice de dónde salen: **tres por tanda** de la prueba de acciones
masivas, más doce de otra. Hoy se han corrido ocho tandas completas.

Retiradas con el mismo procedimiento de tres pasos, cinturones a cero y cuadre
exacto: 80 personas antes, 57 borradas, 23 ahora.

**Pero el arreglo de verdad no es este.** Lo dice el propio mensaje del guard: «no
se arregla subiendo el tope: o una prueba está creando personas que no necesita, o
hace falta poder borrar de verdad a quien no tiene ni un fichaje». Es lo segundo:
la prueba **retira** lo que crea, y retirar es todo lo que se puede hacer, porque
la API no borra personas. Así que el sedimento vuelve a crecer con cada tanda y
volverá a saltar en unas veinte.

Eso ya estaba propuesto en «Por dónde seguir» de `docs/cobertura-legal.md`, y esta
es la segunda vez en el día que aparece por su cuenta. **Es trabajo nuevo y no
estaba en la lista aprobada**, así que se deja propuesto y no se hace.

#### Verde al cerrar

`1.299` pruebas de backend (cinco nuevas), `ruff` 0.16.4 limpio ---su aviso nuevo
sobre supresiones mal formadas cazó un texto mío de la vuelta 130---, sin
migraciones pendientes, `npm audit` a cero.

---

## La lista aprobada el 27/08 está terminada

Diez tareas, nueve vueltas (125 a 133). Ninguna quedó a medias y ninguna se cerró
sin las dos suites en verde.

| | Tarea | Vuelta | Cómo salió |
|---|---|---|---|
| 1 | Los justificantes huérfanos | 125 | 4.917 retirados, en tres pasos y con copia |
| 2 | Unicidad del número de empleado | 126 | Índice funcional, migración que se niega antes de tocar |
| 3 | `record_retention_years` | 127 | Borra de verdad, con el suelo del art. 34.9 aplicado dos veces |
| 4 | Acceso de quien ya no trabaja allí | 128 | Enlace de entrega; **no** una cuenta que sigue abierta |
| 5 | El dossier | 128 | Los tres documentos, y uno estaba dos semanas atrasado |
| 6 | Las esperas por reloj | 129 | Eran **tres** defectos, no 41 |
| 7 | Los `date.today()` | 130 | 25, ninguno en producción, con guard |
| 8 | Catalán y gallego | 131 | 354 por idioma; 147 estaban mal clasificadas |
| 9 | Pausa y modo de trabajo | 132 | Estaba hecho y desconectado |
| 10 | Dependencias | 133 | 2 avisos sin riesgo real, 2 de prestado, 1 que sobraba |

**Cuatro de los diez enunciados contaban mal**, y en todos los casos el número
venía de un recuento sin clasificar: 41 esperas eran 3, 27 fechas eran 25, 501
huecos de traducción eran 354 por idioma con 147 escondidas en el grupo
equivocado, y 4.917 ficheros huérfanos eran exactamente 4.917 pero doce de ellos
sí estaban referenciados. **Clasificar antes de arreglar fue lo que más ahorró y
lo que más encontró.**

Lo que queda propuesto y no hecho está en «Por dónde seguir» de
`docs/cobertura-legal.md`, y lo más concreto es **poder borrar de verdad a quien
no tiene ni un fichaje**: hoy un alta equivocada solo se puede dar de baja y se
queda en la lista para siempre.

### Vuelta 132 --- La pausa y el modo de trabajo, que estaban hechos y desconectados (27/08)

Tarea **9 de la lista**. Francisco la dejó a criterio: «si lo de pausar es
necesario para cumplir ley, se implementa. Si es conveniente, aunque no se exija,
lo implementamos. Si es contraproducente no lo implementamos». La recomendación fue
implementarlo, y al abrirlo resultó que **casi todo estaba ya escrito**.

El backend lo tenía entero desde antes: `PunchInterval.BREAK` con su comentario
explicando por qué la pausa se modela como una clase de intervalo y no como dos
tipos de fichaje más; `register_punch` recibe `interval` y `work_mode`; la vista los
lee del cuerpo; `build_day_status` devuelve **`ON_BREAK`** y cuenta los segundos de
pausa aparte; y la regla de si el descanso se descuenta de las horas sale del
convenio de la empresa y no de nosotros.

Lo que faltaba era **ofrecerlo**: la web mandaba solo el identificador del
dispositivo. Ninguna persona podía abrir una pausa ni decir desde dónde trabaja.

#### El defecto que estaba esperando

`STATES` en el frontend no conocía `ON_BREAK`, así que `STATES[estado]` caía al
respaldo y la pantalla decía **«Sin empezar»** a quien tenía la jornada abierta y
una pausa en marcha. Nadie lo había visto porque nada de la web podía abrir una
pausa ---pero la puerta de integración sí, y ahí el estado llegaba---.

Es el mismo patrón que la vuelta 129: mientras nadie puede llegar a un estado, el
error de ese estado no se ve.

#### Lo construido

- **Un botón secundario, «Empezar una pausa»**, solo mientras trabaja. Debajo del
  principal y en texto, no compitiendo con él: fichar es lo que se viene a hacer
  aquí, la pausa es una vez al día.
- **En pausa, el botón principal es «Volver de la pausa»**, y **no se ofrece
  fichar la salida**. Cerrar la jornada con la pausa abierta dejaría un día que
  dice que alguien se fue a comer y no volvió nunca; el art. 3.d pide el final de
  la pausa.
- **El modo de trabajo (art. 3.e)**, dos chips antes de entrar, y **sin
  preselección**. Vacío significa «no consta», y suponer «presencial» llenaría el
  registro de un dato que nadie ha afirmado ---peor que el hueco, porque el hueco
  se ve---. Se recuerda por día, no para siempre: el artículo habla del día «o
  parte de él».
- Solo se manda **en la entrada de la jornada**: es el fichaje que abre el tramo y
  todo lo descriptivo viaja en el que abre.
- **El desglose dice qué fue cada tramo.** Una pausa se leía igual que un rato
  trabajado, que es exactamente lo que el art. 3.d viene a distinguir. Y el total
  de pausa del día, con el aviso de que si el convenio la cuenta como trabajo ya
  está dentro de las horas de arriba.

#### Media hora perdida por no mirar la captura

Al correr la prueba falló **el arranque de la sesión de admin**, con un tiempo
agotado en `locator.fill`. Perseguí tres hipótesis ---las credenciales, el cupo de
cinco intentos por IP, el estado de los contenedores--- y comprobé el login por
API, que funcionaba.

La captura del fallo, que Playwright ya había guardado, tenía la respuesta a
pantalla completa: **importé un icono de MUI que no existe**
(`PauseCircleOutline`; los que hay son `PauseCircle` y `PauseCircleOutlined`), y el
overlay de error de Vite tapaba el formulario de login. De ahí que el campo no
apareciera, y de ahí que fallara **solo** el admin: es la única sesión caducada, y
las otras tres no pasan por el formulario.

#### Y un documento que decía más de lo que hay

Al revisar si los textos nuevos había que traducir salió que el catálogo del
frontend tiene **23 claves, y son las del menú**: el resto de la interfaz está en
castellano fijo. Así que `docs/traducciones.md`, escrito ayer, empezaba diciendo
«el producto habla castellano, catalán y gallego», y lo que hay es **el servidor
traducido y la pantalla no**. Corregido con una tabla que lo separa.

#### Verde al cerrar

`1.294` pruebas de backend, `ruff` y los linters del frontend limpios, cinco
pruebas de navegador nuevas. Las cuatro piezas comprobadas rompiéndolas una a una
---sin el estado, sin el botón, preseleccionando el modo, sin las etiquetas del
desglose---: cada una pone exactamente una prueba en rojo.

### Vuelta 131 --- Catalán y gallego, y la clasificación que escondía la mitad (27/08)

Tarea **8 de la lista**. Eran **507 huecos**, de los que 354 eran cadenas cortas, y
la primera lectura decía que 300 de ellos eran «etiquetas de modelo» que **se dejan
sin traducir a propósito**: así lo tenía decidido el proyecto y así lo explica el
docstring de `test_lo_que_no_esta_traducido_cae_al_castellano_y_no_al_ingles`, que
además comprueba lo único que hace viable esa decisión ---que lo que falta cae al
castellano y no al inglés---.

Con esa lectura el trabajo eran 207. Se tradujeron.

#### Y entonces la clasificación resultó estar mal

La regla era «si el mensaje sale de un `models.py`, es una etiqueta de campo». Y en
este proyecto **los modelos no viven solo en `models.py`**: están también en
`corrections.py`, `applications.py`, `holidays.py`, `rules.py` y `payroll.py` ---lo
mismo que ya había sorprendido en la vuelta 127 buscando las claves ajenas hacia
`Punch`---. Así que dieciocho etiquetas de campo caían en el grupo equivocado.

Eso era lo de menos. Rehecha la clasificación con `ast`, mirando **qué envuelve
cada cadena** en vez de en qué fichero está, salió lo otro: de las 300 supuestas
etiquetas internas, **147 eran visibles**. Los tipos de ausencia («Vacaciones»,
«Baja médica»), los estados, las veintitantas acciones que salen en el rastro, las
unidades de los topes de permisos. Todo eso aparece en el calendario, en el informe
y en los correos, y estaba clasificado como interno porque su `TextChoices` vive en
un `models.py`.

Total: **354 mensajes traducidos por idioma**, 708 traducciones. Quedan 153 sin
traducir, que son las etiquetas de campo de verdad ---las que están dentro de un
`XxxField(...)`--- y siguen cayendo al castellano.

#### Lo que hace que esto no se repita

`test_los_dos_idiomas_van_al_dia` clasifica con `ast` y exige que lo visible esté en
los dos idiomas. Sin él el criterio no se sostiene solo: **nadie había dejado esos
207 sin traducir a propósito**. Se fueron añadiendo funciones, los catálogos no
crecieron con ellas, y no se notaba porque cada mensaje caía al castellano y la
pantalla seguía siendo legible. Un hueco que no se ve no se arregla.

Con cuatro contrastes, porque la comprobación acaba de dar cero: que la
clasificación distingue el mismo texto puesto en un campo y en un `TextChoices`;
que una cadena en los dos sitios cuenta como visible ---traducir de más cuesta una
traducción de sobra, traducir de menos cuesta una pantalla en dos idiomas---; y que
el lector del catálogo encuentra huecos de verdad, porque si devolviera un conjunto
vacío por un error de parseo las dos comprobaciones pasarían para siempre.

Comprobado quitando la traducción de «Sick leave»: se pone rojo y la nombra.

#### Que piden revisión, dicho donde se ve

Cada traducción lleva `# revisar: traducido sin hablante nativo el 2026-08-27` en
el catálogo, y `docs/traducciones.md` explica el criterio, cómo listarlas y qué
hacer al revisarlas: corregir lo que esté mal y **quitar la marca** de lo aprobado,
para que lo que siga marcado sea lo que siga sin revisar.

La marca va como comentario del traductor (`# `) y no como `#.`, que es el hueco de
los comentarios extraídos del código y `makemessages` regenera en cada pasada. Y
**no** como `#, fuzzy`, que era la tentación evidente: Django ignora los fuzzy, así
que marcarlas así equivaldría a no haberlas traducido.

#### Verde al cerrar

`1.294` pruebas de backend (cinco nuevas), `ruff` limpio, los tres catálogos
compilando sin avisos y a **cero `fuzzy`**.

### Vuelta 130 --- El hoy de quien pregunta, y un guard para que no vuelva (27/08)

Tarea **7 de la lista**. Eran **25**, no 27, y ninguna estaba donde el enunciado
temía: **cero en el código de producción**.

#### El detector que me engañó primero

El primer barrido dijo **36 usos, cinco de ellos en producción**, y eso encendió
todas las luces: `attendance_api.py`, `shifts/views.py`, `agreements.py`,
`clock.py`. Los cinco eran **comentarios explicando por qué no se usa
`date.today()`**. Cuanto mejor documentado está un antipatrón, más falsos
positivos da buscarlo por texto ---y este está documentado con esmero, porque ya
se había colado cinco veces---.

Rehecho con `ast`: **25 llamadas reales, todas en pruebas**.

#### Por qué no eran inocuas

Una prueba que siembra un rango con `date.today()` y luego pregunta al producto
---que responde con `local_today(empresa)`--- compara **dos días distintos** entre
medianoche y las dos de la madrugada en España. El fallo sale de madrugada, en una
máquina y no en otra, y se lee como un defecto del producto. Es la misma familia
que los rojos intermitentes de la vuelta 129, con otro reloj.

#### Cómo se cambiaron

`local_today(X)` responde con la zona de quien pregunta: una persona contesta con
la de su centro de trabajo, cayendo a la de su empresa. Así que la sustitución no
es mecánica, hay que decidir **de quién es el día**:

- **12** se hicieron con un script sobre `ast`, que sabe en qué función está cada
  llamada y qué nombres tiene a mano ---empresa, centro, persona---.
- **10** tenían el sujeto dentro de un diccionario (`mundo["empresa"]`,
  `ours["worker"]`) o con otro nombre (`acme`, `elsewhere`), donde el script no
  llega. A mano, mirando cada contexto.
- **1** era un helper compartido, `ask_absence(client, **extra)`, sin nada a mano:
  ahora recibe de quién es el calendario y sus cuatro llamadas lo dicen.
- **2** estaban a **nivel de módulo**, donde todavía no existe ninguna empresa.
  Ahí se ancla la zona a mano ---todas las empresas de ese fichero son de
  Madrid--- y queda dicho por qué, que es lo único honesto: `timezone.localdate()`
  no habría servido, porque `TIME_ZONE` es `UTC` y devuelve exactamente lo mismo
  que `date.today()`.

Y un doble de pruebas que se rompió por el camino: el `mundo_falso` del barrido de
permisos solo finge tener `.id`, porque esa prueba solo quiere las rutas. Ahora
finge también la zona, que es lo justo para que la lista se pueda montar.

#### El guard, que es la mitad del trabajo

Nada en el lenguaje señala `date.today()` como sospechoso: es la llamada obvia, y
la correcta pide un argumento que hay que ir a buscar. Sin un guard vuelve ---ya
volvió cinco veces---.

`test_el_hoy_de_quien_pregunta.py` recorre `apps/` con `ast` y exige cero. Con
cuatro pruebas de contraste, porque un guard que da cero no prueba nada por sí
solo:

1. **Encuentra** `datetime.date.today()` y `date.today()`.
2. **No cuenta** lo que solo lo menciona: un comentario, un docstring, una cadena.
   Es la que de verdad importa, y la que me habría ahorrado la hora de antes.
3. **Deja pasar** `algo.today(empresa)`: lo que la trampa tiene de trampa es que no
   pregunta de quién es el día.
4. **`local_today` sigue existiendo**, porque si alguien lo retirase el guard
   seguiría en verde sin haber con qué sustituir lo que prohíbe.

Comprobado en las dos direcciones: metiendo una llamada real en `apps/legal/base.py`
se pone rojo y la nombra; metiendo solo la mención en un comentario, sigue verde.

#### Verde al cerrar

`1.289` pruebas de backend (cinco nuevas), `ruff` limpio, sin migraciones
pendientes.

### Vuelta 129 --- Las esperas por reloj: eran tres defectos, no cuarenta y una (27/08)

Tarea **6 de la lista**, y el resultado cambia el enunciado. Se pidió «sustituir
las 41 esperas por reloj por esperas por condición», y ese número venía de contar
`waitForTimeout` sin distinguir para qué estaba cada una. Clasificadas por lo que
llevan detrás salen **cuatro clases**, y solo una es un defecto:

| Clase | Cuántas | Qué es |
|---|---|---|
| **Carrera** | 3 | Un valor del DOM sacado a una variable, que no reintenta. **Son los rojos intermitentes.** |
| Aserción negativa | 4 | Se comprueba que **nada** pasó. Hay que dar margen a que el efecto indeseado ocurra, y no hay condición que esperar. El reloj es lo correcto. |
| Estado intermedio | 1 | Se mira a propósito **antes** de que llegue la respuesta ---el buscador a los 300 ms---. Tampoco es expresable como condición. |
| «A que se asiente» | 25 | No sacan ningún valor: la aserción que sigue ya reintenta. Son lentas, no frágiles. |

Las tres carreras están arregladas: una en la vuelta 126 y dos aquí. **No queda
ninguna.**

#### Lo arreglado

**El bucle sobre una foto.** `for (const fila of await filas().all())` toma la
lista en el instante en que se pide, así que sin la espera recorría las filas
viejas ---y con ella, casi siempre---. Se cambia por lo que se quería decir: «no
hay ninguna fila que incumpla», con un locator filtrado, que reintenta hasta el
plazo. Más corto y más fuerte.

**Y la de `12-acciones-masivas`**, que es la misma de la vuelta 126: `count()` sin
reintento detrás de un reloj de 800 ms.

#### El hallazgo: una prueba que no probaba nada, por dos motivos a la vez

«Calendario del equipo › filtra por tipo y por estado» comprobaba
`personas().count() <= todas`, con este comentario: «o quedan menos filas o el mes
no tenía de ese tipo. Las dos cosas valen; **lo que no vale es que no cambie nada
nunca**». Y eso es exactamente lo que dejaba pasar: con el filtro desconectado el
conteo no cambia, y «no cambia» cumple `<=`.

Pero había algo peor debajo. El locator era `getByRole('row')` y el calendario
**no es una tabla**: es una rejilla de `Box` con `display: grid` y **ningún
`role`**. Así que `todas` valía **cero**, la aserción era «0 <= 0», y la prueba
llevaba pasando sin mirar una sola fila.

Dos arreglos:

1. **La rejilla ahora tiene semántica**: `role="table"`, `row`, `columnheader` y
   `rowheader`. Era un defecto de accesibilidad de verdad ---un lector de pantalla
   no podía recorrer el calendario--- y de paso hace que se pueda localizar por
   rol como en el resto de la suite. Las **celdas** quedan sin marcar a propósito:
   la que tiene una ausencia ya es `role="button"` para poder abrirla, y meterla
   dentro de una celda pide un elemento más en la rejilla; eso se hace mirando la
   pantalla, no a ciegas.
2. **La aserción cuenta el número exacto**, calculado de los datos que la propia
   pantalla trajo ---el filtrado es en el cliente sobre una sola petición, así que
   se puede saber---. Más un contraste: al menos uno de los filtros tiene que
   quitar filas, o los tres conteos podrían cuadrar con el filtrado desconectado.

Comprobado desconectando el filtrado en `TeamCalendar.jsx`: **ahora se pone roja,
y antes pasaba**.

#### Lo que queda, y por qué no se toca

Las 25 esperas de «a que se asiente» suman 32 s de una tanda de 11,2 min, un 4,8 %.
Las dos que más pesan están dentro de bucles ---`07-pantallas` 600 ms × 13
pantallas, `30-contraste` 400 ms × 10 × 2 temas--- y las dos son **aserciones
negativas**: comprueban que la consola no se quejó y que ningún texto queda por
debajo del contraste mínimo. Quitarles el margen no las haría más rápidas, las
haría ciegas.

Así que la tarea 6 se cierra aquí: lo que causaba rojos está arreglado, y lo que
queda es lentitud medida que no conviene tocar.

### Vuelta 128 --- Quien ya no trabaja allí puede pedir su registro (27/08)

Tarea **4 de la lista**, y Francisco la planteó como pregunta: «en teoría no
debería tener acceso a recursos de la empresa si no trabaja. ¿Existen precedentes
que digan que sí puede seguir teniendo acceso hasta que finalice el tiempo de
retención de sus datos?».

**La respuesta corta es que el derecho no se extingue, pero no es un acceso.** El
art. 34.9 ET obliga a conservar el registro cuatro años y a tenerlo a disposición
de la persona trabajadora; el art. 15 del RGPD le da derecho a pedir sus datos
mientras se conserven, y ese derecho no se acaba el último día de contrato: lo que
se acaba es la relación laboral, no el tratamiento. Pero el art. 15 se ejerce **por
solicitud y se satisface con una entrega**: no obliga a mantener a nadie dentro de
la aplicación. Y mantenerla dentro tiene coste real ---vería el cuadrante, a sus
antiguos compañeros y lo que la empresa haya cambiado desde que se fue---, así que
la lectura amplia sería peor para todos, incluida esa persona.

*No se citan sentencias porque no se han comprobado. Lo de arriba sale del texto
de los dos artículos, y conviene que lo confirme la asesoría antes de ponerlo en
un documento que salga de aquí.*

#### Lo construido: una entrega, no una cuenta

`apps/reports/delivery.py`. La administración genera un enlace para una persona
concreta ---de alta o de baja--- y le llega por correo. El enlace no abre sesión ni
sirve para nada más que descargar **su** registro.

Tres cosas lo acotan, y las tres tienen prueba:

1. **No hay parámetro que diga de quién es el registro**: sale del identificador
   firmado. Así que no hay nada que cambiar para alcanzar a otra persona; añadir
   `?employee=` a mano no cambia lo que sale.
2. **Se entrega exactamente lo que se conserva.** El periodo lo decide
   `first_day_kept`, el mismo que usa la purga de la vuelta 127 para decidir qué
   borrar. Con dos definiciones del plazo, un día habría registro entregable que ya
   no existe, o registro guardado que no se entrega.
3. **Un ámbito propio dentro del valor firmado.** Sin él, el enlace de invitación
   ---que se deriva de los mismos campos--- descargaría el registro de esa persona.

Y lo que lo mata antes de tiempo: **reactivar la cuenta** y **cambiar la
contraseña**. Las dos significan que ya hay otra puerta.

#### Un error mío, corregido antes de cerrar

Escribí en tres sitios que el enlace es «de un solo uso», copiando el del
restablecimiento de contraseña. **Es falso**: aquel se invalida al usarse porque
poner una contraseña cambia el hash que va en el valor firmado, y descargar un
informe no cambia nada. Con este mecanismo vale hasta que caduque.

Lo que corregí fue el texto, no el mecanismo, porque **usarlo dos veces es el caso
normal**: el PDF y el CSV son dos descargas de la misma solicitud. Un enlace que
muere en la primera obligaría a pedir otro para la segunda.

#### Y de camino, 946 personas de basura

Al buscar a alguien de baja para probar salieron **946 personas de prueba dadas de
baja** en la empresa de demostración, de 969 en total: la pantalla de Personas era
basura en un 98 %. Ninguna tenía un solo fichaje.

El guard de residuos las ignoraba **a propósito**, y su razón está escrita: «el
producto no borra personas a propósito, que los fichajes viven cuatro años». Es
verdad a medias ---del todo para quien tiene fichajes, falso para quien no tiene
ninguno--- y el razonamiento se muerde la cola: no se miraban porque eran
demasiadas para traerlas en una página, y eran demasiadas porque nadie las miraba.

Retiradas en tres pasos, con copia de 946 entradas y seis cinturones a cero (sin
fichajes, sin correcciones, ninguna de alta, ninguna de otra empresa, ninguna
staff, ninguna exenta) **y el contraste**: metiendo a Hugo en la lista el detector
de fichajes da 56, así que los ceros no eran un detector roto.

Quedan 23 personas. Añadido al guard un tope de 60 para el sedimento de las de
baja, con el aviso de que subir el tope no es el arreglo: o una prueba crea
personas que no necesita, o **hace falta poder borrar de verdad a quien no tiene ni
un fichaje**, porque un alta equivocada no puede quedarse para siempre. Eso último
es una propuesta, no está hecho.

#### Dos guards que hicieron su trabajo

El barrido de aislamiento se puso rojo al añadir las dos rutas nuevas y no dejó
cerrar hasta declararlas ---la pública con la razón, la del panel al barrido
normal---. Y la prueba de traducciones marcadas `fuzzy` cazó tres que eran
peligrosas de verdad: la acción nueva del rastro heredó «Consultó el registro de
otra persona» y el asunto del correo heredó «Tu registro de jornada ha cambiado».
Django ignora los `fuzzy`, así que no se veían; aceptarlos a ciegas habría puesto
el rastro a decir que alguien fisgó donde lo que hubo fue una entrega.

**Y un detector mío mal hecho**: al retirar los flags usé `^#, fuzzy\n`, que no
coincide con `#, fuzzy, python-format`. Los dos mensajes con `%(company)s` dentro
se quedaron marcados aunque estuvieran traducidos. El patrón del guard ya estaba
bien escrito ---`^#,.*\bfuzzy\b`--- y el mío era más estrecho que el que iba a
tener que satisfacer.

#### Verde al cerrar

`1.284` pruebas de backend (doce nuevas), `ruff` limpio, sin migraciones
pendientes, castellano a **711 mensajes traducidos y cero sin traducir**, y los
tres catálogos a **cero `fuzzy`**.

### Tarea 5 --- Los tres documentos al día (27/08)

Francisco pidió el dossier, la cobertura legal y el diseño de la aplicación, cada
uno en su artefacto y en su `.md`.

**El dossier** (v1.4 → v1.5, y artefacto): cifras al día ---1.272 pruebas de
backend, 286 de navegador en 50 ficheros, 127 vueltas--- y un cambio que toca lo
que se puede afirmar. El pilar «nada se borra» **decía más de lo que el producto
hacía**; ahora dice «nada se borra a mano», que es más fuerte y es verdad, y añade
el argumento de protección de datos que antes no se podía usar. Los huecos de
catalán y gallego pasan de «unas 460» a **507 de 703**, y el documento explica que
la cifra sube en vez de bajar porque cada función nueva añade mensajes.

**La cobertura legal**: aquí lo que iba a ser «añadir un apartado» resultó ser
**medio inventario mal**. El artefacto estaba en el corte del 12/08 y daba por
inexistentes los permisos retribuidos, las quince suspensiones del art. 45, los
festivos, las ausencias de parte del día y el tope de horas extra ---todo
construido desde entonces---. Reescrito desde el `.md`, que es su fuente
declarada, y las tablas se generan ahora con un script que **cuenta las filas** y
con eso rellena el total, la barra, la leyenda y el `aria-label`: el recuento
escrito a mano se había desincronizado y decía 91 situaciones con 49 sin cubrir
cuando había 90 filas con 48.

De 21/21/48 a **72 cubierto, 12 a medias, 27 falta** sobre 111. Lo que el `.md` no
detallaba se comprobó en el código: la baja **sí** distingue contingencia ---común
y accidente de trabajo, separadas y con su nota---, que el artefacto daba por «A
medias» y «Falta».

Añadida al `.md` y al artefacto la sección de **conservación del registro**, que
entra por la misma prueba que las demás y no estaba: el plazo obliga en los dos
sentidos, y el borrado no toca ausencias, contratos ni el rastro.

**El diseño de la aplicación** es un documento de otra naturaleza ---una propuesta
escrita el 11/08, antes de construir--- así que no se actualiza, se **contrasta**.
Se conserva la propuesta tal cual y cada decisión abierta lleva ahora su «así
quedó», más una sección final de lo propuesto frente a lo que hay. Tachar lo que
se pensó y dejar solo el resultado haría que dejase de servir para lo único que
sirve: saber por qué se eligió una cosa y no otra.

Tres de las seis salieron distintas de lo previsto, y por razones que el diseño no
podía ver: la bandeja de atención **se partió en dos** (el resumen se mira, la
bandeja se vacía), el menú creció de 9 a 13+4 entradas ---todas las nuevas salen
de un artículo, ninguna es idea de producto--- y turnos **se adelantó** porque sin
cuadrante no hay contra qué contrastar lo trabajado.

El documento de diseño **no tiene `.md`**: vive solo como artefacto.

### Vuelta 127 --- El plazo de conservación se cumple solo (27/08)

Tarea **3 de la lista**. `record_retention_years` llevaba desde la vuelta 60
declarando una política que ninguna tarea aplicaba, y el propio modelo lo decía en
un comentario: «lo que falta es que se cumpla sola, y eso es una operación
destructiva sobre el registro legal, así que no se añade sin decidirlo». Francisco
lo decidió el 27/08 con una condición ---que no se lleve por delante historiales
ni datos de la empresa--- y eso es lo que hay escrito en las pruebas.

Ahora lo aplica `purge_expired_records`, hermano de `purge_security_metadata` y
escrito siguiendo su patrón, que ya estaba resuelto: todas las empresas incluidas
las de baja, `objects_all_tenants` con filtro por empresa porque corre fuera de
petición, `--dry-run`, `--tenant`, asiento en el rastro y decir en voz alta lo que
se salta.

**Las tres decisiones que no eran obvias:**

1. **El suelo se aplica otra vez aquí.** `max(record_retention_years, 4)`, aunque
   el serializador ya rechace menos de cuatro desde antes: la validación de la API
   no alcanza a un número escrito por consola, por importación o por una migración
   de datos, y **este es el código que borra**. Con la fila a 1 año se habría
   llevado fichajes que el art. 34.9 obliga a tener; la prueba lo comprueba
   poniendo el 1 por `update` y verificando que se usan 4.

2. **El corte es un día entero en el huso de la empresa.** Cortar por instante
   ---que es lo que hace el hermano, y para metadatos está bien--- se llevaría la
   mañana de un día y dejaría la tarde. Y media jornada no es un dato menos: es un
   dato **falso**, un día en que alguien parece haber trabajado cuatro horas. Con
   `local_today(empresa)`, que ya existía.

3. **Las correcciones abiertas retienen su fichaje.** Un cambio que nadie resolvió
   no es un registro cerrado. Se cuentan y se dicen; borrarlas en silencio sería
   perder la única señal de que alguien pidió algo y no se le contestó en cuatro
   años.

**La trampa que casi se cuela:** `PunchCorrection.target` es `on_delete=PROTECT`,
así que borrar un fichaje corregido lanza `ProtectedError` y la pasada se planta a
mitad. No apareció en el primer barrido porque **busqué solo en `models.py`** y en
esta app los modelos están repartidos en seis ficheros (`corrections.py`,
`delegated.py`, `overtime.py`, `reminders.py`, `workday.py`). El barrido bien hecho
---todas las `ForeignKey` a `Punch` en cualquier `.py`--- sacó tres, más la
autorreferencia `replaced_by`.

**Y la pieza que iba a quedarse desconectada:** el comando solo no sirve para el
despliegue que eligió Celery. Registrada la tarea en `beat` a las 4:30 ---la última,
porque es la que borra jornada: si una noche algo va mal, las otras ya han pasado y
se lee en el registro cuál fue---. Aquí no hacía falta escribir la prueba: la de la
vuelta 99 **cuenta** los trabajos de Celery y los de la crontab del documento y
exige que sean los mismos, así que al añadir uno se puso roja sola. Es lo que se
quiere de un guard.

Actualizado `docs/trabajos-periodicos.md`, que decía «dos trabajos» y ya listaba
tres, y ahora son cuatro.

#### Lo que el borrado no toca, y por qué cada cosa

Ausencias y contratos (una vacación de 2021 explica un hueco en una nómina de
2021), decisiones de horas extra (son un acuerdo, y el art. 35 tiene su cuenta) y
el rastro de auditoría. Este último se comprobó antes de dar la purga por buena:
**si el rastro guardase las horas, la purga sería decorativa**. Guarda el UUID de
la corrección, no el antes y el después ---medido sobre los 27.101 asientos de la
empresa de demostración---, así que borrar el fichaje sí borra el dato.

#### Comprobado rompiendo, y en caliente

Las cuatro defensas del comando, una a una: sin el suelo, con corte por instante,
sin borrar antes las correcciones y sin retener las abiertas. **Cada una pone
exactamente una prueba en rojo**, y al restaurar vuelven las trece.

Y en la base de desarrollo, porque `Would delete 0 events` no prueba nada: creado
un fichaje de marzo de 2019, visto en seco, borrado de verdad, comprobado que se
fue, que el rastro tiene el asiento firmado por «sistema» y que no cayó nada más.

#### Verde al cerrar

`1.272` pruebas de backend (trece nuevas), `286` de navegador, `ruff` limpio, sin
migraciones pendientes. Dos migraciones que se detectaron **antes** del commit y no
después: el `help_text` del campo ---que decía «nothing is deleted automatically
yet» y ahora sería falso--- y las `choices` del rastro con la acción nueva.

Traducciones: los tres catálogos a **cero mensajes marcados `fuzzy`**. Aparecieron
dos al regenerar, y uno no era mío: el título del resumen del art. 6.1 arrastraba
la traducción de «un cambio en el registro de jornada» en catalán y gallego. Django
ignora los fuzzy, así que no se veía; aceptarlo a ciegas habría puesto ese título
en un documento legal.

### Vuelta 126 --- El número de empleado ya es único también para la base (27/08)

Tarea **2 de la lista**. La vuelta 118 arregló que dos personas de la misma
empresa pudieran llevar el mismo número escrito con otra caja ---`EMP-9` y
`emp-9`---, pero lo arregló **solo en el alta por API**: `validate_employee_id`
compara con `iexact`, igual que los dos sitios que resuelven una referencia (la
puerta de integración y el fichaje delegado). La restricción de la base seguía
comparando exacto.

Eso dejaba la puerta abierta a todo lo que no pasa por el serializador: el shell,
una importación, un `update` masivo, un `loaddata`. Y el daño no es del que lo
crea: cuando existen las dos, una puerta resuelve **una al azar** y la otra se
planta con «la referencia coincide con más de una persona», **para todos los
fichajes de esa empresa**.

Ahora el índice es funcional, sobre `Lower(employee_id)`:

```python
models.UniqueConstraint(
    Lower("employee_id"), "tenant",
    condition=~models.Q(employee_id=""),
    name="unique_staff_number_per_company",
)
```

Se conservan las dos mitades de la condición vieja, porque cada una sostiene un
caso real: el `condition` deja que **varias personas no lleven número** (numerar
es opcional, y sin eso una empresa que no numera solo podría dar de alta a una),
y el `tenant` deja que **dos clientes numeren desde el uno**. Las dos tienen
prueba propia, no solo el caso que se venía a arreglar.

#### La migración se niega antes de tocar nada

Cambiar un índice a único puede reventar a mitad si ya hay duplicados, y el
mensaje que da Postgres ---la clave que colisiona--- no dice **quién** es. Así que
la operación **primera** de la migración, antes del `RemoveConstraint`, es un
`RunPython` que agrupa por `(tenant_id, Lower(employee_id))`, y si algo sale con
más de uno lanza `RuntimeError` nombrando empresa, número y los correos:

```
Jardines Demo S.L.: 2 personas con el número «emp-choque»
  -> «EMP-CHOQUE» choque.mayus@demo.local, «emp-choque» choque.minus@demo.local
```

Y **no elige por su cuenta**: dice que cambie el número quien tenga que hacerlo,
«porque quién se queda el número lo decide la empresa: el número identifica a la
persona en sus nóminas y en su convenio». Renombrar a `EMP-9-bis` por detrás
sería un cambio silencioso en un dato que sale en documentos que firma un tercero.

En esta base **no hay ni un choque**, así que la defensa no salta sola. Se
comprobó a mano: vuelta a `users 0015`, dos personas creadas por shell con
`EMP-CHOQUE` y `emp-choque`, y al migrar se plantó con el mensaje de arriba
dejando la migración **sin aplicar** ---verificado con `showmigrations`---. Luego
se retiró el choque y migró a la primera. Una defensa que no se ha visto saltar
no está puesta.

#### Y de paso, el primer trozo de la tarea 6 --- con causa

La tanda de navegador de esta vuelta salió con **un rojo**: «Fichajes › filtra por
persona y por fechas», que a solas pasa. Es el patrón que ya conocíamos, pero esta
vez la causa se dejó ver entera, y **es la tarea 6**:

```js
await page.getByRole('option', { name: /Hugo Bermejo/ }).click()
await page.waitForTimeout(900)          // <-- espera por reloj
expect(await filas().count()).toBeLessThan(antes)   // <-- count() no espera
```

La pantalla de fichajes usa `placeholderData: (previous) => previous`, y hace
bien: **retiene las filas de antes** mientras llega la respuesta filtrada, en vez
de parpadear en blanco. El efecto es que a los 900 ms se pueden estar contando
**las cincuenta filas viejas**, y el fallo sale como «filtrar no quitó nada»
---acusando al producto de un defecto que no tiene---.

Medido para descartar la otra hipótesis: sin filtro la página va llena (50 de las
879 del mes), y con Hugo son 14 fichajes en 7 días. El margen es de 50 a ~21, así
que la aserción no es frágil por volumen: **lo único que puede fallar es la
carrera**.

Sustituida por espera por condición (`expect.poll`), más una comprobación de que
no pasó por quedarse vacía a medio pintar, que también sería «menos filas».

Y demostrado en caliente, con la API retardada a 2 s por `page.route`, las dos
versiones una al lado de la otra: **la vieja falla con el mismo mensaje que salió
en la tanda y la nueva pasa**. La demostración era un fichero de usar y tirar y ya
está borrado.

De paso, a dos líneas de allí había una aserción hueca: se pedía
`/punches/?search=Hugo` y solo se comprobaba el `200`, bajo un comentario que
prometía «que de verdad sean los suyos». Un filtro que ignorase el término
devolvería `200` con la empresa entera. Ahora se mira lo que trae.

**Quedan 40 esperas por reloj**, y ya se sabe qué buscar en cada una: no es el
reloj lo que falla, es el `count()`/`textContent()` crudo que hay detrás. Barridas
las cuarenta con ese criterio ---un `expect(await ...)` en las ocho líneas
siguientes---, **diez llevan el patrón exacto que acaba de fallar**:

```
03-sesion.spec.js:83            (2500 ms)
07-pantallas.spec.js:87          (600 ms)
11-resto-de-pantallas.spec.js:126, :242
12-acciones-masivas.spec.js:66   (800 ms)
15-filtros.spec.js:38, :53, :137, :147   <-- cuatro en el mismo fichero
30-contraste.spec.js:96          (400 ms)
```

Esas diez van primero en la vuelta que siga con la tarea 6, y `15-filtros` va
antes que ninguna. Las otras treinta esperan a que algo se asiente sin sacar
ningún valor detrás: son lentas, no frágiles, y se miran después.

#### Verde al cerrar

`1.259` pruebas de backend (siete nuevas), la suite de navegador entera, `ruff`
limpio, sin migraciones pendientes.

**Queda de la lista**: 3 (`record_retention_years`), 4 (acceso de quien ya no
trabaja allí), 5 (el `.md` del dossier; el artefacto ya está al día), 6 (las 41
esperas por reloj, que **no cabe en una vuelta** y se partirá), 7 (los 27
`date.today()`), 8 (los 501 huecos de catalán y gallego), 9 (pausa y modo de
trabajo al fichar, **recomendado implementar**) y 10 (dependencias).

### Vuelta 125 --- Retirados los huérfanos, y tres colores que no se leían (27/08)

**El bucle cambia de naturaleza aquí.** Francisco revisó los hallazgos abiertos el
27/08 y aprobó una lista de diez tareas; a partir de esta vuelta el `/loop` no
busca lentes nuevas, **ejecuta esa lista**. El contador de vueltas en blanco
---que iba por 2 de 3--- queda en suspenso: no aplica a un bucle que no está
buscando.

#### Lo hecho: la tarea 1

Retirados **4.917 ficheros** de `media/justifications`, 8,1 MiB. Quedan los **12**
que alguna ausencia referencia, y los doce siguen en disco.

El encargo venía con un aviso ---«cuidado con las comillas y las rutas»--- así que
se hizo en tres pasos y sin shell:

1. **Copia de seguridad** completa antes de tocar nada: 4.932 entradas en 111 KB,
   comprobada leyéndola. Está en el directorio de trabajo de la sesión.
2. **Simulacro** que no escribe: contó 4.929 ficheros, 12 referenciados, 4.917
   candidatos, y comprobó lo que de verdad importa ---**cero candidatos fuera de
   la raíz y cero enlaces simbólicos**---.
3. **La purga**, en Python y no en shell, repitiendo los mismos cinturones ---la
   raíz existe, se llama `justifications`, cuelga de `MEDIA_ROOT`--- y exigiendo
   las tres condiciones por fichero: dentro de la raíz, sin referencia, y fichero
   de verdad y no enlace.

Resultado: 4.917 borrados, **cero fallos**, y el resto de `media/` intacto. La
suite de backend en verde después, y el almacén sigue en 12 tras correrla ---que
es lo que arregló la vuelta 122---.

#### Y de camino, tres colores de la paleta

La tanda de navegador que cerraba la vuelta salió con cinco rojos. Cuatro eran
esperas por reloj con los contenedores recién levantados ---pasan aislados--- y el
quinto no: **«esperando a la empresa» estaba a 3,11 de contraste** sobre el blanco
que MUI le pone encima, cuando el mínimo para texto normal es 4,5.

Ese estado no aparecía en ninguna de las pantallas que recorre el barrido de
contraste, y saltó porque la demo tenía hoy una corrección en él. El tema ya
avisaba de esto mismo sobre un color anterior: «no lo vio el barrido ---su estado
no aparecía en ninguna de las pantallas recorridas--- sino la cuenta».

Así que la prueba nueva **cuenta la paleta** en vez de recorrer pantallas. Y al
escribirla aparecieron dos más: el rojo de error a **3,68** y el azul de
información a **3,86**, ninguno de los dos declarado en el tema ---venían de MUI---
y ninguno visto nunca por el recorrido.

Los tres declarados ahora con tonos propios: 5,26 el ámbar, 5,62 el rojo y 5,80 el
azul. En oscuro los de MUI ya iban bien, porque ahí el texto que llevan encima es
casi negro.

**Un tropiezo que casi lo estropea**: la primera versión de la prueba decidía el
color del texto por luminancia, que es la regla de manual. MUI usa otra ---blanco
siempre que el blanco llegue a 3--- y con la mía el rojo salía a 4,18, casi
aprobado. Con la de verdad, 3,68.

#### Y la cadena que llevaba desde la vuelta 96

La tanda de cierre volvió con dos rojos, **distintos** de los anteriores: la
prueba de las cuatro manos con **200 donde espera 409**, y el guard cazando un
departamento. Perseguirlo hasta el final dio la explicación de los rojos
intermitentes que arrastraba el proyecto:

1. Una prueba falla por espera por reloj y deja **un departamento con
   responsable**.
2. Eso activa el **alcance por departamentos** en toda la empresa.
3. Con el alcance activo, el único responsable de la demo deja de alcanzar a la
   administradora.
4. Sin nadie más que pueda decidir sobre ella, **el producto la deja aprobar** ---y
   hace bien: lo contrario deja un asiento mal sin forma de arreglarlo---.
5. La prueba se para ahí y deja la ausencia **aprobada**. Una aprobada no se puede
   cancelar, así que su propia limpieza no la recoge. **A partir de ahí no vuelve a
   pasar nunca**: choca por solapamiento antes de llegar a lo que quiere probar.

Medido al desenredarlo: **43 ausencias apiladas** en las mismas dos fechas, 42
canceladas y una aprobada bloqueando a las demás.

Arreglado dando a esa prueba **días propios de cada corrida**, que es lo que ya
hacía la prueba de al lado en el mismo fichero, con el porqué escrito a diez
líneas de distancia. Tres corridas seguidas en verde, donde antes la segunda ya
fallaba.

**Esto confirma que la tarea 6 ---las esperas por reloj--- es la raíz**, y pasa a
ser la siguiente.

### Vuelta 124 --- Las trece comprobaciones del cuadrante, rotas una a una (27/08) --- LIMPIA

Lente: **romper cada comprobación y ver cuál no echa nada de menos**, que es la
técnica que validó la vuelta anterior. Aplicada a los trece `_check_*` del repaso
del cuadrante, que son los avisos legales del producto.

Silenciando cada uno ---`return []` como primera sentencia--- y corriendo la suite:

| Comprobación | Pruebas que se rompen |
|---|---|
| descanso entre jornadas | 11 |
| horas semanales | 7 |
| menores de 18 | 6 |
| preaviso del cuadrante | 4 |
| trabajo nocturno | 3 |
| descanso semanal, festivo | 2 |
| pausa, promedio nocturno, semanas seguidas de noche, ausencia aprobada, tiempo real trabajado, fuera del contrato | 1 |

**Las trece están cubiertas.**

#### El falso hueco, y por qué

El primer barrido corrió solo `apps/shifts`, `apps/reports` y `apps/legal`, donde
uno esperaría que vivan esas pruebas. Con ese alcance, **dos salían sin
cobertura**: el turno en festivo y el turno fuera de las fechas del contrato. Dos
avisos legales sin nadie mirándolos habría sido un hallazgo gordo.

Con la suite entera, las dos rompen pruebas. Las cubren ficheros de otras apps,
que es lo normal en pruebas de extremo a extremo: una prueba de ausencias
ejercita el cuadrante sin vivir en `apps/shifts`.

Acotar la suite acelera el triaje ---once de trece resueltas en veinte segundos
cada una--- y a cambio convierte «no lo cubre esta app» en «no lo cubre nadie».
Cada candidato limpio se repite con todo antes de escribirlo.

### Vuelta 123 --- Los efectos diferidos, y cuáles prueba alguien (27/08) --- LIMPIA

Lente: **todo lo que va en `on_commit`**, que sale de la vuelta anterior: si algo
se hace ahí, en una prueba **no se hace**, y eso puede dejar comprobaciones que
pasan siempre.

Seis efectos diferidos: el apunte del rastro, tres avisos de corrección y el
borrado del justificante.

#### Primer ángulo: las aserciones que podrían no comprobar nada

Una prueba que afirme «no se mandó correo» sin capturar los callbacks pasa
siempre. Salieron **ocho candidatas** y **las ocho son válidas**: los correos de
invitación, de contraseña y de recordatorio se mandan **directamente** con
`send_mail`. Solo los de corrección son diferidos, y sus pruebas sí capturan.

La comprobación que las descartó cuesta un `grep`: no es «¿captura?», es «¿este
efecto es diferido?».

#### Segundo ángulo: qué efecto diferido no prueba nadie

Los tres avisos de corrección ---al proponer, al retirar y al resolver--- **no
aparecen por su nombre en ninguna prueba**. Parecía el hallazgo.

La medición buena no es buscar el nombre: es **silenciar la línea y ver qué se
rompe**. Silenciando cada uno de los tres, cada vez falló exactamente una prueba.
Los tres están cubiertos, por pruebas que los ejercitan por el endpoint y miran el
buzón sin nombrar la función. Y el borrado del justificante tiene la suya.

`grep` del nombre mide cómo están escritas las pruebas, no qué cubren.

### Vuelta 122 --- Las pruebas escribían en el almacén de desarrollo (27/08)

Lente: **los ficheros que entran**, los justificantes de una ausencia.

#### Lo que aguantó, y es mucho

- **La descarga, con los cuatro roles.** El interesado la obtiene y **no** deja
  apunte ---leer lo propio no deja rastro---; administración la obtiene y **sí**
  deja apunte; un colega y otra empresa reciben **404**, no 403, para no
  confirmar que la ausencia existe.
- **Las firmas de bytes**, que el módulo ya comprobaba: un PNG llamado
  `parte.pdf` y un HTML llamado `foto.png` se rechazan. También el fichero vacío.
- **Los nombres torcidos**, saneados o rechazados: `../../../etc/passwd.pdf` acabó
  guardado como `passwd_PRPASzA.pdf` ---la ruta se descarta---, la comilla y el
  salto de línea desaparecen, el nombre de trescientos caracteres se trunca y
  `...pdf` da 400.

#### Lo que no

Al retirar los ficheros de mi propia sonda apareció el número: **4.936 ficheros
en el almacén y 12 referenciados por una ausencia**. 8,1 MiB de huérfanos. Y
creciendo de forma medible: **4.391** el 26/08 por la mañana (v98), **4.625** unas
horas después (v108), **4.936** hoy.

La causa no es el producto. `descartar_justificante` borra el fichero en
`transaction.on_commit`, que es lo correcto ---no se tira un fichero hasta que la
fila que lo suelta está confirmada---. Pero **una prueba con `django_db` nunca
confirma su transacción**, así que ese borrado no se ejecuta jamás. Y como pytest
corre con los ajustes de desarrollo, escribía en `media/` de desarrollo.

Dos cosas correctas por separado que juntas hacen un almacén que solo crece.

#### Qué se ha hecho

`MEDIA_ROOT` a un temporal de sesión en `conftest.py`. Comprobado: la suite
entera ---1.252 pruebas--- deja el almacén en los mismos 4.929 ficheros, donde
antes cada tanda añadía cientos.

Dos pruebas, y la segunda es el contraste: que el almacén siga siendo escribible,
porque un `MEDIA_ROOT` apuntando a un sitio inválido pasaría la primera y rompería
el producto.

#### Pendiente de una decisión

**Los 4.917 huérfanos que ya están** siguen ahí. Son 8,1 MiB de ficheros de
prueba en `media/justifications/` y borrarlos es un `rm` de casi cinco mil
ficheros en la máquina: **no se hace sin que Francisco lo diga**. Lo que sí está
hecho es que dejen de aparecer.

### Vuelta 121 --- Los contenedores vacíos, uno a uno (27/08) --- LIMPIA

Lente: **los vacíos sin comentario**, que la vuelta anterior señaló como «una de
las señales más baratas que hay». Sin cambios de código: todo estaba en su sitio.

#### Lo que se comprobó

- **Los contenedores vacíos** declarados a nivel de módulo o de clase: nueve, de
  los cuales ocho llevan su explicación. El noveno es el `authentication_classes`
  del login, y **tiene que estar vacío**: si no, un token caducado en la cabecera
  daría 401 antes de poder entrar.
- **Las siete vistas abiertas a cualquiera**, leídas en columna: salud, la clave
  pública de avisos, alta, entrada, refresco, petición de contraseña y fijarla.
  **Las siete vacían la autenticación.** La columna está alineada.
- **Los ceros de los marcos legales**: `extra_when_travelling` y
  `qualifying_annual_share`, los dos documentados en su declaración.

#### Dos falsos positivos míos, y lo que enseñan

**El primer barrido dio 39 sospechosos.** Treinta y nueve en un producto con
veinte vueltas encima era demasiado bueno para ser cierto: casi todos eran
parámetros con `None` por defecto en firmas de varias líneas, y el resto tenían la
explicación en el docstring de la clase, seis líneas por encima de donde miraba.
Rehecho el detector con `ast` en vez de expresiones sobre texto, quedó **uno**.

**Y `qualifying_annual_share=0` parecía la pieza desconectada número veintiuno.**
Se rellena con el dato del art. 36.1 ---un tercio de la jornada anual--- y no lo
lee nadie. Pero la razón estaba escrita en los dos sitios donde tenía que estar,
y yo había leído uno: «el tercio anual no es algo que un mes de calendario pueda
ver, y por eso la empresa puede declararlo». El criterio se cubre por
declaración; la cifra está para que conste.

### Vuelta 120 --- Diecinueve avisos sin base legal para cualquier país que no sea España (27/08)

Lente: **leer en columna las comprobaciones hermanas**, que es la técnica que dio
los tres hallazgos anteriores. Aquí, los diecinueve avisos del cuadrante contra el
mapa que les pone el artículo.

#### Lo que se encontró

`finding_citations={}` en el marco de la directiva. Doce caracteres, **sin
comentario**, en un fichero donde cada hueco deliberado lleva su explicación: el
marco español tiene tres vacíos y los tres dicen por qué ---«sin cita a
propósito», «es un error de planificación»---.

Con él vacío, una empresa de un país no reconocido recibía **los diecinueve avisos
sin ninguna base legal**, cuando ese marco existe precisamente para «degradar a
algo defendible en vez de a las cifras de España bajo otra bandera». Y
`shifts/services.py` dice de sí mismo que «`basis` no es decoración: un aviso que
nadie puede rastrear a un artículo» no sirve.

Los artículos estaban escritos **diez líneas más arriba**, en las citas de las
cifras: art. 3 el descanso diario, art. 5 el semanal, art. 4 la pausa, art. 6.b
las cuarenta y ocho horas. El aviso y la cifra que lo produce salen del mismo
sitio y solo una de las dos citaba.

#### Qué se ha hecho

Los **siete** que la directiva sí fundamenta, citados. Los **doce** que no,
declarados con su motivo, cada uno por lo suyo: el preaviso de la distribución
irregular es nacional, las horas complementarias no existen en la directiva
---eso ya lo decía `complementary=None`--- y **los tres de menores los regula la
Directiva 94/33/CE, no esta**: citar la 2003/88 ahí sería apuntar a la ley
equivocada, que es peor que no citar.

De 19 mudos a 12 declarados. España no cambia: sus tres vacíos ya eran
deliberados.

#### La prueba no comprueba una lista

Lo fácil era comprobar los siete que cité. Eso protege siete y no impide que el
aviso número veinte salga mudo.

La prueba lee **los `code=` del propio fichero del cuadrante** y exige que de cada
uno haya una decisión: o cita un artículo, o está en una tabla de exentos **con el
motivo escrito**. Añadir un aviso obliga a pasar por ahí. Y la mitad contraria:
que los declarados sin cita **sigan sin ella**, porque rellenar por rellenar es
lo que un inspector desmonta en la primera pregunta.

### Vuelta 119 --- La identidad federada se podía duplicar cambiando una mayúscula (27/08)

Lente: **cada `iexact` contra su pareja de escritura**, el barrido que pedía la
lección de la vuelta anterior.

#### Lo que se encontró

En la función que impide pisar la ficha de otro, tres comprobaciones seguidas:

    if otros.filter(email__iexact=person.email)...
    if otros.filter(employee_id__iexact=person.employee_id)...
    if otros.filter(oidc_sub=person.oidc_sub)...          # <- exacto

Dos con `iexact` y la tercera sin él, mientras `_resolve` busca las tres con
`iexact`. Medido, empujando la misma identidad con la caja cambiada:

    SUB-1   -> 409 identity_taken
    sub-1   -> 201   crea otra persona
    Sub-1   -> 201   y otra

**Tres personas con la misma identidad**, y `_resolve` devolviendo la primera sin
decir que había más.

Era la peor de las tres para perder esa palabra. `oidc_sub` es «the immutable
anchor» del acceso federado, así que con tres anclas iguales quien entra por el
proveedor de identidad cae en cualquiera de las tres --- lo mismo que
`users/backends.py` ya advierte del correo duplicado, «son la misma persona
duplicada, y el acceso entraría en cualquiera», pero por la puerta que usan las
integraciones.

#### Qué se ha hecho

Una palabra: `iexact` en esa tercera línea. De tres personas a **una**, y las
tres cajas llegan a ella.

La mitad de las ocho pruebas es lo que no puede romperse: otra identidad distinta
sigue entrando, no tener identidad es lo normal en una empresa sin proveedor, y
**el empuje repetido de la misma ficha** ---lo que hace un conector cada noche---
no puede chocar consigo mismo.

#### Lo que escribí y retiré

También puse un `validate_oidc_sub` en el serializador de personas, que no tenía
ninguna comprobación. **No corría nunca**: DRF solo llama a `validate_<campo>`
para los campos declarados, y ese serializador no expone `oidc_sub` ---la API de
personas ignora el campo, la persona queda sin identidad---. Retirado con su
cadena de traducción: era exactamente lo que estas vueltas llevan encontrando,
código que parece proteger y no se ejecuta.

Medido en desarrollo: **cero identidades duplicadas** hoy.

### Vuelta 118 --- «EMP-9» y «emp-9» eran dos personas al crearlas y una al buscarlas (27/08)

Lente: **las escrituras de cada dato, no sus valores**, generalizando el hallazgo
de la 117 a los identificadores.

#### Lo que aguantó

**El correo está bien resuelto.** Se guarda normalizado ---`Ana.Lopez@Example.COM`
entra y queda `ana.lopez@example.com`--- y las cuatro variantes que probé
---minúsculas, mayúsculas, con espacios alrededor, caja mezclada--- se rechazan
como duplicado. Queda **una** persona.

#### Lo que no

El **número de empleado** distinguía mayúsculas al darlo de alta y no al
buscarlo. Los dos sitios que resuelven una referencia usan `iexact` ---la puerta
de integración y el fichaje delegado---, y el alta comparaba exacto. Con las dos
creadas:

    _resolve(«EMP-9»)          -> una de las dos, la primera, sin decir que hay otra
    resolve_employee(«EMP-9»)  -> «la referencia coincide con más de una persona»

Una puerta elegía al azar y la otra **se plantaba para todo el mundo**. Y el
conflicto lo creaba un tercer sitio que no sabía de los otros dos.

La pista, otra vez, fue la asimetría: el espacio **sí** se normalizaba ---« EMP-9 »
chocaba--- y la caja no. Igual que los ceros de la vuelta anterior.

#### Qué se ha hecho

`validate_employee_id` compara con `iexact`, que es lo que ya hacía todo lo demás.
La puerta de aplicaciones **ya estaba protegida** ---su `PUT` contestaba 409--- así
que era la de personas la que faltaba.

La mitad de las ocho pruebas es lo que no puede romperse: numerar es opcional,
dos personas sin número no chocan entre sí, un número distinto sigue valiendo, y
**quien conserva el suyo al editarse tiene que poder guardar** ---esa se rompe
sola si la comprobación no se excluye a sí misma---.

#### Decisión abierta

La restricción de la base ---`unique_staff_number_per_company`--- sigue siendo
sensible a la caja, así que por shell o por importación el conflicto todavía se
puede crear. Hacerla insensible pide una migración con índice funcional sobre
`Lower(employee_id)`, y **eso falla si en producción ya existen dos que chocan**.
Medido en desarrollo: **cero choques**. La decisión de migrar no es de auditoría.

### Vuelta 117 --- «20.00» no era 20 (27/08)

Lente: **lo que se valida al crear y no al modificar**, que sale de la lección de
la 116 ---una comprobación hecha en un sentido señala la que falta en el otro---.

#### Lo que aguantó

Las validaciones cruzadas de personas **sí corren en un `PATCH` parcial**, que es
donde suelen escaparse: pasar a tiempo parcial sin horas da 400, poner una fecha
de fin anterior al inicio mandando **solo** el fin da 400, y un `PATCH` legítimo
sigue dando 200. Están escritas combinando lo que llega con lo que ya había
---`attrs.get(campo, getattr(instancia, campo))`--- que es justo lo que hay que
hacer.

#### Lo que no, y apareció de rebote

Mandando las horas pactadas como `"20.00"` ---porque a mí me salió escribirlo
así--- contestó **400**. Con `20` contestaba 201.

    20      -> 201        0020.0  -> 201
    20.0    -> 201        20.00   -> 400
    20.5    -> 201        20.50   -> 400

**Los ceros de la izquierda daban igual y los de la derecha no.** Esa asimetría
es la pista: `DecimalField` cuenta los decimales del `Decimal` tal como llega, no
los significativos. Y el mensaje no ayudaba a verlo porque era cierto: «asegúrese
de que no haya más de 1 decimales» ---tiene dos, y ninguno cuenta---.

Pasaba en los tres campos que se pactan en horas ---las de la persona y las dos
del convenio--- y en el porcentaje del ERTE. Duele en integraciones: dos decimales
es como formatea cualquiera que venga del mundo de las nóminas, así que un
cliente correcto se comía un 400 por escribir el mismo número de otra manera.

#### Qué se ha hecho

`apps/common/campos.py`, que no existía: un decimal que normaliza el valor antes
de validar. Va como **mixin** de `ModelSerializer` para que los campos sigan
sacando `max_digits` y `decimal_places` del modelo ---declararlos a mano en cada
serializador es lo que hace que un día dejen de coincidir con la columna---.

Y la mitad de las nueve pruebas es lo que **no** puede aflojarse: `20.55` no es
`20,5`, media hora es el grano con el que se pactan las jornadas, y esa precisión
se sigue rechazando. Más lo que no es un número, que tiene que seguir dando su
propio error.

### Vuelta 116 --- La puerta de integración, atacada por dentro (27/08) --- LIMPIA

Lente: seguir donde la 115 lo dejó. Aquella encontró el **cruce** entre las dos
puertas; esta ataca la puerta propia de las aplicaciones.

**Todo aguantó**, y se midió cada cosa:

- **Aislamiento entre empresas**, por las cinco vías que hay para nombrar a una
  persona: correo, número de empleado, identificador, y también el `PUT` y el
  `DELETE`. Y fichar por alguien de otra empresa. Todas contestan **409
  «ninguna persona activa coincide»**, indistinguible de «no existe», que es lo
  correcto: confirmar que existe en otro sitio ya sería decir algo.
- **Los alcances**: una credencial de solo lectura **lee** (200) y no escribe ni
  borra (403), y una sin `punch:delegated` no ficha (403).
- **Revocar funciona**: 200 antes, **401** después.
- **La idempotencia**: la misma clave dos veces deja **un solo fichaje** (201 y
  luego 200), y sin clave contesta 400 con código propio.
- **El rastro identifica a la aplicación**: `PERSON_CREATED` con
  `actor=«aplicación · Conector»`.

#### Dos cosas que parecían hallazgos y eran mías

**El `PUT` sobre el correo de alguien de otra empresa devolvía 201.** Parecía
fuga; no lo es. Crea en `request.user.application.tenant` ---su propia empresa---
y el «crear si no existe» es el empuje de plantilla que el código documenta:
«alguien de temporada vuelve, y la aplicación de gestión lo da de alta otra vez
con el mismo número».

**El rastro parecía vacío**: cero apuntes al dar de alta. Se escribe en
`transaction.on_commit`, que en una prueba con `django_db` no llega a correr. Lo
desmontó el contraste ---medir lo mismo hecho por una persona, que también daba
cero--- y con `django_capture_on_commit_callbacks` aparecieron los apuntes.

#### Lo que sí deja esta vuelta

Al mirar si hacía falta escribir pruebas, apareció que **ya existían todas**
---aislamiento, alcances, el empuje que no roba el número de otro--- y entre ellas
esta: `test_a_person_token_does_not_open_the_application_doors`.

Es decir: **el cruce estaba probado en un sentido y no en el otro**, y el que
faltaba era justo el que la vuelta 115 encontró roto. Se prueba el sentido que
preocupa al escribir la puerta nueva; el inverso exige acordarse de un código que
ya funcionaba.

No se añaden pruebas: duplicarlas no protege más.

### Vuelta 115 --- Una credencial sin permisos entraba por la puerta de las personas (27/08)

Lente: **la puerta de integración**, atacada como lo haría una aplicación de
terceros. El producto tiene dos formas de entrar ---personas con sesión,
aplicaciones con credencial--- y cada una tiene su permiso. Los dos están bien
escritos. **El cruce no lo miraba nadie.**

#### Lo que se encontró

`ApplicationUser` contesta `is_authenticated` y trae `tenant_id`, porque el código
compartido no debería tener que preguntar con quién habla. Y eso es justo lo que
`IsAuthenticatedInTenant` comprueba. Medido con una credencial **sin ningún
permiso declarado** (`scopes: []`):

| Endpoint | Antes |
|---|---|
| `/departments/`, `/workplaces/` | **200** --- la estructura de la empresa |
| `/working-time-rules/` | **200** --- sus reglas de jornada |
| `/audit/` | `AttributeError: sin 'id'` --- un **500** |
| `/punches/`, `/absences/` | `AttributeError: sin 'pk'` |
| los dos informes | `AttributeError: sin 'tzinfo'` |

Donde no llegaba a leer, reventaba: un 500 en el sitio de un 403.

`HasApplicationScope` dice de sí mismo que «olvidar declarar un permiso no debe
abrir una puerta». No la abría él; la abría el permiso de al lado, que no sabía de
aplicaciones.

#### Qué se ha hecho

Una línea en `IsAuthenticatedInTenant`: si quien llama es una aplicación, 403 con
un mensaje que dice **cuál es su puerta**. Los doce endpoints pasan de 200 o 500 a
403.

Y **dos tercios de las quince pruebas son lo que no puede romperse**, porque una
línea mal puesta ahí deja fuera a toda integración ---daño mucho mayor que el que
arregla---: que la aplicación siga entrando por `/api/app/people/` y
`/api/app/attendance/`, y que una persona siga entrando por la suya. Comprobado en
caliente antes de escribirlas.

Una cadena nueva, traducida: **702 mensajes, cero sin traducir**.

### Vuelta 114 --- Una letra de menos y el informe era de otra persona (27/08)

Lente: **los mensajes de error, leídos**. Sale de la lección de la vuelta
anterior: probar los errores igual que las respuestas buenas, pasándole a cada
endpoint entradas malas y **leyendo la frase**, no solo el código.

#### Lo que aguantó

Quince formas de entrada mala ---identificadores que no son identificadores en
siete listados, cuerpos vacíos, JSON roto, tipos equivocados, páginas
inexistentes, fechas imposibles--- y **todas contestan una frase limpia y
traducida**, con el campo que falla en `details`. Los rangos numéricos también:
`0`, `-5` y `1.5` en el tope de jornada dan su mensaje propio.

El detector se calibró antes de fiarse de él: marca la forma del fallo de la
vuelta 113 y no marca una frase normal.

#### Lo que no

Los parámetros desconocidos se ignoran ---comportamiento por defecto---, y en el
documento del art. 34.9 eso no es una molestia:

    ?employe=<id de otra persona>      -> 200 con el registro de quien pregunta
    ?employee_id=<id>                  -> igual
    ?user=<id>                         -> igual
    ?date_form=2026-08-01               -> 200 con el periodo por defecto

Una letra de menos y el fichero que sale lleva otro nombre dentro. Un guion que
descargue la plantilla entera con la errata produce una carpeta de documentos que
no son de quien dicen ser.

**El proyecto ya había tomado esta decisión** en `refuse_wrong_period_names`, y
se había quedado en dos nombres: «lo que se pone a disposición de la Inspección es
el registro que se pidió, no otro». Aquí no es otro periodo: es otra persona.

Arreglado con lista blanca explícita en los dos documentos ---informe y resumen---
y **solo ahí**: en un listado corriente, rechazar lo desconocido rompería a quien
añade un parámetro para saltarse una caché; en un documento probatorio, un 400 es
mejor respuesta que el registro de otra persona.

Trece pruebas, y **la mitad son la lista blanca**: `format`, `scope`,
`department`, el periodo y ninguno, cada uno comprobando que sigue dando 200. Una
lista blanca a la que le falte un nombre rompe el producto de forma más cara que
el fallo que arregla.

Una cadena nueva, traducida: **701 mensajes, cero sin traducir**.

#### Tres fallos que eran míos

Las tres pruebas que fallaron al principio no eran del producto: había creado a
quien manda con `is_staff=True`, y lo que el código lee es `role`. `is_staff` es
de Django y aquí no decide nada. El 400 que volvía ---«solo puedes pedir tu propio
registro»--- se lee como un fallo y era un fixture mal armado.

### Vuelta 113 --- El mensaje de error salía con la clase de DRF dentro (27/08)

Lente: **el operario y su propio registro**, el perfil que llevaba varias vueltas
sin tocar. El art. 34.9 le da derecho a consultarlo y el 6.1 a recibir el
resumen.

#### Lo que aguantó

- **El operario obtiene su informe** ---PDF de 14 KB--- y en los tres formatos.
- **No ve a nadie más**: `/employees/` solo le devuelve a sí mismo, así que no
  hay ni a quién pedirle el informe.
- Administración y responsable sí obtienen el de otra persona de su alcance, y la
  empresa vecina solo el suyo.
- Antes, dos pares de la lente anterior: **turno sobre ausencia aprobada** ya lo
  avisa `_check_leave_clashes` ---y con el matiz de excluir las parciales y los
  ERTE de reducción, que son gente que sí debe estar en el cuadrante--- y los
  **fichajes anulados** no entran en el informe, que filtra `is_active=True`.

#### Lo que no

El manejador de errores metía el mensaje con `str(detail)`. Cuando el error viene
como **lista** ---lo que produce `ValidationError([...])`, y lo que sale cuando la
regla no cuelga de un campo--- el cliente recibía esto:

    [ErrorDetail(string='“pepe” no es un UUID válido.', code='invalid')]

La frase buena dentro, envuelta en el nombre de una clase de DRF. No se notaba
porque **el caso frecuente iba bien**: un error por campo llega como diccionario y
sale limpio, y un `NotFound` trae texto. Solo la rama de la lista, la menos
transitada, salía así. `ErrorDetail` hereda de `str`, de modo que uno suelto se ve
bien y la lista no.

Arreglado en el manejador, que es donde afecta a **todos** los endpoints a la vez.
Cinco pruebas, y dos son contraste: que los errores por campo sigan yendo a
`details` ---quien integra necesita saber cuál falla--- y que un `detail` de texto
se quede como estaba.

#### Cómo apareció, que es lo que conviene contar

Mi propia sonda estaba mal. Mandaba `?employee=<mi id>` y daba 400 en las cuatro
sesiones, lo que parecía un fallo redondo. No lo era: `/auth/me/` no devuelve el
identificador en el campo que yo leía, así que enviaba `?employee=undefined`.

Lo delató **el propio mensaje**, que decía «“undefined” no es un UUID válido» ---y
ese mensaje era el que estaba mal formado---. El experimento salió al revés de lo
previsto y encontró otra cosa por el camino.

### Vuelta 112 --- El día de vacaciones en el que se trabajó salía como un día normal (27/08)

Lente: **cuando dos cosas legítimas coinciden**. Una ausencia aprobada y fichajes
el mismo día: pasa, y no es raro ---a alguien de vacaciones lo llaman y viene---.

El sistema lo sabía. `build_report` rellena `row.absence`, y la ausencia **ya
entraba en la huella de verificación**, o sea que el producto la considera parte
del registro. El documento salía así:

    2026-08-12;08:00;13:00;05:00;

Las horas, y observaciones en blanco. Indistinguible de un día ordinario, en el
CSV y en el PDF.

#### Por qué es un fallo y no una cuestión de alcance

Porque **el documento ya había decidido que las ausencias constan en él**: un día
de vacaciones sin fichajes sale con «Vacaciones» en su columna. Dejaba de decirlo
justo cuando coincide con trabajo, que es el caso que hay que poder ver. Un día
libre sin trabajar no le hace falta explicarlo a nadie; uno en el que se vino, sí
---a la persona, si le descuentan el día y además trabajó, y a quien lee el
registro, para preguntar por qué---.

Y el código lo dice literalmente:

    if row.absence and not row.entries:      # aquí sí
    for entry, exit_ in row.entries:         # y aquí se olvidó

Es el mismo patrón que este fichero ya arregló una vez con la discrepancia del
art. 4.b: un dato calculado que los dos renderizadores ignoraban.

#### Qué se ha hecho

La nota va en `day_notes`, que es donde el proyecto decidió que vivan «para que
los dos renderizadores no se separen ---lo que ya pasó una vez, con el PDF
diciéndolo y el CSV callado»---. Una cadena nueva, traducida: **700 mensajes,
cero sin traducir**.

Cuatro pruebas, y tres son contraste: que un día de vacaciones **sin** fichar no
lo diga dos veces, que un día corriente no lleve ninguna nota ---o dejaría de
leerse--- y que dos días iguales en horas, uno con ausencia detrás y otro sin
ella, no compartan huella.

### Vuelta 111 --- El rastro contestaba «cero» a un periodo al revés (27/08)

Lente: **cada descarga contra su pantalla**, que sale de la lección de la 110
---cuando una salida enseña menos que otra del mismo dato, o sobra en una o falta
en la otra---.

#### Lo que aguantó, y se midió

El rastro de auditoría dice de sí mismo que el fichero lleva «las mismas
entradas que devuelve la lista, con los mismos filtros». Comprobado:

| Sesión | La lista dice | El fichero trae |
|---|---|---|
| administración | 22.598 | 22.598 |
| responsable | 292 | 292 |
| operario | 1.828 | 1.828 |
| empresa vecina | 2 | 2 |

Con filtros puestos también cuadra ---5.328 y 2.949 por tipo de acción--- y el
filtro de fechas funciona, validado contra un caso conocido: 2.328 apuntes hoy,
16.547 en dos días, 22.608 en el año.

#### Lo que no

**El periodo al revés.** `?date_from=2026-08-27&date_to=2026-08-26` contestaba
**200 con cero filas**, en el listado y en el fichero.

No hay consulta legítima que vaya del 27 al 26: es siempre un dedo equivocado o
un guion que arma las fechas al revés. Y el cero callado es la peor respuesta,
porque se lee como «no hubo actividad en ese periodo» --- en un rastro de
auditoría, la conclusión contraria a la verdadera.

Lo llamativo es que **la decisión ya estaba tomada**: el informe del art. 34.9 y
el cuadrante lo rechazan, cada uno por su cuenta, con el mismo mensaje ya
traducido. Faltaba en `LocalDayRangeFilter`, el filtro que comparten fichajes y
rastro --- que ya rechazaba los **nombres** equivocados del periodo con este
argumento: contestar 200 con un periodo que nadie pidió es lo que el art. 34.9 no
admite. El orden de las fechas es el mismo argumento.

Arreglado donde vive el mecanismo, reutilizando el mensaje que ya existía, así
que no se abre ningún hueco de traducción. Ocho pruebas, y **la mitad son el
contraste**: el mismo día en los dos extremos ---la consulta más corriente que
hay--- un extremo suelto, y una fecha mal escrita, que tiene que seguir dando su
propio error y no el del orden.

### Vuelta 110 --- El papel que acompaña a la nómina se titulaba como el otro (27/08)

Lente: **lo que quedó pendiente de la 109**, el botón «Generar los de toda la
plantilla», y de ahí a abrir todas las salidas del resumen de nómina.

#### Lo que aguantó

- El botón hace `POST /reports/payroll-summary/`, contesta **201** y la pantalla
  lo dice: «11 resúmenes generados para 2026-08-01 → 2026-08-31», con **los
  nombres** de quien se queda fuera por no tener horas. Sin `console.error`.
- **El periodo lo fija el ciclo de nómina, no quien pregunta**, y está razonado
  en el código: el art. 6.1 lo ata a «el periodo fijado para el abono», y dejar
  elegir fechas produciría resúmenes que no cuadran con ninguna nómina. La
  pantalla tiene su propio campo «Un día del periodo» para eso.
- **Quién puede generarlos**, con las cuatro sesiones: administración y
  responsable sí ---está decidido así, «un responsable o la administración»---, el
  operario recibe un rechazo con el motivo escrito, y la empresa vecina genera
  los suyos y **solo los suyos**.
- **Los formatos**: `json`, `pdf` y `csv` contestan 200 con los bytes que dicen
  ser ---`%PDF-1.4`, texto--- y con `Content-Disposition`; `xml` y `exe` dan 404
  con un error limpio, no un traceback.

#### Lo que no

**El CSV y el PDF del resumen eran el registro diario del art. 34.9.** Titulados
«Registro de jornada» ---el nombre del otro documento--- dentro de un fichero
llamado `resumen_…`. Y sin el **régimen** ni la **jornada pactada**, que la misma
petición en JSON sí devolvía.

Lo encontró comparar las tres salidas: **el JSON traía campos que el fichero no
enseñaba**. Cuando eso pasa, o sobra en la API o falta en el documento.

Importa por a quién va. El del art. 6.1 se entrega **con el recibo de salarios**,
y quien lo recibe compara sus horas con lo que cobra: un papel que se calla
contra qué régimen se miden esas horas no le sirve para eso, por más detalle que
lleve.

Arreglado: título propio, la línea que cita el art. 6.1, y las dos cifras que lo
hacen ser ese documento ---régimen y jornada pactada, más horas extra y días con
actividad---. El detalle diario se queda: informa de más, no de menos. Cuatro
pruebas, y una de ellas es **el contraste**: que el documento del art. 34.9 no se
haya convertido en un resumen, porque un `para_nomina=True` cableado por error
pasaría igual todo lo demás.

Cinco cadenas nuevas, traducidas al castellano ---699 mensajes, cero sin
traducir---. Catalán y gallego suman cinco huecos a los 501 que ya tenían, que
sigue siendo su propio hallazgo abierto.

### Vuelta 109 --- El informe acusaba de manipulación a 577 fichajes intactos (27/08)

Lente: **Inspección pidiendo un periodo**, uno de los cuatro perfiles, haciendo
su tarea entera y ---esto es lo que la hizo rendir--- **abriendo lo que se
descarga**.

El PDF empieza por `%PDF-1.4` y el CSV por `Registro`; los nombres llevan
apellido y periodo. Todo bien hasta abrir el CSV y leerlo:

    2026-08-03;07:53;12:53;05:00;un fichaje ya no cuadra con su sello de
    integridad: se alteró fuera de la aplicación

**Las siete filas con fichajes, todas.** Es la acusación más grave que ese
documento puede hacer, y la hacía sobre registros que nadie había tocado.

#### La causa

`compute_hash` sellaba `timestamp.isoformat()`, y esa cadena no depende solo del
instante sino del huso en que esté el objeto que lo lleva:

    2026-07-02T06:58:00+02:00   <- construido en la hora de la empresa
    2026-07-02T04:58:00+00:00   <- releído de la base, que devuelve UTC

Mismo momento, dos huellas. Todo lo escrito con hora local ---la semilla, una
importación, cualquier integración que arme el instante en el huso del centro---
se sellaba con una cadena y se verificaba con la otra.

Medido antes de tocar nada: **577 de 1.185 fichajes de la empresa de
demostración daban el sello por roto** ---el 100 % de los `MOBILE`, el 100 % de
los `TERMINAL` y el 28 % de los `WEB`--- y **los 577 cuadraban en hora local**.
Ninguno quedaba sin explicar, que es lo que convierte una hipótesis en una causa.

De paso, otra afirmación del código que no se cumplía: `seed_demo._history` dice
«the hash still comes out correct: it is computed on save from the fields». No
salía correcto.

#### El arreglo, sin reescribir un solo sello

El módulo lo prohíbe por escrito ---«reescribir un sello guardado es exactamente
la manipulación que el sello existe para hacer visible»---, así que:

- **`hash v4`**: igual que la v3 con el instante en UTC. Lo que se grabe desde
  ahora tiene una sola escritura posible.
- **Las anteriores** sellaron una representación, así que se prueban las
  escrituras válidas del mismo instante ---la de la persona y la de la empresa---.
  No afloja nada: todas describen el mismo momento.

De 577 rotos a **cero en toda la base**.

#### Y la mitad del trabajo fue comprobar que no se afloja

Porque un arreglo así puede convertirse en un permiso. Comprobado en caliente,
por SQL directo contra la base: adelantar el fichaje **dos horas justas** ---el
desfase de Madrid en verano, el caso que más de cerca pasa--- sigue dando el
sello por roto, y cambiar el origen también. El desfase va dentro de la cadena,
así que la misma hora escrita en otro huso no se confunde con otra hora.

Ocho pruebas, cuatro de ellas alteraciones de verdad que tienen que seguir
cazándose.

#### Lo que queda de esta lente

El botón **«Generar los de toda la plantilla»** no se llegó a comprobar: la sonda
esperaba la descarga sesenta segundos y el tope de una prueba son treinta, así
que se cortó sin decir si produce un ZIP, un fichero o nada. Queda para la
siguiente, y con ello «comprobar los bytes» de esa tercera salida.

### Vuelta 108 --- Las salvaguardas de la base, por su estado real (27/08) --- LIMPIA

Lente: la continuación de la anterior. Si un trigger podía estar presente e
inerte, **¿qué más protege la base y podría estar inerte?** Las veinte
constraints que declaran los modelos, y los índices únicos.

**Todas presentes y activas.** Catorce viven en `pg_constraint` y seis son
índices únicos parciales, los seis válidos. Ninguna constraint `NOT VALID`
---esas no se comprobaron sobre las filas que ya había--- y ningún índice
inválido, de los que un `CREATE INDEX CONCURRENTLY` a medias deja existiendo sin
imponer nada.

#### El falso positivo, que casi es el hallazgo

El primer cotejo dijo que **faltaban seis**: los dos de festivos, los tres de
`users_user` y el de los tipos de permiso. Seis de golpe es demasiado ordenado
para ser cierto, y no lo era: Django implementa una `UniqueConstraint` con
`condition=` como **índice único parcial**, así que vive en `pg_index` y no en
`pg_constraint`. La consulta miraba un solo sitio.

#### Lo que se ejercitó de verdad

- **La unicidad del correo.** `unique_email_per_company` es (empresa, correo) sin
  condición, y `unique_email_without_company` cubre el caso de empresa nula,
  porque Postgres trata los `NULL` como distintos y la primera no protegería ahí.
  El diseño está completo: una persona puede trabajar en dos empresas con el
  mismo correo y aun así no puede duplicarse dentro de una.
- **El parte de baja, que es dato del art. 9.** Se intentó subir un PDF a una
  ausencia de tipo baja médica: contesta **409** citando el RD 1060/2022, y
  ---lo que importaba--- **no queda ningún fichero en el almacén**: 4.625 antes y
  4.625 después. La constraint que lo prohíbe vive en la base «y no solo en un
  formulario», y el rechazo llega antes de escribir nada.

#### Validado contra dos casos conocidos

Un resultado limpio no vale sin esto. Se quitó `one_shift_per_person_per_day` y
se invalidó a mano `unique_identity_per_company`, cada una dentro de una
transacción deshecha: **el cotejo las echó de menos las dos veces**, y volvió a
«nada falta» al restaurarlas.

#### Descartado, con su motivo

**`transaction=True` no se puede usar en las pruebas**, porque ese modo vacía las
tablas con `TRUNCATE` en el desmontaje y el rastro no lo permite ---el mismo
trigger de la vuelta anterior---. Lo descubrí tropezando con ello, y resulta que
**el proyecto ya lo tenía documentado en cuatro ficheros de prueba**, con la
salida adoptada: `django_capture_on_commit_callbacks` para lo que necesitaría ese
modo. No es un hallazgo; queda aquí para no volver a proponerlo.

#### Decisión abierta que deja esta vuelta

El guardián de salud vigila **tres triggers y ninguna constraint**. La historia
del proyecto dice que estas cosas se evaporan ---los triggers se perdieron una vez
en una base real, con la migración marcada como aplicada--- y el mismo argumento
vale para las veinte. La comprobación está escrita y **validada dos veces** en
esta vuelta; conectarla al health es una decisión, no un arreglo, porque hoy no
falta ninguna. Y tiene que ir al health y no a una prueba, por lo que el propio
guardián ya razona: «las pruebas corren sus migraciones enteras y siempre los
ven; es exactamente el sitio donde no estaba el problema».

### Vuelta 107 --- El guardián del rastro no veía un trigger apagado (27/08)

Lente: **atacar lo que el código declara imposible**. Sale de la lección de la
vuelta anterior ---cuando el código afirma algo de sí mismo, hay que
comprobarlo--- pero apuntando a las afirmaciones más fuertes que hay: «nadie
escribe en el rastro por construcción», «la API no deja editar un fichaje», y los
tres triggers que hacen la tabla de solo añadir.

#### Lo que aguantó

Los siete métodos que no deberían existir, con **las cuatro sesiones**
---administración, responsable, operario y una empresa vecina---: `POST`, `PATCH`,
`PUT` y `DELETE` sobre el rastro y sobre un fichaje. **Los 26 intentos, 405.**

Y de paso, el aislamiento: el operario ve solo sus fichajes, administración y el
responsable los de su alcance, y la empresa vecina **cero**. El control ---un
`GET` que sí debe funcionar--- contestó 200 en las cuatro, que es lo que
demuestra que la sonda sabía distinguir.

Los triggers, atacados por SQL directo, rechazan `UPDATE`, `DELETE` y `TRUNCATE`
con su mensaje propio, y dejan pasar el `INSERT`.

#### Lo que no

`_check_audit_is_append_only`, el guardián de salud, preguntaba **si los tres
triggers están**. Existe precisamente porque una vez se perdieron en una base
real con la migración marcada como aplicada ---«una garantía que solo vive en una
migración se puede evaporar sin ruido», dice su comentario, que enumera «una
tabla recreada, una restauración, un `migrate --fake`»---.

**Estar no basta.** `ALTER TABLE ... DISABLE TRIGGER` deja el nombre en
`pg_trigger` y el trigger sin disparar, y eso es lo que hace `pg_restore
--disable-triggers`: **la restauración de una copia**, que su propia lista ya
citaba. Medido:

    trigger apagado (tgenabled='D')  ->  el guardián decía  (True, 'ok')
    y una fila del rastro se dejó reescribir

Arreglado: se mira `tgenabled` y solo valen `O` y `A`. El aviso distingue
«faltan» de «apagados», porque son averías distintas ---una se recrea, la otra se
vuelve a encender---. Tres pruebas, y con el guardián sin endurecer falla la del
trigger apagado.

#### El falso negativo que casi me creo

Los tres primeros ataques por SQL salieron «rechazados» y parecían la
confirmación de que los triggers protegían. No lo eran: la tabla no se llama
`audit_log` sino `audit_auditlog`, y los tres errores eran «relation does not
exist». Lo delató el **control** ---un `INSERT` que sí debía funcionar y
funcionó---, que dejaba claro que el modelo existía y que mi consulta no lo
estaba tocando. Sin esas dos líneas, la vuelta habría cerrado diciendo que todo
estaba protegido, y por el motivo contrario.

#### Anotado por honestidad

La sonda del trigger apagado **reescribió el campo `note` de una fila del rastro
de la base de desarrollo** (una de `STRUCTURE_CHANGED`) y lo dejó vacío. Es la
base de desarrollo y la fila sigue ahí, pero conviene que conste: la
comprobación consistía justamente en escribir donde no se debe poder.

### Vuelta 106 --- El informe declaraba ocho horas donde se trabajaron nueve (27/08)

Lente: **la noche del cambio de hora**. `apps/common/dst.py` ya existía, con las
dos fechas de 2026 y el razonamiento entero: quien entra a las 22:00 y sale a las
06:00 trabaja siete horas en marzo y nueve en octubre, y «los números que da el
producto ya son correctos» ---eso dice el módulo--- porque los fichajes guardan
instantes reales.

Se comprobó, que es de lo que va esto. **Los números eran correctos en la
pantalla y no en el documento:**

| Noche | Trabajado real | Pantalla | Informe |
|---|---|---|---|
| 25 de octubre (25 h) | 9 h | 9 h | **8 h** |
| 29 de marzo (23 h) | 7 h | 7 h | **8 h** |
| una corriente | 8 h | 8 h | 8 h |

La noche corriente es el contraste, y es lo que descarta que fuera un error del
montaje.

#### La causa

Python resta dos `datetime` que comparten `tzinfo` **como reloj de pared**:
ignora el `tzinfo` común y hace la cuenta ingenua. De 22:00 a 06:00 salen ocho
horas los 365 días del año. `build_report` convertía cada fichaje a la hora local
---para pintarlo--- y restaba esas horas ya convertidas.

`build_day_status`, que es lo que ve la pantalla, resta los instantes tal como
salen de la base, en UTC, que no cambia de offset. De ahí que una cifra fuera
bien y la otra no: **dos caminos para el mismo dato, y solo uno pasaba por el
módulo que sabía de esto**. `dst.py` lo tenía resuelto en `real_gap()`, importado
por las horas extra, el cuadrante y la cobertura. Por el informe, no.

#### Lo que esto significa

Es el documento del art. 34.9, el que se entrega. La ley va por el tiempo
efectivamente trabajado: en octubre le quitaba una hora a quien la había
trabajado ---y esa hora es la que la cola de horas extra sí registraba, con lo
que el papel y la cola tampoco cuadraban---; en marzo le atribuía una que no.
Dos noches al año, toda la plantilla que hace noches.

#### El comentario que era una prueba sin escribir

Tres líneas encima del fallo, el propio fichero decía: «`build_day_status` asks
the same question, and the two must agree: the figure on screen and the figure in
the document are the same day». Lo decía y no se cumplía. Ahora hay siete
pruebas ---las tres noches por las dos vías, más el CSV que se entrega--- y con
el arreglo revertido fallan las dos noches del cambio y la corriente pasa.

#### Repasado, no supuesto

Las **siete restas de tiempo** que hay en el producto: cinco operan sobre
instantes en UTC ---y UTC no cambia de offset, así que son correctas---, una es
la del propio `dst.py`, y la séptima era esta.

### Vuelta 105 --- Las dos mitades de la pantalla, a la una de la madrugada (27/08)

Lente elegida por el reloj: **el producto a esta hora**. La vuelta anterior había
dejado escrito que hay comprobaciones que solo se pueden hacer de madrugada, y a
la una de la mañana la ocasión estaba puesta.

El backend contesta bien lo básico ---`/shifts/today/` y `/overview/` decían el 27
cuando en UTC era el 26---, así que la pregunta se afinó: **el turno de noche**,
que en este dominio ---limpieza, seguridad, sanidad--- es de todos los días.

#### Lo que se encontró

`apps/punches/workday.py` existe para esto y lo explica con sus artículos: la
unidad no es el día natural sino **la jornada**, y la jornada entera cuenta en el
día en que empieza ---las nueve horas del art. 34.3, las doce de descanso entre
jornadas, el día y medio del art. 37.1, todo se mide así---. Lo usan el informe,
las horas extra y `/punches/today/`.

**`/shifts/today/` no.** Preguntaba por `local_today`, el día natural. Y las dos
pintan la misma pantalla de fichar. Medido, con una entrada real de las 23:10 y
la sonda a la una de la madrugada:

    /punches/today/   state=WORKING       worked=6398s
    /shifts/today/    state=NOT_STARTED   worked_minutes=0

La misma persona, el mismo instante: **está trabajando desde hace hora y tres
cuartos y no ha empezado**. Es literalmente el fallo que `punches/services.py`
dice haber arreglado ---«a las tres de la mañana un turno de noche veía "sin
empezar" en su propia pantalla mientras estaba trabajando»--- sobreviviendo en el
endpoint hermano.

#### Por qué llevaba ahí tanto tiempo

Porque **ya lo habían arreglado a medias**, y eso lo esconde mejor que el fallo
original. La vista preguntaba antes por `date.today()`; alguien lo vio, lo cambió
por `local_today` y dejó tres líneas explicando la medianoche. El huso quedó
bien; la unidad, no. Un `date.today()` pelado se caza con `grep`; un `local_today`
con un comentario sobre la medianoche se lee y se pasa de largo, porque parece el
sitio donde alguien ya pensó en esto.

#### Qué se ha hecho

- `/shifts/today/` pregunta por `current_workday`. Comprobado en caliente: pasa a
  decir `day=2026-08-26`, 107 minutos y `WORKING`, que es lo mismo que dice la
  otra mitad.
- `test_las_dos_pantallas_dicen_lo_mismo.py`, **con el tiempo congelado**: una
  prueba que solo dijera la verdad entre medianoche y las dos es justamente lo
  que dejó pasar esto. Comprueba que las dos concuerdan a la una de la madrugada
  y que el caso corriente de las diez de la mañana sigue bien. Con el arreglo
  revertido, falla.
- Repasados los **siete usos de `local_today`**: los otros seis son correctos
  ---la fecha de cabecera del conector, el fin de contrato, si una ausencia
  bloquea hoy, el consumo de permisos y los dos que son el propio respaldo de
  `current_workday`---. Van por día natural porque su pregunta es de día natural.

### Vuelta 104 --- El trabajo que solo corría en la mitad de los despliegues (27/08)

Lente nueva: **los trabajos periódicos**, que tienen estado propio y nadie mira
hasta que fallan. Dos hallazgos, y el segundo salió de rebote y vale más que el
primero.

#### Uno: la purga de testigos no corre en la instalación por defecto

Hay dos formas de programar los trabajos y `docs/trabajos-periodicos.md` las
documenta las dos: **cron, que es la de por defecto**, y Celery. La vuelta 99
añadió la purga de testigos de sesión caducados ---la que impedía que una tabla
creciera «del orden de dos millones de filas al año en una empresa de doscientas
personas»--- y la añadió **solo al `beat_schedule` de Celery**. La crontab del
documento seguía con dos líneas.

Es decir: el trabajo que existía para que algo no creciera sin techo no corría en
la instalación normal. La pieza hecha y desconectada otra vez, en su variante
«hecha para una de las dos vías».

Arreglado: la línea en la crontab, la fila en la tabla, y el apartado «qué pasa
si no configuras ninguno» ---que hablaba de una sola purga--- ahora habla de las
dos, con el art. 5.1.e para la segunda.

**La prueba que lo ata**: `test_los_trabajos_periodicos.py` registra los trabajos
de Celery con un sender espía y los cuenta contra los `manage.py` de la crontab
del documento. Se cuentan en vez de compararse por nombre porque los nombres no
coinciden a propósito ---la tarea es `flush_expired_tokens` y el comando
`flushexpiredtokens`, que lo trae simplejwt---. Comprueba además que cada comando
de la crontab **existe**: una errata ahí no falla, cron la ejecuta y el error se
va al correo de root que nadie lee.

Para que la prueba pudiera leer el documento hubo que montarlo: el contenedor
solo monta `backend/`. Va como `/docs` en solo lectura, igual que ya iban
`agreements` y `holidays`, y la prueba busca en los dos sitios y **falla diciendo
dónde buscó** en vez de saltarse a sí misma.

#### Dos: la suite entera miente según la hora a la que se corra

Al correr la tanda de backend a las 00:10 falló una prueba del PDF que llevaba
semanas en verde. No era fragilidad: fallaba tres de tres, aislada, y también con
el árbol limpio del commit anterior.

Dos husos. El contenedor va en UTC; la empresa de la prueba, en `Europe/Madrid`.
El fixture fichaba con `register_punch()` ---que guarda el día en la hora de la
empresa, el 27--- y pedía el informe de `date.today()` ---la fecha del
contenedor, el 26---. **Entre medianoche y las dos de la madrugada en verano son
días distintos.**

Y lo llamativo: **el producto ya lo tenía resuelto**. `apps/common/clock.py`
existe para esto, dice que `date.today()` es la trampa, que «se coló cuatro veces
antes de que este módulo existiera», y un comentario de `attendance_api` celebra
haber quitado «el último que quedaba en todo el código». Las pruebas se quedaron
con la trampa: **28 usos**, y nueve ficheros la mezclan con hora local.

**Esto explica el misterio que llevaba abierto desde la vuelta 97**: por qué la
tanda completa fallaba en una prueba distinta cada vez. Las vueltas se dan de
madrugada.

Arreglada la que rompía. Las otras se dejan medidas, no tocadas: con la suite
corrida **dentro de la franja** ---22:14 UTC, que son las 00:14 en Madrid--- las
1.150 pasan, así que ninguna de las otras 27 rompe hoy. Queda como hallazgo
abierto con su plan.

#### Tres: dos segundos y medio que dejaron de bastar

La tanda de frontend, corrida también dentro de la franja, dio **cuatro rojos**.
Eran dos, y sus consecuencias: dos pruebas de acciones masivas fallaron a mitad,
y el guard de la vuelta 101 cazó lo que dejaron puesto ---tres personas y dos
departamentos---.

Y ahí el guard hizo más que avisar: **los cinco residuos llevaban la marca de la
misma tanda**. Eso descartó de un vistazo la hipótesis con la que empecé
---sedimento acumulado de corridas anteriores--- y dejó la causa dentro de esa
misma corrida.

Medido antes de concluir: la prueba **pasa aislada**, y **pasa también con los
doce primeros ficheros** ---124 pruebas---. Solo cae dentro de las 283. La causa
estaba escrita a la vista: `await page.waitForTimeout(2500)` entre pulsar «mover»
y preguntar por el resultado. Dos segundos y medio bastan casi siempre; al final
de una tanda larga, no. Y el fallo no se parecía a su causa ---decía «esperaba 3,
encontré 0», que suena a que no se movió nadie, cuando lo que pasaba es que
todavía no se había movido---.

Arreglado con `expect.poll`, que pregunta hasta que la respuesta llega y falla
con tope. Además:

- La segunda prueba **no retiraba su departamento si fallaba antes de llegar al
  final**: ahora lo busca por nombre y lo borra en un `finally`, porque cuando
  esto falla lo hace antes de que la prueba sepa el id.
- Cuando el diálogo no se cierra, el fallo ahora **dice lo que el diálogo pone**
  en vez de limitarse a «seguía visible».

Quedan **42 esperas por reloj** en veintiún ficheros. Anotado, no tocado.

### Vuelta 103 --- Las advertencias del propio código, comprobadas (27/08) --- LIMPIA

La lente sale de la 102, que salió de la 101: **si un comentario avisa de un mal
uso, ese mal uso está en alguna parte**. Fue así como se encontraron los cinco
catálogos cortados. La pregunta era si el filón seguía dando.

Hay 76 advertencias en comentarios ---53 en el backend, 23 en el frontend---, así
que se acotó a las verificables: las que dicen «esto solo vale para X» y las que
narran un fallo pasado. Cinco ángulos, **los cinco limpios**:

1. **Diez `queryFn` pasados «pelados»** a React Query, que los llama con su
   propio contexto ---`{client, queryKey, signal}`--- y lo manda como parámetros
   de consulta. El comentario que lo cuenta dice que «rompería el día que exista
   un filtro que se llame como una de esas tres claves». Los diez apuntan a
   getters con firma **sin parámetros**, así que el contexto se ignora. Sin caso.
2. **Las protecciones de menores.** El aviso dice que sin `date_of_birth` no se
   aplica ninguna. Las dos mitades están: el campo, en el formulario de personas;
   y del otro lado `_check_under_eighteen`, el descanso semanal propio y la
   prohibición de horas extra del art. 6.3.
3. **Los diecisiete sitios que decidían quién ve a quién**, unificados en
   `common/scope.py`. Cuatro vistas no lo usan, y las cuatro tienen su propia
   regla y es la correcta: el rastro da la vista de empresa **solo** a
   administración ---y deja fuera al responsable a propósito, porque es de quien
   el rastro suele tener algo que decir---, las aplicaciones piden `IsAdmin`, las
   suscripciones filtran por la propia persona y la clave pública es pública.
4. **Los dos avisos que hablan de «la primera página»** ---la plantilla en
   Informes y el nombre en los avisos del cuadrante--- describen fallos ya
   arreglados, no vigentes.
5. **`updated_at` con `update_fields`.** Se arregló en la raíz, en el `save()` de
   la base. Queda el hueco de `queryset.update()`, que no pasa por ahí: hay
   cuatro usos y ninguno toca campos que el conector sincronice
   ---`last_used_at`, `last_sent_at` y la purga de IP---. Y los cuatro modelos
   que no heredan de la base no los expone el conector.

#### Por qué esta vuelta cuenta como limpia y no como floja

Porque la lente está **calibrada**: el barrido de advertencias incluye el
comentario de `rows()`, que es el que dio el hallazgo de la vuelta anterior. Una
comprobación que no encuentra nada solo vale si se ha visto encontrar algo, y
esta lo encontró ---ayer---.

#### Anotado

El aviso del punto 1 describe una bomba con la espoleta puesta: el día que
alguien añada un parámetro a uno de esos ocho getters, la petición se irá con el
contexto de React Query dentro y DRF lo ignorará en silencio. Se puede cerrar
haciendo que `get()` rechace `client`, `queryKey` y `signal`. **No se hace ahora**
---no hay ningún caso y el comentario ya lo advierte--- pero queda dicho.

### Vuelta 102 --- Los cinco catálogos que venían cortados a cincuenta (27/08)

La lente sale de la lección de la vuelta anterior, que es como salió también la
99 de la 98: **qué más asume que cabe en una página**. El guard del sedimento
casi se queda ciego por eso, y la pregunta era si el producto tenía el mismo
punto ciego.

Lo tenía, y el propio código lo decía. `rows()` en `services/api.js` lleva
escrito encima que es «solo para endpoints que responden con todo» y que usarlo
en uno paginado tira `count` y `next` ---«que es exactamente lo que pasaba, y
hacía que los fichajes, las personas y el rastro enseñaran las cincuenta
primeras filas»---. Ese aviso es de cuando se arreglaron esas tres pantallas.
**Quedaron cinco llamadas más sin tocar**, y ninguna vista del backend desactiva
la paginación, así que la condición del comentario no la cumplía nadie:

| Catálogo | Cuántos hay hoy | Para qué se usa |
|---|---|---|
| `/leave-types/` | **32** de 50 | el selector de «qué permiso pido» |
| `/holidays/` | 0 en la demo | los días que no se espera que se trabaje |
| `/departments/` | 4 | selector de departamento |
| `/workplaces/` | 2 | selector de centro |
| `/shift-patterns/` | 7 | selector de patrón de turno |

**Duele distinto en un catálogo que en una lista.** Una lista con `Pager` dice
«1-50 de 1.284» y quien mira sabe que hay más. Un catálogo llena un **selector**:
lo que no se cargó no se puede elegir, no sale ningún error, la opción
sencillamente no está. Y los dos comentarios que hay sobre estos getters dicen
para qué tienen que estar completos: de los festivos «depende su saldo de
vacaciones», y del catálogo de permisos, «nadie puede pedir un permiso que no
ve».

El de permisos va por **32 de 50**, y crece con cada convenio. Los festivos pasan
de cincuenta en cuanto la empresa tiene centros en varios municipios: dos locales
por cada uno, más los nacionales y autonómicos.

#### Qué se ha hecho

- **No se ha escrito ningún mecanismo nuevo.** `periodoEntero()` ya existía en el
  mismo fichero ---recorre páginas, con tope de veinte y `hasMore` para no
  mentir---, así que los cinco getters pasan por él a través de
  `catalogoEntero()`. Si alguna vez hubiera más de mil, se dice por consola en
  vez de callarlo.
- **`48-el-catalogo-entero.spec.js`**: crea 55 festivos ---cinco más de los que
  caben--- en el año que viene, comprueba que la pantalla enseña el de fecha más
  tardía y que el contador dice 55, y los retira en un `finally`.
- **El guard de la vuelta 101 vigila ahora también los festivos**, que son
  catálogo y no estaban: un día marcado como festivo cambia lo que se espera que
  la gente trabaje.

#### Comprobado, no supuesto

Los nueve endpoints que pasaban por `rows()` se midieron uno a uno con la sesión
real: **cinco vienen paginados y cuatro planos** ---`/leave-types/usage/`,
`/shifts/roster/`, `/absences/calendar/` y `/absences/pending/`---, y esos cuatro
se han dejado como estaban.

Y la prueba se validó al revés antes de darla por buena: **con el arreglo
revertido falla**, diciendo que el festivo 55 no llegó a la pantalla. Sin eso no
habría sabido si prueba algo.

### Vuelta 101 --- El guard del sedimento (26/08)

Cuatro vueltas seguidas se habían ido en arreglar pruebas que fallaban **por lo
que había dejado otra**: dos cuentas apellidadas «Bloque» que se colaban al
principio del orden (94), una ausencia en fechas fijas que chocaba con la de la
tanda anterior (95), ocho centros que ponían tres botones «Editar» en una
pantalla (96), un tope de jornada que quedó en 26 (97). Cada vez el síntoma
señalaba un sitio distinto del culpable, y cada vez lo arreglé caso por caso.

Eso no converge. Esta vuelta pone el **guard**: `e2e/zz-sin-residuos.spec.js`,
que corre el último de la tanda ---por el prefijo `zz`--- y falla **nombrando**
lo que quedó.

#### Qué se ha hecho

- **La limpieza de lo ya acumulado**: 15 centros de prueba y 5 personas
  retiradas. La demo baja de 26 personas activas a 21.
- **El guard**, con cuatro comprobaciones: personas activas de prueba, centros,
  departamentos, y que los ajustes de empresa quedan como estaban.
- **`08-formularios-gestion`** ya retira el centro que crea.
- **`31-idioma`** da de baja a su persona en un `finally`: estaba fuera, así que
  cualquier fallo intermedio la dejaba activa para siempre. De ahí salieron las
  que hubo que barrer a mano.
- **`corrections.py`** llevaba desde la vuelta 93 sin pasar por `ruff format`, y
  nadie lo vio porque el formateador del backend no estaba en mi comprobación de
  cierre. Ahora sí.

#### Lo que costó tres intentos, que es lo que vale la vuelta

El guard **se puso verde a la primera**, y verde era el resultado correcto:
acababa de limpiar la base a mano. Eso no demuestra nada, así que planté un
centro y un departamento con marca y volví a correrlo. Falló nombrando
exactamente esos dos. Tres cosas salieron de ahí:

1. **El patrón cazaba a la semilla.** Pedía `p` y seis caracteres, y
   `parcial@demo.local` encaja. Un guard que señala lo que tiene que estar ahí se
   apaga a la semana. Ahora pide doce, que es lo que mide la marca de verdad.
2. **La lista venía paginada.** `PAGE_SIZE` es 50; con 21 personas activas cabía
   todo y por eso pasaba. En cuanto el sedimento creciera de 50 ---justo cuando
   hace falta--- habría estado mirando las 50 primeras y **callándose sobre el
   resto**. Y pedir `page_size=1000` tampoco basta: la API tope ese valor y sobre
   las 709 personas de la base la lista seguía partida. Solo se supo porque la
   comprobación mira `next`.
3. **Dos personas activas eran intencionadas.** `37-cobertura` y
   `38-datos-extremos` reutilizan un correo **fijo**: es la misma persona tanda
   tras tanda, no crece, y la de cobertura queda activa porque su caso consiste
   en darle de baja y hay que devolverle el alta. El guard buscaba mal: lo que
   persigue es **lo que crece**, no lo que existe. Ahora hay una lista cerrada de
   reutilizados ---y una comprobación de que no se dupliquen, porque si una
   prueba deja de encontrar el suyo da de alta otro con el mismo correo y la
   lista empieza a crecer por donde nadie mira.

En la primera tanda completa el guard cazó exactamente esos dos casos legítimos,
que es como se supo del punto 3.

#### De paso: la tabla de cobertura legal

Verificadas contra el código las **nueve filas incompletas** de la tabla de
situaciones de jornada. **Ocho son correctas**; una estaba desfasada:

- **Horas extraordinarias (art. 35)** decía «el tope de 80 al año no se contrasta
  con lo trabajado». Sí se contrasta: `overtime_used()` lo calcula descontando
  las compensadas con descanso y las de fuerza mayor, `overtime_views` lo sirve y
  `Decisions.jsx` lo avisa en pantalla citando el 35.2. Conectado de punta a
  punta. Fila corregida.

Las otras ocho se sostienen: complementarias sin acumular el tope mensual,
distribución irregular sin saldo, guarda legal sin fracción ni fechas de la
reducción, adaptación del 34.8 solo como razón de fichaje, trabajo a distancia
sin acuerdo ni umbral, y las tres del RD 1561/1995 ---guardias, tiempo de
presencia, jornadas especiales--- que no existen como concepto.

También se verificaron las **cinco filas incompletas de la tabla de modalidades
de contrato**, y las cinco se sostienen:

- **Fijo discontinuo** tiene la casilla, pero no hay llamamiento ni periodos de
  actividad.
- **Los dos formativos** comparten un único `WorkingTimeRegime.TRAINING`: ni se
  distingue el 11.2 del 11.3, ni se topea el 65 % / 85 % del 11.2.b.
- **Contrato de relevo**: lo que el código llama «relevo» es siempre el relevo de
  turno, otra cosa.
- **Jubilación parcial**: no aparece.

**Catorce filas comprobadas contra el código, una desfasada.** La tabla es
fiable: las carencias que enumera son reales, y la respuesta a «¿habría que
implementar esto?» es que sí ---salvo el tope de horas extra, que ya está---.
Queda como decisión de producto, no de auditoría, en qué orden.

#### Anotado, no arreglado

- **Los catálogos de catalán y gallego han pasado de 460 huecos a 501.** Cada
  vuelta que añade cadenas de interfaz amplía el hueco; la propia vuelta 100 lo
  hizo. Sigue en hallazgos abiertos.

### Vuelta 100 --- Un convenio nuevo ya no reescribe lo cerrado (26/08)

No es una lente: es la **decisión abierta de la vuelta 94**, que Francisco tomó
hoy --- «versionar por fecha de efecto, pero solo esas dos reglas».

La vuelta empezó con otra lente ---**qué sale por correo**--- y esa salió limpia en
los seis ángulos que se midieron, así que queda hecha:

- Las plantillas **no llevan el motivo** al aviso a la representación legal, que
  sería colar un dato del art. 9 a un tercero. Llevan persona y día, que es lo que
  el art. 4.b pide.
- **Solo administración** marca a alguien como representante: responsable y
  operario reciben 403, también sobre sí mismos. Importaba porque quien lleve esa
  marca recibe avisos de discrepancias de **toda** la empresa, no solo de su
  departamento.
- El filtro de representantes es por empresa y activos, y **si no hay ninguno lo
  hace constar** en vez de callarse.
- Los recordatorios son **opt-in**, solo a quien está de alta, y respetan la
  ventana de silencio **en la hora de cada persona** ---art. 88 LOPDGDD, con
  Canarias contemplada.
- El enlace de cuenta es **de un solo uso** de verdad: el testigo se deriva del
  hash de la contraseña, así que usarlo lo invalida.
- Y el plazo que promete ese correo **no está escrito a mano**: sale de
  `PASSWORD_RESET_TIMEOUT`, precisamente porque el ajuste se puede cambiar. Era el
  candidato más claro a «el texto promete lo que el código no hace», y no lo era.

#### Qué se ha hecho

`ComputationRuleChange`: desde cuándo aplica cada valor de las **dos** reglas que
deciden qué dice el registro.

- **Solo dos**, y la razón es la misma que separó el huso en la vuelta 93.
  `break_counts_as_work` y `max_open_hours` deciden **cuántas horas figura que se
  trabajó**; eso es un hecho y el art. 34.9 lo quiere reproducible. Las otras
  dieciséis deciden **si eso cumple**, y deben recalcularse con lo vigente hoy: si
  un convenio nuevo mejora el descanso, se quiere ver qué días de antes no lo
  cumplirían. Hay prueba de que esas dieciséis **no** piden fecha.
- **La fecha la declara quien cambia la regla.** Cambiar una de las dos sin
  `effective_from` contesta 400. El sistema no puede saber desde cuándo aplica un
  convenio, y poner «desde hoy» sería tomar una decisión laboral que no le toca.

#### Dos cosas que solo aparecieron midiendo

**El arreglo no servía de nada sin anclar el pasado.** Declarando que la pausa
cuenta desde julio, abril **se movía igual** de 7:00 a 8:00: los días anteriores a
la fecha no encuentran ninguna vigencia y caían en las reglas de hoy, que son
justo las que se acababan de cambiar. Así que el primer cambio deja constancia de
cómo se contaba hasta entonces.

**Y el ancla tuvo que regir desde siempre.** Con la fecha de alta de la empresa no
bastaba: si el alta es posterior al periodo que se consulta ---una empresa dada de
alta después de importar su historial--- el ancla no lo cubre y vuelve a caer en
las reglas de hoy. Medido las dos veces, con el mismo abril.

#### Y un orden de validación que estaba del revés

Al exigir la fecha **antes** de validar el valor, poner un tope de cero contestaba
«falta la fecha de efecto» --- te hacía declarar una fecha para un número que se
iba a rechazar igual. Ahora el valor se valida primero. Lo destaparon las dos
pruebas de la vuelta 95, que se pusieron rojas al cambiar el comportamiento y
tenían razón.

#### Y una regresión mía, cazada por una prueba de la vuelta 97

Al exigir la fecha en la API **rompí la pantalla de Ajustes**: el formulario
seguía guardando sin ella, el servidor contestaba 400 y el tope no cambiaba. La
cazó `35-jornada-abierta` ---la misma prueba cuya restauración se arregló en la
vuelta 97--- con su mensaje de siempre: «la pantalla decía que guardaba y el
backend seguía con lo de antes».

Cambiar la API sin la pantalla deja el producto roto para quien lo usa, aunque las
pruebas del backend estén todas en verde. Ahora el formulario pide la fecha, y solo
cuando se toca una de las dos: pedir una fecha de convenio para cambiar el margen
de entrada sería ruido.

El valor por defecto es hoy, pero se puede mover, porque **un convenio se firma en
marzo y entra en enero** más veces de las que uno cree.

6 pruebas nuevas en el backend (1.147) y 2 de navegador (277), una migración y los
textos traducidos.

### Vuelta 99 --- Lo que crece y nadie recoge (26/08)

La lente sale directa de la lección de la vuelta anterior: **contar es más rápido
que forzar**. Aplicada en general --- ¿qué tablas crecen sin que nada las recoja?

#### El recuento

| tabla | filas |
|---|---|
| `audit_auditlog` | 19.513 |
| `token_blacklist_outstandingtoken` | **3.322** |
| `token_blacklist_blacklistedtoken` | **2.348** |
| `punches_punch` | 1.410 |

Y frente a eso, **una sola purga programada**: `purge_security_metadata`, a las
3:30. El planificador tiene exactamente dos trabajos, y ninguno toca los testigos.

#### El hallazgo

La rotación de testigos está activada ---y con razón, es lo que impide reutilizar
un refresco robado--- así que **cada renovación deja dos filas**: el nuevo
registrado y el viejo en la lista negra. Con un acceso de quince minutos son unas
treinta por persona y jornada.

De los 3.322 registrados, **1.769 estaban ya caducados**: el 53 %, y el más
antiguo de dos semanas atrás. En una empresa de doscientas personas eso son del
orden de **dos millones de filas al año**, creciendo para siempre.

Y no son filas cualesquiera: cada una dice **de quién** era la sesión y cuándo
empezó. Guardarlas sin plazo es exactamente lo que el propio producto ya razona en
`purge_security_metadata` para los metadatos de red --- «conservar un dato porque
algún día pueda ser útil no es una base» (art. 5.1.e).

`flushexpiredtokens` viene con simplejwt **hecho**. Lo que faltaba era llamarlo:
es el patrón de la auditoría entera, la pieza existe y nadie la conecta.

Programado a las 4:00, separado de la otra purga para que los registros se lean
bien cuando una tarde de más. Con prueba de que **no echa a nadie de su sesión**:
un testigo vigente sigue sirviendo para renovar después de purgar.

3 pruebas nuevas (1.141 en el backend).

### Vuelta 98 --- Cuatro mil justificantes sin dueño (26/08)

La lente: **fallos parciales.** Qué queda a medias cuando algo del camino falla.
El teclado, que era la otra candidata, ya estaba hecho ---`33-teclado.spec.js`, y
su docstring dice que salió limpio.

#### Tres ángulos que salieron limpios, y por qué

- **El rastro antes del zip.** `_many` escribe los asientos de exportación y
  **después** arma el fichero. Forzando que el PDF de la tercera persona reviente:
  la descarga da 500 y el rastro suma **+0**. Lo salva `ATOMIC_REQUESTS = True`
  ---la petición entera es una transacción, y los `on_commit` de `record()` no
  llegan a correr. El rastro no miente.
- **El almacén caído al subir.** Con el guardado del fichero reventando, la
  ausencia **no se crea**: la transacción lo deshace.
- **La solicitud rechazada.** Una segunda ausencia que se solapa contesta 409 y
  **no deja su fichero**: el fichero solo se escribe cuando el modelo se guarda.

#### Y el hallazgo, contando lo que hay en disco

En vez de seguir forzando fallos, la comprobación directa: **cuántos ficheros hay
sin fila que los apunte**.

| | |
|---|---|
| ficheros en el almacén | **4.403** |
| referenciados por una ausencia | **12** |
| **huérfanos** | **4.391** (8,1 MiB) |

Y repartidos por todos los días con tandas ---1.226 el 12/08, 975 el 13, 841 el
14, 990 hoy---, o sea **unos mil por tanda**.

El camino resultó ser el más frecuente de todos: **sustituir el justificante**.
Django asigna el nuevo y no toca el viejo, así que quien sube el bueno después del
equivocado deja el equivocado en el servidor para siempre. Al borrar la fila
después, la señal de la vuelta 45 se lleva **el actual**; el sustituido llevaba ya
tiempo sin dueño.

Eso es exactamente lo que aquella vuelta quería evitar y dejó escrito: sin nada que
sepa que el fichero existe no se puede atender una supresión (art. 17) ni cumplir
el plazo de conservación (art. 5.1.e). Y son justificantes, art. 9.

Arreglado con una señal `pre_save` que reutiliza `descartar_justificante`, mirando
solo ese campo y solo cuando de verdad cambia --- con prueba de que un `save()` de
otro campo no se lleva el fichero por delante.

**Los 4.391 que ya están en disco no se han tocado**: son de la base de desarrollo
y borrar ficheros de ahí lo decide su dueño. Queda en hallazgos abiertos.

2 pruebas nuevas (1.138 en el backend).

### Vuelta 97 --- Un fallo que fabricaba los siguientes (26/08)

La lente: el hallazgo abierto de la vuelta anterior, porque sin una tanda fiable
cada vuelta cuesta el doble y ningún rojo significa nada.

#### Lo que fui descartando, con su dato

- **No es acumulación por posición.** Los fallos caían en los ficheros 04, 09, 12,
  14 y 28: repartidos por toda la tanda, no al final.
- **No es carga.** 4,3 de media con **32 núcleos**. Haberlo dicho antes de medirlo
  fue un error mío, y está como lección.
- **No es degradación gradual.** Una prueba normal tarda **un segundo** y el margen
  de `expect` son siete: un fallo ahí es un salto de siete veces, o sea un evento,
  no lentitud.
- **No es el navegador reutilizado.** Partiendo la tanda en dos mitades, **cada
  mitad falla una**: 142 pruebas → 1 fallo, 137 → 1 fallo, 275 → 1 fallo. No se
  concentra en la segunda.

Ese último número es el que abrió la puerta: si el fallo no crece con el número de
pruebas, no es acumulación --- es algo ligado a la corrida.

#### El hallazgo

Los dos fallos de las mitades eran de **Ajustes**, y el segundo lo decía con todas
las letras: «la pantalla decía que guardaba y el backend seguía con lo de antes».

`35-jornada-abierta` cambia el tope de jornada abierta **de la empresa**, comprueba,
y lo restaura **al final del test**. Si falla a mitad, la restauración no llega. Y
la demo apareció con el tope en **26** en vez de 16, residuo de una corrida rota
horas antes --- con eso, las pruebas de Ajustes de las corridas siguientes fallaban.

**Un fallo suelto fabricaba los siguientes.** Eso explica por qué cada corrida caía
en un sitio distinto: el residuo cambiaba de sitio.

Y no era nuevo: `08-formularios-gestion` ya llevaba escrito el síntoma ---«si una
tanda anterior se cortó antes de restaurar, el valor ya era 72»--- y lo habían
parcheado eligiendo un valor distinto del actual. El síntoma esquivado, el
mecanismo intacto.

#### El arreglo

Restauración en `finally`, y **por la API en vez de por la pantalla**: si lo que
falló fue la pantalla, volver a pulsar «Guardar» no restauraría nada. En las dos
pruebas que lo hacían al final; la tercera que toca ajustes globales
---`21-organizacion-registro`--- ya limpiaba **al empezar**, que es aún mejor, y no
se ha tocado. El patrón de `try/finally` tampoco es nuevo: `36-interfaz-traducida`
ya lo usaba para el idioma de la empresa.

**Comprobado forzando el fallo**: con la aserción cambiada a un valor imposible, la
prueba cae y el ajuste **queda restaurado igualmente**.

Esto no explica el fallo *original* de cada corrida ---sigue sin causa, y sigue
abierto--- pero sí por qué se multiplicaba. Con la propagación cortada, un rojo
vuelve a ser un dato de una prueba y no de las diez siguientes.

### Vuelta 96 --- Doce botones que se llamaban igual (26/08)

La lente venía medida de la vuelta anterior: bajando el umbral de la prueba de
accesibilidad a dos ---en una sonda, no en la prueba--- para ver qué pantallas
fallarían con una fila más, salió esto:

| pantalla | rótulos repetidos |
|---|---|
| `/panel/aplicaciones` | «Emitir token» ×2, «Revocar la aplicación» ×2 |
| `/panel/cuadrante` | **«Asignar» ×12** |

Los doce **ya** estaban cuatro veces por encima del umbral de tres que esa prueba
vigila. No fallaba por un motivo simple: **`/panel/cuadrante` y
`/panel/aplicaciones` no estaban en su lista de pantallas**, que se escribe a
mano. Un hueco de cobertura tapando un fallo actual, y de los que no se notan
nunca.

#### El fallo

`CoberturaPendiente.jsx` pinta un botón por hueco sin cubrir del cuadrante. En un
mes con doce, quien navega con lector de pantalla oye «Asignar» doce veces
seguidas sin saber cuál es cuál --- y cada uno asigna un turno distinto a una
persona distinta. Lo mismo con el desplegable «Quién lo cubre», repetido igual.

#### El arreglo, en dos intentos

El primero puso el turno y a quién cubre, y **seguía fallando**: cinco «Asignar el
turno de 07:00 a 15:00 que cubre a Paco Trillo», porque es el mismo turno de la
misma persona en **cinco días distintos**. Lo que los distingue es el día, y la
pantalla ya lo pintaba en el título --- ahora se calcula una vez y lo usan el
título y los dos nombres.

Y las dos pantallas entran en la lista de la prueba, que es lo que impide que
vuelva a haber un fallo sin quien lo mire.

2 arreglos de pantalla y 2 pantallas más cubiertas (275 declaradas de navegador).
Comprobado que cae sin el arreglo.

#### La tanda completa se ha vuelto inestable, y no sé por qué

Tres corridas seguidas del mismo árbol, sin tocar nada entre ellas:

| corrida | falla | aislada |
|---|---|---|
| 1ª | `13-descargas` ×2, `28-nombres-accesibles` ×2 | 24 verdes |
| 2ª | `28-nombres-accesibles` ×2 (`/panel/informes`) | 20 verdes |
| 3ª | `14-decidir-en-bloque` | 8 verdes |

**274 de 275 pasan siempre, y la que cae es distinta cada vez.** Todas verdes al
ejecutarlas solas, todas por tiempo agotado o por un elemento que no aparece en
siete segundos.

La primera la expliqué ---Vite recompilando, porque lancé justo tras editar--- y
está como regla. Las otras dos no. **Atribuirlo a la máquina fue un error mío**:
la carga estaba en 4,3 con **32 núcleos**, así que de saturación nada.

Lo que queda por descartar, y no cabía en esta vuelta: la tanda corre con **un
solo worker** y reutiliza el navegador a lo largo de once minutos y 275 pruebas,
así que el sospechoso natural es el propio navegador acumulando estado o memoria,
no el producto. Se comprueba partiendo la tanda en dos mitades y viendo si el
fallo sigue apareciendo en la segunda.

Queda en hallazgos abiertos: mientras esto siga así, **un rojo suelto de la tanda
no significa nada hasta comprobarlo aislado**, y eso hace la auditoría más lenta y
menos fiable.

### Vuelta 95 --- Un cero que separaba la pantalla del documento (26/08)

La lente: **la pantalla y el documento tienen que decir lo mismo.** El informe lo
promete por escrito ---«la cifra en pantalla y la del documento son el mismo
día»--- y salió de leer, mientras corría la tanda anterior, que el tope de jornada
abierta lo resolvían **dos sitios de dos maneras**:

- `punches.services`, con `getattr(rules, "max_open_hours", None) or DEFAULT`,
- el informe, con el campo a pelo.

Iguales para cualquier valor normal. Distintos para el cero.

#### El hallazgo

`PositiveSmallIntegerField` admite cero y el campo no tenía suelo, así que la API
lo aceptaba con **200 y sin avisos**. Y entonces:

| | qué tope usaba |
|---|---|
| fichar | **16**, porque el cero caía al valor por defecto |
| el informe | **0** |

Con eso, un turno de noche bien fichado ---entra a las 21:00, sale a las 05:00---
salía en el documento como `21:00;;00:00;entrada sin salida`, mientras la pantalla
de fichar seguía funcionando como si nada. Ocho horas trabajadas que el documento
no reconoce y la pantalla sí.

Es el patrón de la vuelta 77 ---un cero apagando una salvaguarda--- con un
agravante: aquí el cero no apaga algo, **separa a dos que tienen que coincidir**.

#### Dos arreglos, uno por mitad

**El suelo**: `MinValueValidator(1)`. Cero no significa nada en «cuánto aguanta
abierta una jornada», y ahora contesta 400. Subirlo a 24 para guardias sigue
valiendo, con prueba, porque para eso existe el ajuste.

**La resolución, en un solo sitio**: `max_open_hours()` deja de ser privada
---ahora la usan dos apps--- y el informe pregunta a la misma función que el
fichaje. El suelo evita el estado absurdo; esto evita que cualquier otro valor
tratado de forma especial vuelva a separarlos. La prueba escribe el cero
**saltándose la validación**, como llegaría un dato heredado, y comprueba que los
dos caen al mismo número.

Comprobado que cada mitad tiene su prueba y que cada una cae al quitar su arreglo.

4 pruebas nuevas (1.136 en el backend) y una migración.

#### Y otro rojo de la tanda que no era del cambio

`09-cuadrante-calendario` falló con un diálogo que no se cerraba al registrar una
ausencia. Aislado, nueve verdes. El mecanismo lo tenía **escrito la propia prueba**
unas líneas más abajo:

> como la suite deja ausencias de prueba que quedan aprobadas ---y una aprobada no
> se puede cancelar, así que la limpieza no se las lleva--- llegaron a acumularse
> cincuenta y cuatro

Ese residuo ya había roto antes la búsqueda de la propia prueba, y se arregló
buscando por marca propia. Volvió por otro lado: la prueba pedía siempre **el 14 y
el 15 de diciembre**, así que la ausencia que deja adrede sin resolver choca con la
de la tanda anterior en cuanto una queda aprobada. Ahora el **día sale de la
tanda** ---el mes se queda en diciembre porque la navegación del calendario avanza
hasta él a botonazos.

Tres pruebas en dos vueltas por lo mismo: **una prueba que escribe no puede
compartir sus sujetos ni sus fechas con las demás.** Está como regla en las
lecciones 170 y 174.

#### El cuarto rojo sí era del producto

`28-nombres-accesibles` falló en `/panel/centros`: **tres botones «Editar»**
idénticos. Su regla es que más de dos rótulos iguales son un fallo, y lo explica:
«a partir de tres es una lista de filas y hay que decir de cuál es cada uno».

Con los **dos** centros de la semilla no se notaba nunca. Apareció porque una
prueba dejó un tercero, y entonces un lector de pantalla oye «Editar, Editar,
Editar» sin saber de qué centro. `Departments.jsx` ya lo hacía bien
---`aria-label={`Editar ${department.name}`}`--- y por eso pasa con seis filas;
`Workplaces.jsx` se había quedado sin ello. Arreglado, con la comprobación de que
cae sin el arreglo.

**El sedimento sirvió de algo por una vez**: fue lo que puso la tercera fila.

#### Y midiendo el alcance salió un hueco para la vuelta siguiente

Bajando el umbral a dos ---una sonda, no la prueba--- para ver qué pantallas
fallarían con una fila más:

| pantalla | rótulos repetidos |
|---|---|
| `/panel/aplicaciones` | «Emitir token» ×2, «Revocar la aplicación» ×2 |
| `/panel/cuadrante` | **«Asignar» ×12** |

Los doce del cuadrante **ya** están muy por encima del umbral, y la prueba no
falla ahí por un motivo simple: `/panel/cuadrante` y `/panel/aplicaciones` **no
están en su lista de pantallas**. Un hueco de cobertura tapando un fallo actual.
Queda para la vuelta 96, con los botones por localizar en el DOM.

### Vuelta 94 --- Ocho horas que pasaban a cero (26/08)

La lente sale de la anterior: si el huso había que congelarlo porque es un hecho,
**qué más se consulta al presente** para interpretar un hecho pasado. En
`reports/services.py` había tres candidatos, y los tres dan.

#### Lo medido, sobre un abril ya cerrado

| lo que se cambia hoy | la fila del informe pasa de | a |
|---|---|---|
| la pausa cuenta como trabajo | `08:00;13:00;07:00` | `08:00;13:00;`**`08:00`** |
| el tope de jornada abierta, a 4 h | `22:00;06:00;08:00` | `22:00;;`**`00:00;entrada sin salida`** |

El segundo es el peor de los dos: un turno de noche **bien fichado** pasa a cero
horas y aparece una incidencia que no ocurrió. No desplaza el dato como el huso,
lo destruye.

#### Y aquí la lente se para, a propósito

Con el huso estaba claro: es un **hecho** ---dónde se vivió esa hora--- y se
congela. Pero «la pausa cuenta como tiempo de trabajo» es una **regla de cómputo
que sale del convenio** (art. 34.4 ET), y las reglas cambian de verdad. Lo que no
puede es que el cambio alcance hacia atrás.

Arreglarlo bien pide **reglas con fechas de vigencia**, y con eso viene una
pregunta que no es técnica: desde cuándo aplica un convenio nuevo, y qué pasa con
los informes ya entregados. Eso **no se decide desde una vuelta de auditoría**, así
que queda en hallazgos abiertos con las cifras medidas.

#### Lo que sí cabía hacer hoy

El documento ahora **dice bajo qué reglas se emitió**: el trato de la pausa y el
tope de jornada abierta, en la cabecera, junto al periodo y al huso ---que ya
estaban ahí por el mismo motivo. No cambia ninguna cifra: hace que dos versiones
del mismo mes se puedan comparar en vez de contradecirse sin explicación.

En el CSV y en el PDF, porque el PDF es el que se entrega.

#### Un fallo mío que cazaron los catálogos

Puse los valores como `_("yes")` y `_("no")`. Al regenerar, **`no` venía traducido
como «nota»** y en catalán y gallego los dos valores **opuestos** heredaban la
misma frase ---que en uno de los dos casos habría dicho lo contrario de lo que
pasa. Una cadena de una palabra la traduce cada idioma por su cuenta y se presta
de cualquier contexto. Cambiado a frases enteras: «Descanso | no computa como
trabajo efectivo».

4 pruebas nuevas (1.132 en el backend), una de ellas de que las cifras **no**
cambian por esto.

#### Y el rojo que costó cerrar la vuelta, que no era de la vuelta

La tanda de navegador falló dos veces, y ninguna por este cambio:

**La primera**, en el *setup* del login: 120 s agotados esperando el token y
«browser has been closed». Relanzada sin tocar nada, la misma sesión pasa en
**2,4 s**. El recargador de Django estaba reiniciando por mis ediciones cuando
arrancó la tanda. Tercera vez en el día que pasa esto por un sitio distinto, y ya
está escrito como regla.

**La segunda** fue de verdad interesante: dos fallos en `12-acciones-masivas`, uno
esperando 3 personas movidas y encontrando 2, y otro con un diálogo que no se
cerraba. Aislado, el fichero da **10 verdes**. La cadena entera:

1. La prueba marcaba **«las tres primeras»** casillas de la lista y las cruzaba
   con las tres primeras de la API: frágil dos veces, porque depende de cuánta
   gente hay y de en qué orden sale.
2. Y el orden empezaba así: Jose Almenara, Hugo Bermejo, **«Prueba Bloque
   p69728000»**, **«Prueba Bloque p69729721»**. Esos dos son los residuos
   activos del 14 de agosto que **en la vuelta 90 declaré sedimento
   inofensivo**. Por el apellido «Bloque» se colaban al principio del alfabeto.
3. Al arrastrar a Hugo consigo, la prueba siguiente ---que lo busca por su
   nombre--- se quedaba sin poder componer su departamento. **Un fallo, no dos.**

Arreglado en el fondo: la prueba **crea sus propias tres personas** y las retira
al terminar, así que dice exactamente sobre quién actúa. Y los seis residuos
activos, retirados: la demo vuelve de 24 personas activas a 18.

La vuelta 90 se corrige a sí misma. Dije que el sedimento no era un fallo porque
la limpieza funcionaba y el producto no borra a propósito, y las dos cosas siguen
siendo verdad --- pero cuatro cuentas activas de prueba, con un apellido que las
pone primeras, sí eran un fallo esperando.

### Vuelta 93 --- El registro que cambiaba hacia atrás (26/08)

La lente: **qué se lleva por delante un borrado.** Seguía el hilo de la vuelta
anterior: si cancelar borraba sin dejar rastro, ¿qué más se borra, y qué cuelga en
cascada de lo que sí se puede borrar?

#### Tres candidatos que salieron limpios

- **El `delete()` de `audit/trail.py`** parecía borrar el rastro. No: es el mixin
  de los viewsets y borra el objeto que gestionan, anotando antes con la foto de
  sus campos. «Antes de borrar: después el objeto ya no puede decir cómo se
  llamaba.» Ejemplar.
- **El catálogo de permisos** está protegido: borrar un tipo que alguien usó
  contesta 409 `leave_type_in_use`, y borrar uno sin usar deja su asiento en el
  rastro. Mi hipótesis era que al no llevar `StructureTrail` no anotaba nada, y
  era falsa.
- **El recibo de idempotencia** cuelga en cascada de la aplicación integrada, y su
  docstring explica por qué está ahí y no en el fichaje: «el registro de lo que
  pasó se queda exactamente como estaba».

#### Y el hallazgo, por el único camino que quedaba

Un centro de trabajo se puede retirar cuando no queda nadie dentro. Y con él se
van sus festivos locales, que era lo que iba buscando. Pero al comparar el informe
antes y después apareció otra cosa, más grave:

| | la misma fila del informe |
|---|---|
| antes de retirar el centro | `2026-05-30;09:00;17:00;08:00` |
| después | `2026-05-30;10:00;18:00;08:00` |

**Una hora de diferencia en el documento del art. 34.9.** No era el festivo: era
el **huso**. El centro estaba en `Atlantic/Canary` y, al retirarlo, la persona
hereda el de la empresa, `Europe/Madrid`.

La marca se guarda en UTC y hay que leerla en algún huso para decir «las nueve».
Ese huso salía de `employee.tzinfo` ---un dato de **hoy** aplicado a un hecho de
**entonces**. Y el `hash_integrity` seguía cuadrando, porque la fila no había
cambiado: lo que cambiaba era **cómo se leía**.

Hay tres caminos al mismo sitio, y el borrado es el menos probable de los tres:
retirar el centro, **cambiarle el huso**, o **mover a la persona a otro centro**.
Los tres reescribían su registro anterior.

#### El arreglo: el huso se congela con la hora

`Punch.time_zone`, por lo mismo que `hash_integrity` congela el contenido. Lo
escriben el fichaje y la corrección ---que cambia la hora, no el sitio donde se
vivió--- y lo leen el informe y la API.

La vuelta 70 ya había puesto el huso en cada fichaje de la API, y por eso creí un
momento que estaba resuelto: pero lo puso **derivado** con un
`SerializerMethodField` sobre el centro actual, así que se movía con la empresa.

Lo que no se rompe, y va con prueba: los fichajes anteriores al campo caen al huso
de la persona ---la mejor respuesta que hay para ellos, y la que tenían--- y un
huso que ya no exista en la base del sistema no tumba el informe.

5 pruebas nuevas (1.128 en el backend) y una migración. Comprobado que los tres
caminos caen sin el arreglo.

### Vuelta 92 --- La solicitud que desaparecía (26/08)

La lente: **lo que se borra de verdad.** Qué desaparece de la base y qué se
conserva, y si lo que desaparece deja constancia de haber existido. Salió de leer
`cancel_absence` mientras esperaba la tanda anterior: hacía `delete()`.

#### El hallazgo

Cancelar una solicitud de ausencia **borraba la fila**. Y cancelar la solicitud de
**otra persona** está permitido: la comprobación es
`absence.employee_id != cancelled_by.id and not cancelled_by.can_manage`.

Medido: la responsable cancela la petición de vacaciones del obrero, y la fila no
queda **ni en `objects_all_tenants`**. Cero entradas nuevas en el rastro.

Así que quien pidió sus vacaciones no tenía manera de demostrar que las pidió, ni
con qué fechas, ni quién quitó la petición. En las correcciones esto ya estaba
decidido en el otro sentido y escrito: «una petición rechazada también es
historia». Aquí faltaba.

#### El arreglo, y la parte que **no** se conserva

Estado `CANCELLED` con quién la canceló y cuándo, más su asiento en el rastro con
nombre, apellidos y las fechas que se retiraron ---sin las fechas el asiento no
dice qué se quitó.

Pero el **justificante sí se borra**, y eso es lo que hizo pensar la vuelta. Al
conservar la fila se rompieron dos pruebas de la vuelta 45, la que arregló «el
fichero se va con su fila», y su docstring dice exactamente por qué:

> Un justificante es a menudo un dato del art. 9 del RGPD ---una citación, un
> informe de un familiar hospitalizado--- y la persona que retira su solicitud
> está diciendo justamente que no quiere que se quede.

Eso sigue siendo verdad aunque la fila se quede. Así que el borrado del fichero se
sacó de la señal de `post_delete` a `descartar_justificante()`, y cancelar lo
llama: **queda la solicitud, no queda el documento**. Trazabilidad sin retener un
dato de salud que ya no sostiene nada.

#### Las tres pruebas existentes, leídas antes de tocarlas

Las tres fijaban el borrado, y ninguna sobraba:

- La del justificante huérfano defendía el art. 17 y el 5.1.e. **Sigue verde sin
  cambiarla**, porque el fichero se sigue borrando.
- «Una ausencia sin justificante se borra sin ruido» defendía que la falta de
  fichero no rompa nada. Renombrada a `..._se_cancela_sin_ruido`, con la misma
  intención y la aserción puesta al día.
- «Puedes retirar la tuya» defendía el permiso, no el borrado. Ahora comprueba
  que queda cancelada y a nombre de quien la retiró.

#### Lo que no podía romperse, y se probó

Una cancelada **no consume saldo** y **no bloquea sus días**: se pueden volver a
pedir los mismos y sale 201. Sale gratis porque el saldo y el solapamiento cuentan
solo lo aprobado y lo pendiente, pero conservar una fila que antes desaparecía es
justo el cambio que puede crear un solapamiento fantasma, así que va con prueba.

6 pruebas nuevas (1.123 en el backend), dos migraciones y el estado traducido.

### Vuelta 91 --- Una propuesta sin marcha atrás (26/08)

**Contador: 1 → 0.**

La lente: **el camino de vuelta.** Cada acción del producto que se puede deshacer,
y sobre todo las que no. Empezó de la vuelta anterior, donde vi que el resumen
dice de las propuestas de la empresa que «se pueden retirar o aplicar» y no
encontré por ninguna parte el retirar.

#### El hallazgo, medido por la API antes de tocar nada

Cuando la empresa propone cambiar un asiento, queda esperando la conformidad de
la persona (art. 4.b). Desde ahí:

| intento | respuesta |
|---|---|
| rechazarla, la propia jefa | 409 `awaiting_the_employee` |
| rechazarla, otra jefa | 409 `awaiting_the_employee` |
| aprobarla | 409 `awaiting_the_employee` |
| borrarla | 405 |
| retirarla / cancelarla | **404, no existían** |

**No había marcha atrás.** Las únicas salidas eran que la persona acepte, que la
discuta, o que la empresa la aplique al vencer el plazo.

Lo que eso deja es una propuesta errónea que **obliga a actuar a la otra parte**:
la persona ha recibido un aviso de un cambio que la empresa ya sabe que está mal,
y tiene que discutirlo para pararlo. El art. 4.b pide el acuerdo de las dos partes
para tocar un asiento; hacer que la persona gestione el error de la empresa es lo
contrario de eso. Y mientras, el asiento sigue en el aire.

#### El arreglo, y las dos decisiones que lleva dentro

`withdraw_correction` y `POST /api/corrections/{id}/withdraw/`.

**Estado propio, `WITHDRAWN`, y no `REJECTED`.** En el historial de un registro con
valor probatorio no es lo mismo «te lo negamos» que «nos equivocamos al
proponerlo»: la primera es una decisión sobre lo que pidió la persona, la segunda
no lo es. Reutilizar `REJECTED` habría ahorrado una migración y ensuciado el
historial.

**Pasa por los cuatro ojos**, por lo mismo que rechazar desde la vuelta 72: si la
propuesta es sobre el fichaje de quien la retira, retirarla en solitario es
decidir sobre su propio registro. Hay prueba de que la interesada sola recibe
`cannot_decide_your_own` y otra persona sí puede.

Y **se avisa a quien esperaba**: se le pidió una respuesta y esa petición ha
dejado de existir. Callarse dejaría a alguien pendiente de un plazo, y con la idea
de que su registro sigue en discusión, por un error que no era suyo.

#### Un falso hallazgo mío, y de los feos

Antes de esto creí que `propose_correction` **no tenía endpoint**: el grep solo la
encontraba en `seed_demo.py`, así que parecía una pieza entera ---flujo, avisos,
ventana de consentimiento--- escrita y desconectada.

Era mentira. La línea 195 de las vistas dice
`maker = propose_correction if employee.id != request.user.id else request_correction`.
Lo que pasó es que corté el grep con `head -4` y la llamada estaba más abajo.

#### El guard de aislamiento hizo su trabajo

Al añadir la ruta, `test_every_route_is_covered_by_this_sweep` se puso roja: una
ruta nueva sin cobertura de aislamiento. Cubierta en las dos pruebas que barren
---la empresa de al lado y el operario--- y en la lista. Es el mismo tipo de guard
que dejó la vuelta 83, y esta vez avisó a los diez minutos de escribir el
endpoint.

8 pruebas nuevas (1.117 en el backend), migraciones, y el correo traducido al
castellano.

### Vuelta 90 --- Lo que las tandas dejan detrás (26/08)

**Segunda vuelta sin hallazgo.** Contador: 0 → **1**.

La lente salió de un dato que apareció limpiando la vuelta anterior: la empresa de
demostración tenía **533 personas** cuando la semilla monta catorce. Si cada tanda
deja gente detrás, ninguna medición es comparable con la siguiente ---y eso
explicaría la lentitud y los recuentos que bailaron durante el día.

#### Lo que resultó ser

| | |
|---|---|
| personas en la demo | 533 |
| de ellas, **activas** | 24 |
| creadas hoy por las tandas | 209 |
| de esas, activas al terminar | **0** |

**La suite limpia bien.** Da de baja lo que crea, y las 209 de hoy quedaron todas
retiradas. Lo que no puede hacer es borrarlas, porque el producto **no borra a
propósito**: `perform_destroy` desactiva para que los fichajes sobrevivan, que es
lo correcto para un registro de jornada. Así que el sedimento es inevitable, no un
descuido.

Las cuatro de prueba que sí quedaron activas son del **14 de agosto**, de antes de
que la limpieza se arreglara. Sedimento histórico, no una fuga viva.

#### Y las colas acumuladas, que parecían lo gordo

452 correcciones, 193 ausencias y 413 turnos acumulados. De las correcciones,
**209 en `AWAITING_EMPLOYEE`**: asientos esperando la conformidad de la persona.

Eso llevaba a una pregunta de ley buena ---¿puede una corrección quedarse
esperando para siempre?--- y la respuesta ya está en el producto:

- El art. 4.b **no exige** que la persona conteste: «el silencio o la negativa no
  detienen a la empresa, obligan al registro a llevar las dos versiones». El
  camino existe y se usa: hay 87 en `DISPUTED`, aplicadas con la discrepancia
  registrada.
- La persona ve las suyas en su resumen, y quien administra ve el contador de las
  que esperan, con el comentario que dice por qué cuenta: «se pueden retirar o
  aplicar, y hasta entonces cuentan».

Así que no hay limbo silencioso. Está mirado y decidido.

#### Lo que sí queda dicho, y no se ha hecho

`python manage.py seed_demo --reset` **ya existe** y devuelve la demo a su estado
de catorce personas. No se ha ejecutado a propósito: borraría 509 personas y 452
correcciones de la base de desarrollo, y eso lo decide su dueño, no una vuelta de
auditoría.

**Conviene hacerlo entre sesiones**, y anotarlo aquí es el punto: sin eso, dos
mediciones de rendimiento separadas por unos días no son comparables, y las
pruebas que cuentan filas se vuelven frágiles solas.

Sin cambios de código en esta vuelta. Las dos suites siguen en verde.

### Vuelta 89 --- Cinco bytes que decían «error» (26/08)

La lente: **el volumen.** La Inspección pidiendo un año de una empresa con
plantilla, que es el cuarto perfil del cuaderno y no se había medido nunca con
datos de verdad. Se sembraron **99.500 fichajes**: 200 personas por un año.

#### El volumen sale limpio, y con números

| petición | tiempo | consultas | tamaño |
|---|---|---|---|
| una persona, un año, CSV | 0,18 s | 11 | 29 KiB |
| 200 personas, un mes, CSV | 2,5 s | 1005 | 0,5 MiB |
| 200 personas, un año, CSV | 5,7 s | 1005 | 5,6 MiB |
| 200 personas, un año, PDF | **15,7 s** | 1005 | 2,5 MiB |

Hay un N+1 claro ---cinco consultas por persona, 1005 para doscientas--- pero
**está acotado a propósito** y el comentario de `MAX_PEOPLE_PER_EXPORT = 200` da
exactamente el razonamiento correcto: se genera de forma sincrónica y pasadas unas
centenas la petición tarda más de lo que espera cualquier proxy inverso, así que
negar con un número es mejor que un tiempo de espera agotado que parece que la
función está rota.

Y **el tope está calibrado**: en el peor caso que permite, 15,7 s, por debajo de
los treinta de un proxy. No es un hallazgo, es una decisión medida.

#### Pero al equivocarme con el nombre de un parámetro salió lo otro

Medí «un año de la empresa» con `from`/`to` y estaba midiendo **treinta días**:
0,3 KiB y menos consultas que el informe de una sola persona. Lo delató comparar
con el caso conocido.

Aquí el periodo se pide como `date_from`/`date_to`, y **`from`/`to` es como lo
pide de verdad otro endpoint de este mismo producto**, el de horas extra. Así que
no es un despiste hipotético. Lo desconocido se ignora, así que salía **200 con
el periodo por defecto**: entregar el registro de un periodo que nadie pidió,
cuando lo que el art. 34.9 pone a disposición de la Inspección es el del periodo
que se pidió.

Y el docstring de `LocalDayRangeFilter` llevaba escrito «Adds `from` and `to`»
mientras sus campos se llamaban `date_from`/`date_to`, que es de dónde venía la
confusión.

Rechazado en el filtro común, así que queda cubierto de una vez para todos los
listados que lo heredan. Y horas extra acepta ahora los dos nombres.

#### Y buscando el mensaje de ese error, el hallazgo de verdad

No aparecía en ninguna parte. El cuerpo del 400 eran **cinco bytes: `error`**, con
`Content-Type: application/pdf`.

`PDFRenderer` y `CSVRenderer` entregan los bytes del documento tal cual ---lo
correcto para una respuesta buena--- pero al ser los únicos declarados también
renderizan los cuerpos de error, y pasarle un diccionario a `HttpResponse` hace
que Django recorra sus claves. La única clave era `error`.

De modo que **ningún rechazo de este endpoint llegó nunca a nadie**:

- «201 personas pasan de las 200 que se pueden generar de una vez. Acota por
  departamento» --- el mensaje que explica qué hacer con una plantilla grande, y
  el único camino que el producto ofrece para ella.
- «La fecha final no puede ir antes que la inicial».
- «Nadie trabajó en ese periodo».
- «Las fechas se escriben como AAAA-MM-DD».

Todos escritos con cuidado. Todos invisibles. Es el patrón que más ha rendido en
esta auditoría: la pieza está hecha y no llega.

10 pruebas nuevas (1.110 en el backend), y una de ellas de lo que no se puede
romper: el documento bueno sigue saliendo como bytes con su propio tipo, y el PDF
sigue empezando por `%PDF-`.

### Vuelta 88 --- Dos pestañas abiertas, una a la calle (26/08)

La lente: **dos pestañas del mismo navegador**, que es como se trabaja de verdad
---el cuadrante en una y los fichajes en otra.

#### El hallazgo

El acceso dura quince minutos y el refresco **rota**: al usarlo, el viejo va a la
lista negra. Dentro de una pestaña eso ya estaba resuelto, y con un comentario que
explica por qué ---cinco peticiones caducadas comparten una sola renovación,
«refrescar cinco veces con rotación activada invalidaría los tokens de las otras
cuatro».

Pero `renewing` es una variable de módulo, y **cada pestaña tiene la suya**. Las
dos leen el mismo refresco de `localStorage`, así que era una carrera con
perdedor:

| | |
|---|---|
| pestaña A refresca | **200**, y el refresco viejo a la lista negra |
| pestaña B, con el mismo | **409 `session_expired`** |

Y `session_expired` está en la lista de rechazos definitivos ---con razón, porque
este servidor no contesta 401 a un refresco malo---, así que a B le borraba los
tokens y la mandaba al formulario de entrada. **Tener dos pestañas abiertas
costaba una sesión cada cuarto de hora.**

#### El arreglo: el canal ya existía

No hacía falta `BroadcastChannel` ni un cerrojo entre pestañas. El propio
`localStorage` es el canal: si al fallar el refresco lo que hay guardado **ya no
es lo que se envió**, alguien lo rotó mientras la petición estaba en vuelo. Eso
no es una sesión caducada, es una carrera, y se reintenta una vez con el nuevo.

#### La prueba pasaba sin el arreglo, y eso era el verdadero problema

Primer intento: dos pestañas, invalidar el acceso en las dos, pedir a la vez.
Verde con el arreglo... y **verde también sin él**.

El motivo es justo lo que hace que el arreglo funcione: las dos pestañas comparten
`localStorage` de verdad. Si la segunda lee el refresco *después* de que la
primera lo haya guardado, coge el nuevo y no hay carrera que probar. `Promise.all`
no garantiza que colisionen.

Se fuerza el orden retrasando el refresco de la segunda con `page.route`: lee el
viejo, se queda en vuelo mientras la primera lo rota, y llega con uno que ya está
en la lista negra. Sin el arreglo falla con `token_not_valid`; con él, 200.

Y antes de eso hubo otro tropiezo: la prueba usaba la sesión compartida del
arranque, cuyo refresco **ya lo habían rotado otras pruebas**. Eso no medía la
carrera, medía un refresco caducado. Ahora entra ella misma.

1 prueba de navegador (272 → 273).

### Vuelta 87 --- Un motivo que se lee al revés (26/08)

La lente: **el texto que escribe la persona.** Unicode trae caracteres que no se
ven y cambian lo que se lee, y este producto guarda texto que otro lee para
decidir.

#### El hallazgo: `U+202E` en el motivo de una corrección

`RIGHT-TO-LEFT OVERRIDE` invierte todo lo que va detrás. El motivo lo escribe
quien pide la corrección y lo lee quien la aprueba, así que
`"Fiche a las 8\u202e00:41 sal y 00:9 a"` **está guardado tal cual** y en
pantalla se lee al revés a partir de la marca.

No es cosmético: el art. 4.b pide que las dos partes acuerden el cambio de un
asiento, y el acuerdo se da leyendo ese motivo. Su último inciso obliga a
reflejar la discrepancia de quien no está de acuerdo, que es otro campo de texto
libre ---`employee_dissent`--- y el más delicado de los tres.

**Se rechaza en vez de limpiarse, y es una decisión.** Limpiar significaría
editar lo que alguien escribió, y uno de esos campos es justamente la
discrepancia que un trabajador hace constar. Quitarle caracteres a eso, aunque
sean invisibles, es corregir su declaración.

El mensaje dice **qué carácter** y con su número ---`U+202E (RIGHT-TO-LEFT
OVERRIDE)`---, porque decir «hay un carácter raro» sobre un texto donde no se ve
nada raro no sirve para arreglarlo.

Y llega como 400 gracias a la vuelta 85: hasta entonces una `ValidationError` de
modelo salía como 500.

#### Los tres sitios que salieron limpios, que es la mitad del trabajo

- **El nombre de una persona no es vector.** Un operario no puede cambiárselo:
  403. Lo pone administración, que ya tiene todo el poder. Aun así lleva el
  validador, porque un nombre invertido en el PDF que se entrega es otro nombre.
- **El CSV aguanta.** Un nombre con salto de línea sale entrecomillado y un
  `;9999` pegado dentro no crea columnas: 11 filas de CSV frente a 12 líneas
  físicas, y la diferencia es exactamente el salto embebido. Medido por los
  bytes, no por cómo se ve.
- **El PDF también.** ReportLab no arrastra la marca: la dibuja como un cuadrado
  y el `U+202E` **no viaja dentro del fichero**. Feo, no engañoso.

#### Dónde tuvo que ir el validador, y por qué no donde yo creía

Puesto en los campos del modelo, no se ejecutaba: el servicio crea con
`objects.create()`, que no pasa por `full_clean()`. Es la lección 144, escrita
esta misma tarde, cazándome a las dos horas.

El alta de personas sí funcionaba desde el principio, y eso enseñó dónde está la
diferencia: su serializer es un `ModelSerializer` y hereda los validadores del
campo; los de corrección y ausencia declaran los campos a mano y no heredan nada.
Así que la declaración va también ahí. La regla sigue viviendo en un solo sitio,
`apps/common/texto.py`; lo que se repite es la declaración, no la lógica.

8 pruebas nuevas (1.100 en el backend), cuatro de ellas de lo que **no** se puede
romper: acentos, eñes, emoji, saltos de línea y tabuladores siguen pasando. Un
filtro que se lleve por delante un texto normal se apaga a la semana.

### Vuelta 86 --- «Que lo decida otra», y esa otra no la ve (26/08)

La lente: **lo que mis propias vueltas dejaron desfasado.** Cambiar una regla deja
detrás los textos que la explicaban, y eso no lo caza ninguna prueba: un
comentario o un mensaje son plantillas, no aserciones. La lección 143, escrita
dos vueltas antes, decía justo esto ---y aun así se me había escapado uno.

#### Empezó por dos textos que mentían

**El mensaje del 409 de departamentos.** La vuelta 73 lo puso porque quedarse sin
departamento *ampliaba* el alcance a toda la empresa. La vuelta 84 cerró esa
puerta, y el mensaje siguió prometiendo lo contrario de lo que ocurre: «leaving
them in charge of nothing widens what they can read to the whole company».
Estaba en el código, en el docstring que lo justifica y en **tres catálogos de
traducción**.

Corregido a lo que pasa de verdad: quedan sin poder leer a nadie más que a sí
mismas. La refusal se queda ---sigue siendo una consecuencia que nadie busca al
retirar un departamento--- pero por su motivo nuevo. **Anotado como pregunta de
diseño**: `PATCH` con `managers` vacío llega al mismo estado y contesta 200. La
asimetría no se decide aquí.

**El comentario del serializer de ausencias.** Decía que sin replicar los
validadores del justificante un fichero grande volvía como 500. La vuelta 85 cerró
eso en el manejador, así que ya no es lo que separa un fichero grande de una
traza. Se quedan, pero por otra razón: validar ahí nombra el campo.

#### Y tirando de ahí salió el hallazgo de verdad

`someone_else_could_decide` contestaba a la pregunta «¿hay otra responsable o
administradora activa?». Contar no es poder. Desde que una responsable lee solo
sus departamentos, la que existe puede no alcanzar a la persona del caso.

Medido por la API, con la única administradora pidiendo corregir un fichaje suyo:

| quién lo intenta | respuesta |
|---|---|
| ella misma | **409** `cannot_decide_your_own` --- «existe otra» |
| esa otra | **404** --- no la ve |

**No la podía resolver nadie.** Un asiento del registro mal y sin manera de
arreglarlo: el art. 34.9 lo quiere fiable y el art. 4.b quiere que la corrección
se pueda tramitar. La excepción de la administradora en solitario existe
exactamente para esto y no llegaba a aplicarse, porque preguntaba por la
existencia y no por el alcance.

#### El primer arreglo estaba mal, y lo dijo una prueba de las líneas rojas

Reescribí la regla del alcance dentro de `four_eyes`: administradora sí,
responsable solo si dirige el departamento de la persona. Con eso
`test_an_administrator_cannot_either` se puso **roja**, y esa prueba defiende una
de las líneas que no se cruzan ---si el registro lo puede reescribir una sola
persona, su valor como prueba depende de confiar en ella.

Tenía razón la prueba. En su empresa no hay ningún departamento, y desde la
vuelta 84 eso significa que toda responsable lee a todo el mundo: sí había una
segunda persona capaz. Mi copia de la regla se había dejado fuera precisamente el
caso que yo mismo había escrito dos vueltas antes.

Rehecho delegando en `can_see`, que ya sabe de la empresa con el acotado apagado,
del departamento que se dirige frente al que se pertenece, y del que todavía no
lleva nadie. La regla vive en un sitio.

**Comprobado que no afloja las cuatro manos**: con dos administradoras se sigue
negando, con una responsable que sí dirige el departamento también, y solo cede
cuando de verdad no queda nadie que pueda.

7 pruebas nuevas (1.092 en el backend). Comprobado que las tres que deben caer
caen sin el arreglo.

### Vuelta 85 --- La Nochevieja partida en dos (26/08)

La lente: **el borde del año.** La vuelta 81 hizo la semana del borde del mes y el
año es el hermano mayor: el saldo de vacaciones, el tope anual de horas extra
(art. 35.2), el periodo de devengo y la semana ISO 53 viven todos ahí.

#### Lo que salió limpio, y es la mitad del trabajo

- **El saldo reparte bien.** Nueve días del 28/12 al 5/1 se cargan 4 contra un
  año y 5 contra el otro, no nueve contra cada uno. `_days_within` recorta al
  periodo.
- **El tope anual de horas extra** va por año natural a propósito, y el
  comentario lo dice: el periodo de las vacaciones puede ser otro y no se
  mezclan.
- **El periodo del saldo** es el año natural incluso cuando la empresa mueve su
  año de vacaciones, y está argumentado: el art. 38 deja mover el año de
  vacaciones y no dice nada del resto, así que aplicar el de abril-a-marzo a una
  urgencia familiar sería inventárselo.

#### Un hallazgo mío que era falso, y cómo se cayó

Midiendo el saldo en horas salió **doble cargo**: 4 h de consulta médica se
cobraban 4 en un año y 4 en el otro, 8 de un saldo de 20. En días recortaba y en
horas no.

Era falso: lo había montado con `Absence.objects.create`, que **no pasa por
`full_clean`**, y el modelo prohíbe exactamente eso ---«Parte de un día es un día.
Para varios días deja las horas vacías y cuentan enteros»---. Por la API no se
puede crear. La sonda estaba midiendo un estado que el producto no permite.

Es el sexto falso hallazgo de la auditoría y todos han caído por lo mismo:
repetirlo por el camino real.

#### Pero al repetirlo por el camino real apareció uno de verdad: un 500

Pedir esa ausencia por la API no daba 400 con ese mensaje. Daba **500**.

`full_clean` lanza la `ValidationError` de Django y DRF solo entiende la suya, así
que la regla se perdía y salía una traza. El mensaje ---que es el bueno, porque
explica qué hacer en su lugar--- no llegaba nunca.

Lo llamativo es que **ya estaba avisado en el propio código**. El serializer
lleva escrito que replicó a mano los validadores del justificante porque «un
fichero demasiado grande volvía como un 500 en vez de un mensaje». Se arregló
aquel caso y se dejó el mecanismo: cualquier otra regla del modelo seguía saliendo
como traza.

Arreglado donde ya se traducen `Http404` y `PermissionDenied`, en
`api_exception_handler`. Vale para todas las reglas del modelo a la vez, las de
hoy y las que se escriban.

#### Y el segundo: las vacaciones que no salían en el año que se disfrutan

`?year=` filtraba por `start_date__year`. Unas vacaciones del 28/12/2026 al
5/1/2027 ---201, perfectamente normales--- **no aparecían al pedir 2027**, que es
justo cuando la persona las está disfrutando y las busca.

El docstring del filtro lo llama «el corte natural de las vacaciones», lo que
hace peor que se le escape la única ausencia que cruza el corte. Ahora filtra por
solape y sale en los dos años, con una prueba de que no se convierte en «sale
siempre»: 2025 y 2028 siguen vacíos.

Mismo patrón que la vuelta 81: un periodo se filtra por solape, nunca por uno de
sus dos extremos.

5 pruebas nuevas (1.085 en el backend). Comprobado que las dos que deben caer
caen sin el arreglo.

### Vuelta 84 --- Ceder un departamento le daba la empresa entera (26/08)

**Contador de vueltas sin hallazgos: 1 → 0.**

La lente: **la persona que se mueve.** Cambiar de departamento, de centro o de
jornada a mitad de mes. El huso ya viaja con cada fichaje desde la vuelta 70, así
que ese ángulo estaba cubierto y no se repitió; el que no lo estaba es quién
puede leer qué después de una reorganización.

#### El hallazgo: quitarle un departamento a alguien se lo ampliaba

`visible_people` trataba dos estados como uno solo: *no llevas ningún
departamento* y *aquí todavía no se ha decidido nada*. Para el segundo devolvía
«sin restricción», que es la concesión deliberada del diseño ---una empresa que
se da de alta hoy no puede tener una responsable que no ve a nadie--- y está
argumentada en el docstring del módulo.

El problema es que al primero le aplicaba la misma respuesta. Consecuencia:

| operación | antes | después |
|---|---|---|
| borrar el departamento | 409 (tapado en la v73) | igual |
| `PATCH managers=[]` | **200, y pasaba a ver 5 de 5** | 200, ve solo la suya |
| `PATCH managers=[otra]` | **200, y pasaba a ver 5 de 5** | 200, ve solo la suya |

La tercera fila es la grave, porque es la reorganización de toda la vida: «Ana ya
no lleva Obras, ahora lo lleva Berta». El resultado era que Ana, a quien le
acababan de **quitar** su departamento, pasaba de leer a su cuadrilla a leer a
toda la plantilla ---incluidas las ausencias de la gente de oficina, que es donde
se ve la enfermedad. Escalada de privilegios por sustracción.

La vuelta 73 ya había cerrado una puerta a este mismo estado, la del borrado, con
un 409. Quedaban las dos del `PATCH`, que contestaban 200.

#### El arreglo: la regla ya estaba escrita en dos sitios

No hizo falta inventar el criterio, porque **ya estaba escrito y sin aplicar** en
los dos comentarios que rodean la funcionalidad:

- `tenants/views.py`: «Scoping managers by department only bites once somebody is
  put in charge of one».
- `Settings.jsx`: «acotar por departamento no empieza a aplicar hasta que alguien
  lleva uno».

Los dos describen exactamente la regla correcta. `visible_people` no la
implementaba. Es el patrón que más ha rendido en toda la auditoría, otra vez.

`department_scoping_in_use(company)` la deja en un solo sitio: ¿lleva alguien
algún departamento en esta empresa? Antes de ese momento nada se ha decidido y
una responsable lee a todos; a partir de él, llevar ninguno es una respuesta y no
un silencio. Cierra las tres puertas de golpe **sin impedir ninguna de las tres
operaciones**: las tres siguen dando 200, y ninguna reparte permisos.

#### Lo que el arreglo rompía y hubo que arreglar también

El aviso de Ajustes decía «no lleva ningún departamento, **así que ve a toda la
empresa**». Con el cambio eso solo es cierto mientras nadie lleve nada; pasado
ese punto significa lo contrario ---no ve a nadie, y no puede hacer su trabajo---
y le pasa justo a quien acaba de ceder el suyo. Un aviso que dice lo contrario de
lo que ocurre es peor que no tenerlo, así que ahora el servidor manda
`department_scoping_in_use` y la pantalla dice cuál de las dos cosas es, con
`info` en vez de `warning` cuando es la segunda. La regla no se recalcula en el
cliente: habría dos copias y una se quedaría atrás.

#### La prueba existente que pasaba por un motivo más estrecho que su nombre

`test_a_manager_in_charge_of_nothing_reads_everybody` seguía verde con el arreglo
puesto. No por casualidad: en su fixture `boss` es la **única** responsable
asignada, así que al quitarla no queda nadie llevando nada ---el estado del día
uno--- y la rama nueva no se dispara. La prueba era cierta, pero decía más de lo
que probaba. Renombrada a `..._reads_everybody_while_nobody_is`, con una
aserción explícita de que ahí no queda nadie al mando y un puntero a la prueba
del caso contrario.

**Comprobado que las pruebas nuevas cazan el fallo**: quitando el arreglo, tres
se ponen rojas y las tres que defienden el día uno siguen verdes.

#### Y una prueba para la frase, no solo para la regla

La lección de la vuelta es que **un texto puede mentir sin romper nada**: el aviso
era una plantilla dentro del JSX, así que ninguna prueba se enteraba. Para poder
probarlo se sacó a `avisoDeAlcance()` en su propio módulo, lo que además deja el
componente sin la decisión metida en una expresión.

La prueba de navegador ejercita el helper y no la pantalla montada: para verla en
pie haría falta dejar sin departamento a una responsable de la semilla, y una
prueba que reorganiza la empresa de demostración le cambia los datos a las demás.
Cubre los dos textos, la concordancia en plural ---que aquí afecta al verbo y al
posesivo, no solo al sustantivo--- y los dos vacíos: sin nadie suelto, y con la
API todavía sin responder.

7 pruebas nuevas en el backend (1.080) y 1 de navegador (272).

### Vuelta 83 --- La matriz entera, y esta vez no había nada (26/08)

**Primera vuelta sin hallazgo.** Contador de vueltas seguidas sin hallazgos: 0 → **1**.

La lente: dejar de mirar áreas y mirar **la matriz completa**, cada ruta contra
cada rol. Las vueltas anteriores han ido comprobando permisos área por área, que
es como se encuentran los fallos de una pantalla; lo que no se había hecho nunca
es la tabla entera de una vez, que es como se encuentran los **huecos entre**
áreas --- la ruta que nadie revisó porque no era de nadie.

#### Los cuatro ejes, y lo que dio cada uno

**Lectura por rol.** Las 51 rutas de lista, con sesión de operario, responsable,
administración y una administradora de otra empresa. Todas filtran por alcance.
Dos merecían una segunda mirada y las dos aguantaron:

- `/api/audit/` responde **200 a un operario**, que de primeras parece un hueco.
  No lo es: la lista le llega **vacía** ---0 entradas, contra 1 que ve la
  administración--- porque el filtro es por alcance, no por ruta. Un 403 sería
  más legible, pero no es un fallo de aislamiento.
- El cuadrante (`/api/shifts/roster/` y `/review/`) le enseña al operario **solo
  el suyo**, y solo su propio aviso ---un `break_owed` sobre sí mismo---, no los
  del compañero de otro departamento.

**Escritura de gestión con sesión de operario.** Diez intentos: 403 en los nueve
de gestión, y 409 `not_your_request` al pedir una ausencia a nombre de otro.

**Una responsable haciendo de administración.** Diez intentos, diez 403: reglas
de jornada, datos de empresa, crear departamento, centro o persona, autorizar una
aplicación, declarar el registro, **subirse a sí misma a administradora**, y
tocar o dar de baja a alguien de otro departamento. Comprobado después contra la
base: sigue siendo `MANAGER`, y el de Oficina sigue llamándose como se llamaba y
sigue activo.

**Otra empresa con nuestros identificadores en la mano.** Diez intentos, todos
**404** ---leer, dar de baja, renombrar, aprobar una corrección, aprobar una
ausencia, leer un justificante, borrar un turno--- y 400 el informe. El 404 en
vez del 403 es deliberado: un 403 confirmaría que el recurso existe, y eso ya es
contar algo de una empresa que no es la suya.

#### Lo que deja la vuelta, ya que no deja un arreglo

`apps/common/tests/test_la_matriz_de_permisos.py`, cinco pruebas. **Saca las
rutas del enrutador**, no de una lista escrita a mano, así que una ruta nueva sin
permisos aparece ahí el día que se escribe, sin que nadie se acuerde de añadirla.

Es el mismo tipo de guard que `test_entrada_malformada` y
`test_no_crece_con_la_plantilla`, y los dos encontraron cosas **en vueltas
posteriores** a la que los escribió: tres 500 el primero, dos N+1 el segundo. Una
vuelta sin hallazgo no tiene por qué acabar sin dejar nada.

**Lo que el guard no cubre**, y queda dicho para que un verde no se lea como más
de lo que es: comprueba **códigos**, no contenidos. Un 200 con la lista filtrada
y un 200 con la lista entera son idénticos desde fuera. Eso lo siguen cubriendo
las pruebas de cada área ---el rastro, el cuadrante, los justificantes--- y son
esas las que hay que mirar si algún día se sospecha de una fuga *dentro* de una
respuesta.

### Vuelta 82 --- Recuperar la cuenta no echaba a nadie (26/08)

**Lente:** la sesión y los testigos. Un acceso vive quince minutos y un refresco
**siete días**, y rota --- mientras alguien lo use, se renueva solo. Así que una
sesión abierta no caduca por sí sola en ningún plazo útil, y la pregunta es qué la
cierra.

#### Antes, un cierre de la lente anterior

Las dependencias del frontend: `npm audit` da **cero** vulnerabilidades sobre 255
dependencias analizadas ---comprobado que mira algo, no que no mire---, así que el
cero de Dependabot para npm era correcto y no un hueco de vigilancia.

#### El hallazgo, en dos momentos y los dos fallando

**Cambiar la contraseña.** Es lo que hace quien cree que le han visto la clave o ha
perdido el móvil, y era exactamente lo que no servía: ese dispositivo seguía
renovando la sesión (200) y leyendo datos (200) después del cambio. Recuperar la
cuenta no echaba a nadie.

**Dar de baja a una persona.** El acceso deja de valer al instante ---la
autenticación mira `is_active`, y eso estaba bien: 401 en todo--- pero el refresco
sobrevivía. Y lo que hace el caso concreto es que la baja es **reversible**: al
reincorporarla, la sesión de antes volvía a funcionar sin que hubiera vuelto a
escribir la contraseña. El móvil que llevaba cuando se fue seguía dentro el día que
la readmitieron.

**El mecanismo ya estaba puesto** ---la rotación pone en la lista negra el refresco
usado--- y no se llamaba desde ninguno de los dos sitios. `revoke_sessions()` en
`passwords.py`, llamada al cambiar la clave ---**antes** de emitir la nueva sesión,
o se revocaría la que se acaba de dar--- y al dar de baja.

Lo que **no** se revoca son los accesos ya emitidos: quince minutos de vida a
propósito, y cortarlos exigiría consultar la base en cada petición. Queda dicho en
el docstring para que nadie lo descubra creyendo que es un olvido.

**Prueba.** `apps/users/tests/test_recuperar_la_cuenta_echa_a_quien_esta_dentro.py`,
cinco casos, incluidos el de que quien cambia la clave entra sin volver a
escribirla ---si se revocara después de emitir, se mataría la sesión nueva--- y el
de que la sesión de otra persona no se toca.

**Y las pruebas pasaban con el arreglo quitado.** El control «la sesión valía
antes» **consume** la sesión: la rotación la pone en la lista negra, así que el
rechazo de después venía de eso. Se abren dos sesiones, una para el control y otra
que llega sin estrenar al momento que importa. Salió al validar contra el fallo:
solo caía una de las tres.

**Estado:** área «Sesión» limpia, con una lente más. Cerrada con **1068 pruebas
de backend y 271 de navegador en verde**, linters limpios, castellano sin huecos,
cero `fuzzy` y sin migraciones pendientes.

### Vuelta 81 --- La semana que no cabía en ningún mes (26/08)

**Lente:** el calendario en los bordes --- semanas que cruzan el año, semana 53,
cambios de mes.

#### Lo que salió limpio

El agrupado del cómputo semanal va por **año ISO** y eso es lo correcto: el 29 de
diciembre de 2025 es la semana 1 de 2026, así que la semana del cambio de año se
cuenta como una. Comprobado con datos: 45 horas en un solo aviso, no dos mitades
de 27 y 18 que no llegarían al tope. Y 2026 tiene 53 semanas ISO, que también
maneja bien porque `fromisocalendar` es la inversa exacta.

#### El hallazgo: la semana del borde no se revisaba nunca

El chequeo exigía que la semana **cupiera entera** dentro del periodo pedido y la
descartaba si no. Y un cuadrante se revisa mes a mes:

| Quien revisa | Antes | Después |
|---|---|---|
| Junio | nada | avisa |
| Julio | nada | avisa |
| Los dos meses juntos | avisa | avisa |

Cuarenta y cinco horas planificadas del 29 de junio al 5 de julio de 2026, por
encima de las cuarenta del art. 34.1, y quien revisa el cuadrante mes a mes no las
veía en ninguno de los dos.

**El razonamiento de descartarla era bueno** y está escrito en su docstring:
contar media semana y avisar es peor que callar, porque quien lo lee va a buscar
horas que no están. Lo que no se consideró es la tercera opción --- contar la
semana **completa**. Esos turnos están en la base; solo estaban fuera del rango
pedido.

**Arreglo.** `review_roster` ya leía un día a cada lado por el descanso entre
jornadas; ahora lee hasta el lunes y el domingo de las semanas de los bordes, y el
cómputo semanal juzga las que **solapan** en vez de las que caben. Los demás
chequeos no se enteran: los cinco filtran por `first`/`last` antes de reportar, así
que leer más días les da contexto y no les hace hablar de días que nadie pidió ---
comprobado antes de tocar la carga, y con una prueba propia.

**Prueba.** `apps/shifts/tests/test_la_semana_del_borde_del_mes.py`, seis casos.
El que distingue las tres conductas posibles es el de las horas: 45 es la semana
entera, 18 serían los dos días de junio y «nada» era el descarte. **Validada
contra el fallo**: revertida la condición, caen tres y los tres controles
aguantan.

**Y una prueba existente que fijaba el descarte.** `test_a_week_only_half_inside_
the_window_is_not_reported` afirmaba que no se reportaba nada, con el razonamiento
correcto para lo que el código podía hacer entonces. Reescrita con su misma
intención ---no contar medias semanas--- y el comportamiento nuevo: siete mañanas
son 56 horas, y la cifra dice cuál de las tres conductas está puesta.

**Estado:** área «Cuadrante» limpia, con una lente más. Cerrada con **1063
pruebas de backend y 271 de navegador en verde**, linters limpios, castellano sin
huecos, cero `fuzzy` y sin migraciones pendientes.

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
