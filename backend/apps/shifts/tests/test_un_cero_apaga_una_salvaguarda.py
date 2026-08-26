"""Bajar una regla por debajo del suelo legal no avisaba por la API.

La pantalla de ajustes sí avisa: tiene las `citations` con su `floor` y pinta el
campo en amarillo. Por la API no había nada, y ahí entran los conectores y los
scripts de migración.

Y no es un valor raro y ya. Medido: con el suelo de descanso entre jornadas en
doce horas, un cuadrante con ocho horas de descanso produce
`short_daily_rest`; poniendo el suelo a **cero** por la API, ese aviso
**desaparece**. Una salvaguarda del art. 34.3 se desactiva escribiendo un número,
y quien lo escribe no recibe ninguna señal.

**Se avisa y no se impide**, que es como funciona el resto de la pantalla y lo
que hace la validación de las fichas de convenio con `fatal=False`: el RD
1561/1995 baja algunos de estos suelos para sectores concretos, así que un valor
por debajo puede ser correcto y quien lo sabe es la empresa. Lo que no puede
pasar es que nadie lo diga.

En el rastro también: «12 → 0» no dice por sí solo que ese cero esté por debajo
de un mínimo legal, y quien lo lea dentro de dos años no tiene por qué saberse el
artículo.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.shifts.models import Shift
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"
LUNES, MARTES = date(2026, 5, 11), date(2026, 5, 12)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con turnos", tax_id="B91919191", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def equipo(company):
    """Alguien con dos turnos y ocho horas de descanso: incumple sin discusión."""
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        admin = User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Admin",
            last_name="Equis",
            role=Role.ADMIN,
        )
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Equis",
            department=obras,
        )
        Shift.objects.create(
            tenant=company, employee=quien, day=LUNES, segments=[{"start": "14:00", "end": "22:00"}]
        )
        Shift.objects.create(
            tenant=company,
            employee=quien,
            day=MARTES,
            segments=[{"start": "06:00", "end": "14:00"}],
        )
        yield {"admin": admin, "quien": quien}


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


def avisos_de_descanso(company, quien):
    """Con la empresa recargada, y no es un detalle.

    `WorkingTimeRules.for_company` recuerda las reglas en el objeto `Tenant`
    mientras dure la petición, así que reutilizar la misma instancia después de
    un PATCH lee las de antes. Eso convirtió la primera medición de esto en un
    «está bien» que no lo era.
    """
    fresca = Tenant.objects.get(pk=company.pk)
    with tenant_context(company.id):
        hallazgos = review_roster(company=fresca, first=LUNES, last=MARTES, employee=quien)
    return [h.code for h in hallazgos if h.code == "short_daily_rest"]


@pytest.mark.django_db
def test_el_cuadrante_avisa_mientras_el_suelo_sea_el_legal(company, equipo):
    """El control: sin esto, la prueba de abajo no distingue nada."""
    assert avisos_de_descanso(company, equipo["quien"]) == ["short_daily_rest"]


@pytest.mark.django_db
def test_un_cero_apaga_el_aviso_y_la_api_lo_dice(company, equipo):
    respuesta = como(equipo["admin"]).patch(
        "/api/working-time-rules/", {"daily_rest_hours": 0}, format="json"
    )

    assert respuesta.status_code == 200, "no se impide: la decisión es de la empresa"
    avisos = respuesta.data["warnings"]
    assert [a["field"] for a in avisos] == ["daily_rest_hours"]
    assert avisos[0]["basis"] == "Art. 34.3 ET"
    assert "12" in avisos[0]["message"]

    # Y el efecto que el aviso está señalando, medido.
    assert avisos_de_descanso(company, equipo["quien"]) == []


@pytest.mark.django_db
def test_el_rastro_dice_por_que_ese_numero_importa(
    company, equipo, django_capture_on_commit_callbacks
):
    # `record` escribe en `on_commit`, que en una prueba no corre solo: sin esto
    # el rastro no existe y el vacío pasaría por «no deja rastro».
    with django_capture_on_commit_callbacks(execute=True):
        como(equipo["admin"]).patch(
            "/api/working-time-rules/", {"daily_rest_hours": 0}, format="json"
        )

    rastro = AuditLog.objects.filter(action=AuditAction.RULES_CHANGED).order_by("-at").first()
    assert rastro is not None, "el cambio de reglas no dejó rastro"
    assert rastro.changes == {"daily_rest_hours": [12, 0]}
    assert "Art. 34.3 ET" in rastro.note, rastro.note


@pytest.mark.django_db
def test_un_valor_dentro_de_la_ley_no_avisa_de_nada(company, equipo):
    """El otro control. Un aviso que sale siempre no lo lee nadie."""
    respuesta = como(equipo["admin"]).patch(
        "/api/working-time-rules/", {"daily_rest_hours": 14}, format="json"
    )

    assert respuesta.status_code == 200
    assert respuesta.data["warnings"] == []
    assert avisos_de_descanso(company, equipo["quien"]) == ["short_daily_rest"]


@pytest.mark.django_db
def test_solo_avisa_de_lo_que_acaba_de_cambiar(company, equipo):
    """Repetir en cada respuesta lo que la empresa decidió hace meses es ruido."""
    cliente = como(equipo["admin"])
    cliente.patch("/api/working-time-rules/", {"daily_rest_hours": 0}, format="json")

    otra = cliente.patch("/api/working-time-rules/", {"roster_notice_days": 9}, format="json")

    assert otra.status_code == 200
    assert [a["field"] for a in otra.data["warnings"]] == []
    with tenant_context(company.id):
        assert WorkingTimeRules.objects.get(tenant=company).daily_rest_hours == 0


@pytest.mark.django_db
def test_el_descanso_semanal_tambien_lleva_su_articulo(company, equipo):
    """Para que no sea una regla escrita para un solo campo."""
    respuesta = como(equipo["admin"]).patch(
        "/api/working-time-rules/", {"weekly_rest_hours": 10}, format="json"
    )

    avisos = respuesta.data["warnings"]
    assert [a["basis"] for a in avisos] == ["Art. 37.1 ET"]
    assert "36" in avisos[0]["message"]
