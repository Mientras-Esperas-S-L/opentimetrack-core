"""La API que usa otra herramienta para integrarse: personas y asistencia.

Lo que se prueba aquí es lo que hace fiable a un conector: que reintentar no
duplique, que la baja no borre, que cada permiso abra solo su puerta, y que
nada de esto cruce de una empresa a otra.
"""

from __future__ import annotations

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def other_company(db):
    return Tenant.objects.create(name="Globex", tax_id="B22222222", time_zone="Europe/Madrid")


def credential(company, *scopes):
    with tenant_context(company.id):
        application = Application.objects.create(
            tenant=company, name="Geosian", scopes=[str(scope) for scope in scopes]
        )
        _credential, secret = ApplicationCredential.issue(application)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {secret}")
    return client, application


@pytest.fixture
def connector(company):
    client, _ = credential(
        company,
        ApplicationScope.READ_PEOPLE,
        ApplicationScope.WRITE_PEOPLE,
        ApplicationScope.READ_ATTENDANCE,
    )
    return client


# --------------------------------------------------------------- el empuje


@pytest.mark.django_db
def test_pushing_somebody_creates_them(connector, company):
    answer = connector.put(
        "/api/app/people/EMP-0042/",
        {
            "email": "rosa@acme.example",
            "first_name": "Rosa",
            "last_name": "Campos",
            "employee_id": "EMP-0042",
        },
        format="json",
    )
    assert answer.status_code == 201
    assert answer.json()["employee_id"] == "EMP-0042"

    with tenant_context(company.id):
        assert User.objects.filter(tenant=company, employee_id="EMP-0042").count() == 1


@pytest.mark.django_db
def test_pushing_twice_updates_instead_of_duplicating(connector, company):
    """Lo que hace que un conector pueda reintentar. La red se cae y el
    servidor se despliega; reintentar no puede crear una segunda persona."""
    cuerpo = {
        "email": "rosa@acme.example",
        "first_name": "Rosa",
        "last_name": "Campos",
        "employee_id": "EMP-0042",
    }
    primera = connector.put("/api/app/people/EMP-0042/", cuerpo, format="json")
    segunda = connector.put(
        "/api/app/people/EMP-0042/", {**cuerpo, "last_name": "Campos Ruiz"}, format="json"
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200  # actualizada, no creada
    assert segunda.json()["last_name"] == "Campos Ruiz"
    with tenant_context(company.id):
        assert User.objects.filter(tenant=company, employee_id="EMP-0042").count() == 1


@pytest.mark.django_db
def test_the_reference_may_be_the_identity_provider_subject(connector, company):
    connector.put(
        "/api/app/people/EMP-0042/",
        {
            "email": "rosa@acme.example",
            "first_name": "Rosa",
            "employee_id": "EMP-0042",
            "oidc_sub": "azure|abc123",
        },
        format="json",
    )
    # La misma persona, encontrada por el ancla del proveedor de identidad.
    de_nuevo = connector.get("/api/app/people/azure|abc123/")
    assert de_nuevo.status_code == 200
    assert de_nuevo.json()["employee_id"] == "EMP-0042"


@pytest.mark.django_db
def test_the_push_refuses_to_steal_somebody_elses_staff_number(connector, company):
    connector.put(
        "/api/app/people/EMP-0001/",
        {"email": "uno@acme.example", "first_name": "Uno", "employee_id": "EMP-0001"},
        format="json",
    )
    choque = connector.put(
        "/api/app/people/otra@acme.example/",
        {"email": "otra@acme.example", "first_name": "Otra", "employee_id": "EMP-0001"},
        format="json",
    )
    assert choque.status_code == 409
    assert choque.json()["error"]["code"] == "staff_number_taken"


@pytest.mark.django_db
def test_the_baja_deactivates_and_keeps_the_record(connector, company):
    """Los fichajes viven cuatro años y sobreviven a quien los hizo."""
    connector.put(
        "/api/app/people/EMP-0042/",
        {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"},
        format="json",
    )
    baja = connector.delete("/api/app/people/EMP-0042/")

    assert baja.status_code == 200
    assert baja.json()["is_active"] is False
    with tenant_context(company.id):
        assert User.objects.filter(tenant=company, employee_id="EMP-0042").exists()


@pytest.mark.django_db
def test_pushing_again_brings_a_seasonal_worker_back(connector, company):
    """Quien viene por temporadas vuelve con el mismo número."""
    cuerpo = {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"}
    connector.put("/api/app/people/EMP-0042/", cuerpo, format="json")
    connector.delete("/api/app/people/EMP-0042/")
    vuelta = connector.put("/api/app/people/EMP-0042/", cuerpo, format="json")

    assert vuelta.json()["is_active"] is True


# ------------------------------------------------------------- los permisos


@pytest.mark.django_db
def test_reading_does_not_grant_writing(company):
    """Una integración que solo pinta la asistencia no puede dar de alta."""
    client, _ = credential(company, ApplicationScope.READ_PEOPLE)

    assert client.get("/api/app/people/").status_code == 200
    escribir = client.put(
        "/api/app/people/EMP-0001/",
        {"email": "x@acme.example", "first_name": "X"},
        format="json",
    )
    assert escribir.status_code == 403


@pytest.mark.django_db
def test_attendance_needs_its_own_permission(company):
    client, _ = credential(company, ApplicationScope.READ_PEOPLE)
    assert client.get("/api/app/attendance/").status_code == 403


@pytest.mark.django_db
def test_a_person_token_does_not_open_the_application_doors(company):
    """Estas puertas son para aplicaciones. Una sesión de persona, por
    administradora que sea, no entra por aquí."""
    with tenant_context(company.id):
        from apps.users.models import Role

        admin = User.objects.create_user(
            email="jefa@acme.example", password=PASSWORD, tenant=company, role=Role.ADMIN
        )
    client = APIClient()
    client.force_authenticate(user=admin)

    assert client.get("/api/app/people/").status_code == 403


# ------------------------------------------------------------ el aislamiento


@pytest.mark.django_db
def test_a_credential_only_reaches_its_own_company(company, other_company):
    with tenant_context(other_company.id):
        ajena = User.objects.create_user(
            email="rosa@globex.example",
            password=PASSWORD,
            tenant=other_company,
            employee_id="EMP-0042",
        )

    client, _ = credential(company, ApplicationScope.READ_PEOPLE, ApplicationScope.WRITE_PEOPLE)

    # El mismo número existe en la otra empresa y aquí no.
    assert client.get("/api/app/people/EMP-0042/").status_code == 409
    # Y empujarlo crea uno **propio**, no toca al de al lado.
    client.put(
        "/api/app/people/EMP-0042/",
        {"email": "rosa@acme.example", "first_name": "Rosa", "employee_id": "EMP-0042"},
        format="json",
    )
    ajena.refresh_from_db()
    assert ajena.email == "rosa@globex.example"
    assert ajena.tenant_id == other_company.id


# ------------------------------------------------------------- la asistencia


@pytest.mark.django_db
def test_attendance_answers_with_the_day_and_no_capture_metadata(connector, company):
    """La IP y el dispositivo son datos de seguridad de esta empresa y no salen
    hacia otra aplicación por poder leer la asistencia."""
    from apps.punches.services import register_punch

    with tenant_context(company.id):
        persona = User.objects.create_user(
            email="rosa@acme.example", password=PASSWORD, tenant=company, employee_id="EMP-0042"
        )
        register_punch(employee=persona, company=company, ip_address="10.0.0.9")

    answer = connector.get("/api/app/attendance/", {"employee_ref": "EMP-0042"})
    assert answer.status_code == 200
    dia = answer.json()["people"][0]
    assert dia["state"] == "WORKING"
    assert "10.0.0.9" not in str(answer.json())
    assert all("ip" not in tramo for tramo in dia["segments"])


# ------------------------------------------------- leer la plantilla entera


@pytest.mark.django_db
def test_una_plantilla_grande_dice_que_no_cabe_de_una_vez(connector, company):
    """Devolvía quinientas y ni una palabra de que hubiera más.

    Un conector de una empresa de seiscientas daba la plantilla por leída, y las
    otras cien no existían para él: ni sus altas, ni sus bajas, ni sus fichajes.
    Un recorte callado en una integración es peor que en una pantalla, porque no
    hay nadie mirando que sospeche.
    """
    with tenant_context(company.id):
        User.objects.bulk_create(
            [
                User(email=f"grande{n}@example.com", tenant=company, first_name=f"P{n}")
                for n in range(505)
            ]
        )
        total = User.objects.filter(tenant=company).count()

    respuesta = connector.get("/api/app/people/")

    assert respuesta.status_code == 200
    assert len(respuesta.data["people"]) == 500
    assert respuesta.data["count"] == total
    assert respuesta.data["has_more"] is True
    assert respuesta.data["next_since"]


@pytest.mark.django_db
def test_el_cursor_llega_a_los_que_faltan(connector, company):
    """Y avisar no basta: hay que poder terminar.

    La prueba que no valdría es comprobar solo que `has_more` es verdadero. Eso
    pasaría igual con un cursor roto, y el conector se quedaría dando vueltas o
    perdiendo gente. Aquí se recorre hasta el final y se cuenta a todo el mundo.
    """
    with tenant_context(company.id):
        User.objects.bulk_create(
            [
                User(email=f"vuelta{n}@example.com", tenant=company, first_name=f"P{n}")
                for n in range(505)
            ]
        )
        total = User.objects.filter(tenant=company).count()

    vistos: set[str] = set()
    since = None
    for _ in range(10):  # tope de seguridad: sin él, un cursor roto cuelga la prueba
        url = "/api/app/people/" + (f"?since={since}" if since else "")
        pagina = connector.get(url).data
        vistos.update(p["id"] for p in pagina["people"])
        if not pagina["has_more"]:
            break
        since = pagina["next_since"]

    assert len(vistos) == total, "el cursor no llegó a toda la plantilla"


@pytest.mark.django_db
def test_una_plantilla_pequeña_no_dice_que_haya_mas(connector, company):
    """El otro lado del aviso.

    Sin esto, un `has_more` clavado a verdadero pasaría la prueba de arriba y
    dejaría a todos los conectores dando una vuelta de más para siempre.
    """
    respuesta = connector.get("/api/app/people/")

    assert respuesta.data["has_more"] is False
    assert respuesta.data["count"] == len(respuesta.data["people"])


@pytest.mark.django_db
def test_el_cursor_aguanta_que_el_mas_del_huso_llegue_como_espacio(connector, company):
    """El fallo que rompía la segunda vuelta de cualquier conector.

    `next_since` sale con el huso pegado ---«…123456+00:00»--- y en una URL el
    `+` significa espacio si el cliente no lo codifica. Llegaba «…123456 00:00»,
    no parseaba, y la respuesta era un 409: el conector se quedaba con la
    primera tanda creyendo que era la plantilla entera.

    Se perdona en el servidor porque ese espacio no puede venir de otro sitio:
    una marca de tiempo no lleva espacios.
    """
    with tenant_context(company.id):
        persona = User.objects.create_user(
            email="cursor@example.com", tenant=company, first_name="Cursor"
        )
        marca = persona.updated_at.isoformat()

    sin_codificar = connector.get(f"/api/app/people/?since={marca.replace('+', ' ')}")
    codificado = connector.get(f"/api/app/people/?since={marca.replace('+', '%2B')}")

    assert sin_codificar.status_code == 200
    assert codificado.status_code == 200
    assert sin_codificar.data["count"] == codificado.data["count"]


@pytest.mark.django_db
def test_un_since_que_no_es_una_fecha_sigue_rechazandose(connector, company):
    """Perdonar el espacio no es tragar cualquier cosa.

    Sin esta, el arreglo de arriba podría haber sido «acepta lo que sea y no
    filtres», que pasaría la prueba anterior y devolvería la plantilla entera a
    quien pidió los cambios de ayer.
    """
    respuesta = connector.get("/api/app/people/?since=ayer-por-la-tarde")

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "bad_since"


# -------------------------------------------------------- la asistencia


@pytest.mark.django_db
def test_el_dia_es_el_de_la_empresa_no_el_del_contenedor(connector, company):
    """La quinta vez que se cuela `date.today()`, y la primera con prueba.

    El servidor va en UTC. A las 00:30 de Madrid ---22:30 UTC del día
    anterior--- la respuesta decía que era ayer mientras los tramos ya eran de
    hoy: la aplicación que pinta esto ponía la fecha de un día y los fichajes de
    otro. Quien más lo sufre es el turno de noche, que cruza esa frontera todas
    las madrugadas.

    `apps/common/clock.py` existe justo por esto y avisa de que ya había pasado
    cuatro veces antes.
    """
    with tenant_context(company.id):
        User.objects.create_user(email="noche@example.com", tenant=company, employee_id="EMP-NOC")

    with freeze_time("2026-08-13 22:30:00"):  # 00:30 del 14 en Madrid
        respuesta = connector.get("/api/app/attendance/")

    assert respuesta.status_code == 200
    assert respuesta.json()["time_zone"] == "Europe/Madrid"
    assert respuesta.json()["day"] == "2026-08-14", "devolvió la fecha UTC del contenedor"


@pytest.mark.django_db
def test_a_mediodia_no_hay_diferencia(connector, company):
    """El otro lado: fuera de la franja de madrugada las dos fechas coinciden.

    Sin esta, un arreglo que sumara un día siempre pasaría la de arriba.
    """
    with freeze_time("2026-08-13 10:00:00"):  # 12:00 en Madrid
        respuesta = connector.get("/api/app/attendance/")

    assert respuesta.json()["day"] == "2026-08-13"


@pytest.mark.django_db
def test_la_asistencia_no_sale_de_la_empresa(company, other_company):
    """Una credencial solo ve su plantilla, también aquí.

    Estaba probado para el empuje de personas y no para la asistencia, que es
    la puerta que **enseña** dónde está cada uno ahora mismo.
    """
    with tenant_context(other_company.id):
        User.objects.create_user(
            email="ajena@globex.example", tenant=other_company, employee_id="EMP-AJENA"
        )

    client, _ = credential(company, ApplicationScope.READ_ATTENDANCE)

    todos = client.get("/api/app/attendance/")
    concreta = client.get("/api/app/attendance/", {"employee_ref": "EMP-AJENA"})

    assert "ajena@globex.example" not in str(todos.json())
    assert concreta.status_code == 409
    assert concreta.data["error"]["code"] == "employee_not_found"
