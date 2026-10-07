"""Dar de baja a alguien: una sola forma, la llame quien la llame.

Había dos. La de la pantalla protegía al último administrador, ponía la fecha de
fin de contrato y contaba los turnos que se quedaban colgando; la de la API de
aplicaciones solo apagaba `is_active`. Un conector que daba de baja al único
administrador dejaba la empresa sin nadie que pudiera administrarla, y la baja
sin fecha no la veía nada de lo que razona por fechas ---la revisión del
cuadrante, las ausencias---.

Aquí vive lo que tiene que pasar siempre. Lo que depende de quién pide la baja
---que nadie se dé de baja a sí mismo desde su sesión--- se queda en quien la pide.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.users.models import Role, User
from apps.users.passwords import revoke_sessions


def refuse_if_it_leaves_no_admin(person, *, new_role=None, deactivating=False) -> None:
    """Stops a company ending up with nobody able to administer it.

    A company in that state cannot add people, resolve requests, or undo
    whatever caused it: the only way out is somebody with database access.

    From the screen the realistic way in is **demotion** ---the sole administrator
    changing their own role to employee, one dropdown away---, because only an
    administrator can deactivate and their own existence guarantees another one
    remains. From an application it is deactivation: the connector has no
    administrator of its own standing behind it.

    Counted within the person's company, and **without the support account**: it
    is an administrator on paper, but it belongs to the installation and is only
    opened from its console. Counting it would let a company keep "an
    administrator" nobody inside can use.
    """
    stays_admin = not deactivating and (new_role or person.role) == Role.ADMIN
    if stays_admin:
        return

    others = (
        User.objects.filter(tenant_id=person.tenant_id, role=Role.ADMIN, is_active=True)
        .exclude(is_support=True)
        .exclude(pk=person.pk)
    )
    if person.role == Role.ADMIN and person.is_active and not others.exists():
        raise BusinessRuleError(
            code="last_administrator",
            message=_(
                "This is the only active administrator. Appoint another one first, "
                "or the company is left with nobody able to manage it."
            ),
        )


def deactivate(person, *, actor, actor_label: str = "", company=None) -> int:
    """Da de baja a `person` y devuelve cuántos turnos le quedaban por delante.

    Desactiva, nunca borra: sus fichajes viven cuatro años y sobreviven a quien
    los hizo. `actor` es quien lo pide; con una aplicación no hay persona detrás,
    y entonces van `actor_label` y `company`, igual que en `record()`.
    """
    refuse_if_it_leaves_no_admin(person, deactivating=True)

    # Una baja sin fecha no se puede responder, y eso es justo lo que faltaba.
    # `is_active` es un sí o un no sin día, así que nada de lo que razona por
    # fechas ---la revisión del cuadrante, las ausencias--- podía enterarse:
    # quien se iba seguía con sus turnos del mes que viene asignados, y como el
    # cuadrante es contra lo que se comparan los fichajes, iba a salir como
    # ausencia sin justificar cada día.
    #
    # La fecha es hoy, en la zona de la empresa. Se pisa un `contract_end`
    # posterior porque irse antes de que venza el contrato es lo corriente ---una
    # baja voluntaria, un despido--- y lo que la fecha tiene que decir es el
    # último día que la relación cubre. Uno anterior no se toca: ese contrato ya
    # había terminado y la baja solo lo formaliza en el sistema.
    campos = ["is_active"]
    hoy = local_today(person)
    if person.contract_end is None or person.contract_end > hoy:
        person.contract_end = hoy
        campos.append("contract_end")

    person.is_active = False
    person.save(update_fields=campos)

    # Y se cierran sus sesiones. El acceso deja de valer al instante ---la
    # autenticación mira `is_active`--- pero el refresco vivía siete días y
    # rotando, así que el móvil de quien acaba de irse seguía teniendo una
    # credencial viva. Y la baja es reversible: sin esto, al reincorporar a la
    # persona su sesión de antes volvía a funcionar sin contraseña.
    revoke_sessions(person)

    # Los turnos que le quedaban no se borran: dar de baja no borra nada. Se
    # cuentan para decirlo, y a partir de ahora la revisión del cuadrante los
    # marca sola, porque ya hay una fecha contra la que compararlos.
    from apps.shifts.models import Shift

    pendientes = Shift.objects.filter(employee=person, day__gt=hoy).count()

    record(
        action=AuditAction.PERSON_DEACTIVATED,
        actor=actor,
        actor_label=actor_label,
        company=company,
        target=person,
        target_type="user",
        target_label=person.get_full_name() or person.email,
        changes={"contract_end": hoy.isoformat(), "future_shifts": pendientes},
        note=(
            str(_("Left on %(day)s. %(count)s shift(s) still rostered after that."))
            % {"day": hoy.isoformat(), "count": pendientes}
            if pendientes
            else str(_("Left on %(day)s.")) % {"day": hoy.isoformat()}
        ),
    )
    return pendientes
