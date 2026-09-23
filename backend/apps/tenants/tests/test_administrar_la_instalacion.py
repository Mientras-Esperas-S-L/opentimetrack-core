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


# --------------------------------------------------- lo que NO puede esta cuenta
#
# La cuenta de la instalación no pertenece a ninguna empresa, así que dentro del
# servicio no hay nada suyo que enseñar. Eso lo tenía escrito el permiso ---«does
# not operate on service data»--- y no lo cumplía: dejaba pasar a todo y las
# vistas de dentro, que dan por hecha una empresa, reventaban. Medido el
# 22/09/2026 contra la instalación de pruebas, nada más entrar: dos **500**.


def test_su_jornada_de_hoy_no_revienta_el_servidor(plataforma):
    """La jornada de quien no tiene empresa: 403, nunca 500."""
    respuesta = cliente(plataforma).get("/api/punches/today/")

    assert respuesta.status_code == 403


def test_su_turno_de_hoy_no_revienta_el_servidor(plataforma):
    respuesta = cliente(plataforma).get("/api/shifts/today/")

    assert respuesta.status_code == 403


def test_al_entrar_la_sesion_dice_que_no_hay_empresa(plataforma):
    """Y lo dice **al entrar**, que es de donde el navegador saca la sesión.

    Estaba arreglado en `/me/` y no aquí, y no se notaba de cerca: la pantalla
    de entrada se elige con lo que devuelve el login, así que la cuenta de la
    instalación seguía aterrizando en el reloj.
    """
    plataforma.set_password("X" * 14)
    plataforma.save(update_fields=["password"])

    respuesta = APIClient().post(
        reverse("auth:token"),
        {"email": plataforma.email, "password": "X" * 14},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.data["tenant"] is None


def test_sigue_pudiendo_decir_quien_es_y_salir(plataforma):
    """Y lo que sí necesita para tener sesión sigue abierto."""
    api = cliente(plataforma)

    yo = api.get(reverse("auth:me"))

    assert yo.status_code == 200
    assert yo.data["tenant"] is None

    # Salir sin token de refresco se queja del token que falta, no de quién
    # pide: lo que se comprueba aquí es que la puerta no le echa.
    assert api.post(reverse("auth:logout"), {}, format="json").status_code == 409


# ------------------------------------------------ la credencial, desde la consola
#
# Antes había que salir de la consola, entrar como administrador de esa empresa y
# volver: el alta de un cliente se partía en dos sesiones por una casilla de diez.


def test_da_de_alta_la_aplicacion_con_su_credencial(plataforma, company):
    respuesta = cliente(plataforma).post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "GreenCityControl"},
        format="json",
    )

    assert respuesta.status_code == 201
    # El testigo, una vez y entero.
    assert respuesta.data["token"].startswith("ott_app_")
    # Y sin decir qué permisos, los que la integración usa.
    assert "read:people" in respuesta.data["scopes"]
    assert "punch:delegated" in respuesta.data["scopes"]
    assert len(respuesta.data["scopes"]) == 10


def test_la_credencial_no_se_vuelve_a_ver(plataforma, company):
    api = cliente(plataforma)
    creada = api.post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "GreenCityControl"},
        format="json",
    )
    testigo = creada.data["token"]

    lista = api.get(f"/api/platform/companies/{company.id}/applications/")

    assert lista.status_code == 200
    assert testigo not in str(lista.data)
    # Lo que sí se ve es el rabito, para distinguir una credencial de otra.
    assert lista.data["applications"][0]["credentials"][0]["token_hint"] == testigo[-6:]


def test_se_pueden_pedir_permisos_a_medida(plataforma, company):
    respuesta = cliente(plataforma).post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "Reloj de la entrada", "scopes": ["punch:delegated"]},
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["scopes"] == ["punch:delegated"]


def test_un_permiso_que_no_existe_se_rechaza(plataforma, company):
    respuesta = cliente(plataforma).post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "Cualquiera", "scopes": ["read:todo"]},
        format="json",
    )

    assert respuesta.status_code == 400


def test_rotar_deja_las_dos_credenciales_y_revocar_quita_una(plataforma, company):
    api = cliente(plataforma)
    app = api.post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "GreenCityControl"},
        format="json",
    ).data
    base = f"/api/platform/companies/{company.id}/applications/{app['id']}"

    otra = api.post(f"{base}/credentials/", {"label": "la nueva"}, format="json")

    assert otra.status_code == 201
    assert otra.data["token"] != app["token"]
    # Conviven: es lo que permite cambiarla sin cortar el servicio.
    vivas = api.get(f"/api/platform/companies/{company.id}/applications/").data["applications"][0]
    assert sum(1 for c in vivas["credentials"] if c["is_valid"]) == 2

    fuera = api.delete(f"{base}/credentials/{otra.data['id']}/")

    assert fuera.status_code == 204
    quedan = api.get(f"/api/platform/companies/{company.id}/applications/").data["applications"][0]
    assert sum(1 for c in quedan["credentials"] if c["is_valid"]) == 1


def test_retirar_una_aplicacion_no_la_borra(plataforma, company):
    """Lo que registró sigue siendo suyo; una fila menos dejaría fichajes sin dueño."""
    api = cliente(plataforma)
    app = api.post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "GreenCityControl"},
        format="json",
    ).data

    fuera = api.delete(f"/api/platform/companies/{company.id}/applications/{app['id']}/")

    assert fuera.status_code == 204
    lista = api.get(f"/api/platform/companies/{company.id}/applications/").data["applications"]
    assert len(lista) == 1
    assert lista[0]["is_active"] is False
    assert all(not c["is_valid"] for c in lista[0]["credentials"])


def test_la_ficha_de_la_empresa_dice_cuantas_aplicaciones_tiene(plataforma, company):
    api = cliente(plataforma)
    antes = api.get("/api/platform/companies/").data["companies"]
    assert next(e for e in antes if e["tax_id"] == company.tax_id)["applications"] == 0

    api.post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "GreenCityControl"},
        format="json",
    )

    despues = api.get("/api/platform/companies/").data["companies"]
    assert next(e for e in despues if e["tax_id"] == company.tax_id)["applications"] == 1


def test_el_administrador_de_una_empresa_no_entra_en_la_consola(company):
    """La puerta es la misma para todo lo de plataforma, y esto lo fija aquí."""
    suyo = User.objects.create_user(
        email="jefa@acme.test", password="X" * 14, tenant=company, role=Role.ADMIN
    )

    respuesta = cliente(suyo).get(f"/api/platform/companies/{company.id}/applications/")

    assert respuesta.status_code == 403


# ------------------------------------------- quién administra esta instalación
#
# La primera cuenta se crea con `create_installation_admin` y no hay forma de
# evitarlo: no hay sesión con la que autorizar su alta. La segunda sí, y que
# siguiera pidiendo un shell dejaba la instalación con una sola persona capaz de
# operarla.


def test_da_de_alta_otra_cuenta_de_la_instalacion(plataforma):
    respuesta = cliente(plataforma).post(
        "/api/platform/admins/",
        {"email": "relevo@ejemplo.test", "first_name": "Ada", "last_name": "Lovelace"},
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["password"]
    nueva = User.objects.get(email="relevo@ejemplo.test")
    assert nueva.tenant_id is None
    assert nueva.is_superuser is True
    assert nueva.check_password(respuesta.data["password"])


def test_la_lista_son_solo_las_de_la_instalacion(plataforma, company):
    """Quien administra una empresa no sale aquí: no administra la instalación."""
    User.objects.create_user(
        email="jefa@acme.test", password="X" * 14, tenant=company, role=Role.ADMIN
    )

    respuesta = cliente(plataforma).get("/api/platform/admins/")

    assert respuesta.status_code == 200
    assert [a["email"] for a in respuesta.data["admins"]] == [plataforma.email]


def test_no_se_repite_el_correo(plataforma):
    api = cliente(plataforma)
    datos = {"email": "relevo@ejemplo.test", "first_name": "Ada", "last_name": "Lovelace"}
    api.post("/api/platform/admins/", datos, format="json")

    otra = api.post("/api/platform/admins/", datos, format="json")

    assert otra.status_code == 400


def test_restablecer_la_contrasena_la_enseña_una_vez(plataforma):
    api = cliente(plataforma)
    creada = api.post(
        "/api/platform/admins/",
        {"email": "relevo@ejemplo.test", "first_name": "Ada", "last_name": "Lovelace"},
        format="json",
    ).data

    nueva = api.post(f"/api/platform/admins/{creada['id']}/password/", format="json")

    assert nueva.status_code == 200
    assert nueva.data["password"] != creada["password"]
    assert User.objects.get(pk=creada["id"]).check_password(nueva.data["password"])


def test_no_se_puede_desactivar_la_unica_cuenta(plataforma):
    """Quedarse sin ninguna deja la instalación sin quien la administre.

    Y de ahí solo se sale abriendo un shell, que es lo que esta pantalla existe
    para no tener que hacer.
    """
    otra = User.objects.create_superuser(email="otra@ejemplo.test", password="X" * 14, tenant=None)

    # Con dos cuentas, desactivar una de ellas se puede.
    assert cliente(plataforma).delete(f"/api/platform/admins/{otra.pk}/").status_code == 204

    # Con una sola, no. Se intenta desde la otra, ya reactivada, para no chocar
    # antes con la regla de no desactivarse a uno mismo.
    otra.refresh_from_db()
    otra.is_active = True
    otra.save(update_fields=["is_active"])
    plataforma.is_active = False
    plataforma.save(update_fields=["is_active"])

    ultima = cliente(otra).delete(f"/api/platform/admins/{otra.pk}/")

    assert ultima.status_code == 400


def test_nadie_se_deja_a_si_mismo_fuera(plataforma):
    User.objects.create_superuser(email="otra@ejemplo.test", password="X" * 14, tenant=None)

    respuesta = cliente(plataforma).delete(f"/api/platform/admins/{plataforma.pk}/")

    assert respuesta.status_code == 400
    plataforma.refresh_from_db()
    assert plataforma.is_active is True


def test_el_administrador_de_una_empresa_no_ve_las_cuentas(company):
    suyo = User.objects.create_user(
        email="jefe@acme.test", password="X" * 14, tenant=company, role=Role.ADMIN
    )

    assert cliente(suyo).get("/api/platform/admins/").status_code == 403


# ----------------------------------------------- qué le falta a cada empresa
#
# El «¿y ahora qué?» de quien acaba de dar un alta. La lista lo dice sin que haya
# que abrir tres diálogos para averiguarlo.


def test_una_empresa_recien_creada_dice_que_le_falta_todo(plataforma):
    creada = cliente(plataforma).post(
        reverse("platform-companies"),
        {
            "company_name": "Nueva SL",
            "tax_id": "B22222222",
            "email": "jefa@nueva.test",
            "first_name": "Ana",
            "last_name": "Nueva",
        },
        format="json",
    )

    assert creada.status_code == 201
    # Identidad y credencial no las trae el alta, y dentro solo está quien la creó.
    assert creada.data["missing"] == ["identity", "application", "people"]


def test_cada_hueco_se_cierra_por_separado(plataforma, company):
    api = cliente(plataforma)

    def huecos():
        empresas = api.get(reverse("platform-companies")).data["companies"]
        return next(e for e in empresas if e["tax_id"] == company.tax_id)["missing"]

    assert "application" in huecos()

    api.post(
        f"/api/platform/companies/{company.id}/applications/",
        {"name": "GreenCityControl"},
        format="json",
    )

    assert "application" not in huecos()
    assert "identity" in huecos()

    api.put(
        reverse("platform-company-identity", args=[company.id]),
        {
            "name": "GreenCityControl",
            "issuer": "https://api.ejemplo.test/o",
            "domains": ["acme.test"],
        },
        format="json",
    )

    assert "identity" not in huecos()


def test_un_proveedor_apagado_cuenta_como_que_falta(plataforma, company):
    """Estar y no valer es lo mismo que no estar, y cuesta más de ver."""
    api = cliente(plataforma)
    api.put(
        reverse("platform-company-identity", args=[company.id]),
        {
            "name": "GreenCityControl",
            "issuer": "https://api.ejemplo.test/o",
            "domains": ["acme.test"],
            "is_active": False,
        },
        format="json",
    )

    empresas = api.get(reverse("platform-companies")).data["companies"]
    assert "identity" in next(e for e in empresas if e["tax_id"] == company.tax_id)["missing"]


def test_con_su_gente_dentro_ya_no_falta_gente(plataforma, company):
    User.objects.create_user(email="uno@acme.test", password="X" * 14, tenant=company)
    User.objects.create_user(email="dos@acme.test", password="X" * 14, tenant=company)

    empresas = cliente(plataforma).get(reverse("platform-companies")).data["companies"]

    assert "people" not in next(e for e in empresas if e["tax_id"] == company.tax_id)["missing"]


def test_no_se_crea_una_cuenta_que_no_podria_entrar(plataforma, company):
    """Un correo que ya usa alguien de una empresa deja la cuenta sin forma de entrar.

    Con dos cuentas del mismo correo, la pantalla de entrada pide el identificador
    fiscal para saber a cuál se refiere, y la de la instalación no tiene ninguno.
    Pasó en producción el 23/09/2026: se creó una, no pudo entrar, y hubo que
    desactivarla.
    """
    User.objects.create_user(email="repetido@acme.test", password="X" * 14, tenant=company)

    respuesta = cliente(plataforma).post(
        "/api/platform/admins/",
        {"email": "repetido@acme.test", "first_name": "Quien", "last_name": "Sea"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert company.name in respuesta.data["detail"]
    assert User.objects.filter(email="repetido@acme.test", tenant__isnull=True).count() == 0
