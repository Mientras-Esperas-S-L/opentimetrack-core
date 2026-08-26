"""Clocking in from an external application.

This is the reason the project exists: a product like GreenCity records the
working time of its field operatives against this service instead of keeping its
own module. What is checked here is that it works, that it does not become a way
around isolation, and that the resulting record still says what it is.
"""

from __future__ import annotations

import itertools

import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchSource, PunchTrigger, PunchType
from apps.punches.services import build_day_status
from apps.reports.services import build_report, day_notes, to_csv
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def other_company(db):
    return Tenant.objects.create(name="Globex Inc", tax_id="B22222222")


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="marta@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Marta",
            last_name="Ruiz",
            employee_id="EMP-0003",
        )


def authorise(company, scopes, name="GreenCity"):
    with tenant_context(company.id):
        application = Application.objects.create(tenant=company, name=name, scopes=scopes)
        _credential, raw = ApplicationCredential.issue(application)
    return application, raw


#: Una clave distinta por llamada. La cabecera es obligatoria, y ponerle la
#: misma a todas las pruebas convertiría el segundo fichaje de cada una en el
#: primero repetido ---que es justo lo que la cabecera existe para hacer---.
_llamadas = itertools.count()


def as_application(client, token, key=None):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_IDEMPOTENCY_KEY=key or f"prueba-{next(_llamadas)}",
    )
    return client


# --------------------------------------------------------------------- happy path


@pytest.mark.django_db
def test_an_application_clocks_in_for_an_employee(client, company, employee):
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003", "device_id": "site-tablet"}
    )

    assert response.status_code == 201
    assert response.data["source"] == PunchSource.DELEGATED
    assert response.data["source_application"] == "GreenCity"
    assert response.data["day_status"]["state"] == "WORKING"


@pytest.mark.django_db
def test_the_employee_can_be_named_by_staff_number_email_or_id(client, company, employee):
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = as_application(client, token)

    # Con una hora entre cada uno: tres formas de nombrar a la misma persona,
    # pero son tres fichajes de la misma jornada y pegados los rechaza la
    # protección del doble toque, que es lo que tiene que hacer.
    momentos = ("2026-08-13 08:00:00", "2026-08-13 13:00:00", "2026-08-13 14:00:00")
    for reference, cuando in zip(
        ("EMP-0003", "marta@example.com", str(employee.id)), momentos, strict=True
    ):
        # Cada fichaje es una operación distinta, así que lleva su clave. La
        # misma para los tres los convertiría en uno solo repetido.
        as_application(client, token, key=f"referencia-{reference}")
        with freeze_time(cuando):
            response = caller.post(reverse("punch-delegated"), {"employee_ref": reference})
        assert response.status_code == 201, reference


@pytest.mark.django_db
def test_a_shared_terminal_is_recorded_as_such(client, company, employee):
    """Not the same as an application acting on its own: worth telling apart."""
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003", "terminal": True}
    )

    assert response.data["source"] == PunchSource.TERMINAL


@pytest.mark.django_db
def test_the_server_still_owns_the_clock(client, company, employee):
    """Delegating who presses the button does not delegate who sets the time."""
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"),
        {
            "employee_ref": "EMP-0003",
            # Both ignored: they are not even in the serializer.
            "timestamp": "2020-01-01T00:00:00Z",
            "punch_type": "OUT",
        },
    )

    assert response.status_code == 201
    assert response.data["punch_type"] == "IN"  # inferred, not accepted
    assert response.data["timestamp"].startswith("20")
    assert not response.data["timestamp"].startswith("2020")


# ------------------------------------------------------------------- permissions


@pytest.mark.django_db
def test_without_the_permission_it_is_refused(client, company, employee):
    """An application that may only read must not be able to clock in."""
    _app, token = authorise(company, [ApplicationScope.READ_ATTENDANCE])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_application_with_no_permissions_can_do_nothing(client, company, employee):
    _app, token = authorise(company, [])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_deactivated_application_stops_working(client, company, employee):
    app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    app.is_active = False
    app.save()

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_a_revoked_credential_stops_working(client, company, employee):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="GreenCity", scopes=[ApplicationScope.PUNCH_DELEGATED]
        )
        credential, token = ApplicationCredential.issue(application)
        credential.revoke()

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_a_made_up_token_is_refused(client, company, employee):
    response = as_application(client, "ott_app_made-up").post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 401


# --------------------------------------------------------------------- isolation


@pytest.mark.django_db
def test_an_application_cannot_reach_another_company(client, company, other_company, employee):
    """The reason this test exists: a delegated door is a door.

    An application of Globex naming an employee of ACME must find nobody, even
    knowing the exact staff number.
    """
    _app, token = authorise(other_company, [ApplicationScope.PUNCH_DELEGATED], name="Otra")

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "employee_not_found"
    assert Punch.objects_all_tenants.count() == 0


@pytest.mark.django_db
def test_an_unknown_reference_is_refused(client, company, employee):
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    response = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "does-not-exist"}
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "employee_not_found"


# ------------------------------------------------------------------ the evidence


@pytest.mark.django_db
def test_delegation_reaches_the_report(client, company, employee):
    """What ADR-0010 promises: an inspector can tell the two apart.

    Both outputs are checked, because they drifted apart once already -- the PDF
    said it and the CSV kept quiet.

    The language is pinned rather than left to the settings. The note is
    translated, so without this the test passes or fails depending on which
    catalogues happen to be compiled --- which is exactly what happened when the
    Spanish one arrived.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    as_application(client, token).post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    from django.utils import timezone, translation

    today = timezone.now().astimezone(company.tzinfo).date()
    with tenant_context(company.id), translation.override("en"):
        report = build_report(employee=employee, company=company, date_from=today, date_to=today)

        assert report.rows[0].delegated
        assert "application" in day_notes(report.rows[0])
        assert "application" in to_csv(report)


@pytest.mark.django_db
def test_the_delegation_note_is_translated(client, company, employee):
    """And it reaches the report in Spanish too.

    Worth its own test: the note is what tells an inspector the record was not
    made by the person, so it failing to translate would leave an English
    sentence in the middle of a Spanish document --- or, worse, go unnoticed.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    as_application(client, token).post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    from django.utils import timezone, translation

    today = timezone.now().astimezone(company.tzinfo).date()
    with tenant_context(company.id), translation.override("es"):
        report = build_report(employee=employee, company=company, date_from=today, date_to=today)

        assert "aplicación" in day_notes(report.rows[0])
        assert "aplicación" in to_csv(report)


@pytest.mark.django_db
def test_credentials_are_not_stored_in_the_clear(company):
    """A secret the server can read back is a secret the server can leak."""
    with tenant_context(company.id):
        application = Application.objects.create(tenant=company, name="GreenCity", scopes=[])
        credential, raw = ApplicationCredential.issue(application)

        assert credential.token_hash != raw
        assert raw not in credential.token_hash
        assert len(credential.token_hash) == 64
        # Only the tail is kept, to tell one credential from another.
        assert credential.token_hint == raw[-6:]


# ------------------------------------------------------- lo que pasa en la puerta


@pytest.mark.django_db
def test_pasar_la_tarjeta_dos_veces_no_cierra_la_jornada(client, company, employee):
    """El caso más común de un lector: se pasa la tarjeta dos veces por si acaso.

    Y era el peor. El tipo se deduce del estado, así que dos lecturas seguidas
    daban entrada y salida: la persona entraba a trabajar y el registro decía
    que había hecho cero segundos y se había ido. Con guantes, delante de un
    lector que no siempre pita, pasar dos veces es lo normal.

    Se rechaza la segunda con un código que el terminal puede leer y enseñar, y
    la entrada sigue en pie.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = as_application(client, token)

    with freeze_time("2026-08-13 07:00:00"):
        as_application(client, token, key="tarjeta-pase-1")
        primera = caller.post(
            reverse("punch-delegated"), {"employee_ref": "EMP-0003", "terminal": True}
        )
        # Clave distinta a propósito: son dos pasadas de tarjeta, no un reintento
        # de la misma. Lo que tiene que frenar la segunda es la guarda del doble
        # toque, y esta prueba comprueba justo eso.
        as_application(client, token, key="tarjeta-pase-2")
        segunda = caller.post(
            reverse("punch-delegated"), {"employee_ref": "EMP-0003", "terminal": True}
        )

    assert primera.status_code == 201
    assert primera.data["punch_type"] == PunchType.IN
    assert segunda.status_code == 409
    assert segunda.data["error"]["code"] == "punch_too_soon"

    # Con el mismo reloj con el que se fichó: `build_day_status` mira **hoy**, y
    # preguntado desde el día real diría NOT_STARTED con toda la razón.
    with tenant_context(company.id), freeze_time("2026-08-13 07:00:00"):
        assert Punch.objects.filter(employee=employee).count() == 1
        assert build_day_status(employee, company).state == "WORKING"


@pytest.mark.django_db
def test_el_turno_entero_ficha_en_el_mismo_minuto(client, company, employee):
    """Y la protección no puede estorbar a la plantilla.

    Un terminal en la puerta de la nave recibe a todo el mundo a las siete. La
    ventana del doble toque es de cada persona; si fuera del terminal, el
    segundo en llegar no podría fichar --- que es peor que el fallo que evita.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    with tenant_context(company.id):
        for numero in range(4):
            User.objects.create_user(
                email=f"companero{numero}@example.com",
                password="a-sufficiently-long-password",
                tenant=company,
                first_name=f"Compa{numero}",
                employee_id=f"EMP-100{numero}",
            )

    with freeze_time("2026-08-13 07:00:00"):
        # Una clave por persona: cuatro entradas distintas en el mismo minuto,
        # que es exactamente lo que este terminal recibe todas las mañanas.
        respuestas = [
            as_application(client, token, key=f"puerta-EMP-100{n}").post(
                reverse("punch-delegated"), {"employee_ref": f"EMP-100{n}", "terminal": True}
            )
            for n in range(4)
        ]

    assert [r.status_code for r in respuestas] == [201, 201, 201, 201]


@pytest.mark.django_db
def test_una_referencia_que_señala_a_dos_personas_se_rechaza(client, company, employee):
    """Registrar la jornada de quien no es, es peor que no registrar nada.

    Pasa cuando el número de empleado de alguien coincide con el correo de otro
    --- raro, pero el catálogo lo permite y la búsqueda mira los dos campos.
    """
    with tenant_context(company.id):
        User.objects.create_user(
            email="otro@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            first_name="Otro",
            employee_id="marta@example.com",
        )

    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    respuesta = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "marta@example.com"}
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "ambiguous_employee_reference"
    with tenant_context(company.id):
        assert Punch.objects.count() == 0


@pytest.mark.django_db
def test_quien_esta_de_baja_no_ficha_por_el_terminal(client, company, employee):
    """La tarjeta de quien ya no está sigue existiendo.

    Y un terminal no sabe quién sigue en plantilla: lo sabe el servidor. Si la
    aceptara, el registro tendría jornadas de alguien que se fue.
    """
    with tenant_context(company.id):
        employee.is_active = False
        employee.save(update_fields=["is_active"])

    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    respuesta = as_application(client, token).post(
        reverse("punch-delegated"), {"employee_ref": "EMP-0003"}
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "employee_not_found"


@pytest.mark.django_db
def test_lo_que_detecto_el_sensor_llega_al_registro(client, company, employee):
    """El motivo de que exista `trigger` y `evidence`.

    Una valla virtual de Geosian o un lector dicen **qué** detectaron y adjuntan
    la prueba. Sin eso, un fichaje automático es indistinguible de uno que hizo
    una persona, y quien lea el registro tiene derecho a saberlo.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    respuesta = as_application(client, token).post(
        reverse("punch-delegated"),
        {
            "employee_ref": "EMP-0003",
            "trigger": PunchTrigger.GEOFENCE,
            "evidence": {"zona": "Nave 3", "precision_m": 12},
        },
        format="json",
    )

    assert respuesta.status_code == 201
    with tenant_context(company.id):
        guardado = Punch.objects.get(employee=employee)
        assert guardado.trigger == PunchTrigger.GEOFENCE
        assert guardado.evidence == {"zona": "Nave 3", "precision_m": 12}
        assert guardado.source_application == "GreenCity"


@pytest.mark.django_db
def test_una_evidencia_desproporcionada_se_rechaza(client, company, employee):
    """El campo lo escribe alguien de fuera y no tenía tope.

    Con seis mil peticiones por hora de cupo, un conector con una fuga ---o uno
    honesto que vuelca la traza GPS entera en cada fichaje--- llena la base sin
    hacer nada prohibido. Y esos fichajes viven cuatro años y salen en cada
    informe que se entrega.

    Lo que cabe es lo que el campo existe para guardar: unas coordenadas, una
    red, el identificador de un evento.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = as_application(client, token)

    respuesta = caller.post(
        reverse("punch-delegated"),
        {"employee_ref": "EMP-0003", "evidence": {"traza": ["x" * 100] * 100}},
        format="json",
    )

    assert respuesta.status_code == 400
    assert "evidence" in respuesta.data["error"]["details"]
    with tenant_context(company.id):
        assert Punch.objects.count() == 0


@pytest.mark.django_db
def test_una_evidencia_normal_pasa(client, company, employee):
    """El tope no puede estorbar a lo que el campo existe para guardar.

    Validar el rechazo sin validar la aceptación deja pasar un tope de cero: la
    prueba de arriba seguiría en verde y nadie podría adjuntar nada.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])

    respuesta = as_application(client, token).post(
        reverse("punch-delegated"),
        {
            "employee_ref": "EMP-0003",
            "trigger": PunchTrigger.GEOFENCE,
            "evidence": {"lat": 36.6866, "lon": -6.1367, "precision_m": 8, "zona": "Nave 3"},
        },
        format="json",
    )

    assert respuesta.status_code == 201


# ------------------------------------------------------------------ the retry


@pytest.mark.django_db
def test_a_retry_with_the_same_key_returns_the_same_punch(client, company, employee):
    """The commonest way a connector fails: the write landed, the answer did not.

    Without a key the retry does not record a second entry --- it records an
    **exit**, because the type is inferred from the state. Rosa's nine-hour day
    then reads as thirty seconds, and undoing it needs the art. 4.b procedure
    and both parties' agreement.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = as_application(client, token)
    caller.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_IDEMPOTENCY_KEY="nfc-gate-7-2026-08-13-0800"
    )

    with freeze_time("2026-08-13 08:00:00"):
        first = caller.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})
    with freeze_time("2026-08-13 08:00:30"):
        retry = caller.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.data["id"] == first.data["id"]
    assert Punch.objects.filter(employee=employee).count() == 1
    assert retry.data["day_status"]["state"] == "WORKING"


@pytest.mark.django_db
def test_a_different_key_records_a_different_event(client, company, employee):
    """The key protects the retry, it must not block the real exit."""
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = as_application(client, token)

    caller.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_IDEMPOTENCY_KEY="entrada")
    with freeze_time("2026-08-13 08:00:00"):
        entrada = caller.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    caller.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_IDEMPOTENCY_KEY="salida")
    with freeze_time("2026-08-13 17:00:00"):
        salida = caller.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    assert entrada.status_code == 201
    assert salida.status_code == 201
    assert salida.data["punch_type"] == PunchType.OUT
    assert Punch.objects.filter(employee=employee).count() == 2


@pytest.mark.django_db
def test_the_key_belongs_to_the_application_that_sent_it(client, company, other_company):
    """Two connectors picking the same key must not read each other's events."""
    with tenant_context(company.id):
        una = User.objects.create_user(
            email="marta@example.com",
            password="a-sufficiently-long-password",
            tenant=company,
            employee_id="EMP-0003",
        )
    with tenant_context(other_company.id):
        otra = User.objects.create_user(
            email="rosa@globex.example",
            password="a-sufficiently-long-password",
            tenant=other_company,
            employee_id="EMP-0003",
        )

    _app_a, token_a = authorise(company, [ApplicationScope.PUNCH_DELEGATED], name="Geosian")
    _app_b, token_b = authorise(
        other_company, [ApplicationScope.PUNCH_DELEGATED], name="Otro producto"
    )

    primero = APIClient()
    primero.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}", HTTP_IDEMPOTENCY_KEY="turno-1")
    segundo = APIClient()
    segundo.credentials(HTTP_AUTHORIZATION=f"Bearer {token_b}", HTTP_IDEMPOTENCY_KEY="turno-1")

    a = primero.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})
    b = segundo.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    assert a.status_code == 201
    assert b.status_code == 201
    assert a.data["id"] != b.data["id"]
    # Sin filtro por empresa a propósito: `Punch.objects` se acota al contexto y
    # aquí no hay ninguno, así que contaría cero para las dos y la prueba pasaría
    # sin comprobar nada.
    assert Punch.objects_all_tenants.filter(employee=una).count() == 1
    assert Punch.objects_all_tenants.filter(employee=otra).count() == 1


@pytest.mark.django_db
def test_without_a_key_it_is_refused(client, company, employee):
    """Demanded, not offered.

    A connector without a key is a connector one lost answer away from turning
    somebody's nine-hour day into thirty seconds, and it finds out in
    production. Refusing on the first call moves that discovery to the
    developer's screen, which is the only place it is cheap. The refusal is a
    400 with a code of its own so a machine can branch on it.
    """
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = APIClient()
    caller.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = caller.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "idempotency_key_required"
    assert Punch.objects_all_tenants.filter(employee=employee).count() == 0


@pytest.mark.django_db
def test_a_blank_key_is_no_key(client, company, employee):
    """Sending the header empty is the same as not sending it, and worse: it
    looks like the connector did its part."""
    _app, token = authorise(company, [ApplicationScope.PUNCH_DELEGATED])
    caller = APIClient()
    caller.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_IDEMPOTENCY_KEY="   ")

    response = caller.post(reverse("punch-delegated"), {"employee_ref": "EMP-0003"})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "idempotency_key_required"
