"""El estado de cada empresa, de un vistazo y sin datos de nadie.

Para ver un fallo antes de que llame el cliente: si su gente ficha, si su
aplicación habla, si su identidad se usa. Solo fechas y recuentos.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.tenants.platform_views import _callado, _estado_de_todas
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db

MADRID = ZoneInfo("Europe/Madrid")
#: Un lunes. Las fechas de abajo cuentan desde él.
LUNES = date(2026, 9, 21)


@pytest.fixture
def plataforma():
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


@pytest.mark.parametrize(
    ("ultimo", "callado"),
    [
        (None, False),
        (LUNES, False),
        (LUNES - timedelta(days=3), False),  # el viernes: sábado y domingo no cuentan
        (LUNES - timedelta(days=4), True),  # el jueves: el viernes entero sin nada
        (LUNES - timedelta(days=1), False),  # el domingo
    ],
)
def test_que_cuenta_como_callado(ultimo, callado):
    assert _callado(ultimo, LUNES) is callado


@freeze_time("2026-09-21 10:00:00+02:00")
def test_da_fechas_y_recuentos_y_ni_una_persona(plataforma):
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        curro = User.objects.create_user(
            email="curro@acme.test", password="X" * 14, tenant=empresa, role=Role.EMPLOYEE
        )
        User.objects.create_user(
            email="baja@acme.test", password="X" * 14, tenant=empresa, is_active=False
        )
        federada = User.objects.create_user(
            email="fede@acme.test", password="X" * 14, tenant=empresa, oidc_sub="sub-fede"
        )
        User.objects.filter(pk=federada.pk).update(
            last_login=datetime(2026, 9, 18, 9, 0, tzinfo=MADRID)
        )
        # El jueves a las 07:43. Con el viernes entero sin nada, avisa.
        Punch.objects.create(
            tenant=empresa,
            employee=curro,
            timestamp=datetime(2026, 9, 17, 7, 43, tzinfo=MADRID),
            punch_type=PunchType.IN,
            interval=PunchInterval.WORK,
        )
        app = Application.objects.create(
            tenant=empresa, name="Conector de ejemplo", scopes=[s.value for s in ApplicationScope]
        )
        credencial, _testigo = ApplicationCredential.issue(app, label="prueba")
        ApplicationCredential.objects_all_tenants.filter(pk=credencial.pk).update(
            last_used_at=timezone.now()
        )

    respuesta = cliente(plataforma).get("/api/platform/companies/")
    assert respuesta.status_code == 200
    estado = respuesta.data["companies"][0]["status"]

    assert estado["active_people"] == 2
    assert estado["last_punch_day"] == "2026-09-17"
    assert estado["punches_quiet"] is True
    assert estado["last_identity_sign_in_day"] == "2026-09-18"
    assert estado["identity_people"] == 1
    assert estado["applications_detail"] == [
        {"name": "Conector de ejemplo", "last_used": "2026-09-21", "quiet": False}
    ]

    texto = str(respuesta.data)
    assert "curro@acme.test" not in texto and "fede@acme.test" not in texto
    assert "07:43" not in texto and "05:43" not in texto, "la hora del fichaje no sale"


def test_una_empresa_sin_nada_no_sale_callada(plataforma):
    """Recién dada de alta no es una avería: sin fichajes todavía, sin aviso."""
    Tenant.objects.create(name="Nueva", tax_id="B22222222")
    estado = cliente(plataforma).get("/api/platform/companies/").data["companies"][0]["status"]
    assert estado["last_punch_day"] is None and estado["punches_quiet"] is False


def test_siete_consultas_para_todas_por_muchas_que_haya(django_assert_num_queries):
    """Eran cuatro; las tres de más son lo que la lista no miraba ---quién
    administra, si hay centro y si hay festivos---, y siguen sin crecer con el
    número de empresas."""
    for n in range(5):
        Tenant.objects.create(name=f"Empresa {n}", tax_id=f"B0000000{n}")
    with django_assert_num_queries(7):
        _estado_de_todas()


def test_una_identidad_usada_antes_de_anotar_fechas_no_dice_que_nadie_entro(plataforma):
    """Medido en devel: una persona entraba con la identidad desde hacía días, y como
    la fecha no se anotaba, la lista decía «Nadie ha entrado todavía con ella»."""
    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")
    with tenant_context(empresa.id):
        User.objects.create_user(
            email="fede@acme.test", password="X" * 14, tenant=empresa, oidc_sub="sub-fede"
        )
    estado = cliente(plataforma).get("/api/platform/companies/").data["companies"][0]["status"]
    assert estado["last_identity_sign_in_day"] is None
    assert estado["identity_people"] == 1


# ------------------------------------------------- qué le falta, sin falsas alarmas
#
# La lista decía «Lista» a una empresa sin nadie que la administrara, sin festivos y
# sin centro, y le pedía proveedor de identidad y aplicación a una que entra con
# contraseña y no los necesita.


def _fila(plataforma, empresa):
    empresas = cliente(plataforma).get("/api/platform/companies/").data["companies"]
    return next(e for e in empresas if e["id"] == str(empresa.id))


def _empresa_con_contrasena():
    """Una empresa que entra con contraseña, con centro y festivos de este año."""
    from apps.tenants.holidays import PublicHoliday
    from apps.users.models import Workplace

    empresa = Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        User.objects.create_user(
            email="jefa@acme.test", password="X" * 14, tenant=empresa, role=Role.ADMIN
        )
        User.objects.create_user(email="curro@acme.test", password="X" * 14, tenant=empresa)
        Workplace.objects.create(tenant=empresa, name="Oficina")
        PublicHoliday.objects.create(tenant=empresa, day=date(2026, 10, 12), name="Fiesta")
    return empresa


@freeze_time("2026-10-07 10:00:00+02:00")
def test_una_empresa_con_contrasena_no_echa_en_falta_identidad_ni_aplicacion(plataforma):
    empresa = _empresa_con_contrasena()
    assert _fila(plataforma, empresa)["missing"] == []


@freeze_time("2026-10-07 10:00:00+02:00")
def test_con_gente_federada_si_le_falta_la_identidad(plataforma):
    empresa = _empresa_con_contrasena()
    with tenant_context(empresa.id):
        User.objects.create_user(
            email="fede@acme.test", password=None, tenant=empresa, oidc_sub="sub-fede"
        )
    assert {"identity", "application"} <= set(_fila(plataforma, empresa)["missing"])


@freeze_time("2026-10-07 10:00:00+02:00")
def test_sin_administracion_activa_lo_dice_y_soporte_no_cuenta(plataforma):
    from apps.tenants.platform_views import support_account

    empresa = _empresa_con_contrasena()
    User.objects.filter(tenant=empresa, role=Role.ADMIN).update(is_active=False)
    support_account(empresa)

    assert "administrator" in _fila(plataforma, empresa)["missing"]


@freeze_time("2026-10-07 10:00:00+02:00")
def test_sin_festivos_de_este_ano_lo_dice(plataforma):
    from apps.tenants.holidays import PublicHoliday

    empresa = _empresa_con_contrasena()
    with tenant_context(empresa.id):
        PublicHoliday.objects.all().update(day=date(2025, 10, 13))

    assert _fila(plataforma, empresa)["missing"] == ["holidays"]


@freeze_time("2026-10-07 10:00:00+02:00")
def test_sin_centro_lo_dice(plataforma):
    from apps.users.models import Workplace

    empresa = _empresa_con_contrasena()
    with tenant_context(empresa.id):
        Workplace.objects.all().delete()

    assert _fila(plataforma, empresa)["missing"] == ["workplace"]


@freeze_time("2026-10-07 10:00:00+02:00")
def test_soporte_y_las_bajas_no_son_gente(plataforma):
    """Con solo quien la creó, la cuenta de soporte y una baja, no tiene a su gente."""
    from apps.tenants.platform_views import support_account

    empresa = Tenant.objects.create(name="Nueva", tax_id="B22222222")
    with tenant_context(empresa.id):
        User.objects.create_user(
            email="jefa@nueva.test", password="X" * 14, tenant=empresa, role=Role.ADMIN
        )
        User.objects.create_user(
            email="baja@nueva.test", password="X" * 14, tenant=empresa, is_active=False
        )
    support_account(empresa)

    fila = _fila(plataforma, empresa)
    assert "people" in fila["missing"]
    assert fila["status"]["active_people"] == 1
    assert fila["people"] == 2, "la baja cuenta en el total; soporte, no"


def test_una_empresa_con_gente_que_no_ha_fichado_nunca_sale_callada(plataforma):
    """«Sin fichajes todavía» no avisaba nunca, y una empresa con su gente dentro que
    no ha fichado ni una vez es justo la que hay que mirar."""
    with freeze_time("2026-09-14 10:00:00+02:00"):  # un lunes
        empresa = _empresa_con_contrasena()

    with freeze_time("2026-09-21 10:00:00+02:00"):  # una semana después
        estado = _fila(plataforma, empresa)["status"]

    assert estado["last_punch_day"] is None
    assert estado["punches_quiet"] is True


def test_sin_nadie_de_alta_no_sale_callada(plataforma):
    """Sin nadie que pueda fichar no hay avería que mirar."""
    with freeze_time("2026-09-14 10:00:00+02:00"):
        empresa = _empresa_con_contrasena()
        User.objects.filter(tenant=empresa).update(is_active=False)

    with freeze_time("2026-09-21 10:00:00+02:00"):
        estado = _fila(plataforma, empresa)["status"]

    assert estado["punches_quiet"] is False
