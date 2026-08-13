"""Las personas, para una aplicación que las gestiona en otro sitio.

La pieza que hacía falta para que otra herramienta ---Geosian, un ERP, lo que
sea--- pueda delegar el registro horario aquí. Los permisos `read:people` y
`write:people` estaban declarados desde el principio y **no tenían endpoint**,
así que la promesa de «servicio integrable» se quedaba en el fichaje delegado.

## El alta se empuja, no se sincroniza

Es la decisión que evita el problema clásico de las dos bases de datos. Aquí no
hay una tarea nocturna que compare y resuelva conflictos: cuando en la
aplicación de gestión se da de alta a alguien, ella llama y lo empuja. Un solo
sentido, y la aplicación de gestión manda en las personas.

Dos bases sincronizándose en ambos sentidos necesitan resolución de conflictos,
y en la práctica gana el último que escribió. Con un registro de jornada
detrás, «el último que escribió» puede ser quien borró a alguien que estaba
fichando.

## Idempotente por diseño

`PUT` sobre un identificador externo: si esa persona existe se actualiza, y si
no, se crea. Un conector reintenta ---porque la red se cae y porque el servidor
se despliega--- y reintentar no puede crear duplicados. Ese identificador es
único por empresa desde el 13/08/2026, que es lo que hace fiable la resolución.

## La baja desactiva, nunca borra

Los fichajes viven cuatro años y sobreviven a la persona que los hizo. Un
`DELETE` aquí desactiva: quien se fue deja de fichar y su registro sigue
entero, que es lo que pide el art. 34.9.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import HasApplicationScope
from apps.tenants.applications import ApplicationScope
from apps.users.models import Role, User


class PersonFromApplicationSerializer(serializers.Serializer):
    """Lo que una aplicación de gestión sabe de una persona.

    Deliberadamente corto. Todo lo que decide **cómo se mide** su jornada ---el
    régimen, las horas contratadas, la nocturnidad, el centro--- no está aquí: lo
    fija quien administra el tiempo de trabajo, no el sistema que lleva las
    altas. Si un conector pudiera cambiar la jornada contratada de alguien, la
    herramienta de gestión estaría decidiendo sobre el registro legal sin
    saberlo.
    """

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    #: El ancla. Único por empresa, y lo fija quien empuja.
    employee_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    oidc_sub = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


def _resolve(reference: str, company) -> User | None:
    """La persona a la que se refiere el identificador externo.

    Por orden de estabilidad, que es el mismo criterio que el fichaje delegado:
    primero el sujeto del proveedor de identidad, luego el número de empleado, y
    el correo el último ---es el que la gente cambia---.
    """
    reference = (reference or "").strip()
    if not reference:
        return None

    return User.objects.filter(
        Q(oidc_sub__iexact=reference)
        | Q(employee_id__iexact=reference)
        | Q(email__iexact=reference),
        tenant=company,
    ).first()


def _as_dict(person: User) -> dict:
    return {
        "id": str(person.id),
        "email": person.email,
        "first_name": person.first_name,
        "last_name": person.last_name,
        "employee_id": person.employee_id,
        "oidc_sub": person.oidc_sub,
        "is_active": person.is_active,
        "department": person.department.name if person.department_id else "",
    }


@extend_schema(tags=["applications"])
class ApplicationPeopleView(APIView):
    """La lista de personas y el alta, con credencial de aplicación."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_PEOPLE

    @extend_schema(
        summary="List people",
        parameters=[
            OpenApiParameter("active", bool, description="Solo quien está de alta"),
            OpenApiParameter("since", str, description="Cambios desde esta fecha (ISO 8601)"),
        ],
        responses={200: dict},
    )
    def get(self, request):
        company = request.user.application.tenant
        people = User.objects.filter(tenant=company)

        if request.query_params.get("active") in ("1", "true", "True"):
            people = people.filter(is_active=True)

        # Lectura incremental: un conector que ya trajo la plantilla entera solo
        # necesita lo que cambió. Sin esto, cada arranque se lleva mil filas.
        since = request.query_params.get("since")
        if since:
            from django.utils.dateparse import parse_datetime

            moment = parse_datetime(since)
            if moment is None:
                raise BusinessRuleError(
                    code="bad_since", message=_("`since` must be an ISO 8601 timestamp.")
                )
            people = people.filter(updated_at__gte=moment)

        return Response(
            {"people": [_as_dict(person) for person in people.order_by("updated_at")[:500]]}
        )


@extend_schema(tags=["applications"])
class ApplicationPersonView(APIView):
    """Una persona, identificada como la conoce la aplicación que la gestiona."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_PEOPLE

    def required_scope_for(self, request):
        # Leer y escribir no son el mismo permiso: una integración que solo
        # pinta la asistencia no tiene por qué poder dar de alta a nadie.
        return (
            ApplicationScope.WRITE_PEOPLE
            if request.method in ("PUT", "DELETE")
            else ApplicationScope.READ_PEOPLE
        )

    @extend_schema(summary="Read one person by external reference", responses={200: dict})
    def get(self, request, reference: str):
        company = request.user.application.tenant
        person = _resolve(reference, company)
        if person is None:
            raise BusinessRuleError(
                code="person_not_found", message=_("No person matches that reference.")
            )
        return Response(_as_dict(person))

    @extend_schema(
        summary="Create or update a person",
        description=(
            "Idempotent by design: a connector retries, and retrying must not create "
            "duplicates. Requires `write:people`."
        ),
        request=PersonFromApplicationSerializer,
        responses={200: dict, 201: dict},
    )
    def put(self, request, reference: str):
        company = request.user.application.tenant
        form = PersonFromApplicationSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        person = _resolve(reference, company)
        creado = person is None

        if creado:
            # Sin contraseña: entra por el proveedor de identidad, o pide un
            # enlace. Un conector no debería poder fijar la contraseña de nadie.
            person = User(tenant=company, role=Role.EMPLOYEE)
            person.set_unusable_password()

        antes = _as_dict(person) if not creado else {}

        person.email = data["email"].strip().lower()
        person.first_name = data["first_name"]
        person.last_name = data.get("last_name", "")
        if data.get("employee_id"):
            person.employee_id = data["employee_id"].strip()
        if data.get("oidc_sub"):
            person.oidc_sub = data["oidc_sub"].strip()
        # Reactivar es parte del empuje: alguien de temporada vuelve, y la
        # aplicación de gestión lo da de alta otra vez con el mismo número.
        person.is_active = True

        if data.get("department"):
            from apps.users.models import Department

            person.department, _ = Department.objects.get_or_create(
                tenant=company, name=data["department"].strip()
            )

        _refuse_collisions(person, company)
        person.save()

        record(
            action=AuditAction.PERSON_CREATED if creado else AuditAction.PERSON_UPDATED,
            actor=None,
            actor_label=f"aplicación · {request.user.application.name}",
            target=person,
            target_type="user",
            target_label=person.get_full_name() or person.email,
            changes={"before": antes, "after": _as_dict(person)},
            request=request,
        )
        return Response(
            _as_dict(person), status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK
        )

    @extend_schema(
        summary="Deactivate a person",
        description=(
            "Never deletes: clock events outlive the person who made them and are kept "
            "for four years. Requires `write:people`."
        ),
        responses={200: dict},
    )
    def delete(self, request, reference: str):
        company = request.user.application.tenant
        person = _resolve(reference, company)
        if person is None:
            raise BusinessRuleError(
                code="person_not_found", message=_("No person matches that reference.")
            )

        if person.is_active:
            person.is_active = False
            person.save(update_fields=["is_active", "updated_at"])
            record(
                action=AuditAction.PERSON_DEACTIVATED,
                actor=None,
                actor_label=f"aplicación · {request.user.application.name}",
                target=person,
                target_type="user",
                target_label=person.get_full_name() or person.email,
                request=request,
            )
        return Response(_as_dict(person))


def _refuse_collisions(person: User, company) -> None:
    """Que el empuje no pise a otra persona.

    Las dos restricciones existen en la base, pero un choque contra ellas sale
    como un 500 y un conector no puede reaccionar a eso. Aquí sale como un error
    con su código, que es lo que permite que el conector lo registre y siga.
    """
    otros = User.objects.filter(tenant=company).exclude(pk=person.pk)

    if otros.filter(email__iexact=person.email).exists():
        raise BusinessRuleError(
            code="email_taken",
            message=_("Somebody else in this company already uses that address."),
            details={"email": person.email},
        )
    if person.employee_id and otros.filter(employee_id__iexact=person.employee_id).exists():
        raise BusinessRuleError(
            code="staff_number_taken",
            message=_("Somebody else in this company already uses that staff number."),
            details={"employee_id": person.employee_id},
        )
