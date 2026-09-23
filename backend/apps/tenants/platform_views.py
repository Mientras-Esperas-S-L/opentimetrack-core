"""Administrar la instalación: dar de alta empresas y su proveedor de identidad.

Hasta ahora esto solo se podía por consola, con `manage.py shell`. Un producto que
se puede autoalojar y no tiene forma de crear su segunda empresa sin abrir un shell
está incompleto: no es una comodidad de servicio gestionado, es lo mínimo para que
la instalación se pueda operar. Por eso vive aquí y no en la consola del Cloud, que
es la que lleva analítica, facturación y marca blanca.

**Quién entra.** El superusuario de plataforma, que es el que **no pertenece a
ninguna empresa** ---el campo `tenant` de `User` es nulo justo para esto---. Un
administrador de una empresa no puede, por mucho `is_superuser` que tuviera: si
bastara con esa bandera, quien administra una empresa podría crear otras y verlas.

**Qué NO hace.** Ni entra en los datos de una empresa ni los enseña: de cada una se
ve su ficha, cuánta gente tiene y si su identidad está configurada. El aislamiento
sigue siendo el de siempre, y esta pantalla no es una puerta lateral.
"""

from __future__ import annotations

import logging
import secrets
import smtplib
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction, PlatformAction, PlatformAuditEntry
from apps.audit.services import record, record_platform
from apps.common.models import set_current_tenant
from apps.tenants.application_views import (
    ApplicationSerializer,
    CredentialSerializer,
    IssueSerializer,
)
from apps.tenants.identity import SsoDomain, SsoProvider
from apps.tenants.models import (
    Application,
    ApplicationCredential,
    ApplicationScope,
    Tenant,
    validate_time_zone,
)
from apps.users.models import Role, User
from apps.users.passwords import send_account_email
from apps.users.serializers import SignUpSerializer

log = logging.getLogger(__name__)

#: Lo que usa una integración completa ---altas, fichaje en nombre de otros,
#: ausencias, cuadrante, calendario y disponibilidad---, para marcarlo de una vez.
#:
#: Es una sugerencia de la pantalla, no una regla del servidor: la lista viaja en
#: la petición como cualquier otra, y quien da de alta puede quitar lo que no
#: quiera conceder. Existe porque marcar diez casillas a mano es donde se olvida
#: una y el alta parece buena hasta que, semanas después, algo contesta 403.
FULL_INTEGRATION_SCOPES = [
    ApplicationScope.READ_PEOPLE,
    ApplicationScope.WRITE_PEOPLE,
    ApplicationScope.PUNCH_SELF,
    ApplicationScope.PUNCH_DELEGATED,
    ApplicationScope.READ_ATTENDANCE,
    ApplicationScope.READ_ABSENCES,
    ApplicationScope.WRITE_ABSENCES,
    ApplicationScope.READ_ROSTER,
    ApplicationScope.READ_CALENDAR,
    ApplicationScope.READ_AVAILABILITY,
]


class IsPlatformSuperuser(BasePermission):
    """Superusuario **sin empresa**: el que administra la instalación, no una empresa."""

    message = _("Only a platform superuser can administer the installation.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser and user.tenant_id is None)


#: Lo que le falta a una empresa para estar enchufada, en el orden en que se hace.
#:
#: Se calcula **aquí y no en la pantalla** porque es una regla del producto, no una
#: decoración: el asistente de alta necesita la misma respuesta, y dos sitios que
#: contestan «¿está lista?» acaban contestando cosas distintas.
#:
#: Los códigos viajan sin traducir a propósito: el texto lo pone quien pinta, con su
#: catálogo, que es donde se corrige un idioma sin tocar el servidor.
FALTA_IDENTIDAD = "identity"
FALTA_APLICACION = "application"
FALTA_GENTE = "people"


def _le_falta(company: Tenant, *, personas: int, aplicaciones: int, proveedor) -> list[str]:
    huecos = []
    if proveedor is None or not proveedor.is_active:
        huecos.append(FALTA_IDENTIDAD)
    if aplicaciones == 0:
        huecos.append(FALTA_APLICACION)
    # Una sola persona es la que creó el alta: la empresa existe y no hay nadie
    # dentro. No es un error ---puede estar recién dada de alta--- pero sí es lo
    # siguiente que hay que hacer, y sin decirlo la lista no lo distingue de una
    # empresa con su plantilla enlazada.
    if personas <= 1:
        huecos.append(FALTA_GENTE)
    return huecos


def _callado(desde: date | None, hoy: date) -> bool:
    """Si ha pasado al menos un día laborable entero sin nada desde `desde`.

    De lunes a viernes, sin festivos: esto es un aviso para mirar, no un cómputo de
    jornada, y un festivo de más solo da un aviso de más. El viernes y el lunes
    siguiente no avisan; el jueves y el lunes, sí.
    """
    if desde is None:
        return False
    dia = desde + timedelta(days=1)
    while dia < hoy:
        if dia.weekday() < 5:
            return True
        dia += timedelta(days=1)
    return False


def _sin_nada() -> dict:
    return {
        "active_people": 0,
        "last_punch": None,
        "last_identity_sign_in": None,
        "identity_people": 0,
        "apps": [],
    }


def _estado_de_todas() -> dict:
    """Cómo está cada empresa, **en cuatro consultas para todas**, no cuatro por empresa.

    Solo fechas y recuentos. Del último fichaje se da **el día**, sin la hora y sin
    quién: la instalación no ve el registro de jornada de nadie, y en una empresa de
    una sola persona la hora ya sería su dato.

    Con `objects_all_tenants`: el gestor normal no devuelve nada sin inquilino, y
    esta lista saldría con todo a cero sin decir por qué.
    """
    from apps.punches.models import Punch

    estado: dict = {}

    def de(tenant_id):
        return estado.setdefault(tenant_id, _sin_nada())

    for fila in (
        User.objects.filter(tenant__isnull=False, is_active=True)
        .values("tenant_id")
        .annotate(n=Count("id"))
    ):
        de(fila["tenant_id"])["active_people"] = fila["n"]

    for fila in Punch.objects_all_tenants.values("tenant_id").annotate(ultimo=Max("timestamp")):
        de(fila["tenant_id"])["last_punch"] = fila["ultimo"]

    # Quién ha entrado alguna vez con la identidad se sabe siempre: el sujeto se
    # ancla en la primera entrada. **Cuándo**, solo desde el 23/09/2026, que es
    # cuando se empezó a anotar `last_login`. Por eso van los dos: sin el recuento,
    # una identidad en uso desde hace días decía «nadie ha entrado».
    for fila in (
        User.objects.filter(tenant__isnull=False)
        .exclude(Q(oidc_sub="") | Q(oidc_sub__isnull=True))
        .values("tenant_id")
        .annotate(ultimo=Max("last_login"), n=Count("id"))
    ):
        de(fila["tenant_id"])["last_identity_sign_in"] = fila["ultimo"]
        de(fila["tenant_id"])["identity_people"] = fila["n"]

    for app in (
        Application.objects_all_tenants.filter(is_active=True)
        .annotate(ultimo=Max("credentials__last_used_at"))
        .order_by("name")
    ):
        de(app.tenant_id)["apps"].append({"name": app.name, "last_used": app.ultimo})

    return estado


def _estado(company: Tenant, crudo: dict | None) -> dict:
    """El estado de una empresa, en su zona horaria y con lo callado marcado."""
    crudo = crudo or _sin_nada()
    try:
        zona = ZoneInfo(company.time_zone)
    except Exception:
        zona = ZoneInfo("UTC")
    hoy = timezone.now().astimezone(zona).date()

    def dia(instante):
        return instante.astimezone(zona).date() if instante else None

    fichaje = dia(crudo["last_punch"])
    identidad = dia(crudo["last_identity_sign_in"])
    aplicaciones = [
        {
            "name": a["name"],
            "last_used": dia(a["last_used"]).isoformat() if a["last_used"] else None,
            "quiet": _callado(dia(a["last_used"]), hoy),
        }
        for a in crudo["apps"]
    ]
    return {
        "active_people": crudo["active_people"],
        "last_punch_day": fichaje.isoformat() if fichaje else None,
        "punches_quiet": _callado(fichaje, hoy),
        "last_identity_sign_in_day": identidad.isoformat() if identidad else None,
        "identity_people": crudo["identity_people"],
        "applications_detail": aplicaciones,
    }


def _empresa(company: Tenant, *, personas: int | None = None) -> dict:
    proveedor = SsoProvider.objects_all_tenants.filter(tenant=company).first()
    cuanta_gente = personas if personas is not None else User.objects.filter(tenant=company).count()
    cuantas_apps = Application.objects_all_tenants.filter(tenant=company, is_active=True).count()
    return {
        "id": str(company.id),
        "name": company.name,
        "tax_id": company.tax_id,
        "country": company.country,
        "time_zone": company.time_zone,
        "language": company.language,
        "is_active": company.is_active,
        "people": cuanta_gente,
        # Cuántas aplicaciones puede usar hoy. Sin esto, la lista no distingue una
        # empresa lista para integrarse de otra a la que le falta la credencial, que
        # es el hueco con el que la gente se queda encallada.
        "applications": cuantas_apps,
        "missing": _le_falta(
            company, personas=cuanta_gente, aplicaciones=cuantas_apps, proveedor=proveedor
        ),
        "identity": None
        if proveedor is None
        else {
            "name": proveedor.name,
            "slug": proveedor.slug,
            "issuer": proveedor.issuer,
            "jwks_uri": proveedor.jwks_uri,
            "client_id": proveedor.client_id,
            # El secreto no sale nunca: entra y se queda.
            "has_secret": bool(proveedor.client_secret),
            "may_act_for_people": proveedor.may_act_for_people,
            "is_active": proveedor.is_active,
            "domains": sorted(d.domain for d in proveedor.domains.all()),
        },
    }


class NewCompanySerializer(serializers.Serializer):
    """Lo que hace falta para una empresa nueva y quien la va a administrar."""

    company_name = serializers.CharField(max_length=255)
    tax_id = serializers.CharField(max_length=32)
    country = serializers.CharField(max_length=2, default="ES")
    time_zone = serializers.CharField(max_length=64, required=False, allow_blank=True)

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    #: Si se deja, se genera una y se enseña una sola vez.
    password = serializers.CharField(required=False, allow_blank=True, min_length=12)


@extend_schema(tags=["platform"])
class CompaniesView(APIView):
    """Las empresas de esta instalación, y el alta de una nueva."""

    permission_classes = [IsPlatformSuperuser]

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        empresas = Tenant.objects.all().annotate(cuantos=Count("users")).order_by("name")
        estado = _estado_de_todas()
        return Response(
            {
                "companies": [
                    {**_empresa(e, personas=e.cuantos), "status": _estado(e, estado.get(e.id))}
                    for e in empresas
                ]
            }
        )

    @extend_schema(request=NewCompanySerializer, responses={201: dict})
    @transaction.atomic
    def post(self, request):
        datos = NewCompanySerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        valores = dict(datos.validated_data)

        # Generada aquí y enseñada una sola vez, como la credencial de aplicación:
        # así el alta no depende de que el correo salga, que es lo que la dejaría a
        # medias sin que nadie se entere.
        clave = valores.pop("password", "") or f"Ott-{secrets.token_urlsafe(12)}"

        alta = SignUpSerializer(data={**valores, "password": clave})
        alta.is_valid(raise_exception=True)
        creado = alta.save()
        company, admin = creado["company"], creado["user"]
        set_current_tenant(company.id)
        record_platform(
            action=PlatformAction.COMPANY_CREATED,
            actor=request.user,
            company=company,
            target=company,
            target_label=company.name,
            changes={"tax_id": company.tax_id, "administrator": admin.email},
        )

        return Response(
            {**_empresa(company), "administrator": {"email": admin.email, "password": clave}},
            status=status.HTTP_201_CREATED,
        )


class IdentitySerializer(serializers.Serializer):
    """El proveedor con el que entra la gente de esa empresa."""

    name = serializers.CharField(max_length=120)
    issuer = serializers.CharField(max_length=255)
    slug = serializers.CharField(max_length=60, required=False, allow_blank=True)
    jwks_uri = serializers.CharField(max_length=500, required=False, allow_blank=True)
    client_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    #: Entra y no vuelve a salir. En blanco al editar significa «deja el que hay».
    client_secret = serializers.CharField(required=False, allow_blank=True)
    may_act_for_people = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    #: Con `allow_blank`: una caja de texto manda lo que el dedo deje ---un hueco,
    #: una línea vacía--- y eso no es un error del que avisar, es algo que se tira.
    domains = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=True), required=False
    )


@extend_schema(tags=["platform"])
class CompanyIdentityView(APIView):
    """El proveedor de identidad de una empresa: ponerlo, cambiarlo o quitarlo.

    Uno por empresa, que es el caso real: la empresa entra con su sistema o no entra
    con ninguno. Si algún día hace falta más de uno, esto se convierte en una lista;
    hoy sería una pantalla más complicada para un caso que no existe.
    """

    permission_classes = [IsPlatformSuperuser]

    def _company(self, company_id):
        return Tenant.objects.filter(pk=company_id).first()

    @extend_schema(request=IdentitySerializer, responses={200: dict})
    def put(self, request, company_id):
        company = self._company(company_id)
        if company is None:
            return Response({"detail": _("No such company.")}, status=status.HTTP_404_NOT_FOUND)

        datos = IdentitySerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        v = datos.validated_data
        set_current_tenant(company.id)

        proveedor = SsoProvider.objects_all_tenants.filter(tenant=company).first() or SsoProvider(
            tenant=company
        )
        proveedor.name = v["name"]
        proveedor.issuer = v["issuer"].rstrip("/")
        proveedor.slug = v.get("slug") or ""
        proveedor.jwks_uri = v.get("jwks_uri") or ""
        proveedor.client_id = v.get("client_id") or ""
        if v.get("client_secret"):
            proveedor.client_secret = v["client_secret"]
        proveedor.may_act_for_people = v.get("may_act_for_people", False)
        proveedor.is_active = v.get("is_active", True)
        proveedor.full_clean(exclude=["tenant"])
        proveedor.save()

        # Los dominios se sustituyen por los que vengan: la lista es la verdad, y
        # así quitar uno es borrarlo de la caja, sin una pantalla aparte.
        pedidos = {d.strip().lower().lstrip("@") for d in v.get("domains", []) if d.strip()}
        SsoDomain.objects_all_tenants.filter(provider=proveedor).exclude(
            domain__in=pedidos
        ).delete()
        for dominio in pedidos:
            SsoDomain.objects_all_tenants.get_or_create(
                tenant=company, domain=dominio, defaults={"provider": proveedor}
            )

        record(
            action=AuditAction.IDENTITY_CHANGED,
            actor=request.user,
            company=company,
            target_type="identity provider",
            target_label=f"{proveedor.name} ({proveedor.issuer})",
            note=", ".join(sorted(pedidos)) or "sin dominios",
        )
        record_platform(
            action=PlatformAction.IDENTITY_CHANGED,
            actor=request.user,
            company=company,
            target_type="identity provider",
            target_label=f"{proveedor.name} ({proveedor.issuer})",
            note=", ".join(sorted(pedidos)) or "sin dominios",
        )

        company.refresh_from_db()
        return Response(_empresa(company))

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, company_id):
        company = self._company(company_id)
        if company is None:
            return Response({"detail": _("No such company.")}, status=status.HTTP_404_NOT_FOUND)
        set_current_tenant(company.id)
        fuera = SsoProvider.objects_all_tenants.filter(tenant=company).first()
        if fuera is not None:
            record(
                action=AuditAction.IDENTITY_CHANGED,
                actor=request.user,
                company=company,
                target_type="identity provider",
                target_label=f"{fuera.name} ({fuera.issuer})",
                note="retirado: su gente vuelve a entrar con contraseña",
            )
            record_platform(
                action=PlatformAction.IDENTITY_CHANGED,
                actor=request.user,
                company=company,
                target_type="identity provider",
                target_label=f"{fuera.name} ({fuera.issuer})",
                note="retirado: su gente vuelve a entrar con contraseña",
            )
            fuera.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NewApplicationSerializer(serializers.Serializer):
    """La aplicación que va a hablar con esta empresa desde fuera."""

    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    #: Vacío significa el preajuste de una integración completa. Quien quiera otra
    #: cosa manda su lista.
    scopes = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate_scopes(self, value):
        permitidos = set(ApplicationScope.values)
        desconocidos = sorted(set(value) - permitidos)
        if desconocidos:
            raise serializers.ValidationError(
                _("Unknown permissions: %(list)s.") % {"list": ", ".join(desconocidos)}
            )
        return value


class ApplicationChangeSerializer(serializers.Serializer):
    """Lo que se puede cambiar de una aplicación ya dada de alta."""

    scopes = serializers.ListField(child=serializers.CharField(), required=False)
    is_active = serializers.BooleanField(required=False)

    validate_scopes = NewApplicationSerializer.validate_scopes


class _PorEmpresa(APIView):
    """Lo común a las vistas que trabajan dentro de una empresa concreta.

    Fijar el inquilino es **obligatorio** aquí y no una optimización: los gestores
    de estos modelos devuelven *nada* sin él, así que sin esta llamada la lista
    saldría vacía y el alta fallaría por una empresa que sí existe.
    """

    permission_classes = [IsPlatformSuperuser]

    def empresa(self, company_id):
        company = Tenant.objects.filter(pk=company_id).first()
        if company is not None:
            set_current_tenant(company.id)
        return company

    def no_esta(self, que=None):
        return Response({"detail": que or _("No such company.")}, status=status.HTTP_404_NOT_FOUND)


class CompanyChangeSerializer(serializers.Serializer):
    """Lo que se puede cambiar de una empresa desde la consola. Todo opcional."""

    name = serializers.CharField(max_length=255, required=False)
    tax_id = serializers.CharField(max_length=32, required=False)
    country = serializers.CharField(max_length=2, required=False)
    time_zone = serializers.CharField(max_length=64, required=False)
    language = serializers.ChoiceField(choices=settings.LANGUAGES, required=False)
    is_active = serializers.BooleanField(required=False)
    #: El nombre de la empresa, escrito a mano, para desactivarla. Lo pide también
    #: la pantalla, pero la regla vive aquí: una petición suelta no se la salta.
    confirm = serializers.CharField(required=False, allow_blank=True)

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError(_("The name cannot be empty."))
        return value

    def validate_tax_id(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError(_("The tax number cannot be empty."))
        otra = Tenant.objects.filter(tax_id=value).exclude(pk=self.context["company"].pk)
        if otra.exists():
            raise serializers.ValidationError(_("A company with this tax number already exists."))
        return value

    def validate_country(self, value: str) -> str:
        return value.strip().upper()

    def validate_time_zone(self, value: str) -> str:
        validate_time_zone(value)
        return value

    def validate(self, attrs):
        company = self.context["company"]
        if attrs.get("is_active") is False and company.is_active:
            if (attrs.get("confirm") or "").strip() != company.name:
                raise serializers.ValidationError(
                    {"confirm": _("Type the company's name exactly to deactivate it.")}
                )
        return attrs


#: Lo que se copia al rastro cuando cambia. El estado va aparte: tiene su acción.
CAMPOS_DE_LA_FICHA = ("name", "tax_id", "country", "time_zone", "language")


@extend_schema(tags=["platform"])
class PlatformCompanyView(_PorEmpresa):
    """Cambiar la ficha de una empresa, o desactivarla y volver a activarla.

    **Desactivar no borra nada ni toca nada más**: ni su gente, ni sus
    credenciales, ni su registro, que se guarda los años que diga su plazo. Solo
    cambia `is_active`, y por eso reactivar la deja exactamente como estaba.

    Mientras está desactivada nadie de dentro entra ---ni con contraseña, ni con
    su proveedor, ni con una sesión que ya tuviera abierta--- y sus aplicaciones
    reciben 401.
    """

    @extend_schema(request=CompanyChangeSerializer, responses={200: dict})
    @transaction.atomic
    def patch(self, request, company_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()

        datos = CompanyChangeSerializer(data=request.data, context={"company": company})
        datos.is_valid(raise_exception=True)
        v = datos.validated_data

        cambios = {}
        for campo in CAMPOS_DE_LA_FICHA:
            if campo in v and getattr(company, campo) != v[campo]:
                cambios[campo] = [getattr(company, campo), v[campo]]
                setattr(company, campo, v[campo])
        estado_antes = company.is_active
        if "is_active" in v:
            company.is_active = v["is_active"]

        if not cambios and company.is_active == estado_antes:
            return Response(_empresa(company))

        company.save()

        if cambios:
            record(
                action=AuditAction.SETTINGS_CHANGED,
                actor=request.user,
                company=company,
                target=company,
                target_label=company.name,
                changes=cambios,
                note=str(_("Changed from the installation console")),
            )
            record_platform(
                action=PlatformAction.COMPANY_CHANGED,
                actor=request.user,
                company=company,
                target=company,
                target_label=company.name,
                changes=cambios,
            )
        if company.is_active != estado_antes:
            record(
                action=AuditAction.SETTINGS_CHANGED,
                actor=request.user,
                company=company,
                target=company,
                target_label=company.name,
                changes={"is_active": [estado_antes, company.is_active]},
                note=str(_("Changed from the installation console")),
            )
            record_platform(
                action=PlatformAction.COMPANY_REACTIVATED
                if company.is_active
                else PlatformAction.COMPANY_DEACTIVATED,
                actor=request.user,
                company=company,
                target=company,
                target_label=company.name,
            )
        return Response(_empresa(company))


def _administrador_de_empresa(persona: User) -> dict:
    return {
        "id": str(persona.id),
        "first_name": persona.first_name,
        "last_name": persona.last_name,
        "email": persona.email,
        "is_active": persona.is_active,
        #: Entra con la cuenta de su empresa: aquí no tiene contraseña que poner.
        "federated": persona.is_federated,
        "last_login": persona.last_login.isoformat() if persona.last_login else None,
    }


@extend_schema(tags=["platform"])
class CompanyAdminsView(_PorEmpresa):
    """Quién administra una empresa. Solo quien administra: el resto de la plantilla
    es dato de la empresa y desde la instalación no se ve."""

    @extend_schema(request=None, responses={200: dict})
    def get(self, request, company_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()
        quienes = User.objects.filter(tenant=company, role=Role.ADMIN).order_by(
            "first_name", "last_name", "email"
        )
        return Response({"admins": [_administrador_de_empresa(p) for p in quienes]})


@extend_schema(tags=["platform"])
class CompanyAdminLinkView(_PorEmpresa):
    """Mandar a un administrador de una empresa el enlace para poner contraseña.

    **Por correo y a esa persona**: la instalación no ve el enlace ni elige la
    contraseña. Si la viera, podría entrar como esa persona en los datos de su
    empresa, y esta consola existe precisamente para no ser esa puerta.
    """

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, company_id, person_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()
        persona = User.objects.filter(tenant=company, role=Role.ADMIN, pk=person_id).first()
        if persona is None:
            return self.no_esta(_("That person does not administer this company."))

        motivo = None
        if not company.is_active:
            motivo = _("The company is deactivated: the link would not let anybody in.")
        elif not persona.is_active:
            motivo = _("That account is deactivated: the link would not let them in.")
        elif persona.is_federated:
            motivo = _(
                "That person signs in with their company's account and has no password here."
            )
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)

        try:
            send_account_email(persona, base_url=settings.FRONTEND_URL)
        except smtplib.SMTPRecipientsRefused:
            # Rechazo de la dirección, no avería: reintentar no lo arregla. Medido en
            # devel con un `.test`: el relé contesta 554 y la pantalla decía «vuelve a
            # intentarlo más tarde».
            log.warning("The mail relay refused %s", persona.email)
            return Response(
                {
                    "detail": _(
                        "The mail server refuses the address %(email)s. Check that it is right."
                    )
                    % {"email": persona.email}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception:
            # El correo es lo único que esto hace: si no sale, se dice, en vez de
            # contestar «enviado» a un enlace que no va a llegar.
            log.exception("Could not send the password link to %s", persona.email)
            return Response(
                {"detail": _("The email could not be sent. Nothing has changed; try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        etiqueta = persona.get_full_name() or persona.email
        record(
            action=AuditAction.INVITATION_SENT,
            actor=request.user,
            company=company,
            target=persona,
            target_label=etiqueta,
            note=str(_("Sent from the installation console")),
        )
        record_platform(
            action=PlatformAction.COMPANY_ADMIN_LINK_SENT,
            actor=request.user,
            company=company,
            target=persona,
            target_type="person",
            target_label=etiqueta,
        )
        return Response({"sent_to": persona.email})


@extend_schema(tags=["platform"])
class CompanyApplicationsView(_PorEmpresa):
    """Las aplicaciones de una empresa, desde la consola de la instalación.

    Existían solo dentro de la empresa, en la pantalla de su administrador, y eso
    partía el alta en dos: quien da de alta al cliente tenía que salir, entrar con
    otra cuenta y volver. La credencial es lo que hace falta para enchufar una
    aplicación, así que se emite donde se da el alta.

    **Lo que esto NO abre.** Se administra la aplicación, no se miran sus datos: de
    la empresa se sigue viendo lo mismo que antes. Y el testigo se enseña **una vez**
    ---se guarda cifrado de un solo sentido--- exactamente igual que en la pantalla
    de la empresa; que lo emita la consola no lo hace recuperable.
    """

    @extend_schema(request=None, responses={200: dict})
    def get(self, request, company_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()
        aplicaciones = Application.objects.prefetch_related("credentials").order_by(
            "-is_active", "-created_at"
        )
        return Response(
            {
                "applications": ApplicationSerializer(aplicaciones, many=True).data,
                # Para que la pantalla ofrezca las casillas sin conocer el catálogo.
                "all_scopes": [
                    {"value": valor, "label": str(etiqueta)}
                    for valor, etiqueta in ApplicationScope.choices
                ],
                "integration_scopes": [str(s) for s in FULL_INTEGRATION_SCOPES],
            }
        )

    @extend_schema(request=NewApplicationSerializer, responses={201: dict})
    @transaction.atomic
    def post(self, request, company_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()

        datos = NewApplicationSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        v = datos.validated_data

        aplicacion = Application.objects.create(
            tenant=company,
            name=v["name"],
            description=v.get("description", ""),
            scopes=[str(s) for s in (v.get("scopes") or FULL_INTEGRATION_SCOPES)],
            created_by=None,  # la cuenta de la instalación no es de esta empresa
        )
        credencial, testigo = ApplicationCredential.issue(aplicacion, label=v["name"])

        record(
            action=AuditAction.APPLICATION_CREATED,
            actor=request.user,
            company=company,
            target=aplicacion,
            target_label=aplicacion.name,
            changes={"scopes": aplicacion.scopes},
            note=str(_("Authorised from the installation console")),
        )
        record_platform(
            action=PlatformAction.APPLICATION_AUTHORISED,
            actor=request.user,
            company=company,
            target=aplicacion,
            target_label=aplicacion.name,
            changes={"scopes": aplicacion.scopes},
        )

        return Response(
            {
                **ApplicationSerializer(aplicacion).data,
                # La única vez que existe fuera de quien lo va a guardar.
                "token": testigo,
                "token_hint": credencial.token_hint,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["platform"])
class CompanyApplicationView(_PorEmpresa):
    """Cambiar los permisos de una aplicación, o retirarla."""

    def _aplicacion(self, application_id):
        return Application.objects.filter(pk=application_id).first()

    @extend_schema(request=ApplicationChangeSerializer, responses={200: dict})
    def patch(self, request, company_id, application_id):
        if self.empresa(company_id) is None:
            return self.no_esta()
        aplicacion = self._aplicacion(application_id)
        if aplicacion is None:
            return self.no_esta(_("No such application."))

        datos = ApplicationChangeSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        v = datos.validated_data
        antes = list(aplicacion.scopes)
        activa_antes = aplicacion.is_active

        if "scopes" in v:
            aplicacion.scopes = [str(s) for s in v["scopes"]]
        if "is_active" in v:
            aplicacion.is_active = v["is_active"]
        aplicacion.save(update_fields=["scopes", "is_active"])

        if aplicacion.scopes != antes:
            record(
                action=AuditAction.APPLICATION_CREATED,
                actor=request.user,
                company=aplicacion.tenant,
                target=aplicacion,
                target_label=aplicacion.name,
                changes={"scopes": [antes, aplicacion.scopes]},
                note=str(_("Permissions changed")),
            )
        cambios = {}
        if aplicacion.scopes != antes:
            cambios["scopes"] = [antes, aplicacion.scopes]
        if aplicacion.is_active != activa_antes:
            cambios["is_active"] = [activa_antes, aplicacion.is_active]
        if cambios:
            record_platform(
                action=PlatformAction.APPLICATION_CHANGED,
                actor=request.user,
                company=aplicacion.tenant,
                target=aplicacion,
                target_label=aplicacion.name,
                changes=cambios,
            )
        return Response(ApplicationSerializer(aplicacion).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, company_id, application_id):
        """Retira la aplicación: la desactiva y revoca lo que tuviera.

        No se borra, por lo mismo que en la pantalla de la empresa: lo que registró
        sigue siendo suyo, y una fila menos dejaría esos fichajes sin dueño.
        """
        if self.empresa(company_id) is None:
            return self.no_esta()
        aplicacion = self._aplicacion(application_id)
        if aplicacion is None:
            return self.no_esta(_("No such application."))

        aplicacion.is_active = False
        aplicacion.save(update_fields=["is_active"])
        for credencial in aplicacion.credentials.filter(revoked_at__isnull=True):
            credencial.revoke()

        record(
            action=AuditAction.APPLICATION_REVOKED,
            actor=request.user,
            company=aplicacion.tenant,
            target=aplicacion,
            target_label=aplicacion.name,
        )
        record_platform(
            action=PlatformAction.APPLICATION_WITHDRAWN,
            actor=request.user,
            company=aplicacion.tenant,
            target=aplicacion,
            target_label=aplicacion.name,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["platform"])
class CompanyCredentialsView(_PorEmpresa):
    """Emitir otra credencial.

    Varias conviven a propósito: es lo que permite rotar sin cortar el servicio
    ---se emite la nueva, se cambia donde toque, se revoca la vieja---.

    Revocar vive en su propia clase, y no es manía: una sola clase para las dos
    rutas deja dos operaciones con el mismo nombre en el esquema ---la colección y
    el elemento--- y el generador las desempata con un número. Quien lea el
    contrato se encuentra `…_create_2` y no sabe cuál es cuál.
    """

    def _aplicacion(self, application_id):
        return Application.objects.filter(pk=application_id).first()

    @extend_schema(request=IssueSerializer, responses={201: dict})
    def post(self, request, company_id, application_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()
        aplicacion = self._aplicacion(application_id)
        if aplicacion is None:
            return self.no_esta(_("No such application."))
        if not aplicacion.is_active:
            return Response(
                {"detail": _("Reactivate the application before issuing a credential.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = IssueSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        credencial, testigo = ApplicationCredential.issue(
            aplicacion,
            label=form.validated_data["label"],
            expires_at=form.validated_data.get("expires_at"),
        )
        record(
            action=AuditAction.APPLICATION_CREATED,
            actor=request.user,
            company=company,
            target=aplicacion,
            target_label=aplicacion.name,
            note=str(_("Credential issued: …%(hint)s")) % {"hint": credencial.token_hint},
        )
        # La pista, que es lo que la pantalla ya enseña de cada una. El testigo, nunca.
        record_platform(
            action=PlatformAction.CREDENTIAL_ISSUED,
            actor=request.user,
            company=company,
            target=aplicacion,
            target_label=aplicacion.name,
            note=f"…{credencial.token_hint}",
        )
        return Response(
            {**CredentialSerializer(credencial).data, "token": testigo},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["platform"])
class CompanyCredentialView(_PorEmpresa):
    """Revocar una credencial concreta, sin tocar las demás."""

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, company_id, application_id, credential_id):
        company = self.empresa(company_id)
        if company is None:
            return self.no_esta()
        credencial = ApplicationCredential.objects.filter(
            pk=credential_id, application_id=application_id
        ).first()
        if credencial is None:
            return self.no_esta(_("No such credential."))
        if credencial.revoked_at is None:
            credencial.revoke()
            record(
                action=AuditAction.APPLICATION_REVOKED,
                actor=request.user,
                company=company,
                target=credencial.application,
                target_label=credencial.application.name,
                note=str(_("Credential revoked: …%(hint)s")) % {"hint": credencial.token_hint},
            )
            record_platform(
                action=PlatformAction.CREDENTIAL_REVOKED,
                actor=request.user,
                company=company,
                target=credencial.application,
                target_label=credencial.application.name,
                note=f"…{credencial.token_hint}",
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class NewAdminSerializer(serializers.Serializer):
    """Otra cuenta que administre esta instalación."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    #: Si se deja, se genera y se enseña una sola vez.
    password = serializers.CharField(required=False, allow_blank=True, min_length=12)


def _administrador(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _correo_ocupado(correo: str, *, salvo=None) -> str | None:
    """Por qué no vale ese correo para una cuenta de la instalación, o nada.

    Ni repetido entre ellas, ni de alguien de una empresa. Lo segundo porque con
    dos cuentas del mismo correo la pantalla de entrada pide el identificador
    fiscal para saber a cuál se refiere ---y la de la instalación no tiene ninguno---,
    así que la cuenta se quedaría sin forma de entrar. Pasó en producción el
    23/09/2026: se creó una, no pudo entrar, y hubo que desactivarla.
    """
    fuera = {"pk": salvo.pk} if salvo is not None else {}
    de_la_instalacion = User.objects.filter(email__iexact=correo, tenant__isnull=True)
    if de_la_instalacion.exclude(**fuera).exists():
        return _("There is already an installation account with that address.")
    de_una_empresa = (
        User.objects.filter(email__iexact=correo, tenant__isnull=False)
        .select_related("tenant")
        .first()
    )
    if de_una_empresa is not None:
        return _(
            "That address already belongs to somebody in %(company)s. An "
            "installation account with a repeated address could not sign in, "
            "because the sign-in screen would ask which company it is, and this "
            "one has none. Use a different address."
        ) % {"company": de_una_empresa.tenant.name}
    return None


def _los_de_la_instalacion():
    """Las cuentas sin empresa. Es lo que las define, no una bandera aparte."""
    return User.objects.filter(tenant__isnull=True, is_superuser=True).order_by("email")


@extend_schema(tags=["platform"])
class PlatformAdminsView(APIView):
    """Quién administra esta instalación, y el alta de otra cuenta.

    La **primera** se crea en el contenedor y no hay forma de evitarlo: es el huevo
    y la gallina, no hay sesión con la que autorizar el alta. Pero que la segunda
    siguiera pidiendo un shell sí era evitable, y es lo que deja una instalación con
    una sola persona capaz de operarla ---y sin relevo si se va de vacaciones.

    No se crean aquí cuentas de ninguna empresa: el alta de una empresa ya trae su
    administrador, y esta puerta es para quien administra el sistema entero.
    """

    permission_classes = [IsPlatformSuperuser]

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        return Response({"admins": [_administrador(u) for u in _los_de_la_instalacion()]})

    @extend_schema(request=NewAdminSerializer, responses={201: dict})
    def post(self, request):
        datos = NewAdminSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        v = datos.validated_data

        correo = v["email"].lower()
        motivo = _correo_ocupado(correo)
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)

        clave = v.get("password") or f"Ott-{secrets.token_urlsafe(12)}"
        creado = User.objects.create_superuser(
            email=correo,
            password=clave,
            first_name=v["first_name"],
            last_name=v["last_name"],
            tenant=None,
        )
        # En el registro de la instalación, que no va por empresa. El de las
        # empresas no: una entrada sin empresa sería una que otra podría leer.
        record_platform(
            action=PlatformAction.ADMIN_CREATED,
            actor=request.user,
            target=creado,
            target_type="installation account",
            target_label=creado.email,
        )
        return Response(
            {**_administrador(creado), "password": clave}, status=status.HTTP_201_CREATED
        )


class _UnaCuenta(APIView):
    """Lo común: encontrar una cuenta de la instalación por su identificador."""

    permission_classes = [IsPlatformSuperuser]

    def _cuenta(self, admin_id):
        return _los_de_la_instalacion().filter(pk=admin_id).first()


@extend_schema(tags=["platform"])
class PlatformAdminPasswordView(_UnaCuenta):
    """Una contraseña nueva para una cuenta de la instalación.

    En su propia ruta y no como otro método de la de al lado: dos POST bajo el
    mismo nombre dejan el esquema con `…_create` y `…_create_2`, y quien lee el
    contrato no sabe cuál es cuál.
    """

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, admin_id):
        """Una contraseña nueva, enseñada una sola vez.

        No se manda por correo a propósito: en una instalación recién puesta el
        correo es lo último que funciona, y una cuenta que no entra porque el envío
        falló es exactamente el problema que esta pantalla viene a quitar.
        """
        cuenta = self._cuenta(admin_id)
        if cuenta is None:
            return Response(
                {"detail": _("No such installation account.")}, status=status.HTTP_404_NOT_FOUND
            )
        clave = f"Ott-{secrets.token_urlsafe(12)}"
        cuenta.set_password(clave)
        cuenta.is_active = True
        cuenta.save(update_fields=["password", "is_active"])
        record_platform(
            action=PlatformAction.ADMIN_PASSWORD_RESET,
            actor=request.user,
            target=cuenta,
            target_type="installation account",
            target_label=cuenta.email,
        )
        return Response({**_administrador(cuenta), "password": clave})


class AdminChangeSerializer(serializers.Serializer):
    """Lo que se puede cambiar de una cuenta de la instalación. Todo opcional."""

    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    #: Solo `true`: reactivar. Desactivar tiene sus reglas y va por DELETE.
    is_active = serializers.BooleanField(required=False)

    def validate_is_active(self, value):
        if value is False:
            raise serializers.ValidationError(_("To deactivate an account, use its own action."))
        return value


@extend_schema(tags=["platform"])
class PlatformAdminLinkView(_UnaCuenta):
    """Mandar a una cuenta de la instalación el enlace para poner contraseña.

    La otra salida, la contraseña nueva enseñada una vez, sigue ahí para cuando el
    correo no sale. Esta es la buena cuando sí: la contraseña no pasa por las manos
    de quien la da de alta.
    """

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, admin_id):
        cuenta = self._cuenta(admin_id)
        if cuenta is None:
            return Response(
                {"detail": _("No such installation account.")}, status=status.HTTP_404_NOT_FOUND
            )
        if not cuenta.is_active:
            return Response(
                {
                    "detail": _(
                        "That account is deactivated: reactivate it before sending the link."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            send_account_email(cuenta, base_url=settings.FRONTEND_URL)
        except smtplib.SMTPRecipientsRefused:
            log.warning("The mail relay refused %s", cuenta.email)
            return Response(
                {
                    "detail": _(
                        "The mail server refuses the address %(email)s. Check that it is right."
                    )
                    % {"email": cuenta.email}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception:
            log.exception("Could not send the password link to %s", cuenta.email)
            return Response(
                {"detail": _("The email could not be sent. Nothing has changed; try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        record_platform(
            action=PlatformAction.ADMIN_LINK_SENT,
            actor=request.user,
            target=cuenta,
            target_type="installation account",
            target_label=cuenta.email,
        )
        return Response({"sent_to": cuenta.email})


@extend_schema(tags=["platform"])
class PlatformAdminView(_UnaCuenta):
    """Cambiar, reactivar o desactivar una cuenta de la instalación."""

    @extend_schema(request=AdminChangeSerializer, responses={200: dict})
    def patch(self, request, admin_id):
        cuenta = self._cuenta(admin_id)
        if cuenta is None:
            return Response(
                {"detail": _("No such installation account.")}, status=status.HTTP_404_NOT_FOUND
            )
        datos = AdminChangeSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        v = datos.validated_data

        if "email" in v:
            v["email"] = v["email"].lower()
            if v["email"] != cuenta.email.lower():
                motivo = _correo_ocupado(v["email"], salvo=cuenta)
                if motivo:
                    return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)

        cambios = {}
        for campo in ("email", "first_name", "last_name"):
            if campo in v and getattr(cuenta, campo) != v[campo]:
                cambios[campo] = [getattr(cuenta, campo), v[campo]]
                setattr(cuenta, campo, v[campo])
        reactivada = v.get("is_active") is True and not cuenta.is_active
        if reactivada:
            cuenta.is_active = True

        if cambios or reactivada:
            cuenta.save()
        if cambios:
            record_platform(
                action=PlatformAction.ADMIN_CHANGED,
                actor=request.user,
                target=cuenta,
                target_type="installation account",
                target_label=cuenta.email,
                changes=cambios,
            )
        if reactivada:
            record_platform(
                action=PlatformAction.ADMIN_REACTIVATED,
                actor=request.user,
                target=cuenta,
                target_type="installation account",
                target_label=cuenta.email,
            )
        return Response(_administrador(cuenta))

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, admin_id):
        """Desactiva, no borra. Y nunca la última, ni la propia.

        Quedarse sin ninguna cuenta activa deja la instalación **sin quien la
        administre** y solo se sale de ahí abriendo un shell, que es justo lo que
        esto existe para no tener que hacer. Y desactivarse a uno mismo es la forma
        rápida de conseguir lo mismo con dos cuentas.
        """
        cuenta = self._cuenta(admin_id)
        if cuenta is None:
            return Response(
                {"detail": _("No such installation account.")}, status=status.HTTP_404_NOT_FOUND
            )
        if cuenta.pk == request.user.pk:
            return Response(
                {"detail": _("You cannot deactivate the account you are using.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _los_de_la_instalacion().filter(is_active=True).exclude(pk=cuenta.pk).count() == 0:
            return Response(
                {
                    "detail": _(
                        "This is the only account that can administer the installation. "
                        "Create another one before deactivating it."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        cuenta.is_active = False
        cuenta.save(update_fields=["is_active"])
        record_platform(
            action=PlatformAction.ADMIN_DEACTIVATED,
            actor=request.user,
            target=cuenta,
            target_type="installation account",
            target_label=cuenta.email,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["platform"])
class WhoAmIView(APIView):
    """Si quien pregunta administra la instalación.

    Lo pide el frontal para decidir si enseña el menú: preguntarlo es más barato
    que deducirlo, y deducirlo mal deja una pantalla que responde 403 a todo.
    """

    permission_classes = [IsPlatformSuperuser]

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        return Response({"platform_admin": True, "roles": [r.value for r in Role]})


def _asiento(entrada: PlatformAuditEntry) -> dict:
    return {
        "id": str(entrada.id),
        "at": entrada.at.isoformat(),
        "actor": entrada.actor_label,
        "action": entrada.action,
        "action_label": entrada.get_action_display(),
        "company": str(entrada.company_id) if entrada.company_id else None,
        "company_label": entrada.company_label,
        "target_type": entrada.target_type,
        "target_label": entrada.target_label,
        "changes": entrada.changes,
        "note": entrada.note,
    }


@extend_schema(tags=["platform"])
class PlatformAuditView(APIView):
    """Lo que han hecho las cuentas de la instalación, lo más reciente arriba.

    Solo lo de la instalación. Lo que pasa **dentro** de una empresa está en el
    rastro de esa empresa y aquí no se ve: esta pantalla no es una puerta lateral.
    """

    permission_classes = [IsPlatformSuperuser]

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        pagina = PageNumberPagination()
        filas = pagina.paginate_queryset(
            PlatformAuditEntry.objects.order_by("-at"), request, view=self
        )
        return pagina.get_paginated_response([_asiento(e) for e in filas])
