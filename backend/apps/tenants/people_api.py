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


class PersonInTheAnswerSerializer(serializers.Serializer):
    """Una persona, tal y como sale. Solo para que el esquema lo diga."""

    id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    employee_id = serializers.CharField()
    oidc_sub = serializers.CharField()
    is_active = serializers.BooleanField()
    department = serializers.CharField()


class PeoplePageSerializer(serializers.Serializer):
    """Una tanda de personas, y cómo pedir la siguiente.

    Declarado para el esquema, no para validar nada. Sin esto la respuesta
    figuraba como «un objeto cualquiera» y quien escribiera un conector tenía
    que leerse el código o adivinar --- y adivinando se pasa por alto
    `has_more`, que es justo lo que hace falta para no quedarse con media
    plantilla.
    """

    people = PersonInTheAnswerSerializer(many=True)
    count = serializers.IntegerField(help_text="Cuánta gente encaja con el filtro, en total.")
    has_more = serializers.BooleanField(help_text="Si falta gente por leer en otra tanda.")
    next_since = serializers.DateTimeField(
        allow_null=True,
        help_text=(
            "Con qué llamar otra vez: `?since=<esto>` trae la siguiente tanda. "
            "Codifica el `+` del huso como `%2B`, o llegará como un espacio."
        ),
    )


#: Cuánta gente devuelve una tanda de la lectura masiva.
#:
#: No es paginación al uso: el cursor es `updated_at`, que ya hacía falta para
#: la lectura incremental. Quinientas caben de sobra en una respuesta y llevan a
#: la siguiente tanda por el mismo camino.
PAGE = 500


@extend_schema(tags=["applications"])
class ApplicationPeopleView(APIView):
    """La lista de personas y el alta, con credencial de aplicación."""

    permission_classes = [HasApplicationScope]
    required_scope = ApplicationScope.READ_PEOPLE

    # El nombre de la operación se pone a mano porque el generador lo saca de
    # la ruta y aquí las dos lecturas dan el mismo: `/app/people/` y
    # `/app/people/{reference}/` se quedan las dos en «app_people_retrieve», y
    # la colisión la resuelve él poniendo un número al final. Un cliente
    # generado del esquema acaba con `app_people_retrieve` y
    # `app_people_retrieve_2`, y cuál es cuál depende del orden en que se
    # recorrieron las rutas: cambia solo el día que se añada otra.
    @extend_schema(
        operation_id="app_people_list",
        summary="List people",
        parameters=[
            OpenApiParameter("active", bool, description="Solo quien está de alta"),
            OpenApiParameter(
                "since",
                str,
                description=(
                    "Cambios desde esta fecha (ISO 8601). También es el cursor: "
                    "vuelve a llamar con el `next_since` de la respuesta anterior "
                    "mientras `has_more` sea cierto."
                ),
            ),
        ],
        responses={200: PeoplePageSerializer},
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

            # El `+` del huso se convierte en espacio al viajar en una URL si
            # el cliente no lo codifica, y entonces «…123456+00:00» llega como
            # «…123456 00:00» y no parsea. Se devuelve tal cual en `next_since`,
            # así que un conector que siga el cursor de la forma más obvia se
            # comía un 409 en la segunda vuelta --- y se quedaba con media
            # plantilla creyendo que la tenía entera.
            #
            # Se perdona en el servidor porque ese espacio no puede venir de
            # ningún otro sitio: una marca de tiempo no lleva espacios.
            moment = parse_datetime(since) or parse_datetime(since.replace(" ", "+"))
            if moment is None:
                raise BusinessRuleError(
                    code="bad_since", message=_("`since` must be an ISO 8601 timestamp.")
                )
            people = people.filter(updated_at__gte=moment)

        # Ordenado por `updated_at` porque ese es el cursor: el conector pide
        # la siguiente tanda con `?since=` igual a la última fecha que vio.
        people = people.order_by("updated_at")
        total = people.count()
        tanda = list(people[:PAGE])

        return Response(
            {
                "people": [_as_dict(person) for person in tanda],
                # Sin esto la respuesta mentía por omisión. Devolvía quinientas
                # y ni una palabra de que hubiera más: un conector de una
                # empresa de seiscientas daba la plantilla por leída y las otras
                # cien no existían para él --- ni sus fichajes, ni sus altas, ni
                # sus bajas. Un recorte callado en una integración es peor que
                # en una pantalla, porque no hay nadie mirando.
                "count": total,
                "has_more": total > len(tanda),
                # Con qué seguir. Va aquí y no en la documentación porque una
                # instrucción que hay que ir a buscar es una instrucción que no
                # se sigue.
                #
                # El corte es inclusivo (`>=`), así que la última persona de
                # esta tanda vuelve en la siguiente. Es a propósito: excluirla
                # se saltaría a quien comparta su marca de tiempo, y el empuje
                # es idempotente --- repetir una no cuesta nada, perder una sí.
                "next_since": tanda[-1].updated_at.isoformat() if tanda else None,
            }
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

    @extend_schema(
        operation_id="app_people_retrieve",
        summary="Read one person by external reference",
        responses={200: dict},
    )
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
