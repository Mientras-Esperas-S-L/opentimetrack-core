# Cuaderno del bucle: la consola de Instalación

Estado entre pasadas. El prompt está en `consola-instalacion-loop.md`.

| # | Trozo | Estado |
|---|---|---|
| T1 | Registro de lo que hacen las cuentas de instalación | **hecho** (PR core 26) |
| T2 | Editar y desactivar una empresa | pendiente |
| T3 | Los administradores de cada empresa y su contraseña | pendiente |
| T4 | El estado de cada empresa de un vistazo | pendiente |

## Qué toca ahora

T2: editar y desactivar una empresa.

## Qué se hizo en la última pasada

**T1**, 23/09/2026.

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

- **Tabla propia para la instalación** y no `tenant` nulo en `AuditLog`: esa tabla
  va por empresa para que ninguna lea la de otra, y un nulo ahí es una fila que
  cada consulta tendría que acordarse de excluir.
- **La pista de la credencial sí se guarda** (los últimos caracteres, `…abcd`), que
  es lo que la pantalla ya enseña de cada una. El testigo entero, nunca.
- **Crear una empresa no se anota en el rastro de la empresa**, solo en el de la
  instalación: antes de existir no tiene rastro, y su administrador ya sabe que se
  creó.

## Lo que espera decisión del usuario

- **Producción, cuando se despliegue T1, trae dos migraciones** (`audit/0021` y
  `0022`): copia previa de la base antes.
