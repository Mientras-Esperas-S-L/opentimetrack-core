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
            tenant=empresa, name="GreenCityControl", scopes=[s.value for s in ApplicationScope]
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
    assert estado["applications_detail"] == [
        {"name": "GreenCityControl", "last_used": "2026-09-21", "quiet": False}
    ]

    texto = str(respuesta.data)
    assert "curro@acme.test" not in texto and "fede@acme.test" not in texto
    assert "07:43" not in texto and "05:43" not in texto, "la hora del fichaje no sale"


def test_una_empresa_sin_nada_no_sale_callada(plataforma):
    """Recién dada de alta no es una avería: sin fichajes todavía, sin aviso."""
    Tenant.objects.create(name="Nueva", tax_id="B22222222")
    estado = cliente(plataforma).get("/api/platform/companies/").data["companies"][0]["status"]
    assert estado["last_punch_day"] is None and estado["punches_quiet"] is False


def test_cuatro_consultas_para_todas_por_muchas_que_haya(django_assert_num_queries):
    for n in range(5):
        Tenant.objects.create(name=f"Empresa {n}", tax_id=f"B0000000{n}")
    with django_assert_num_queries(4):
        _estado_de_todas()
