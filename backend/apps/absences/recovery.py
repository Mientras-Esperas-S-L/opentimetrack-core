"""La baja que se come unas vacaciones, y las vacaciones que no se pierden.

Art. 38.3 ET. Si el periodo de vacaciones coincide con una incapacidad
temporal, esos días **no se han disfrutado** y se disfrutan después. El saldo
los daba por gastados hasta el 13/08/2026, que es quitarle días a alguien justo
cuando está de baja.

La ley distingue dos regímenes y se confunden con facilidad, porque el párrafo
largo y detallado es justo el que **no** caduca:

- **Sin plazo** (párrafo 2.º): incapacidad derivada del embarazo, el parto o la
  lactancia natural, y las suspensiones de los arts. 48.4, 48.5 y 48.7. Se
  disfrutan al terminar la suspensión, «aunque haya terminado el año natural a
  que correspondan».
- **Dieciocho meses** (párrafo 3.º): el resto de contingencias. Hasta dieciocho
  meses desde el final del año en que se originaron; pasado el plazo, se
  pierden.

Da igual que la baja empezara antes de las vacaciones o durante ellas: el
precepto solo dice «coincida». Lo segundo fue discutido en España ---la STS de
2005 decía lo contrario--- y quedó zanjado por el TJUE en el asunto ANGED
(C-78/11) y por la STS del Pleno de 3 de octubre de 2012.

Y solo se recupera **lo que coincide**, no el periodo entero: la propia ley dice
«total o parcialmente».

Qué régimen aplica cada permiso no se decide aquí: lo dice el catálogo de la
empresa (`LeaveType.vacation_recovery`), que lo copia del marco legal del país.
En este módulo no hay ni una lista de códigos, porque un país con otras reglas
trae las suyas y esto no debería cambiar.
"""

from __future__ import annotations

from datetime import date

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.absences.models import Absence, AbsenceStatus, AbsenceType, RecoveredHoliday
from apps.common.exceptions import BusinessRuleError
from apps.common.four_eyes import refuse_self_decision


def detect_recoveries(*, absence, company) -> list[RecoveredHoliday]:
    """Anota los días de vacaciones que esta baja pisa. No devuelve nada al saldo.

    Se llama al aprobar o registrar una baja. Deja las anotaciones en
    `PENDING`: el derecho se ve desde el primer momento ---en la cola de
    decisiones y en la pantalla de la persona--- y quien lo confirma es un
    responsable, porque devolver días solo es de las cosas que después nadie
    sabe explicar.

    Idempotente: correr esto dos veces sobre la misma baja no duplica nada.
    """
    kind = absence.leave_type
    regime = getattr(kind, "vacation_recovery", "") if kind else ""
    if not regime or absence.status != AbsenceStatus.APPROVED:
        return []

    pisadas = Absence.objects.filter(
        employee=absence.employee,
        absence_type=AbsenceType.VACATION,
        status=AbsenceStatus.APPROVED,
        start_date__lte=absence.end_date,
        end_date__gte=absence.start_date,
        # Solo las de días completos: una ausencia por horas no es un periodo
        # de vacaciones del calendario, que es de lo que habla el art. 38.3.
        start_time__isnull=True,
    )

    from apps.absences.services import _days_within

    anotadas = []
    for vacaciones in pisadas:
        first = max(vacaciones.start_date, absence.start_date)
        last = min(vacaciones.end_date, absence.end_date)
        if first > last:
            continue

        unit = company.leave_days_are_working_days
        solapado = Absence(
            employee=absence.employee, start_date=first, end_date=last, start_time=None
        )
        days = _days_within(solapado, first, last, working_days=unit)
        if days <= 0:
            # El solape cae entero en días que esa persona no iba a trabajar.
            # No hay nada que devolver: no se gastó nada.
            continue

        recovery, _created = RecoveredHoliday.objects.get_or_create(
            tenant=company,
            holiday=vacaciones,
            sick_leave=absence,
            first_day=first,
            defaults={
                "employee": absence.employee,
                "last_day": last,
                "days": days,
                "working_days": unit,
                "regime": regime,
                "expires_on": _deadline(regime, vacaciones),
            },
        )
        anotadas.append(recovery)

    return anotadas


def _deadline(regime: str, holiday) -> date | None:
    """Hasta cuándo se pueden disfrutar.

    En el régimen sin plazo devuelve `None`, y eso no es «todavía no se sabe»:
    es que no hay fecha. La ley dice expresamente «aunque haya terminado el año
    natural a que correspondan».

    En el otro, dieciocho meses **desde el final del año en que se originaron**,
    que no es lo mismo que dieciocho meses desde la baja: el año de referencia
    es el de las vacaciones.
    """
    if regime != RecoveredHoliday.Regime.EIGHTEEN_MONTHS:
        return None

    fin_de_año = date(holiday.start_date.year, 12, 31)
    mes = fin_de_año.month + 18
    año = fin_de_año.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return date(año, mes, min(fin_de_año.day, _last_day(año, mes)))


def _last_day(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timezone.timedelta(days=1)).day


def pending_recoveries(*, company, scope=None) -> list[dict]:
    """Lo detectado y todavía sin confirmar, para la cola de decisiones."""
    rows = RecoveredHoliday.objects.filter(status=RecoveredHoliday.Status.PENDING).select_related(
        "employee", "sick_leave", "sick_leave__leave_type", "holiday"
    )
    if scope is not None:
        rows = rows.filter(employee__in=scope)

    return [
        {
            "id": str(row.id),
            "employee": str(row.employee_id),
            "employee_name": row.employee.get_full_name(),
            "first_day": row.first_day.isoformat(),
            "last_day": row.last_day.isoformat(),
            "days": row.days,
            "working_days": row.working_days,
            "regime": row.regime,
            "expires_on": row.expires_on.isoformat() if row.expires_on else None,
            "because_of": (
                row.sick_leave.leave_type.name if row.sick_leave.leave_type else str(row.sick_leave)
            ),
        }
        for row in rows.order_by("employee_id", "first_day")
    ]


def confirm_recovery(
    *, recovery, company, decided_by, accept: bool, note: str = ""
) -> RecoveredHoliday:
    """Confirma que esos días vuelven al saldo, o descarta la anotación.

    Descartar es una decisión legítima y hay casos ---el solape lo detectó una
    baja que luego se anuló, o esas vacaciones no llegaron a disfrutarse por
    otro motivo--- pero es una decisión sobre el derecho de otra persona, así
    que pasa por los cuatro ojos como las demás.
    """
    if recovery.status != RecoveredHoliday.Status.PENDING:
        raise BusinessRuleError(
            code="already_decided",
            message=_("That recovery has already been decided."),
        )

    alone = refuse_self_decision(
        subject=recovery.employee,
        decider=decided_by,
        company=company,
        what=_("a holiday recovery"),
    )

    recovery.status = (
        RecoveredHoliday.Status.CONFIRMED if accept else RecoveredHoliday.Status.DISMISSED
    )
    recovery.confirmed_by = decided_by
    recovery.confirmed_at = timezone.now()
    recovery.note = note
    recovery.save(update_fields=["status", "confirmed_by", "confirmed_at", "note", "updated_at"])
    del alone  # la marca de «en solitario» la lleva la auditoría, como en las demás
    return recovery


def recovered_days(*, employee, company, start: date, end: date) -> int:
    """Días confirmados que hay que devolver al saldo de ese periodo.

    Se cuentan contra el periodo de **las vacaciones pisadas**, no contra aquel
    en que se disfruten después: son días de ese año, y colocarlos en el
    siguiente descuadraría los dos.
    """
    rows = RecoveredHoliday.objects.filter(
        employee=employee,
        status=RecoveredHoliday.Status.CONFIRMED,
        first_day__lte=end,
        last_day__gte=start,
    )
    return sum(row.days for row in rows)
