"""Borrar de verdad a quien no dejó rastro.

Dar de baja no es borrar, y hace bien en no serlo: los fichajes de quien trabajó
aquí viven cuatro años (art. 34.9 ET) y su ficha tiene que seguir explicándolos.
Por eso `DELETE /api/employees/<id>/` desactiva en vez de borrar.

Pero eso deja un caso sin salida: **el alta equivocada**. El correo mal escrito, la
persona duplicada, la que se creó en la empresa que no era. Hoy solo se puede dar de
baja, y se queda en la lista para siempre ---en la base de demostración llegaron a
ser 946 de 969 personas---.

Así que se puede borrar, y solo cuando no queda nada que explicar. Lo que hay que
comprobar no es «no tiene fichajes»: son tres familias, y la tercera es la que no
se ve.

**Lo que la base ya protege** (`on_delete=PROTECT`): fichajes y correcciones. Sin
esto el borrado fallaría con un `ProtectedError` que no dice de quién ni cuántos.

**Lo que se iría en cascada** y es historial: ausencias, decisiones de horas extra,
resúmenes de nómina entregados con el recibo de salarios (art. 6.1) y vacaciones
recuperadas de una baja. Nada de eso lo tiene un alta equivocada, y si lo tiene es
que no lo es.

**Lo que decidió sobre otras personas**, que es lo que no se ve: si aprobó una
ausencia, resolvió una corrección, autorizó horas extra o generó un resumen,
borrarla deja esos registros **con «decidido por: nadie»**. Son `SET_NULL`, así que
no protestan: se vacían en silencio. El rastro de auditoría sí sobrevive ---guarda
`actor_label`, el nombre tal como se escribió--- pero una aprobación no tiene esa
copia, y el art. 4.b pide que un cambio en el registro lleve nombre y apellidos.

Lo que sí se lleva por delante, porque no explica nada de nadie: sus recordatorios
de fichaje, sus suscripciones de avisos y su pertenencia a departamentos.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Rastro:
    """Qué deja atrás una persona, agrupado por lo que impide borrarla."""

    #: `{qué: cuántos}`, solo lo que tiene algo.
    suyo: dict[str, int]
    decidido: dict[str, int]

    @property
    def hay(self) -> bool:
        return bool(self.suyo or self.decidido)


def rastro_de(persona) -> Rastro:
    """Todo lo que cuelga de esa persona, contado.

    Se cuenta con `objects_all_tenants` y filtrando por la persona: esto puede
    correr desde una acción de la API ---con empresa en contexto--- y también
    desde una comprobación suelta, y el filtro por `persona` ya acota tanto como
    el de empresa, porque una persona pertenece a una sola.
    """
    from apps.absences.models import Absence, RecoveredHoliday
    from apps.punches.corrections import PunchCorrection
    from apps.punches.models import OvertimeDecision, Punch
    from apps.reports.payroll import PayrollSummary
    from apps.shifts.models import Shift
    from apps.tenants.applications import Application
    from apps.tenants.rules import ComputationRuleChange

    def cuantos(modelo, **filtro) -> int:
        gestor = getattr(modelo, "objects_all_tenants", modelo.objects)
        return gestor.filter(**filtro).count()

    #: Lo que es suyo: su trabajo y lo que lo explica.
    suyo = {
        _("clock events"): cuantos(Punch, employee=persona),
        _("corrections"): cuantos(PunchCorrection, employee=persona)
        + cuantos(PunchCorrection, requested_by=persona),
        _("absences"): cuantos(Absence, employee=persona),
        _("overtime decisions"): cuantos(OvertimeDecision, employee=persona),
        _("payroll summaries"): cuantos(PayrollSummary, employee=persona),
        _("recovered holidays"): cuantos(RecoveredHoliday, employee=persona),
        # Un turno es lo que se esperaba de esa persona, y el cuadrante es contra
        # lo que se contrasta el registro. Un alta equivocada no tiene ninguno.
        _("rostered shifts"): cuantos(Shift, employee=persona),
    }

    #: Lo que decidió sobre otras personas. Estos son `SET_NULL`: borrarla no
    #: falla, **vacía**. Y una aprobación sin nombre no vale como aprobación.
    decidido = {
        _("leave they approved"): cuantos(Absence, approved_by=persona),
        _("leave they requested for somebody else"): cuantos(Absence, requested_by=persona),
        _("corrections they resolved"): cuantos(PunchCorrection, resolved_by=persona),
        _("overtime they decided"): cuantos(OvertimeDecision, decided_by=persona),
        _("payroll summaries they generated"): cuantos(PayrollSummary, generated_by=persona),
        _("holiday recoveries they confirmed"): cuantos(RecoveredHoliday, confirmed_by=persona),
        _("clock events they recorded for others"): cuantos(Punch, recorded_by=persona),
        _("changes to how time is counted"): cuantos(ComputationRuleChange, recorded_by=persona),
        _("application credentials they created"): cuantos(Application, created_by=persona),
    }

    return Rastro(
        suyo={k: v for k, v in suyo.items() if v},
        decidido={k: v for k, v in decidido.items() if v},
    )
