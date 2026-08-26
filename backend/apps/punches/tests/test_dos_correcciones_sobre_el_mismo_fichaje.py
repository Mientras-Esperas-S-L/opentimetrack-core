"""Aprobar dos correcciones del mismo asiento dejaba dos entradas activas.

Nada impide pedir dos correcciones sobre el mismo fichaje, y no debería: te
deniegan una y pides otra con mejor motivo. Lo que no puede pasar es que se
apliquen las dos.

Medido **sin concurrencia de por medio** ---dos peticiones seguidas y dos
aprobaciones seguidas, que es un camino normal del producto---:

| | Fichajes de esa persona |
|---|---|
| Antes | 3: `IN` activo, `IN` activo, `IN` anulado |
| Después | 2: `IN` activo, `IN` anulado |

Dos entradas activas donde había una. El registro decía que la persona entró dos
veces sin salir, y eso rompe el cómputo del día: la jornada no cierra, el
cuadrante no cuadra y el informe que se entrega lleva un asiento que no ocurrió.

El motivo era mecánico. `approve_correction` con un cambio de hora crea el
sustituto y anula el original; la segunda vez anulaba un fichaje **ya anulado**
---o sea, nada--- y creaba otro sustituto encima.

Se rechaza en vez de aplicarse: el asiento que esa solicitud describía ya no
existe. Y la vía correcta sigue abierta --- pedir una corrección nueva sobre el
fichaje vigente, que es el que hay que discutir ahora.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, CorrectionStatus
from apps.punches.models import Punch, PunchCorrection, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con correcciones", tax_id="B16161616", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def escena(company):
    """Una persona con un fichaje, y quien puede resolver sus solicitudes."""
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Jefa",
            last_name="Equis",
            role=Role.MANAGER,
            department=obras,
        )
        obras.managers.add(jefa)
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Equis",
            department=obras,
        )
        yield {
            "jefa": jefa,
            "quien": quien,
            "fichaje": Punch.objects.create(
                tenant=company,
                employee=quien,
                punch_type=PunchType.IN,
                timestamp=timezone.now() - timedelta(days=2),
            ),
        }


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


def pide(escena, horas):
    respuesta = como(escena["quien"]).post(
        "/api/corrections/",
        {
            "kind": CorrectionKind.MODIFY,
            "target": str(escena["fichaje"].pk),
            "proposed_timestamp": (timezone.now() - timedelta(days=2, hours=horas)).isoformat(),
            "reason": f"Entré {horas} horas antes de lo que dice el registro",
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.data
    return respuesta.data["id"]


@pytest.mark.django_db
def test_pedir_dos_correcciones_del_mismo_fichaje_sigue_valiendo(company, escena):
    """El control, y es deliberado: te deniegan una y pides otra."""
    primera, segunda = pide(escena, 1), pide(escena, 3)

    assert primera != segunda
    with tenant_context(company.id):
        assert PunchCorrection.objects.filter(target=escena["fichaje"]).count() == 2


@pytest.mark.django_db
def test_la_segunda_no_se_aplica_encima_de_la_primera(company, escena):
    primera, segunda = pide(escena, 1), pide(escena, 3)
    jefa = como(escena["jefa"])

    assert jefa.post(f"/api/corrections/{primera}/approve/", {}, format="json").status_code == 200

    respuesta = jefa.post(f"/api/corrections/{segunda}/approve/", {}, format="json")
    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "target_already_changed"


@pytest.mark.django_db
def test_y_el_registro_queda_con_una_sola_entrada_activa(company, escena):
    """Lo que el rechazo protege, dicho en el registro."""
    primera, segunda = pide(escena, 1), pide(escena, 3)
    jefa = como(escena["jefa"])
    jefa.post(f"/api/corrections/{primera}/approve/", {}, format="json")
    jefa.post(f"/api/corrections/{segunda}/approve/", {}, format="json")

    with tenant_context(company.id):
        activos = Punch.objects.filter(employee=escena["quien"], is_active=True)
        assert activos.count() == 1, [(p.punch_type, p.timestamp) for p in activos]
        # Y el original sigue legible, anulado: no se borra nada.
        escena["fichaje"].refresh_from_db()
        assert not escena["fichaje"].is_active


@pytest.mark.django_db
def test_la_segunda_se_queda_pendiente_para_poder_retirarla(company, escena):
    """No se resuelve sola: quien la pidió tiene que ver qué pasó con ella."""
    primera, segunda = pide(escena, 1), pide(escena, 3)
    jefa = como(escena["jefa"])
    jefa.post(f"/api/corrections/{primera}/approve/", {}, format="json")
    jefa.post(f"/api/corrections/{segunda}/approve/", {}, format="json")

    with tenant_context(company.id):
        quedo = PunchCorrection.objects.get(pk=segunda)
    assert quedo.status == CorrectionStatus.PENDING
    assert quedo.result_id is None


@pytest.mark.django_db
def test_rechazarla_sigue_siendo_posible(company, escena):
    """Es la salida natural: el asiento que describía ya no existe."""
    primera, segunda = pide(escena, 1), pide(escena, 3)
    jefa = como(escena["jefa"])
    jefa.post(f"/api/corrections/{primera}/approve/", {}, format="json")

    respuesta = jefa.post(
        f"/api/corrections/{segunda}/reject/",
        {"note": "El fichaje ya se corrigió por la otra vía"},
        format="json",
    )

    assert respuesta.status_code == 200
    with tenant_context(company.id):
        assert PunchCorrection.objects.get(pk=segunda).status == CorrectionStatus.REJECTED


@pytest.mark.django_db
def test_una_sola_correccion_se_aplica_como_siempre(company, escena):
    """El otro control: el arreglo no puede estorbar al caso normal."""
    solo = pide(escena, 1)

    assert (
        como(escena["jefa"])
        .post(f"/api/corrections/{solo}/approve/", {}, format="json")
        .status_code
        == 200
    )
    with tenant_context(company.id):
        assert Punch.objects.filter(employee=escena["quien"], is_active=True).count() == 1
