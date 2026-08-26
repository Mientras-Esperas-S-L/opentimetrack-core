"""Una propuesta equivocada no tenía marcha atrás.

Cuando la empresa propone cambiar un asiento, la corrección queda esperando la
conformidad de la persona (art. 4.b). Desde ahí solo había tres salidas ---que la
acepte, que la discuta, o que la empresa la aplique al vencer el plazo--- y
ninguna era «nos hemos equivocado». Medido por la API antes de arreglarlo:

| intento | respuesta |
|---|---|
| rechazarla | 409 `awaiting_the_employee` |
| aprobarla | 409 `awaiting_the_employee` |
| borrarla | 405 |
| retirarla / cancelarla | 404, no existían |

Lo que eso deja es una propuesta errónea que **obliga a actuar a la otra parte**:
la persona ha recibido un aviso de un cambio que la empresa ya sabe que está mal,
y tiene que discutirlo para pararlo. El art. 4.b pide el acuerdo de las dos partes
para tocar un asiento; hacer que la persona gestione el error de la empresa es lo
contrario.

Y el resumen decía desde el principio que estas propuestas «se pueden retirar o
aplicar». Lo de aplicar estaba; lo de retirar, no.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionStatus, PunchCorrection
from apps.punches.models import Punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Retiradas", tax_id="B90600001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )
        otra = User.objects.create_user(
            email="otra@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Otra",
            last_name="Jefa",
            role=Role.ADMIN,
        )
        obrero = User.objects.create_user(
            email="obrero@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Obrero",
            last_name="Equis",
        )
        fichaje = Punch.objects.create(
            tenant=empresa,
            employee=obrero,
            punch_type="IN",
            timestamp=timezone.now() - timedelta(hours=4),
            source="WEB",
        )
        yield {
            "empresa": empresa,
            "jefa": jefa,
            "otra": otra,
            "obrero": obrero,
            "fichaje": fichaje,
        }


def como(quien):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente


def proponer(mundo, *, sobre=None):
    """La empresa propone un cambio sobre el fichaje de alguien."""
    persona = sobre or mundo["obrero"]
    fichaje = mundo["fichaje"]
    respuesta = como(mundo["jefa"]).post(
        "/api/corrections/",
        {
            "employee": str(persona.pk),
            "target": str(fichaje.pk),
            "kind": "MODIFY",
            "proposed_timestamp": (fichaje.timestamp + timedelta(hours=3)).isoformat(),
            "reason": "me he equivocado al proponer esto",
        },
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.content
    assert respuesta.json()["status"] == CorrectionStatus.AWAITING_EMPLOYEE
    return respuesta.json()["id"]


@pytest.mark.django_db
def test_la_empresa_retira_su_propuesta_y_el_asiento_no_se_toca(
    mundo, django_capture_on_commit_callbacks
):
    cual = proponer(mundo)

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = como(mundo["jefa"]).post(
            f"/api/corrections/{cual}/withdraw/", {"note": "era otra persona"}, format="json"
        )

    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["status"] == CorrectionStatus.WITHDRAWN

    with tenant_context(mundo["empresa"].id):
        mundo["fichaje"].refresh_from_db()
        antes = timezone.now() - timedelta(hours=4)
    # El asiento se queda exactamente como estaba: retirar no es corregir.
    assert abs((mundo["fichaje"].timestamp - antes).total_seconds()) < 60


@pytest.mark.django_db
def test_se_le_avisa_a_quien_esperaba_una_respuesta(
    mundo, django_capture_on_commit_callbacks, mailoutbox
):
    cual = proponer(mundo)
    mailoutbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        como(mundo["jefa"]).post(f"/api/corrections/{cual}/withdraw/", {}, format="json")

    assert len(mailoutbox) == 1, "se le pidió una respuesta y nadie le dijo que ya no hacía falta"
    assert mailoutbox[0].to == ["obrero@example.com"]


@pytest.mark.django_db
def test_solo_se_retira_lo_que_esta_esperando(mundo):
    cual = proponer(mundo)
    como(mundo["jefa"]).post(f"/api/corrections/{cual}/withdraw/", {}, format="json")

    otra_vez = como(mundo["jefa"]).post(f"/api/corrections/{cual}/withdraw/", {}, format="json")
    assert otra_vez.status_code == 409
    assert otra_vez.json()["error"]["code"] == "not_awaiting"


@pytest.mark.django_db
def test_una_solicitud_de_la_persona_no_se_retira_asi(mundo):
    """Lo que pide el trabajador se rechaza, que es otra cosa y deja otro rastro."""
    suya = como(mundo["obrero"]).post(
        "/api/corrections/",
        {
            "target": str(mundo["fichaje"].pk),
            "kind": "MODIFY",
            "proposed_timestamp": (mundo["fichaje"].timestamp + timedelta(hours=1)).isoformat(),
            "reason": "fiche mal, era mas tarde",
        },
        format="json",
    )
    assert suya.status_code == 201
    assert suya.json()["status"] == CorrectionStatus.PENDING

    respuesta = como(mundo["jefa"]).post(
        f"/api/corrections/{suya.json()['id']}/withdraw/", {}, format="json"
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "not_awaiting"


@pytest.mark.django_db
def test_retirar_una_propuesta_sobre_uno_mismo_pasa_por_otra_persona(mundo):
    """La línea de la vuelta 72: no cambiar nada también es decidir.

    Si la propuesta es sobre el fichaje de quien la retira, retirarla en
    solitario sería decidir sobre su propio registro.
    """
    with tenant_context(mundo["empresa"].id):
        suyo = Punch.objects.create(
            tenant=mundo["empresa"],
            employee=mundo["jefa"],
            punch_type="IN",
            timestamp=timezone.now() - timedelta(hours=5),
            source="WEB",
        )

    creada = como(mundo["otra"]).post(
        "/api/corrections/",
        {
            "employee": str(mundo["jefa"].pk),
            "target": str(suyo.pk),
            "kind": "MODIFY",
            "proposed_timestamp": (suyo.timestamp + timedelta(hours=2)).isoformat(),
            "reason": "le sobra una hora que no trabajo",
        },
        format="json",
    )
    assert creada.status_code == 201, creada.content

    # La propia interesada no puede archivarla ella sola.
    sola = como(mundo["jefa"]).post(
        f"/api/corrections/{creada.json()['id']}/withdraw/", {}, format="json"
    )
    assert sola.status_code == 409
    assert sola.json()["error"]["code"] == "cannot_decide_your_own"

    # Otra sí.
    con_dos = como(mundo["otra"]).post(
        f"/api/corrections/{creada.json()['id']}/withdraw/", {}, format="json"
    )
    assert con_dos.status_code == 200


@pytest.mark.django_db
def test_queda_en_el_rastro_con_nombre_y_apellidos(mundo, django_capture_on_commit_callbacks):
    from apps.audit.models import AuditAction, AuditLog

    cual = proponer(mundo)
    # El rastro se escribe en `on_commit`, a propósito: una entrada que describe
    # algo que luego se deshizo sería una mentira.
    with django_capture_on_commit_callbacks(execute=True):
        como(mundo["jefa"]).post(
            f"/api/corrections/{cual}/withdraw/", {"note": "error mio"}, format="json"
        )

    with tenant_context(mundo["empresa"].id):
        anotado = AuditLog.objects.filter(
            tenant=mundo["empresa"], action=AuditAction.CORRECTION_WITHDRAWN
        ).first()

    assert anotado is not None, "retirar una propuesta no dejaba rastro"
    assert anotado.actor_id == mundo["jefa"].pk
    assert anotado.target_label == "Obrero Equis"


@pytest.mark.django_db
def test_un_operario_no_retira_nada(mundo):
    cual = proponer(mundo)

    assert (
        como(mundo["obrero"])
        .post(f"/api/corrections/{cual}/withdraw/", {}, format="json")
        .status_code
        == 403
    )
    with tenant_context(mundo["empresa"].id):
        assert PunchCorrection.objects.get(pk=cual).status == CorrectionStatus.AWAITING_EMPLOYEE
