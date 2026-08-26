# Trabajos periódicos: cron o Celery

OpenTimeTrack tiene dos trabajos que se repiten solos:

| Trabajo | Cada cuánto | Qué hace |
|---|---|---|
| `send_punch_reminders` | Cada pocos minutos | Avisa a quien empezó su turno y no ha fichado, o dejó la jornada abierta. Nunca ficha por nadie |
| `purge_security_metadata` | Una vez al día | Borra la IP y el dispositivo de los fichajes que ya cumplieron su plazo de conservación |
| `flushexpiredtokens` | Una vez al día | Tira los testigos de sesión caducados. Con la rotación activada se acumulan del orden de dos millones de filas al año en una empresa de doscientas personas, y cada una dice de quién era la sesión (art. 5.1.e RGPD) |

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
```

Las dos purgas van a horas distintas a propósito: no se estorban sobre la misma
base, pero repartirlas deja los registros legibles cuando una tarda de más.

Con contenedores, lo mismo desde el anfitrión:

```cron
*/5 * * * *  docker compose exec -T api python manage.py send_punch_reminders
```

Los dos comandos son **idempotentes**: ejecutarlos dos veces no avisa dos veces
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
que no ocurre es que nadie reciba recordatorios, y que **las dos purgas no se
hagan**: los metadatos de seguridad se quedan más tiempo del que deberían, y la
tabla de testigos de sesión crece sin techo ---cada renovación deja dos filas, y
hay una por persona cada cuarto de hora---.

Las dos purgas conviene programarlas aunque no quieras los avisos: lo primero es
un incumplimiento de tu propia política de conservación, y lo segundo, guardar
sin plazo un dato que dice de quién era cada sesión (art. 5.1.e RGPD).
