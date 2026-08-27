"""Quien ya no trabaja allí y quiere su registro.

Francisco preguntó si hay base para que alguien siga teniendo acceso después de
irse, y la respuesta corta es que **el derecho no se extingue pero no es un
acceso**: el art. 34.9 ET obliga a conservar el registro cuatro años y a tenerlo a
disposición de la persona trabajadora, y el art. 15 del RGPD le da derecho a
pedir sus datos mientras se conserven. Ninguno de los dos obliga a mantenerla
dentro del producto, y mantenerla tiene coste: vería el cuadrante, a sus antiguos
compañeros y lo que la empresa haya cambiado desde que se fue.

Así que se entrega, no se da acceso. Lo que se fija aquí:

- Una persona **de baja** obtiene su registro por el enlace. Ese es el caso.
- El enlace **no vale como credencial**: no abre nada más.
- El enlace de una persona **no sirve para otra**, ni cruzando las mitades.
- **Caduca**, y hasta entonces vale más de una vez ---el PDF y el CSV---.
- **Reactivar la cuenta lo mata**, porque entonces hay otra puerta.
- Se entrega **lo que se conserva**: el mismo plazo que decide la purga.
- Cada descarga deja asiento, o no se puede demostrar que se atendió.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.core import mail
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.punches.models import CURRENT_HASH_VERSION, Punch, PunchSource
from apps.reports.delivery import build_delivery_link, resolve_delivery_token
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
AHORA = "2026-08-27 10:00:00"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Entrega SL", tax_id="B51515151", time_zone="Europe/Madrid"
    )


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com", password=PASSWORD, tenant=company,
            first_name="Jefa", last_name="Uno", role=Role.ADMIN,
        )


@pytest.fixture
def se_fue(company):
    """Alguien que trabajó allí y ya no. Con fichajes, que es lo que va a pedir."""
    with tenant_context(company.id):
        persona = User.objects.create_user(
            email="sefue@example.com", password=PASSWORD, tenant=company,
            first_name="Pau", last_name="Serra",
        )
        for dia in (10, 11, 12):
            for hora, tipo in ((8, "IN"), (16, "OUT")):
                p = Punch(
                    tenant=company, employee=persona, punch_type=tipo,
                    timestamp=dt.datetime(2026, 6, dia, hora, tzinfo=dt.UTC),
                    source=PunchSource.WEB,
                )
                p.hash_version = CURRENT_HASH_VERSION
                p.hash_integrity = p.compute_hash()
                p.save()
        persona.is_active = False
        persona.save(update_fields=["is_active"])
        yield persona


def _url(persona):
    enlace = build_delivery_link(persona, base_url="http://testserver")
    return enlace.replace("http://testserver", "")


# ------------------------------------------------------------------ el caso


@freeze_time(AHORA)
@pytest.mark.django_db
def test_quien_se_fue_descarga_su_registro(se_fue):
    respuesta = APIClient().get(_url(se_fue))

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert "mi-registro_Serra" in respuesta["Content-Disposition"]
    assert respuesta["X-Report-Hash"]
    assert respuesta.content[:4] == b"%PDF"


@freeze_time(AHORA)
@pytest.mark.django_db
def test_tambien_en_hoja_de_calculo(se_fue):
    """La misma solicitud, dos formas. Por eso el enlace no es de un solo uso."""
    cliente = APIClient()
    assert cliente.get(_url(se_fue)).status_code == 200

    csv = cliente.get(f"{_url(se_fue)}?format=csv")
    assert csv.status_code == 200
    assert csv["Content-Type"].startswith("text/csv")


@freeze_time(AHORA)
@pytest.mark.django_db
def test_se_entrega_lo_que_se_conserva(se_fue, company):
    """El periodo sale de `first_day_kept`, el mismo que decide qué se borra.

    Si fueran dos definiciones distintas, un día habría registro entregable que ya
    no existe, o registro guardado que no se entrega.
    """
    from apps.punches.management.commands.purge_expired_records import first_day_kept

    respuesta = APIClient().get(f"{_url(se_fue)}?format=csv")

    assert first_day_kept(company).isoformat() in respuesta.content.decode()


# --------------------------------------------------- lo que el enlace no es


@freeze_time(AHORA)
@pytest.mark.django_db
def test_el_enlace_no_abre_sesion(se_fue):
    """Lo importante: autoriza una descarga, no una identidad."""
    cliente = APIClient()
    assert cliente.get(_url(se_fue)).status_code == 200

    # La misma sesión de cliente, ahora contra la API de verdad.
    for ruta in ("/api/auth/me/", "/api/punches/", "/api/employees/"):
        assert cliente.get(ruta).status_code in (401, 403), ruta


@freeze_time(AHORA)
@pytest.mark.django_db
def test_el_enlace_de_uno_no_sirve_para_otro(se_fue, admin):
    """Cruzar las mitades no vale: el token va firmado contra ese identificador."""
    mio = _url(se_fue).strip("/").split("/")
    suyo = _url(admin).strip("/").split("/")
    cruzado = f"/{'/'.join([*mio[:-1], suyo[-1]])}/"

    assert APIClient().get(cruzado).status_code == 404


@freeze_time(AHORA)
@pytest.mark.django_db
def test_no_hay_forma_de_pedir_el_registro_de_otra_persona(se_fue, admin):
    """No hay parámetro que diga de quién: sale del identificador firmado.

    Así que ni siquiera hay que rechazarlo; la comprobación es que añadirlo no
    cambia lo que sale.
    """
    respuesta = APIClient().get(f"{_url(se_fue)}?employee={admin.id}&format=csv")

    assert respuesta.status_code == 200
    cuerpo = respuesta.content.decode()
    assert "Serra" in cuerpo
    assert "Jefa" not in cuerpo


@pytest.mark.django_db
def test_el_enlace_caduca(se_fue, settings):
    with freeze_time(AHORA):
        url = _url(se_fue)
    with freeze_time("2026-08-28 10:00:00"):
        assert APIClient().get(url).status_code == 200
    # Un segundo más allá del plazo configurado.
    tarde = dt.datetime(2026, 8, 27, 10, 0, tzinfo=dt.UTC) + dt.timedelta(
        seconds=settings.PASSWORD_RESET_TIMEOUT + 1
    )
    with freeze_time(tarde):
        assert APIClient().get(url).status_code == 404


@freeze_time(AHORA)
@pytest.mark.django_db
def test_reactivar_la_cuenta_mata_el_enlace(se_fue):
    """Porque entonces esa persona ya tiene su pantalla, y el enlace sobra."""
    url = _url(se_fue)
    assert APIClient().get(url).status_code == 200

    se_fue.is_active = True
    se_fue.save(update_fields=["is_active"])

    assert resolve_delivery_token(*url.strip("/").split("/")[-2:]) is None
    assert APIClient().get(url).status_code == 404


@freeze_time(AHORA)
@pytest.mark.django_db
def test_un_enlace_de_contrasena_no_sirve_para_descargar(se_fue):
    """Los dos se derivan de los mismos campos: lo único que los separa es el
    ámbito metido en el valor firmado. Sin eso, un enlace de invitación
    descargaría el registro de esa persona."""
    from apps.users.passwords import build_token

    uid, token = build_token(se_fue)

    assert APIClient().get(f"/api/record-delivery/{uid}/{token}/").status_code == 404


# ------------------------------------------------------ generarlo y el rastro


@freeze_time(AHORA)
@pytest.mark.django_db
def test_la_administracion_lo_manda_por_correo(
    company, admin, se_fue, django_capture_on_commit_callbacks
):
    cliente = APIClient()
    cliente.force_authenticate(admin)

    with django_capture_on_commit_callbacks(execute=True):
        respuesta = cliente.post(
            reverse("employee-deliver-record", args=[se_fue.id]), format="json"
        )

    assert respuesta.status_code == 200
    assert respuesta.data == {"sent_to": "sefue@example.com"}
    assert len(mail.outbox) == 1
    assert "/api/record-delivery/" in mail.outbox[0].body
    assert mail.outbox[0].to == ["sefue@example.com"]

    asiento = AuditLog.objects.filter(
        tenant=company, action=AuditAction.RECORD_DELIVERED
    ).get()
    assert asiento.changes["picked_up"] is False
    assert asiento.note == "cuenta de baja"
    assert asiento.actor_id == admin.id


@freeze_time(AHORA)
@pytest.mark.django_db
def test_cada_descarga_deja_asiento(company, se_fue, django_capture_on_commit_callbacks):
    """Sin esto solo consta que se contestó, no que llegó a entregarse."""
    with django_capture_on_commit_callbacks(execute=True):
        APIClient().get(_url(se_fue))

    asiento = AuditLog.objects.filter(
        tenant=company, action=AuditAction.RECORD_DELIVERED
    ).get()
    assert asiento.changes["picked_up"] is True
    assert asiento.actor_id is None
    assert asiento.actor_label
    assert asiento.target_id == se_fue.id


@freeze_time(AHORA)
@pytest.mark.django_db
def test_una_persona_normal_no_puede_mandar_entregas(company, se_fue):
    """Es una acción de administración: manda un documento con el registro de
    alguien a una dirección de correo."""
    with tenant_context(company.id):
        cualquiera = User.objects.create_user(
            email="peon@example.com", password=PASSWORD, tenant=company,
            first_name="Peón", last_name="Dos",
        )
    cliente = APIClient()
    cliente.force_authenticate(cualquiera)

    respuesta = cliente.post(reverse("employee-deliver-record", args=[se_fue.id]), format="json")

    assert respuesta.status_code in (403, 404)
    assert mail.outbox == []
