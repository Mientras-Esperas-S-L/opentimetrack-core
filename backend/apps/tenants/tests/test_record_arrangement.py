"""Cómo se organizó el registro de jornada. Art. 34.9, párrafo segundo.

«Mediante negociación colectiva o acuerdo de empresa o, en su defecto, decisión
del empresario previa consulta con los representantes legales de los
trabajadores en la empresa, se organizará y documentará este registro de
jornada.»

El artículo pide dos cosas y el producto solo hacía una: registraba la jornada y
no había **dónde escribir** con qué amparo se organizó ese registro. Es lo
primero que una inspección pide después de los propios registros, antes que
ningún fichaje, porque decide si el sistema tiene respaldo.

Las tres vías son excluyentes y están ordenadas: la decisión del empresario es
la de «en su defecto», y solo esa arrastra la consulta previa. Esa diferencia es
justo la que decide si faltaba una consulta, así que no puede quedar en manos de
cómo lo escribiera cada uno.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.tenants.rules import RecordArrangement, RecordBasis
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
RUTA = "/api/company/record-arrangement/"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def gente(empresa):
    with tenant_context(empresa.id):
        yield {
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Luisa",
                role=Role.ADMIN,
            ),
            "operario": User.objects.create_user(
                email="curro@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Curro",
            ),
        }


def como(quien):
    client = APIClient()
    client.force_authenticate(user=quien)
    return client


@pytest.mark.django_db
def test_al_principio_no_consta_y_lo_dice(empresa, gente):
    """Vacío es una respuesta, y la correcta: nadie lo ha declarado todavía.

    Lo que no puede es inventarse una vía por defecto. Poner «convenio
    colectivo» porque es lo más común dejaría a la empresa con una declaración
    que no ha hecho, y esa declaración es la que se enseña a una inspección.
    """
    with tenant_context(empresa.id):
        respuesta = como(gente["jefa"]).get(RUTA)

    assert respuesta.status_code == 200
    assert respuesta.json()["basis"] == ""
    assert respuesta.json()["missing_consultation"] is False


@pytest.mark.django_db
def test_declarar_un_convenio(empresa, gente):
    with tenant_context(empresa.id):
        respuesta = como(gente["jefa"]).patch(
            RUTA,
            {
                "basis": RecordBasis.COLLECTIVE,
                "reference": "Convenio del metal de Sevilla, art. 22",
                "in_force_since": "2023-05-01",
            },
            format="json",
        )

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["missing_consultation"] is False
    with tenant_context(empresa.id):
        assert RecordArrangement.for_company(empresa).basis == RecordBasis.COLLECTIVE


@pytest.mark.django_db
def test_la_decision_del_empresario_sin_consulta_se_señala(empresa, gente):
    """El hueco concreto que el artículo señala.

    Y el único que el producto puede afirmar mirando sus propios datos: las
    otras dos vías son un acuerdo, y un acuerdo no lleva consulta previa porque
    **es** la negociación.
    """
    with tenant_context(empresa.id):
        respuesta = como(gente["jefa"]).patch(
            RUTA,
            {
                "basis": RecordBasis.EMPLOYER,
                "reference": "Decisión de dirección de 12 de enero de 2024",
                "in_force_since": "2024-01-15",
            },
            format="json",
        )

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["missing_consultation"] is True


@pytest.mark.django_db
def test_con_la_fecha_de_la_consulta_deja_de_faltar(empresa, gente):
    with tenant_context(empresa.id):
        cliente = como(gente["jefa"])
        cliente.patch(
            RUTA,
            {
                "basis": RecordBasis.EMPLOYER,
                "reference": "Decisión de dirección de 12 de enero de 2024",
            },
            format="json",
        )
        respuesta = cliente.patch(RUTA, {"consulted_on": "2024-01-10"}, format="json")

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["missing_consultation"] is False


@pytest.mark.django_db
def test_una_via_sin_decir_cual_se_rechaza(empresa, gente):
    """«Convenio colectivo» a secas no documenta nada: no hay contra qué
    comprobarlo."""
    with tenant_context(empresa.id):
        respuesta = como(gente["jefa"]).patch(
            RUTA, {"basis": RecordBasis.COLLECTIVE}, format="json"
        )

    assert respuesta.status_code == 400
    assert "reference" in str(respuesta.json())


@pytest.mark.django_db
def test_un_acuerdo_no_lleva_consulta_previa(empresa, gente):
    """Una fecha de consulta junto a un convenio sugiere un trámite que no
    existe, y quien lea la ficha luego no sabrá cuál de los dos hechos vale."""
    with tenant_context(empresa.id):
        respuesta = como(gente["jefa"]).patch(
            RUTA,
            {
                "basis": RecordBasis.COLLECTIVE,
                "reference": "Convenio del metal de Sevilla",
                "consulted_on": "2024-01-10",
            },
            format="json",
        )

    assert respuesta.status_code == 400
    assert "consulted_on" in str(respuesta.json())


@pytest.mark.django_db
def test_lo_lee_cualquiera_de_la_empresa(empresa, gente):
    """No es generosidad: el mismo párrafo pone el registro a disposición de las
    personas trabajadoras y de sus representantes, y saber con qué amparo se
    organizó es lo que permite comprobar que se consultó a quien tocaba."""
    with tenant_context(empresa.id):
        assert como(gente["operario"]).get(RUTA).status_code == 200


@pytest.mark.django_db
def test_pero_solo_lo_escribe_quien_administra(empresa, gente):
    with tenant_context(empresa.id):
        respuesta = como(gente["operario"]).patch(
            RUTA, {"basis": RecordBasis.COLLECTIVE, "reference": "El que sea"}, format="json"
        )

    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_queda_en_el_registro_de_actividad(empresa, gente, django_capture_on_commit_callbacks):
    """Es de lo que más falta hace que deje rastro: quién dijo que había
    convenio, o que se consultó, y cuándo lo dijo.

    Con `django_capture_on_commit_callbacks` porque la entrada se guarda
    **después del commit**: una que describiera algo que luego se deshace sería
    mentira, y una mentira en la auditoría es peor que un hueco. En una prueba
    sin transacción real ese commit no llega nunca, y sin esto la comprobación
    daría vacío por el motivo equivocado.
    """
    from apps.audit.models import AuditLog

    with tenant_context(empresa.id):
        with django_capture_on_commit_callbacks(execute=True):
            como(gente["jefa"]).patch(
                RUTA,
                {"basis": RecordBasis.COMPANY, "reference": "Acuerdo de 3 de marzo con el comité"},
                format="json",
            )

        entradas = AuditLog.objects.filter(actor=gente["jefa"])
        assert entradas.exists()
        assert any("34.9" in (e.note or "") for e in entradas)


@pytest.mark.django_db
def test_cada_empresa_la_suya(empresa, gente, db):
    """Lo de siempre, y por eso se comprueba: una empresa no puede leer ni
    tocar la declaración de otra."""
    vecina = Tenant.objects.create(
        name="Vecina S.L.", tax_id="B22222222", time_zone="Europe/Madrid"
    )
    with tenant_context(vecina.id):
        de_al_lado = User.objects.create_user(
            email="jefe@vecina.example",
            password=PASSWORD,
            tenant=vecina,
            first_name="Otro",
            role=Role.ADMIN,
        )

    with tenant_context(empresa.id):
        como(gente["jefa"]).patch(
            RUTA,
            {"basis": RecordBasis.COLLECTIVE, "reference": "El de aquí"},
            format="json",
        )

    with tenant_context(vecina.id):
        respuesta = como(de_al_lado).get(RUTA)

    assert respuesta.status_code == 200
    assert respuesta.json()["reference"] == "", "estaba leyendo la de la otra empresa"
