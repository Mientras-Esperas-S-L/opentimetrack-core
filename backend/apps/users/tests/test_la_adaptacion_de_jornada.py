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


# ------------------------------------------------- quién puede qué, art. 34.8


@pytest.mark.django_db
def test_la_pide_quien_trabaja_para_si_mismo(company, quien):
    """El derecho es suyo, así que el expediente lo abre quien lo ejerce.

    Antes de la parte B esto daba 403: el recurso escribía solo administración.
    Un expediente que solo pudiera abrir la empresa dejaría sin rastro justo lo
    que hay que poder mirar ---si se pidió y cuándo---.
    """
    with tenant_context(company.id):
        client = como(quien)
        respuesta = client.post(
            "/api/schedule-adaptations/",
            {
                "requested_on": PIDIÓ.isoformat(),
                "asked_for": "Entrar a las 9:30 para llevar al niño al colegio.",
            },
            format="json",
        )
        assert respuesta.status_code == 201, respuesta.json()
        assert respuesta.json()["employee"] == str(quien.id)


@pytest.mark.django_db
def test_nadie_pide_por_otra_persona(company, quien):
    """El contraste del anterior. Sin esta regla, cualquiera abriría expedientes
    de conciliación a nombre de un compañero."""
    with tenant_context(company.id):
        otra = User.objects.create_user(
            email="otra@concilia.example", password=PASSWORD, tenant=company, first_name="Otra"
        )
        respuesta = como(quien).post(
            "/api/schedule-adaptations/",
            {
                "employee": str(otra.id),
                "requested_on": PIDIÓ.isoformat(),
                "asked_for": "Lo que sea.",
            },
            format="json",
        )
        # 403: es quién eres, no en qué estado está la solicitud.
        assert respuesta.status_code == 403, respuesta.json()


@pytest.mark.django_db
def test_quien_trabaja_no_se_contesta_a_si_mismo(company, quien):
    """Aceptar la propia solicitud sería resolver en causa propia."""
    with tenant_context(company.id):
        suya = ScheduleAdaptation.objects.create(
            tenant=company, employee=quien, requested_on=PIDIÓ, asked_for="Entrar más tarde."
        )
        respuesta = como(quien).patch(
            f"/api/schedule-adaptations/{suya.id}/",
            {"status": AdaptationStatus.ACCEPTED, "answered_on": "2026-08-06"},
            format="json",
        )
        assert respuesta.status_code == 403, respuesta.json()


@pytest.mark.django_db
def test_retirar_la_propia_solicitud_sí_es_suyo(company, quien):
    """Dejar de pedir algo no es decidir sobre ello.

    El mismo criterio que en las ausencias: retirar una petición propia que
    nadie ha resuelto es arrepentirse de pedir, y exigir a administración para
    eso convertiría en trámite lo que no lo es.
    """
    with tenant_context(company.id):
        suya = ScheduleAdaptation.objects.create(
            tenant=company, employee=quien, requested_on=PIDIÓ, asked_for="Entrar más tarde."
        )
        respuesta = como(quien).patch(
            f"/api/schedule-adaptations/{suya.id}/",
            {"status": AdaptationStatus.WITHDRAWN},
            format="json",
        )
        assert respuesta.status_code == 200, respuesta.json()
        assert respuesta.json()["status"] == AdaptationStatus.WITHDRAWN


@pytest.mark.django_db
def test_no_se_puede_retirar_la_de_otra_persona(company, quien):
    """El contraste del anterior: «retirar es de quien la pidió», no de
    cualquiera que pase por ahí."""
    with tenant_context(company.id):
        otra = User.objects.create_user(
            email="tercera@concilia.example", password=PASSWORD, tenant=company, first_name="Ter"
        )
        suya_de_otra = ScheduleAdaptation.objects.create(
            tenant=company, employee=otra, requested_on=PIDIÓ, asked_for="Lo suyo."
        )
        respuesta = como(quien).patch(
            f"/api/schedule-adaptations/{suya_de_otra.id}/",
            {"status": AdaptationStatus.WITHDRAWN},
            format="json",
        )
        # No la ve siquiera: para quien no gestiona, el listado son las suyas.
        assert respuesta.status_code == 404


@pytest.mark.django_db
def test_quien_no_gestiona_solo_ve_las_suyas(company, quien):
    with tenant_context(company.id):
        otra = User.objects.create_user(
            email="cuarta@concilia.example", password=PASSWORD, tenant=company, first_name="Cua"
        )
        ScheduleAdaptation.objects.create(
            tenant=company, employee=quien, requested_on=PIDIÓ, asked_for="La mía."
        )
        ScheduleAdaptation.objects.create(
            tenant=company, employee=otra, requested_on=PIDIÓ, asked_for="La suya."
        )

        listado = como(quien).get("/api/schedule-adaptations/").json()
        assert [f["employee"] for f in listado["results"]] == [str(quien.id)]
