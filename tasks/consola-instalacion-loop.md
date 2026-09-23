# Prompt del bucle: la consola de Instalación, para mantener y no solo para montar

Para `/loop` sin intervalo y **sin pausas**: no se pregunta nada al usuario. Se decide
con este fichero y lo dudoso se anota en el cuaderno
(`tasks/consola-instalacion-cuaderno.md`).

## Cómo lanzarlo

```
/loop Sigue tasks/consola-instalacion-loop.md del worktree /home/freemem/Projects/geosian/.worktrees/ott-core
```

---

## El prompt

> Hoy la consola de Instalación sirve para **montar** una empresa: crearla, ponerle la
> identidad, sus aplicaciones y sus claves, y las cuentas de la propia instalación.
> No sirve para **mantenerla**. Este bucle añade cuatro cosas, **una por pasada y en
> este orden**:
>
> | # | Trozo | Por qué va en este sitio |
> |---|---|---|
> | T1 | Registro de lo que hacen las cuentas de instalación | Primero, para que lo que añaden T2 y T3 ya quede anotado al nacer |
> | T2 | Editar y desactivar una empresa | Hoy solo se puede crear |
> | T3 | Los administradores de cada empresa y su contraseña | La llamada de soporte más habitual: «el responsable no puede entrar» |
> | T4 | El estado de cada empresa de un vistazo | Ver un fallo antes de que llame el cliente |
>
> Cada pasada deja su trozo **terminado**: backend, pantalla, pruebas calibradas,
> artículo de ayuda al día, `scripts/como-el-ci.sh` en verde, PR, checks en verde,
> fusionado, desplegado en devel y **mirado con los ojos** a 1280 y a 360 px. Después
> anota en el cuaderno y programa la siguiente sin esperar.
>
> ### Lo que no se toca, pase lo que pase
>
> - **Los datos del registro de jornada no se enseñan a la instalación.** Ni fichajes,
>   ni nombres de quien ficha, ni ausencias. La cuenta de instalación es ajena a la
>   empresa, y leer datos personales del registro sin ser de la empresa es un problema
>   legal. T4 enseña **fechas y recuentos**, nunca contenido ni personas.
> - **Nada se borra.** Una empresa se desactiva, no se elimina: su registro se guarda
>   los años de `record_retention_years`. Una desactivación tiene que poder deshacerse
>   exactamente.
> - **Producción, nunca.** Eso lo lanza el usuario.
>
> ### T1. El registro de la instalación
>
> Hoy, que una cuenta de instalación cree una empresa, emita una clave o dé de alta
> otra cuenta **no deja rastro en ningún sitio**. Tienen mucho poder y el ENS pide
> saber quién hizo qué y cuándo.
>
> **Ojo con `AuditLog`**: su `tenant` **no admite nulo** y está protegido contra
> escritura posterior (la comprobación `audit_append_only` de `/health`). Lo de la
> instalación no siempre tiene empresa ---crear una cuenta de instalación no la
> tiene---. Lo que sugiere este fichero: **una tabla propia de la instalación**, igual
> de inmutable y con la misma protección que `AuditLog`, en vez de hacer nulo el
> `tenant` de una tabla que guarda cuatro años de registro legal. Y además, cuando la
> acción es **sobre una empresa**, anotarla también en el `AuditLog` de esa empresa,
> para que su administrador vea que alguien de fuera tocó su configuración. Si al
> leer el código otra salida resulta claramente mejor, se toma y se explica en
> «Decisiones tomadas sin preguntar».
>
> Qué se anota: todo lo que escribe en `platform_views.py` ---empresa creada,
> identidad puesta o quitada, aplicación autorizada, cambiada o retirada, clave
> emitida o revocada, cuenta de instalación creada, desactivada o con contraseña
> nueva--- y lo que añadan T2 y T3. **Nunca un secreto**: ni la clave emitida ni la
> contraseña, solo que se emitió.
>
> En la consola, una sección «Registro» con fecha, quién, qué y sobre qué, la más
> reciente arriba y paginada.
>
> ### T2. Editar y desactivar una empresa
>
> - **Editar**: nombre, CIF, país, zona horaria, idioma. **Antes de dejar cambiar el
>   CIF**, mira dónde se usa: la entrada lo pide para desambiguar un correo repetido,
>   y GreenCity lo guardó al dar de alta ---busca `tax_id` y `cif` en
>   `~/Projects/geosian/.worktrees/ott-backend/backend/ott/`---. Si cambiarlo rompe el
>   enlace con GreenCity, la pantalla lo avisa antes de guardar; no se arregla GreenCity
>   en este bucle, se anota.
> - **Desactivar y reactivar**. El backend de autenticación ya rechaza entrar si la
>   empresa está inactiva, pero **eso solo mira al entrar**. Comprueba con una prueba
>   que una sesión ya abierta ---de una persona y de una aplicación de GreenCity--- deja
>   de funcionar al desactivar. Si no deja, ese es el arreglo de verdad de este trozo.
> - La desactivación pide **escribir el nombre de la empresa** para confirmar, y dice
>   qué va a pasar: nadie de dentro entra, GreenCity deja de poder fichar, y los datos
>   se guardan.
>
> ### T3. Los administradores de cada empresa
>
> En la ficha de cada empresa, quién la administra: nombre, correo, si entra con
> contraseña o con la cuenta de su empresa, y cuándo entró por última vez.
>
> Y **mandarle un enlace para poner contraseña nueva**, con el flujo que ya existe
> (`PasswordResetRequestSerializer` y `PasswordSetSerializer`). La instalación **no ve
> ni elige** la contraseña de nadie de una empresa: se manda el enlace a su correo.
> Dos casos que la pantalla tiene que explicar en vez de fallar:
>
> - Quien entra con la cuenta de su empresa (federado) no tiene contraseña aquí: se
>   dice, y no se ofrece el botón.
> - Si producción no tiene correo configurado, el enlace no llega. **Comprueba el
>   `.env` de la pila de producción del CT121** ---solo mirar si `EMAIL_HOST` está
>   puesto, sin enseñar secretos---. Si no lo está, el enlace se enseña una vez en
>   pantalla para copiarlo y el cuaderno lo apunta para el usuario.
>
> Solo administradores. Nada de listar al resto de la plantilla: eso ya es dato de
> la empresa.
>
> ### T4. El estado de cada empresa
>
> En la lista de empresas, por fila: activa o no, identidad puesta y funcionando,
> **fecha** del último fichaje (sin quién), número de personas activas, y por cada
> aplicación la fecha de su último uso (`last_used_at` de sus credenciales). Lo que
> lleve más de un día laborable callado se marca, con texto y no solo con color.
>
> Los recuentos por empresa, **con `objects_all_tenants`**: el manager normal devuelve
> nada sin inquilino y la pantalla diría cero en todas. Y **en una consulta agregada**,
> no una por empresa.
>
> ### Cómo se mira
>
> - Cada pantalla, **a 1280 y a 360 px**, con el navegador contra devel. Comparar
>   `window.innerWidth` con el ancho pedido: si no coincide, el navegador se ha rendido
>   y las medidas no valen.
> - Lo de siempre: consola sin errores, ninguna respuesta 4xx o 5xx que la pantalla no
>   explique, un botón que cambia mientras trabaja, cada icono con nombre accesible.
> - **Hechos, no veredictos**: qué se hizo, qué pasó, qué se esperaba.
>
> ### Con qué se entra en devel
>
> `instalacion@mientrasesperas.es` en `ott.devel.greencitycontrol.com`. La contraseña
> está en la conversación y **no va al repositorio**. Si no funciona, se le pone una
> nueva desde otra cuenta de instalación de devel, que para eso está el botón.
>
> ### Reglas de la casa
>
> - Rama nueva **desde `origin/main` recién traído** en cada pasada. `main` está
>   ocupado por otro worktree: la rama de trabajo se llama como el trozo.
> - Código y comentarios del backend **en inglés**; lo visible por `gettext` en el
>   backend (y a los tres catálogos `ca`, `es`, `gl`, con `compilemessages`) y por el
>   catálogo en el frontal (`npm run i18n:check`).
> - MUI: `slotProps`, no `PaperProps`; las props de sistema por `sx`; un `IconButton`
>   dentro de un `Tooltip` necesita su `aria-label`.
> - Las migraciones del Core **sí** se commitean.
> - Pruebas **calibradas**: se comprueba que fallan sin el arreglo, revirtiendo con
>   `git apply -R` de un parche, nunca con `git stash`, que es compartido.
> - **No encadenar tras una tubería**: `pytest | tail && git commit` commitea en rojo.
> - La ayuda: el artículo `instalacion` de `backend/apps/help/content/es.json` cuenta
>   lo nuevo, y se vuelve a sembrar en devel con `seed_help`.
>
> ### Commits, PR y despliegue
>
> - Un PR por trozo. *Conventional commits*, sin `Co-Authored-By`.
> - El cuerpo del PR lleva **lo que se midió**, no la lista de ficheros.
> - Despliegue en devel:
>   `ssh ulises "pct exec 121 -- /usr/local/sbin/ott-desplegar devel --rama main"`.
>   Si el trozo trae migraciones, dilo en el PR: producción necesitará copia previa.
>
> ### Al final de cada pasada
>
> El cuaderno: qué se hizo, con qué PR, qué se midió, qué se decidió sin preguntar y
> qué toca. Va commiteado en el PR del trozo.
>
> Se para (con `stop`) cuando los cuatro estén hechos, o cuando lo que quede dependa de
> una decisión del usuario, y entonces el cuaderno dice cuál.
