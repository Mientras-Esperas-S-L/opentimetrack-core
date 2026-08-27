# Trabajos periódicos: cron o Celery

OpenTimeTrack tiene cuatro trabajos que se repiten solos:

| Trabajo | Cada cuánto | Qué hace |
|---|---|---|
| `send_punch_reminders` | Cada pocos minutos | Avisa a quien empezó su turno y no ha fichado, o dejó la jornada abierta. Nunca ficha por nadie |
| `purge_security_metadata` | Una vez al día | Borra la IP y el dispositivo de los fichajes que ya cumplieron su plazo de conservación |
| `flushexpiredtokens` | Una vez al día | Tira los testigos de sesión caducados. Con la rotación activada se acumulan del orden de dos millones de filas al año en una empresa de doscientas personas, y cada una dice de quién era la sesión (art. 5.1.e RGPD) |
| `purge_expired_records` | Una vez al día | Borra los fichajes que pasaron el plazo de conservación de su empresa. **El único trabajo que borra registro de jornada**: nunca por debajo de los cuatro años del art. 34.9 ET, corta por día entero en la zona de la empresa, no toca ausencias ni contratos, y deja asiento de cuántos borró |

Puedes ejecutarlos de dos maneras, y **eliges tú**. Se configura con una
variable:

```ini
SCHEDULER=cron     # por defecto
SCHEDULER=celery
```

La lógica es idéntica en los dos casos: las tareas de Celery llaman al mismo
comando de gestión que llamaría cron. No hay dos implementaciones que puedan
divergir.

> **Elige una sola.** Si dejas la línea en la crontab *y* levantas celery-beat,
> los dos programadores lanzarán el mismo trabajo. No corrompe nada —los
> recordatorios están deduplicados y la purga es idempotente— pero es trabajo
> doble y ruido en los registros.

## Opción 1: cron (por defecto)

Para el caso normal: una empresa, un servidor. Cron ya está instalado, no hay
que vigilarlo y toda la configuración son dos líneas.

```cron
*/5 * * * *  cd /srv/opentimetrack/backend && /srv/venv/bin/python manage.py send_punch_reminders
30 3 * * *   cd /srv/opentimetrack/backend && /srv/venv/bin/python manage.py purge_security_metadata
0 4 * * *    cd /srv/opentimetrack/backend && /srv/venv/bin/python manage.py flushexpiredtokens
30 4 * * *   cd /srv/opentimetrack/backend && /srv/venv/bin/python manage.py purge_expired_records
```

Las purgas van a horas distintas a propósito: no se estorban sobre la misma
base, pero repartirlas deja los registros legibles cuando una tarda de más. La
del registro va la última porque es la que borra jornada: si una noche algo va
mal, conviene que las otras ya hayan pasado y se lea en el registro cuál fue.

Antes de programarla la primera vez conviene verla en seco, que no toca nada:

```bash
python manage.py purge_expired_records --dry-run
```

Con contenedores, lo mismo desde el anfitrión:

```cron
*/5 * * * *  docker compose exec -T api python manage.py send_punch_reminders
```

Los comandos son **idempotentes**: ejecutarlos dos veces no avisa dos veces
ni borra dos veces. Si la máquina estuvo apagada una hora, la siguiente
ejecución hace lo que toca en ese momento; no intenta recuperar avisos de hace
una hora, que ya no recuerdan nada.

## Opción 2: Celery con Redis

Para quien ya tiene varias máquinas, quiere ver los trabajos y reintentarlos, o
no quiere que la crontab de un servidor concreto sea el único sitio donde vive
la programación.

```ini
SCHEDULER=celery
CELERY_BROKER_URL=redis://redis:6379/0   # por defecto, el mismo Redis que la caché
REMINDER_EVERY_MINUTES=5
```

Y dos procesos, que hacen cosas distintas y hacen falta los dos:

```bash
celery -A config worker -l info    # ejecuta
celery -A config beat   -l info    # decide cuándo
```

Con el compose incluido:

```bash
podman compose --profile celery up -d
```

Con `SCHEDULER=cron`, `beat` no programa nada aunque lo levantes: la
comprobación está en `config/celery.py`, para que dejarse el perfil puesto no
acabe en dos programadores compitiendo.

## Qué pasa si no configuras ninguno

Nada se rompe y no se pierde ni un fichaje: el registro no depende de esto. Lo
que no ocurre es que nadie reciba recordatorios, y que **las purgas no se hagan**:
los metadatos de seguridad se quedan más tiempo del que deberían, la tabla de
testigos de sesión crece sin techo ---cada renovación deja dos filas, y hay una
por persona cada cuarto de hora--- y **los fichajes se conservan para siempre**.

Las purgas conviene programarlas aunque no quieras los avisos. Las tres son la
misma cosa vista tres veces: conservar un dato porque algún día pueda ser útil no
es una base (art. 5.1.e RGPD). Y la del registro es además la que hace verdad lo
que la empresa declaró en sus ajustes: mientras no corra, el plazo de
conservación de la pantalla es una intención, no un hecho.
