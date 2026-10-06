"""Entrar cuando el mismo correo tiene más de una cuenta.

Con dos cuentas activas del mismo correo y sin identificador fiscal, la entrada se
rechazaba **antes de mirar la contraseña**, y contaba también a la gente de
empresas desactivadas. Una cuenta de la instalación no tiene identificador fiscal
que dar, así que si su correo coincidía con el de alguien de una empresa no podía
entrar nunca.

Ahora se prueba la contraseña contra cada candidata: entra la única que la
acepta, y si la aceptan varias la respuesta dice que falta la empresa ---con su
propio código, para que la pantalla pida el identificador fiscal en vez de decir
«credenciales incorrectas»---.
"""

from __future__ import annotations

from unittest import mock

import pytest
from django.contrib.auth import authenticate
from rest_framework.test import APIClient

from apps.tenants.models import Tenant
from apps.users.backends import MAX_CANDIDATES, CompanyRequired, TenantEmailBackend
from apps.users.models import User

pytestmark = pytest.mark.django_db

CORREO = "ana@example.com"
CLAVE = "a-sufficiently-long-password"
OTRA_CLAVE = "another-sufficiently-long-one"


@pytest.fixture
def acme():
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


@pytest.fixture
def globex():
    return Tenant.objects.create(name="Globex Inc", tax_id="B-22.222 222")


def persona(tenant, password=CLAVE, **extra):
    return User.objects.create_user(email=CORREO, password=password, tenant=tenant, **extra)


def de_la_instalacion(password=CLAVE):
    return User.objects.create_user(
        email=CORREO, password=password, tenant=None, is_superuser=True, is_staff=True
    )


def entrar(**datos):
    return APIClient().post("/api/auth/token/", {"email": CORREO, **datos}, format="json")


# ------------------------------------------------------------- el backend


def test_entra_la_unica_cuenta_que_acepta_la_contrasena(acme, globex):
    persona(acme, password=CLAVE)
    otra = persona(globex, password=OTRA_CLAVE)

    assert authenticate(None, email=CORREO, password=OTRA_CLAVE) == otra


def test_la_cuenta_de_la_instalacion_entra_aunque_alguien_de_una_empresa_tenga_su_correo(acme):
    # El caso de producción: la de la instalación no tiene empresa que nombrar.
    persona(acme, password=OTRA_CLAVE)
    instalacion = de_la_instalacion(password=CLAVE)

    assert authenticate(None, email=CORREO, password=CLAVE) == instalacion


def test_quien_es_de_una_empresa_desactivada_no_cuenta(acme, globex):
    persona(acme, password=CLAVE)
    buena = persona(globex, password=CLAVE)
    acme.is_active = False
    acme.save()

    assert authenticate(None, email=CORREO, password=CLAVE) == buena


def test_si_la_aceptan_varias_falta_la_empresa(acme, globex):
    persona(acme)
    persona(globex)

    # Quien no lo pide ---el admin de Django--- sigue recibiendo None.
    assert authenticate(None, email=CORREO, password=CLAVE) is None
    with pytest.raises(CompanyRequired):
        authenticate(None, email=CORREO, password=CLAVE, distinguish_missing_company=True)


def test_un_hash_por_candidata_aunque_sea_federada(acme, globex):
    """El tiempo de respuesta no dice si el correo existe ni si es federado."""
    persona(acme)
    federada = persona(globex, oidc_sub="sub-1", oidc_issuer="https://idp.example")
    federada.set_unusable_password()
    federada.save()

    with mock.patch("apps.users.backends.User.set_password") as de_relleno:
        assert authenticate(None, email=CORREO, password="wrong-password-here") is None
    assert de_relleno.call_count == 1  # el de la federada; la otra pasa por check_password

    with mock.patch("apps.users.backends.User.set_password") as de_relleno:
        assert authenticate(None, email="nadie@example.com", password=CLAVE) is None
    assert de_relleno.call_count == 1


def test_con_demasiadas_candidatas_no_se_prueba_ninguna(db):
    for n in range(MAX_CANDIDATES + 1):
        empresa = Tenant.objects.create(name=f"E{n}", tax_id=f"B{n:08d}")
        persona(empresa)

    with mock.patch.object(User, "check_password") as comprobar:
        with pytest.raises(CompanyRequired):
            TenantEmailBackend().authenticate(
                None, email=CORREO, password=CLAVE, distinguish_missing_company=True
            )
    comprobar.assert_not_called()


# ------------------------------------------------------- la pantalla de entrada


def test_la_entrada_dice_que_falta_la_empresa_con_su_propio_codigo(acme, globex):
    persona(acme)
    persona(globex)

    respuesta = entrar(password=CLAVE)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["code"] == "company_required"


def test_una_contrasena_mala_sigue_siendo_credenciales_incorrectas(acme, globex):
    persona(acme)
    persona(globex)

    respuesta = entrar(password="wrong-password-here")

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["code"] != "company_required"


def test_con_el_cif_entra_en_esa_empresa(acme, globex):
    persona(acme)
    de_globex = persona(globex)

    respuesta = entrar(password=CLAVE, tax_id="B22222222")

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["user"]["id"] == str(de_globex.id)


@pytest.mark.parametrize("escrito", ["b-11111111", "B 1111 1111", "B.11.111.111", " B11111111 "])
def test_el_cif_se_compara_sin_guiones_espacios_ni_puntos(acme, globex, escrito):
    de_acme = persona(acme)
    persona(globex)

    respuesta = entrar(password=CLAVE, tax_id=escrito)

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["user"]["id"] == str(de_acme.id)


def test_el_alta_no_admite_el_mismo_cif_escrito_de_otra_forma(acme):
    respuesta = APIClient().post(
        "/api/auth/register/",
        {
            "company_name": "Otra",
            "tax_id": "B-1111.1111",
            "email": "otra@example.com",
            "password": CLAVE,
            "first_name": "O",
            "last_name": "T",
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert "tax_id" in respuesta.json()["error"]["details"]
