"""Dar de alta una empresa y su proveedor de identidad, sin consola.

Lo que se fija aquí: quién puede, que el alta deja la empresa utilizable, y que el
secreto del proveedor entra pero no sale.
"""

from __future__ import annotations

import base64

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.absences.models import LeaveType
from apps.tenants.identity import SsoDomain, SsoProvider
from apps.tenants.models import Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

#: El secreto del proveedor es un campo cifrado, así que guardarlo necesita clave.
#: Se fija aquí y no se hereda del entorno: en el runner no existe, y una prueba que
#: pasa en el puesto y falla en la puerta no prueba nada. Mismo patrón que
#: `test_entrar_por_el_proveedor`.
FERNET_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()


@pytest.fixture(autouse=True)
def _con_clave_de_cifrado():
    with override_settings(FIELD_ENCRYPTION_KEY=FERNET_KEY):
        yield


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def plataforma():
    """El superusuario que administra la instalación: **sin empresa**."""
    return User.objects.create_user(
        email="plataforma@ejemplo.test",
        password="X" * 14,
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )


def cliente(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_da_de_alta_una_empresa_con_su_administrador(plataforma):
    respuesta = cliente(plataforma).post(
        reverse("platform-companies"),
        {
            "company_name": "UTE Zonas Verdes Algeciras",
            "tax_id": "U27686062",
            "country": "ES",
            "time_zone": "Europe/Madrid",
            "email": "quien.administre@empresa.example",
            "first_name": "Quien",
            "last_name": "Administre",
        },
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["tax_id"] == "U27686062"
    # La contraseña se enseña una vez, como la credencial de aplicación: así el alta
    # no depende de que el correo salga.
    assert len(respuesta.data["administrator"]["password"]) >= 12

    empresa = Tenant.objects.get(tax_id="U27686062")
    admin = User.objects.get(email="quien.administre@empresa.example")
    assert admin.tenant_id == empresa.id and admin.role == Role.ADMIN
    # Y la empresa nace utilizable: con el catálogo legal de permisos sembrado, que
    # es lo que hace que el desplegable de «qué pides» no salga vacío.
    assert LeaveType.objects_all_tenants.filter(tenant=empresa).exists()


def test_el_administrador_de_una_empresa_no_administra_la_instalacion(company):
    """Aunque tuviera la bandera: si bastara con `is_superuser`, quien administra
    una empresa podría crear otras y verlas."""
    suyo = User.objects.create_user(
        email="jefa@empresa.example",
        password="X" * 14,
        tenant=company,
        role=Role.ADMIN,
        is_superuser=True,
    )

    respuesta = cliente(suyo).get(reverse("platform-companies"))

    assert respuesta.status_code == 403


def test_quien_no_es_nadie_tampoco(company):
    curiosa = User.objects.create_user(
        email="curiosa@empresa.example", password="X" * 14, tenant=company
    )
    assert cliente(curiosa).get(reverse("platform-companies")).status_code == 403


def test_pone_el_proveedor_de_identidad_con_sus_dominios(plataforma, company):
    respuesta = cliente(plataforma).put(
        reverse("platform-company-identity", args=[company.id]),
        {
            "name": "GreenCityControl",
            "issuer": "https://api.greencitycontrol.com/o/",
            "slug": "gcc",
            "jwks_uri": "https://api.greencitycontrol.com/o/jwks.json",
            "client_id": "opentimetrack-prod",
            "client_secret": "un-secreto-larguísimo",
            "may_act_for_people": True,
            "domains": ["ZVAlgeciras.es", "@utealgeciras.com", " "],
        },
        format="json",
    )

    assert respuesta.status_code == 200
    identidad = respuesta.data["identity"]
    # La barra final del emisor se quita: tiene que ser **exactamente** el `iss`.
    assert identidad["issuer"] == "https://api.greencitycontrol.com/o"
    assert identidad["domains"] == ["utealgeciras.com", "zvalgeciras.es"]
    assert identidad["has_secret"] is True
    # El secreto entra y no vuelve a salir.
    assert "un-secreto" not in str(respuesta.data)


def test_editar_sin_secreto_deja_el_que_habia(plataforma, company):
    api = cliente(plataforma)
    url = reverse("platform-company-identity", args=[company.id])
    api.put(
        url,
        {"name": "GCC", "issuer": "https://gcc.example/o", "client_secret": "el-de-antes"},
        format="json",
    )

    api.put(url, {"name": "GreenCityControl", "issuer": "https://gcc.example/o"}, format="json")

    proveedor = SsoProvider.objects_all_tenants.get(tenant=company)
    assert proveedor.client_secret == "el-de-antes"
    assert proveedor.name == "GreenCityControl"


def test_quitar_los_dominios_es_mandar_la_lista_sin_ellos(plataforma, company):
    api = cliente(plataforma)
    url = reverse("platform-company-identity", args=[company.id])
    api.put(
        url,
        {
            "name": "GCC",
            "issuer": "https://gcc.example/o",
            "domains": ["uno.example", "dos.example"],
        },
        format="json",
    )

    respuesta = api.put(
        url,
        {"name": "GCC", "issuer": "https://gcc.example/o", "domains": ["uno.example"]},
        format="json",
    )

    assert respuesta.data["identity"]["domains"] == ["uno.example"]
    assert SsoDomain.objects_all_tenants.filter(tenant=company).count() == 1


def test_la_lista_dice_cuanta_gente_y_si_tiene_identidad(plataforma, company):
    respuesta = cliente(plataforma).get(reverse("platform-companies"))

    assert respuesta.status_code == 200
    fila = next(c for c in respuesta.data["companies"] if c["tax_id"] == company.tax_id)
    assert fila["identity"] is None
    assert fila["people"] == User.objects.filter(tenant=company).count()


def test_el_superusuario_de_plataforma_puede_entrar(plataforma, client):
    """La cuenta que el modelo prevé tiene que poder pasar por la puerta.

    No podía: al no tener empresa, la zona horaria de su jornada ---que no existe,
    porque no tiene jornada--- reventaba la respuesta del acceso con
    `'NoneType' object has no attribute 'tzinfo'`. Ahora cae a la de la instalación.
    """
    plataforma.set_password("una-contraseña-larguísima")
    plataforma.save(update_fields=["password"])

    respuesta = client.post(
        "/api/auth/token/",
        {"email": plataforma.email, "password": "una-contraseña-larguísima"},
        content_type="application/json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["access"]


def test_y_la_zona_que_se_le_supone_es_la_de_la_instalacion(plataforma, settings):
    settings.DEFAULT_TENANT_TIME_ZONE = "Atlantic/Canary"
    assert str(plataforma.tzinfo) == "Atlantic/Canary"
