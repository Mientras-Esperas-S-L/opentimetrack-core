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

import secrets

from django.db import transaction
from django.db.models import Count
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
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User
from apps.users.serializers import SignUpSerializer

#: Lo que la integración con GreenCityControl usa, para marcarlo de una vez.
#:
#: Es una sugerencia de la pantalla, no una regla del servidor: la lista viaja en
#: la petición como cualquier otra, y quien da de alta puede quitar lo que no
#: quiera conceder. Existe porque marcar diez casillas a mano es donde se olvida
#: una y el alta parece buena hasta que, semanas después, algo contesta 403.
GREENCITY_SCOPES = [
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
        return Response({"companies": [_empresa(e, personas=e.cuantos) for e in empresas]})

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
    #: Vacío significa el preajuste de GreenCityControl, que es el caso de nueve de
    #: cada diez altas. Quien quiera otra cosa manda su lista.
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


@extend_schema(tags=["platform"])
class CompanyApplicationsView(_PorEmpresa):
    """Las aplicaciones de una empresa, desde la consola de la instalación.

    Existían solo dentro de la empresa, en la pantalla de su administrador, y eso
    partía el alta en dos: quien da de alta al cliente tenía que salir, entrar con
    otra cuenta y volver. La credencial es lo que hace falta para enchufar
    GreenCity, así que se emite donde se da el alta.

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
                "greencity_scopes": [str(s) for s in GREENCITY_SCOPES],
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
            scopes=[str(s) for s in (v.get("scopes") or GREENCITY_SCOPES)],
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
        "last_login": user.last_login,
    }


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
        if User.objects.filter(email__iexact=correo, tenant__isnull=True).exists():
            return Response(
                {"detail": _("There is already an installation account with that address.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        #  Y tampoco si alguien de una empresa lo usa ya. Con dos cuentas del mismo
        #  correo, la pantalla de entrada pide el identificador fiscal para saber a
        #  cuál se refiere ---y la de la instalación no tiene ninguno---, así que la
        #  cuenta nacería sin forma de entrar. Pasó en producción el 23/09/2026: se
        #  creó una, no pudo entrar, y hubo que desactivarla.
        de_una_empresa = User.objects.filter(email__iexact=correo, tenant__isnull=False).first()
        if de_una_empresa is not None:
            return Response(
                {
                    "detail": _(
                        "That address already belongs to somebody in %(company)s. An "
                        "installation account with a repeated address could not sign in, "
                        "because the sign-in screen would ask which company it is, and this "
                        "one has none. Use a different address."
                    )
                    % {"company": de_una_empresa.tenant.name}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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


@extend_schema(tags=["platform"])
class PlatformAdminView(_UnaCuenta):
    """Desactivar una cuenta de la instalación."""

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
