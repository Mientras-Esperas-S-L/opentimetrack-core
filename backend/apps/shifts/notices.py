"""Avisar a la persona de que le han cambiado el turno, y poder probarlo.

El cuadrante se pintaba, se borraba y se pasaba de una persona a otra sin que a
nadie le llegara nada: quien tenía turno el martes por la mañana se enteraba de
que ahora era por la tarde si abría la pantalla, y la empresa no tenía forma de
decir cuándo se lo había comunicado. El RD 723/2026 pide las dos cosas: informar
de los cambios de jornada y de turno con un preaviso (art. 3.2.g) y, por un
canal electrónico, conservar prueba de la transmisión y la recepción (art. 6).

La forma de usarlo es una foto antes y otra después de escribir:

    with avisando(company=..., actor=..., pairs=[(persona, día), ...]):
        ... lo que cambie el cuadrante ...

Lo que difiere entre las dos fotos se apunta. Así da igual por qué camino cambió
el turno ---pintar, asignar, borrar, cubrir a otro--- y ningún camino nuevo se
queda sin aviso por olvidar llamar a algo.

Apuntar no es avisar. El aviso sale cuando el cuadrante de esa persona lleva
unos minutos quieto (`publicar`, desde `send_shift_notices`), con lo que de
verdad cambió: pintar y deshacer no avisa de nada. O antes, si la persona abre
sus avisos.

Solo se avisa de los días de hoy en adelante. Rellenar el cuadrante de la semana
pasada es poner en orden lo que ya pasó, no un cambio que alguien tenga que
saber para organizarse.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _

from apps.common.clock import local_today
from apps.shifts.models import PendingShiftChange, Shift, ShiftNotice

log = logging.getLogger(__name__)

#: Cómo consta que lo vio desde nuestra propia aplicación. Desde otra, con la
#: sesión de la persona, consta el nombre de esa aplicación.
NUESTRA = "OpenTimeTrack"


def foto(pairs) -> dict:
    """Lo que había en cada `(persona, día)`: sus tramos, o `None` si nada."""
    pares = {(str(persona), dia) for persona, dia in pairs}
    if not pares:
        return {}
    hay = {
        (str(s.employee_id), s.day): s.segments
        for s in Shift.objects.filter(
            employee_id__in={p for p, _d in pares}, day__in={d for _p, d in pares}
        )
    }
    return {par: hay.get(par) for par in pares}


@contextmanager
def avisando(*, company, actor, pairs):
    """Apunta lo que cambie dentro del bloque para avisar de ello. Ver el módulo.

    `resultado["personas"]` dice a cuántas personas se avisará.
    """
    pares = list(pairs)
    antes = foto(pares)
    resultado = {"personas": 0}
    yield resultado
    resultado["personas"] = anotar(company=company, actor=actor, antes=antes, despues=foto(pares))


def anotar(*, company, actor, antes: dict, despues: dict) -> int:
    """Apunta cada día que cambió, guardando lo que había antes del primer cambio.

    No avisa todavía: eso lo hace `publicar` cuando el cuadrante de esa persona
    lleva un rato quieto. Devuelve a cuántas personas les queda algo pendiente
    por esta operación.
    """
    from apps.users.models import User

    por_persona = defaultdict(list)
    for persona, dia in antes.keys() | despues.keys():
        era, es = antes.get((persona, dia)), despues.get((persona, dia))
        if era != es:
            por_persona[persona].append((dia, era))
    if not por_persona:
        return 0

    personas = 0
    # Quien está de baja no tiene a quién avisar: sus turnos se limpian al darle
    # de baja, y eso no es un cambio que tenga que organizar.
    for persona in User.objects.filter(tenant=company, pk__in=list(por_persona), is_active=True):
        hoy = local_today(persona)
        filas = [f for f in por_persona[str(persona.pk)] if f[0] >= hoy]
        for dia, era in filas:
            pendiente, nuevo = PendingShiftChange.objects.get_or_create(
                tenant=company,
                employee=persona,
                day=dia,
                defaults={"original": era, "changed_by": actor},
            )
            if not nuevo:
                # Lo que había antes del **primer** cambio se queda; lo que se
                # mueve es quién tocó el último y cuándo.
                pendiente.changed_by = actor
                pendiente.save(update_fields=["changed_by"])
        personas += bool(filas)
    return personas


def publicar(company, *, employee=None, espera: timedelta | None = None) -> list[ShiftNotice]:
    """Convierte lo pendiente en avisos, uno por persona, con lo que de verdad cambió.

    Solo de quien lleva `espera` sin cambios ---por defecto
    `SHIFT_NOTICE_WAIT_MINUTES`---, para no avisar a mitad de una corrección.
    Con `espera=timedelta(0)` sale ya: es lo que pasa cuando la propia persona
    abre sus avisos, que tiene que ver lo último y no esperar al correo.

    Se compara lo que había antes del primer cambio con lo que hay ahora. Un día
    pintado y deshecho no cambió, y no se avisa.
    """
    from apps.tenants.rules import WorkingTimeRules

    if espera is None:
        espera = timedelta(minutes=settings.SHIFT_NOTICE_WAIT_MINUTES)
    limite = timezone.now() - espera

    pendientes = PendingShiftChange.objects.filter(tenant=company).select_related(
        "employee", "changed_by"
    )
    if employee is not None:
        pendientes = pendientes.filter(employee=employee)

    por_persona = defaultdict(list)
    for fila in pendientes:
        por_persona[fila.employee_id].append(fila)

    minimo = None
    avisos = []
    for filas in por_persona.values():
        if max(f.updated_at for f in filas) > limite:
            continue
        with transaction.atomic():
            # Bloqueadas y por identificador: un cambio que entre mientras tanto
            # crea su propia fila, que se queda para la próxima vuelta.
            ids = [f.pk for f in filas]
            filas = list(
                PendingShiftChange.objects.select_for_update(of=("self",))
                .filter(pk__in=ids)
                .select_related("employee", "changed_by")
                .order_by("day")
            )
            if not filas:
                continue
            persona = filas[0].employee
            ahora = foto((persona.pk, f.day) for f in filas)
            hoy = local_today(persona)
            cambios = [
                {
                    "day": f.day.isoformat(),
                    "before": f.original,
                    "after": ahora[(str(persona.pk), f.day)],
                }
                for f in filas
                if f.day >= hoy and f.original != ahora[(str(persona.pk), f.day)]
            ]
            PendingShiftChange.objects.filter(pk__in=[f.pk for f in filas]).delete()
            if not cambios:
                continue

            if minimo is None:
                minimo = int(WorkingTimeRules.for_company(company).roster_notice_days or 0)
            ultima = max(filas, key=lambda f: f.updated_at)
            primero = date.fromisoformat(cambios[0]["day"])
            dias = (primero - hoy).days
            aviso = ShiftNotice.objects.create(
                tenant=company,
                employee=persona,
                changed_by=ultima.changed_by,
                changes=cambios,
                first_day=primero,
                notice_days=dias,
                short_notice=minimo > 0 and dias < minimo,
            )
            avisos.append(aviso)
            # Después de confirmar: si algo se deshace, no se avisa de lo que no
            # quedó.
            transaction.on_commit(lambda pk=aviso.pk: enviar([pk]))
    return avisos


# --------------------------------------------------------------------- enviar


def tramos(segments) -> str:
    """`08:00-15:00 y 17:00-20:00`, o «sin turno»."""
    if not segments:
        return _("no shift")
    partes = [f"{s['start']}-{s['end']}" for s in segments]
    return (
        partes[0]
        if len(partes) == 1
        else _("%(first)s and %(rest)s")
        % {
            "first": ", ".join(partes[:-1]),
            "rest": partes[-1],
        }
    )


def lineas(aviso: ShiftNotice) -> list[str]:
    """Cada día que cambió, en una línea que se entiende sin la pantalla."""
    from datetime import date

    salida = []
    for cambio in aviso.changes:
        dia = formats.date_format(date.fromisoformat(cambio["day"]), "l j/m/Y")
        if cambio["before"] is None:
            que = _("new shift, %(after)s") % {"after": tramos(cambio["after"])}
        elif cambio["after"] is None:
            que = _("cancelled, it was %(before)s") % {"before": tramos(cambio["before"])}
        else:
            que = _("%(before)s, now %(after)s") % {
                "before": tramos(cambio["before"]),
                "after": tramos(cambio["after"]),
            }
        salida.append(f"{dia}: {que}")
    return salida


def enviar(ids) -> None:
    """Correo y notificación del navegador. Cada canal anota cuándo lo aceptó.

    Nunca falla hacia fuera: el cambio ya está hecho y el aviso ya consta. Lo
    que no salga se ve en el aviso mismo, con la hora de ese canal vacía.
    """
    from apps.common.mail import send_without_failing
    from apps.notifications.push import send_push

    for aviso in ShiftNotice.objects_all_tenants.filter(pk__in=ids).select_related(
        "employee", "tenant", "changed_by"
    ):
        persona = aviso.employee
        try:
            # En el idioma de quien lo recibe, no en el de quien cambió el turno.
            with translation.override(persona.locale or aviso.tenant.language or None):
                cambios = lineas(aviso)
                asunto = _("Your shift has changed")
                cuerpo = render_to_string(
                    "emails/shift_changed.txt",
                    {
                        "first_name": persona.first_name,
                        "company": aviso.tenant.name,
                        "changes": cambios,
                        "changed_by": aviso.changed_by.get_full_name() if aviso.changed_by else "",
                    },
                )
                corto = (
                    cambios[0]
                    if len(cambios) == 1
                    else _("%(count)s days of your roster have changed.") % {"count": len(cambios)}
                )

            if persona.email and send_without_failing(
                subject=asunto, message=cuerpo, to=persona.email, what="a shift change notice"
            ):
                ShiftNotice.objects_all_tenants.filter(pk=aviso.pk, emailed_at__isnull=True).update(
                    emailed_at=timezone.now()
                )
            if send_push(persona, title=asunto, body=corto, url="/fichar", tag=f"turno-{aviso.pk}"):
                ShiftNotice.objects_all_tenants.filter(pk=aviso.pk, pushed_at__isnull=True).update(
                    pushed_at=timezone.now()
                )
        except Exception:
            log.exception("Could not send shift notice %s", aviso.pk)


# ------------------------------------------------------------ llegó y se leyó


def entregados(queryset, via: str) -> int:
    """Los que aún no constaban como llegados, llegan ahora. La hora no se mueve."""
    return queryset.filter(delivered_at__isnull=True).update(
        delivered_at=timezone.now(), delivered_via=via or NUESTRA
    )


def leido(aviso: ShiftNotice, via: str) -> ShiftNotice:
    """Lo leyó. Si no constaba como llegado, llegó en ese mismo momento."""
    via = via or NUESTRA
    entregados(ShiftNotice.objects.filter(pk=aviso.pk), via)
    ShiftNotice.objects.filter(pk=aviso.pk, read_at__isnull=True).update(
        read_at=timezone.now(), read_via=via
    )
    aviso.refresh_from_db()
    return aviso
