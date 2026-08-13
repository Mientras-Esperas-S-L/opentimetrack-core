# Prompt de auditoría completa de OpenTimeTrack

Para pegar tal cual cuando quieras una pasada a fondo. Está escrito con lo que
de verdad ha encontrado fallos, no con buenas intenciones: cada técnica de la
sección «cómo buscar» sacó al menos un error real el 13/08/2026.

---

## El prompt

> Haz una auditoría completa de OpenTimeTrack: frontend, backend, cumplimiento
> legal y experiencia de uso. No quiero un informe de intenciones: quiero
> fallos concretos encontrados ejecutando la aplicación, arreglados, y con una
> prueba que impida que vuelvan.
>
> ### 1. Cobertura: que no se salte nada
>
> Recorre **todas** las pantallas y, en cada una, **todos** sus controles: cada
> formulario con todos sus campos, cada botón, cada desplegable, cada pestaña,
> cada filtro, cada acción de fila y cada diálogo. Empieza sacando el inventario
> real del DOM en vez de adivinarlo: los rótulos que crees que hay casi nunca
> son los que hay.
>
> De cada formulario prueba, como mínimo: guardar con todo relleno, guardar con
> lo obligatorio vacío, valores en el límite y fuera de él, el orden inverso en
> los rangos de fechas, texto donde se espera un número, y **volver a abrirlo**
> para ver que no arrastra el estado anterior. De cada lista: vacía, con una
> fila, con más de una página. De cada descarga: **ábrela**.
>
> ### 2. Cómo buscar (esto es lo que rinde)
>
> - **Escucha la consola en toda prueba de pantalla.** Un `console.error` es un
>   fallo. De los errores que aparecieron probando a mano, tres ya estaban
>   gritando ahí antes de que nadie abriera la pantalla.
> - **Comprueba los bytes, no la extensión.** Un zip empieza por `PK` y un PDF
>   por `%PDF`. Un informe que se llamaba `.pdf` y era un zip estuvo roto meses
>   con la comprobación del nombre en verde.
> - **Valida toda comprobación limpia contra un caso conocido.** Si un filtro
>   «no devuelve nada raro», pruébalo con un valor que sí tenga que devolver
>   algo. `?department=` rechazaba **cualquier** identificador, y una prueba con
>   uno inventado habría pasado.
> - **Pregunta al producto, no al rótulo.** Los contadores llegan tarde: leer
>   «0» de una pestaña que tendrá 22 hace que la prueba se salte sola.
> - **Limpia antes de crear, no solo después.** Una prueba que se cae a mitad
>   deja datos, y la siguiente falla por ellos apuntando a donde no es.
> - **Localiza por rol, no por texto literal.** El asterisco de un campo
>   obligatorio desaparece al rellenarlo, los plurales cambian con el contador y
>   las clases de MUI se renombran entre versiones.
> - **Si el frontend no ve algo que el servidor manda, mira CORS antes que el
>   frontend.** `Content-Disposition` y `Date` no se exponen por defecto.
> - **Muchos fallos a la vez no son muchos fallos.** Antes de leer el primero
>   como real, comprueba que no esté rota la prueba.
>
> ### 3. Seguridad y aislamiento
>
> Por **API y con la sesión del atacante**, no por pantalla: un botón que no se
> pinta no demuestra nada sobre lo que el servidor acepta.
>
> - Con la sesión de otra empresa, intenta leer y escribir en todo recurso
>   conocido su identificador. Consíguelo como se consigue de verdad:
>   preguntándoselo al servidor con la sesión legítima.
> - Con la sesión de un operario, intenta lo de gestión. Y comprueba que lo que
>   **sí** puede ver traiga solo lo suyo, campo a campo: el registro de
>   actividad le enseñaba la dirección IP del responsable que le tocó un fichaje.
> - Prueba la escalada por parámetro: `?employee=<otro>`, cuerpos con
>   `tenant`, identificadores ajenos en campos de relación.
> - Comprueba los límites de peticiones y **qué hace la pantalla cuando saltan**:
>   un 429 no es un cierre de sesión.
>
> ### 4. Lógica de negocio y ley
>
> Revisa punto por punto contra el Estatuto de los Trabajadores y el proyecto de
> RD de registro de jornada, y **en el código que se ejecuta**, no en el marco
> legal ni en los comentarios. Que una cifra esté en `apps/legal/es.py` no
> significa que nada la comprueba: distingue «aplicado», «solo citado» y
> «ausente», y trata «solo citado» como lo más peligroso, porque parece cubierto.
>
> Cubre al menos: registro diario objetivo y fiable y su conservación (34.9),
> jornada y descansos (34), descanso semanal y festivos (37), horas extra con su
> tope anual y sus dos formas de saldarse (35), trabajo nocturno y a turnos (36),
> vacaciones con devengo proporcional y la baja que las pisa (38.3), permisos
> retribuidos (37.3), suspensiones (45-48), teletrabajo (Ley 10/2021),
> protección de datos y desconexión digital (RGPD y art. 88 LOPDGDD), y el
> consentimiento de las dos partes para tocar un asiento (art. 4.b).
>
> Y respeta las dos líneas que no se cruzan, aunque sean incómodas:
>
> - **El registro de jornada no se toca en masa.** Un asiento se corrige de uno
>   en uno. Si aparece un «seleccionar todo» ahí, es un fallo, no una mejora.
> - **Resolver en bloque solo si cada decisión guarda su propio rastro**, con
>   nombre y apellidos, y sin saltarse la separación de las cuatro manos.
>
> Cuando una regla admita excepción legal ---el descanso de doce horas lo baja
> el RD 1561/1995 en algunos sectores--- **avisa citando el artículo, no
> impidas**. Y no escribas la cifra en la pantalla: va en el marco legal del
> país, o acabarás enseñándole el número español a una empresa de fuera.
>
> ### 5. Cuatro perfiles, cuatro recorridos
>
> Ponte en cada uno y haz su tarea de principio a fin, cronometrando los clics.
> Anota dónde te atascas, qué no encuentras y qué te da miedo pulsar.
>
> - **Operario con el móvil, a pie de obra y con prisa.** Fichar, ver lo que
>   lleva, pedir un día, avisar de un fichaje mal. ¿Cuántos toques? ¿Se lee al
>   sol? ¿Entiende qué le van a descontar?
> - **Responsable de veinte personas, un lunes.** Resolver la cola del fin de
>   semana, cuadrar la semana, ver quién falta hoy. ¿Puede hacerlo sin abrir
>   veinte diálogos? ¿Sabe qué es urgente sin contarlo?
> - **Administración en el cierre de mes.** Sacar la totalización para la
>   nómina, revisar horas extra, dar de alta a cinco personas y reorganizar un
>   departamento. ¿Hay acciones masivas donde toca? ¿Los informes salen con un
>   nombre que diga de quién y de cuándo?
> - **Inspección de Trabajo pidiendo un periodo.** ¿Se entrega en un formato que
>   se abre? ¿Distingue lo que hizo la persona de lo que hizo una aplicación en
>   su nombre? ¿Se ven las correcciones y las discrepancias?
>
> Añade un quinto si toca: **la persona con lector de pantalla**. Comprueba que
> las listas sean listas, que los mandos tengan nombre en castellano y que las
> tablas se puedan recorrer.
>
> ### 6. Qué entregar
>
> - Los fallos **arreglados**, cada uno con su prueba automática. Playwright
>   para el frontend, pytest para el backend.
> - Un documento pantalla por pantalla con tres estados: **hecho**, **por
>   hacer** (con su sitio en un orden razonado) y **está bien** ---esto último
>   importa: marca dónde no gastar más---.
> - Las suites enteras en verde, linters limpios, traducciones completas y sin
>   migraciones pendientes.
> - Lo aprendido en `tasks/lessons.md`, como regla que evite repetirlo.
>
> Cuando algo esté mal a propósito, dilo y explica por qué. Y cuando un fallo
> sea tuyo y no del producto, dilo también: si veinte pruebas se ponen rojas a
> la vez, empieza por sospechar de la prueba.

---

## Cómo usarlo

Tal cual, o recortado. Si quieres una pasada corta, quédate con las secciones 1,
2 y 6 y nombra dos o tres pantallas. La sección 4 necesita tiempo y conviene
pedirla sola.

Y una advertencia por experiencia: **este prompt genera trabajo de verdad**. La
primera pasada del 13/08 salió con dieciséis fallos reales, de los que dos eran
serios ---un formulario que no se podía enviar nunca y un informe que no se
podía abrir--- y ninguno se veía sin ejecutar la aplicación.
