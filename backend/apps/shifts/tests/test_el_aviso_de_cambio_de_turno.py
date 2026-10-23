"""A quien le cambian el turno se le avisa, y queda prueba de que lo supo.

El cuadrante se cambiaba sin que a la persona le llegara nada, y la empresa no
podía decir cuándo se lo había comunicado. El RD 723/2026 pide las dos cosas:
avisar de los cambios de turno con preaviso (art. 3.2.g) y, por un canal
electrónico, poder probar la transmisión y la recepción (art. 6).

Las horas de la prueba las pone el servidor y la base de datos no deja
reescribirlas: si pudiera, no probarían nada.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.db import IntegrityError, InternalError, ProgrammingError, transaction
from freezegun import freeze_time
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftNotice
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
MAÑANA = [{"start": "08:00", "end": "15:00"}]
TARDE = [{"start": "15:00", "end": "22:00"}]
HOY = "2026-10-23"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(
        name="Avisos", tax_id="B90400888", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def gente(empresa):
    with tenant_context(empresa.id):

        def alta(email, nombre, role=Role.EMPLOYEE):
            return User.objects.create_user(
                email=email, password=PASSWORD, tenant=empresa, first_name=nombre, role=role
            )

        yield {
            "ana": alta("ana@example.com", "Ana"),
            "luis": alta("luis@example.com", "Luis"),
            "jefa": alta("jefa@example.com", "Luisa", Role.MANAGER),
        }


def cliente(quien):
    c = APIClient()
    c.force_authenticate(user=quien)
    return c


def pintar(jefa, persona, dia, tramos=None):
    celda = {"employee": str(persona.pk), "day": dia}
    if tramos:
        celda["segments"] = tramos
    return cliente(jefa).post("/api/shifts/paint/", {"cells": [celda]}, format="json")


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_cambiar_un_turno_futuro_avisa_por_correo(
    empresa, gente, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        pintar(gente["jefa"], gente["ana"], "2026-10-27", MAÑANA)
    with django_capture_on_commit_callbacks(execute=True):
        respuesta = pintar(gente["jefa"], gente["ana"], "2026-10-27", TARDE)

    assert respuesta.status_code == 200
    assert respuesta.json()["notified"] == 1
    with tenant_context(empresa.id):
        # Dos avisos con el reloj parado: el del turno nuevo y el del cambio.
        avisos = list(ShiftNotice.objects.filter(employee=gente["ana"]))
    assert len(avisos) == 2
    aviso = next(a for a in avisos if a.changes[0]["before"])
    assert aviso.changes == [{"day": "2026-10-27", "before": MAÑANA, "after": TARDE}]
    assert aviso.changed_by == gente["jefa"]
    assert aviso.notice_days == 4
    assert aviso.emailed_at is not None
    assert aviso.delivered_at is None and aviso.read_at is None
    assert mail.outbox[-1].to == ["ana@example.com"]
    assert "15:00-22:00" in mail.outbox[-1].body


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_menos_preaviso_del_que_pide_la_empresa_queda_dicho(empresa, gente):
    pintar(gente["jefa"], gente["ana"], "2026-10-24", MAÑANA)

    with tenant_context(empresa.id):
        aviso = ShiftNotice.objects.get(employee=gente["ana"])
    # Cinco días por defecto; mañana es uno.
    assert aviso.notice_days == 1
    assert aviso.short_notice is True


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_rellenar_dias_pasados_no_avisa(empresa, gente):
    respuesta = pintar(gente["jefa"], gente["ana"], "2026-10-20", MAÑANA)

    assert respuesta.json()["notified"] == 0
    with tenant_context(empresa.id):
        assert not ShiftNotice.objects.exists()


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_pasar_un_turno_a_otra_persona_avisa_a_las_dos(empresa, gente):
    pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)
    with tenant_context(empresa.id):
        turno = Shift.objects.get(employee=gente["ana"])

    cliente(gente["jefa"]).post(
        f"/api/shifts/{turno.pk}/reassign/", {"employee": str(gente["luis"].pk)}, format="json"
    )

    with tenant_context(empresa.id):
        de_ana = [a.changes[0] for a in ShiftNotice.objects.filter(employee=gente["ana"])]
        de_luis = ShiftNotice.objects.get(employee=gente["luis"])
    assert {"day": "2026-10-28", "before": MAÑANA, "after": None} in de_ana
    assert de_luis.changes[0]["before"] is None and de_luis.changes[0]["after"] == MAÑANA


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_llega_cuando_lo_ve_ella_no_cuando_lo_mira_la_jefa(empresa, gente):
    pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)

    cliente(gente["jefa"]).get("/api/shift-notices/")
    with tenant_context(empresa.id):
        assert ShiftNotice.objects.get().delivered_at is None

    respuesta = cliente(gente["ana"]).get("/api/shift-notices/?mine=true")

    fila = respuesta.json()["results"][0]
    assert fila["delivered_at"] is not None
    assert fila["delivered_via"] == "OpenTimeTrack"


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_desde_otra_aplicacion_consta_cual(empresa, gente):
    """Talher ficha desde Geosian. Si Geosian enseña el aviso con la sesión de
    la persona, consta que llegó por Geosian."""
    pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)

    token = AccessToken.for_user(gente["ana"])
    token["act_app"] = "Geosian"
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    lista = c.get("/api/shift-notices/?mine=true").json()["results"]
    leido = c.post(f"/api/shift-notices/{lista[0]['id']}/read/").json()

    assert lista[0]["delivered_via"] == "Geosian"
    assert leido["read_via"] == "Geosian"


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_solo_lo_lee_quien_lo_recibe_y_la_hora_no_se_mueve(empresa, gente):
    pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)
    with tenant_context(empresa.id):
        aviso = ShiftNotice.objects.get()

    ajeno = cliente(gente["jefa"]).post(f"/api/shift-notices/{aviso.pk}/read/")
    assert ajeno.status_code == 409

    primera = cliente(gente["ana"]).post(f"/api/shift-notices/{aviso.pk}/read/").json()
    with freeze_time("2026-10-25 12:00:00"):
        segunda = cliente(gente["ana"]).post(f"/api/shift-notices/{aviso.pk}/read/").json()

    assert primera["read_at"] is not None
    assert segunda["read_at"] == primera["read_at"]
    # Leerlo sin haberlo listado antes también es que llegó.
    assert primera["delivered_at"] is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cambio",
    [
        {"changes": []},
        {"notice_days": 30},
        {"short_notice": False},
    ],
)
def test_lo_que_dice_un_aviso_no_se_reescribe(empresa, gente, cambio):
    with freeze_time(f"{HOY} 09:00:00"):
        pintar(gente["jefa"], gente["ana"], "2026-10-24", MAÑANA)

    with tenant_context(empresa.id):
        aviso = ShiftNotice.objects.get()
        with pytest.raises((InternalError, IntegrityError, ProgrammingError)):
            with transaction.atomic():
                ShiftNotice.objects.filter(pk=aviso.pk).update(**cambio)


@pytest.mark.django_db
def test_una_hora_ya_puesta_no_se_cambia_ni_se_borra_el_aviso(empresa, gente):
    with freeze_time(f"{HOY} 09:00:00"):
        pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)
        cliente(gente["ana"]).get("/api/shift-notices/?mine=true")

    with tenant_context(empresa.id):
        aviso = ShiftNotice.objects.get()
        with pytest.raises((InternalError, IntegrityError, ProgrammingError)):
            with transaction.atomic():
                ShiftNotice.objects.filter(pk=aviso.pk).update(delivered_at=None)
        with pytest.raises((InternalError, IntegrityError, ProgrammingError)):
            with transaction.atomic():
                ShiftNotice.objects.filter(pk=aviso.pk).delete()


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_la_empresa_se_lo_puede_llevar_y_la_plantilla_no(empresa, gente):
    pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)

    suyo = cliente(gente["jefa"]).get("/api/shift-notices/export/")
    ajeno = cliente(gente["luis"]).get("/api/shift-notices/export/")

    assert suyo.status_code == 200
    texto = suyo.content.decode()
    assert "Ana" in texto and "08:00-15:00" in texto
    assert ajeno.status_code == 403


@freeze_time(f"{HOY} 09:00:00")
@pytest.mark.django_db
def test_cada_uno_ve_solo_los_suyos(empresa, gente):
    pintar(gente["jefa"], gente["ana"], "2026-10-28", MAÑANA)

    assert cliente(gente["luis"]).get("/api/shift-notices/").json()["count"] == 0
    assert cliente(gente["ana"]).get("/api/shift-notices/").json()["count"] == 1
