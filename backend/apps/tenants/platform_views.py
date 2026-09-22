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
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.models import set_current_tenant
from apps.tenants.identity import SsoDomain, SsoProvider
from apps.tenants.models import Tenant
from apps.users.models import Role, User
from apps.users.serializers import SignUpSerializer


class IsPlatformSuperuser(BasePermission):
    """Superusuario **sin empresa**: el que administra la instalación, no una empresa."""

    message = _("Only a platform superuser can administer the installation.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser and user.tenant_id is None)


def _empresa(company: Tenant, *, personas: int | None = None) -> dict:
    proveedor = SsoProvider.objects_all_tenants.filter(tenant=company).first()
    return {
        "id": str(company.id),
        "name": company.name,
        "tax_id": company.tax_id,
        "country": company.country,
        "time_zone": company.time_zone,
        "people": personas if personas is not None else User.objects.filter(tenant=company).count(),
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
            fuera.delete()
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
