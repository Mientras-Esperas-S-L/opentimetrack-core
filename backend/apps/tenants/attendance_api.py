"""La asistencia, para la aplicación que la va a pintar en su pantalla.

`read:attendance` estaba declarado y no tenía endpoint, así que una herramienta
podía fichar en nombre de alguien y luego no podía enseñar el resultado. Para
Geosian esto es lo que sustituye a sus widgets de asistencia: la misma
información, pero desde el sistema que sabe defenderla ante una inspección.

Solo lectura, y a propósito. Todo lo que **cambia** el registro pasa por su
puerta: fichar por el fichaje delegado, corregir por el flujo del art. 4.b. Una
aplicación integrada no puede escribir en el registro por un atajo, porque
entonces las garantías serían opcionales.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import HasApplicationScope
from apps.punches.delegated import resolve_employee
from apps.punches.services import build_day_status
from apps.tenants.applications import ApplicationScope


@extend_schema(tags=["applications"])
class ApplicationAttendanceView(APIView):
    """El día en curso de una persona, o el de toda la plantilla."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_ATTENDANCE

    @extend_schema(
        summary="Today's attendance",
        description=(
            "Who is working right now and how long each person has worked today. "
            "With `employee_ref`, just that person. Requires `read:attendance`."
        ),
        parameters=[OpenApiParameter("employee_ref", str, description="Referencia externa")],
        responses={200: dict},
    )
    def get(self, request):
        company = request.user.application.tenant
        wanted = request.query_params.get("employee_ref")

        if wanted:
            person = resolve_employee(wanted, company)
            if person is None:
                raise BusinessRuleError(
                    code="employee_not_found",
                    message=_("No active person matches that reference."),
                    details={"employee_ref": wanted},
                )
            people = [person]
        else:
            from apps.users.models import User

            people = list(User.objects.filter(tenant=company, is_active=True))

        return Response(
            {
                "time_zone": company.time_zone,
                # De la zona de la empresa, no del reloj del contenedor.
                #
                # `date.today()` da la fecha UTC del servidor, que entre
                # medianoche y las dos de la madrugada (en verano) no es la de
                # nadie en España: a las 00:30 de Madrid decía que era ayer
                # mientras los tramos ya eran de hoy. La aplicación que pinta
                # esto ponía la fecha de un día y los fichajes de otro, y quien
                # más lo sufre es el turno de noche, que es justo el que cruza
                # esa frontera todos los días.
                #
                # `apps/common/clock.py` existe por esto y avisa de que ya se
                # había colado cuatro veces. Esta era la quinta, y el único
                # `date.today()` que quedaba en todo el código.
                "day": local_today(company).isoformat(),
                "people": [_day_of(person, company) for person in people],
            }
        )


def _day_of(person, company) -> dict:
    estado = build_day_status(person, company)
    return {
        "employee": str(person.id),
        "employee_id": person.employee_id,
        "name": person.get_full_name(),
        "state": estado.state,
        "worked_seconds": estado.worked_seconds,
        # Los tramos, sin la metadata de captura: la IP y el dispositivo son
        # datos de seguridad de esta empresa y no salen hacia otra aplicación
        # por el hecho de que pueda leer la asistencia.
        "segments": [
            {"in": s.start.isoformat(), "out": s.end.isoformat() if s.end else None}
            for s in estado.segments
        ],
    }
