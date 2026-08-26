"""Rechazar un cambio en el registro es decidir sobre él.

La regla de los cuatro ojos estaba en aprobar y no en rechazar, así que la
puerta quedaba cerrada en un sentido y abierta en el otro: un responsable no
podía aprobar un cambio sobre su propio fichaje ---409 `cannot_decide_your_own`,
medido--- y **sí podía rechazarlo**, él solo.

No cambiar nada también es decidir. Si la empresa propone corregir el fichaje de
un responsable ---quitarle una hora que no trabajó, por ejemplo--- archivar esa
propuesta es exactamente la decisión que el art. 4.b quiere que pase por una
segunda persona. Y `reject` cierra la corrección: quien la propuso tiene que
volver a empezar, y el rastro dice que la resolvió la propia persona afectada.

La excepción de `apps.common.four_eyes` se mantiene y se prueba aquí también:
en una empresa con una sola persona al mando no hay segunda, y negarlo dejaría
a un autónomo sin poder corregir su registro. Va adelante **y la nota lo dice**,
porque una decisión tomada a solas y otra tomada por dos personas no son la
misma prueba.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.four_eyes import someone_else_could_decide
from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, CorrectionStatus
from apps.punches.models import Punch, PunchCorrection, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="Con jefes", tax_id="B99999999", time_zone="Europe/Madrid")


def alguien(company, nombre, rol=Role.EMPLOYEE, dpto=None):
    return User.objects.create_user(
        email=f"{nombre}@example.com",
        password=PASSWORD,
        tenant=company,
        first_name=nombre.title(),
        last_name="Equis",
        role=rol,
        department=dpto,
    )


@pytest.fixture
def equipo(company):
    """Una responsable, un administrador y el departamento que ella dirige."""
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        jefa = alguien(company, "jefa", Role.MANAGER, obras)
        obras.managers.add(jefa)
        yield jefa, alguien(company, "admin", Role.ADMIN)


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


def propuesta_sobre(company, quien, la_pide):
    p = Punch.objects.create(
        tenant=company,
        employee=quien,
        punch_type=PunchType.IN,
        timestamp=timezone.now() - timedelta(days=1),
    )
    return PunchCorrection.objects.create(
        tenant=company,
        employee=quien,
        kind=CorrectionKind.MODIFY,
        target=p,
        proposed_timestamp=timezone.now() - timedelta(days=1, hours=2),
        reason="El parte de obra dice otra hora",
        requested_by=la_pide,
    )


@pytest.mark.django_db
def test_una_responsable_no_archiva_sola_un_cambio_sobre_su_fichaje(company, equipo):
    jefa, admin = equipo
    with tenant_context(company.id):
        correccion = propuesta_sobre(company, jefa, admin)
        # El control que hace que este caso signifique algo: si no hubiera otra
        # persona al mando, negarlo sería el defecto contrario.
        assert someone_else_could_decide(company=company, decider=jefa)

    respuesta = como(jefa).post(
        f"/api/corrections/{correccion.pk}/reject/", {"note": "no procede"}, format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "cannot_decide_your_own"
    correccion.refresh_from_db()
    assert correccion.status == CorrectionStatus.PENDING
    assert correccion.resolved_by is None


@pytest.mark.django_db
def test_y_tampoco_lo_aprueba(company, equipo):
    """La otra mitad, para que la simetría quede fijada y no solo el arreglo."""
    jefa, admin = equipo
    with tenant_context(company.id):
        correccion = propuesta_sobre(company, jefa, admin)

    respuesta = como(jefa).post(
        f"/api/corrections/{correccion.pk}/approve/", {"note": "vale"}, format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "cannot_decide_your_own"


@pytest.mark.django_db
def test_el_administrador_sigue_rechazando_la_de_otra_persona(company, equipo):
    """El control. Sin esto, un arreglo que bloqueara todo pasaría los de arriba."""
    _, admin = equipo
    with tenant_context(company.id):
        obrero = alguien(company, "obrero")
        correccion = propuesta_sobre(company, obrero, obrero)

    respuesta = como(admin).post(
        f"/api/corrections/{correccion.pk}/reject/",
        {"note": "el parte dice otra cosa"},
        format="json",
    )

    assert respuesta.status_code == 200
    correccion.refresh_from_db()
    assert correccion.status == CorrectionStatus.REJECTED
    assert correccion.resolved_by_id == admin.id


@pytest.mark.django_db
def test_quien_esta_sola_al_mando_sigue_pudiendo_y_queda_dicho(db):
    """Un autónomo no tiene segunda persona, y negarlo lo dejaría sin producto.

    Va adelante, y la nota que viaja al informe dice que se resolvió a solas:
    permitirlo en silencio borraría justo la diferencia que el procedimiento
    existe para dejar ver.
    """
    empresa = Tenant.objects.create(name="Autónoma", tax_id="B10101010", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        sola = alguien(empresa, "sola", Role.ADMIN)
        assert not someone_else_could_decide(company=empresa, decider=sola)
        correccion = propuesta_sobre(empresa, sola, sola)

    respuesta = como(sola).post(
        f"/api/corrections/{correccion.pk}/reject/", {"note": "mejor no"}, format="json"
    )

    assert respuesta.status_code == 200
    correccion.refresh_from_db()
    assert correccion.status == CorrectionStatus.REJECTED
    assert "mejor no" in correccion.resolution_note
    assert "misma persona" in correccion.resolution_note, correccion.resolution_note
