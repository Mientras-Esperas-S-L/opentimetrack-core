"""Qué turnos se han quedado sin nadie, y quién puede cogerlos.

El cuadrante ya avisaba de las dos formas en que un turno se queda huérfano
---`outside_the_contract` cuando quien lo tenía dejó la empresa, y
`rostered_on_leave` cuando está de baja--- y ahí se acababa. Avisar no es
cubrir: alguien tiene que poner a otra persona en ese turno, y para eso hacía
falta salir de la revisión, abrir el cuadrante, y mirar ficha por ficha quién
podía.

Este módulo responde las dos preguntas de golpe, y lo hace en un sitio porque
tres pantallas distintas necesitan la misma respuesta: el panel de cobertura
pendiente, las celdas marcadas de la rejilla, y el diálogo que se ofrece al dar
de baja a alguien.

## Duro y blando

Un candidato es **inviable** solo por lo que hace imposible el turno: no está
contratado ese día, tiene una ausencia que le para el día entero, o ya está en
otro turno ---nadie está en dos sitios a la vez---.

Lo demás son **avisos, no vetos**: que se pase de sus horas, que se quede sin
las doce de descanso. Son cosas que a veces se hacen a sabiendas, y quien cubre
una baja a última hora necesita saber el precio, no que se lo escondan. Un
producto que solo ofrece candidatos perfectos no ofrece a nadie el día que hay
gripe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils.translation import gettext_lazy as _

from apps.absences.models import STOPS_THE_WHOLE_DAY, Absence, AbsenceStatus
from apps.shifts.models import Shift

#: Por qué un turno se ha quedado sin nadie.
SE_FUE = "left_the_company"
DE_BAJA = "on_leave"


@dataclass(frozen=True)
class SinCubrir:
    """Un turno cuyo titular no lo va a trabajar."""

    shift: Shift
    reason: str
    detail: str

    def as_dict(self) -> dict:
        return {
            "shift_id": self.shift.id,
            "day": self.shift.day.isoformat(),
            "employee_id": str(self.shift.employee_id),
            "employee_label": self.shift.employee.get_full_name() or self.shift.employee.email,
            "starts_at": self.shift.starts_at.time().isoformat(timespec="minutes"),
            "ends_at": self.shift.ends_at.time().isoformat(timespec="minutes"),
            "minutes": self.shift.minutes,
            "reason": self.reason,
            "detail": str(self.detail),
        }


@dataclass
class Candidato:
    """Alguien que podría coger ese turno, y a qué precio."""

    employee: object
    viable: bool
    blockers: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "employee_id": str(self.employee.id),
            "label": self.employee.get_full_name() or self.employee.email,
            "viable": self.viable,
            "blockers": [str(x) for x in self.blockers],
            "warnings": [str(x) for x in self.warnings],
        }


def _ausencias_que_paran_el_dia(company, first: date, last: date) -> dict:
    """Por persona, los días que tiene tapados de punta a punta.

    Solo las que paran el día entero. Una ausencia de parte del día y un ERTE de
    reducción son gente que **sí** tiene que estar en el cuadrante, y contarlas
    aquí llenaría el panel de huecos que no lo son ---el mismo error que ya
    documenta `_check_leave_clashes`, donde una persona al 40 % generaba
    veintiún avisos falsos en un mes---.
    """
    por_persona: dict = {}
    ausencias = (
        Absence.objects.filter(
            status=AbsenceStatus.APPROVED, start_date__lte=last, end_date__gte=first
        )
        .filter(STOPS_THE_WHOLE_DAY)
        .select_related("employee")
    )
    for ausencia in ausencias:
        dia = max(ausencia.start_date, first)
        tope = min(ausencia.end_date, last)
        while dia <= tope:
            por_persona.setdefault(ausencia.employee_id, {})[dia] = ausencia
            dia += timedelta(days=1)
    return por_persona


def uncovered(*, company, first: date, last: date) -> list[SinCubrir]:
    """Los turnos de ese tramo que nadie va a trabajar.

    Dos motivos, y se distinguen porque no se resuelven igual: quien dejó la
    empresa no vuelve y su turno hay que reasignarlo; quien está de baja vuelve,
    y a veces lo que se decide es no cubrirlo.
    """
    turnos = (
        Shift.objects.filter(day__gte=first, day__lte=last)
        .select_related("employee", "employee__workplace")
        .order_by("day")
    )
    de_baja = _ausencias_que_paran_el_dia(company, first, last)

    fuera = []
    for shift in turnos:
        quien = shift.employee

        if not quien.is_engaged_on(shift.day) or not quien.is_active:
            fuera.append(
                SinCubrir(
                    shift=shift,
                    reason=SE_FUE,
                    detail=_("Their contract does not cover this day."),
                )
            )
            continue

        ausencia = de_baja.get(shift.employee_id, {}).get(shift.day)
        if ausencia is not None:
            fuera.append(
                SinCubrir(
                    shift=shift,
                    reason=DE_BAJA,
                    detail=_("Approved %(kind)s.") % {"kind": ausencia.get_absence_type_display()},
                )
            )
    return fuera


def _minutos_de_la_semana(employee_id, dia: date, turnos_por_persona: dict) -> int:
    lunes = dia - timedelta(days=dia.weekday())
    domingo = lunes + timedelta(days=6)
    return sum(
        s.minutes
        for s in turnos_por_persona.get(employee_id, [])
        if lunes <= s.day <= domingo
    )


def who_can_cover(*, shift: Shift, company, rules=None) -> list[Candidato]:
    """Quién puede coger ese turno, y qué le cuesta.

    Ordenado con los viables delante y, dentro de esos, con quien tenga más
    holgura de horas primero: es el orden en que se decide de verdad.
    """
    from apps.tenants.rules import WorkingTimeRules
    from apps.users.models import HoursPeriod, User

    if rules is None:
        rules = WorkingTimeRules.for_company(company)

    lunes = shift.day - timedelta(days=shift.day.weekday())
    domingo = lunes + timedelta(days=6)

    gente = list(User.objects.filter(is_active=True).select_related("workplace"))

    # Los turnos de esa semana de todo el mundo, de una vez: quien mira esto
    # está mirando a la plantilla entera y una consulta por cabeza convierte una
    # pantalla en una espera.
    turnos_por_persona: dict = {}
    for otro in Shift.objects.filter(day__gte=lunes - timedelta(days=1), day__lte=domingo + timedelta(days=1)):
        turnos_por_persona.setdefault(otro.employee_id, []).append(otro)

    de_baja = _ausencias_que_paran_el_dia(company, shift.day, shift.day)
    descanso = timedelta(hours=rules.daily_rest_hours)

    candidatos = []
    for quien in gente:
        if quien.id == shift.employee_id:
            continue

        bloqueos, avisos = [], []

        if not quien.is_engaged_on(shift.day):
            bloqueos.append(_("Their contract does not cover this day."))
        if de_baja.get(quien.id, {}).get(shift.day) is not None:
            bloqueos.append(_("On approved leave that day."))

        suyos = turnos_por_persona.get(quien.id, [])
        if any(s.day == shift.day for s in suyos):
            bloqueos.append(_("Already rostered that day."))

        # Las doce horas del art. 34.3, por los dos lados: el turno de antes
        # tiene que haber acabado hace doce horas y el de después no puede
        # empezar antes de doce.
        for otro in suyos:
            if otro.day == shift.day:
                continue
            if otro.ends_at <= shift.starts_at and shift.starts_at - otro.ends_at < descanso:
                avisos.append(
                    _("Only %(hours)s h since their previous shift.")
                    % {"hours": f"{(shift.starts_at - otro.ends_at).total_seconds() / 3600:.0f}"}
                )
            if otro.starts_at >= shift.ends_at and otro.starts_at - shift.ends_at < descanso:
                avisos.append(
                    _("Only %(hours)s h before their next shift.")
                    % {"hours": f"{(otro.starts_at - shift.ends_at).total_seconds() / 3600:.0f}"}
                )

        # Lo que ya lleva esa semana más lo que este turno añade. Aviso y no
        # veto: pasarse de lo contratado genera horas complementarias (art.
        # 12.5), que son legales y se registran aparte.
        #
        # Por `agreed_hours` y no por `contracted_hours`, que puede estar vacío
        # ---una jornada completa sin cifra escrita es la semana de la empresa---
        # y que además viene con su período. Solo se compara cuando ese período
        # **es** la semana: dividir 1700 horas al año entre 52 da un número que
        # nadie acordó y que ninguna semana tiene que cumplir, así que un aviso
        # sacado de ahí sería falso todas las semanas del año. Quien tenga la
        # jornada en cómputo anual sale sin aviso de horas, que es lo honesto.
        holgura = None
        acordadas = quien.agreed_hours(rules)
        if acordadas is not None and acordadas[1] == HoursPeriod.WEEK:
            ya = _minutos_de_la_semana(quien.id, shift.day, turnos_por_persona)
            holgura = acordadas[0] * 60 - ya - shift.minutes
            if holgura < 0:
                avisos.append(
                    _("Would put them %(hours)s h over their contract this week.")
                    % {"hours": f"{-holgura / 60:.1f}"}
                )

        candidatos.append(
            Candidato(
                employee=quien,
                viable=not bloqueos,
                blockers=bloqueos,
                warnings=avisos,
                # Se guarda para ordenar y no se sirve: es un número interno.
            )
        )
        candidatos[-1].holgura = holgura if holgura is not None else 0

    candidatos.sort(key=lambda c: (not c.viable, len(c.warnings), -(c.holgura or 0)))
    return candidatos
