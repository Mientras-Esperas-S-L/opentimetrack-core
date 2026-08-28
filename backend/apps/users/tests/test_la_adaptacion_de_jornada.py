"""La solicitud de adaptación de jornada del art. 34.8, y su respuesta.

El derecho es de 2019 y de los más usados que hay: quien tiene hijos menores de
doce años puede pedir cambiar la duración, la distribución o la forma de prestar
su jornada ---incluido pasar a trabajo a distancia--- para conciliar.

El producto sabía la **consecuencia** ---un fichaje puede marcarse como trabajado
bajo una adaptación, art. 3.i--- y no tenía el **expediente**, que es donde está
la obligación:

- Un proceso de negociación de **quince días como máximo**.
- Respuesta **por escrito**: aceptar, proponer una alternativa o negarse.
- **Motivar** en los dos últimos casos.

Lo que se impide y lo que se avisa no es lo mismo, y la diferencia sale del
artículo: la motivación se exige porque «se motivará» no admite lectura; el plazo
se avisa porque se incumple dejando pasar el tiempo y no hay nada que impedir.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import AdaptationStatus, Role, ScheduleAdaptation, User

PASSWORD = "a-sufficiently-long-password"

PIDIÓ = date(2026, 8, 3)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Concilia SL", tax_id="B25252525", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="admin@concilia.example",
            password=PASSWORD,
            tenant=company,
            first_name="Admin",
            last_name="Istra",
            role=Role.ADMIN,
        )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="madre@concilia.example",
            password=PASSWORD,
            tenant=company,
            first_name="Carmen",
            last_name="Ruiz",
        )


def como(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


def pide(client, quien, **extra):
    cuerpo = {
        "employee": str(quien.id),
        "requested_on": PIDIÓ.isoformat(),
        "asked_for": "Entrar a las 9:30 para poder llevar al niño al colegio.",
    }
    cuerpo.update(extra)
    return client.post("/api/schedule-adaptations/", cuerpo, format="json")


@pytest.mark.django_db
def test_se_registra_la_solicitud_y_queda_en_negociacion(company, admin, quien):
    with tenant_context(company.id):
        respuesta = pide(como(admin), quien)
        assert respuesta.status_code == 201, respuesta.json()
        assert respuesta.json()["status"] == AdaptationStatus.PENDING


@pytest.mark.django_db
@pytest.mark.parametrize(
    "estado",
    [AdaptationStatus.REFUSED, AdaptationStatus.ALTERNATIVE],
    ids=["negativa", "alternativa"],
)
def test_negarse_o_proponer_otra_cosa_sin_motivo_no_se_puede(company, admin, quien, estado):
    """«En los dos últimos casos, **se motivará**.»

    Aquí se impide en vez de avisar, y es la excepción a la regla de esta
    auditoría: el artículo no deja margen. Una negativa sin motivo escrito no es
    una negativa mal documentada, es un incumplimiento del art. 34.8.

    La alternativa entra en el mismo saco a propósito. Es el resultado normal de
    una negociación y aun así hay que decir por qué, porque para quien la recibe
    es un «no» a lo que pidió.
    """
    with tenant_context(company.id):
        client = como(admin)
        creada = pide(client, quien).json()

        sin_motivo = client.patch(
            f"/api/schedule-adaptations/{creada['id']}/",
            {"status": estado, "answered_on": "2026-08-10"},
            format="json",
        )
        assert sin_motivo.status_code == 400
        assert "answer" in str(sin_motivo.json())

        con_motivo = client.patch(
            f"/api/schedule-adaptations/{creada['id']}/",
            {
                "status": estado,
                "answered_on": "2026-08-10",
                "answer": "El turno de mañana no se puede cubrir de otra forma en esta sección.",
            },
            format="json",
        )
        assert con_motivo.status_code == 200, con_motivo.json()
        # Y queda dicho quién contestó: una respuesta escrita sin firma no lo es.
        assert con_motivo.json()["answered_by"] == str(admin.id)


@pytest.mark.django_db
def test_aceptar_no_pide_motivo(company, admin, quien):
    """El contraste de la regla anterior.

    Si la motivación se exigiera siempre, esto fallaría y el producto estaría
    inventándose una obligación: quien dice que sí no tiene nada que justificar,
    y el artículo solo la pide para los otros dos casos.
    """
    with tenant_context(company.id):
        client = como(admin)
        creada = pide(client, quien).json()

        respuesta = client.patch(
            f"/api/schedule-adaptations/{creada['id']}/",
            {"status": AdaptationStatus.ACCEPTED, "answered_on": "2026-08-06"},
            format="json",
        )
        assert respuesta.status_code == 200, respuesta.json()


@pytest.mark.django_db
def test_una_respuesta_sin_fecha_deja_el_plazo_sin_medir(company, admin, quien):
    """Sin `answered_on` no se puede decir si se contestó dentro de los quince
    días, que es justo lo que este expediente existe para poder mirar."""
    with tenant_context(company.id):
        client = como(admin)
        creada = pide(client, quien).json()

        respuesta = client.patch(
            f"/api/schedule-adaptations/{creada['id']}/",
            {"status": AdaptationStatus.ACCEPTED},
            format="json",
        )
        assert respuesta.status_code == 400
        assert "answered_on" in str(respuesta.json())


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dias", "avisa"),
    [(15, False), (16, True), (40, True)],
    ids=["el día quince", "el dieciséis", "un mes largo"],
)
def test_el_plazo_de_quince_dias_avisa_al_pasarse(company, admin, quien, dias, avisa):
    """Quince días **incluidos**: el aviso empieza el dieciséis.

    El borde va dentro porque el artículo da quince días para negociar, no
    catorce, y avisar el día quince sería acusar a quien está en plazo.
    """
    with tenant_context(company.id):
        ScheduleAdaptation.objects.create(
            tenant=company,
            employee=quien,
            requested_on=PIDIÓ,
            asked_for="Jornada continua los viernes.",
        )
        hasta = PIDIÓ + timedelta(days=dias)
        codigos = [f.code for f in review_roster(company=company, first=PIDIÓ, last=hasta)]
        assert ("adaptation_answer_overdue" in codigos) is avisa


@pytest.mark.django_db
def test_una_ya_contestada_no_avisa(company, admin, quien):
    """El contraste del plazo. Sin él, «avisa a las no contestadas» y «avisa a
    todas» se ven igual."""
    with tenant_context(company.id):
        ScheduleAdaptation.objects.create(
            tenant=company,
            employee=quien,
            requested_on=PIDIÓ,
            asked_for="Jornada continua los viernes.",
            status=AdaptationStatus.ACCEPTED,
            answered_on=PIDIÓ + timedelta(days=3),
        )
        codigos = [
            f.code
            for f in review_roster(company=company, first=PIDIÓ, last=PIDIÓ + timedelta(days=40))
        ]
        assert "adaptation_answer_overdue" not in codigos


@pytest.mark.django_db
def test_no_se_cuela_la_solicitud_de_otra_empresa(company, admin, quien):
    """`ScheduleAdaptation` sí es `TenantOwnedModel`, así que su gestor acota
    solo. La prueba fija el resultado, no el mecanismo."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B26262626", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        suya = User.objects.create_user(
            email="suya@vecina.example", password=PASSWORD, tenant=vecina, first_name="Ajena"
        )
        ScheduleAdaptation.objects.create(
            tenant=vecina, employee=suya, requested_on=PIDIÓ, asked_for="Lo suyo."
        )

    with tenant_context(company.id):
        ScheduleAdaptation.objects.create(
            tenant=company, employee=quien, requested_on=PIDIÓ, asked_for="Lo nuestro."
        )
        avisos = review_roster(company=company, first=PIDIÓ, last=PIDIÓ + timedelta(days=40))
        de_quien = {f.employee_id for f in avisos if f.code == "adaptation_answer_overdue"}

        assert quien.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suya.id not in de_quien
