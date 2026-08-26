"""Anotar que se informó a alguien no es informarle.

El art. 4.b manda informar a la representación legal cuando una persona
discrepa de un cambio en su registro. El producto guardaba la hora y una nota
con nombre y apellidos ---«Informados: Fulana»--- y ese texto viaja al informe
de inspección. El `help_text` que la empresa lee al marcar la casilla promete
«informado cuando alguien discrepa».

**No salía ningún correo.** Medido en el flujo real y con control: proponer el
cambio mandaba uno a la persona, aplicarlo sin acuerdo mandaba otro, y discrepar
mandaba **cero** mientras la fila afirmaba lo contrario.

Es el «solo citado» en su forma peor: hay campo, hay marca de tiempo, hay nombre
propio y viaja al documento. Todo parece cubierto y nadie recibió nada.

**Qué se manda y qué no.** Que hay una discrepancia, de quién y de qué día. El
texto que la persona escribió no se reproduce: puede contar por qué faltó a una
hora, y eso es suyo. Quien recibe el aviso tiene acceso al registro por el art.
6.2 y puede consultarlo, que es la diferencia entre informar y difundir.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, CorrectionStatus
from apps.punches.models import Punch, PunchCorrection, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"
LO_QUE_ESCRIBE = "Entré a las siete: estuve en el médico y lo puedo justificar."


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="Con comité", tax_id="B51515151", time_zone="Europe/Madrid")


def alguien(company, nombre, **extra):
    return User.objects.create_user(
        email=f"{nombre}@example.com",
        password=PASSWORD,
        tenant=company,
        first_name=nombre.title(),
        last_name="Equis",
        **extra,
    )


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


@pytest.fixture
def equipo(company):
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        jefa = alguien(company, "jefa", role=Role.MANAGER, department=obras)
        obras.managers.add(jefa)
        yield {
            "jefa": jefa,
            "obrero": alguien(company, "obrero", department=obras),
            "obras": obras,
        }


def propone_la_empresa(company, equipo, capturar):
    """El camino real: la empresa propone y la corrección espera respuesta."""
    with tenant_context(company.id):
        p = Punch.objects.create(
            tenant=company,
            employee=equipo["obrero"],
            punch_type=PunchType.IN,
            timestamp=timezone.now() - timedelta(days=1),
        )
    with capturar(execute=True):
        respuesta = como(equipo["jefa"]).post(
            "/api/corrections/",
            {
                "employee": str(equipo["obrero"].id),
                "kind": CorrectionKind.MODIFY,
                "target": str(p.pk),
                "proposed_timestamp": (timezone.now() - timedelta(days=1, hours=2)).isoformat(),
                "reason": "La hora no cuadra con el parte de obra",
            },
            format="json",
        )
    assert respuesta.status_code == 201, respuesta.data
    with tenant_context(company.id):
        return PunchCorrection.objects.get(pk=respuesta.data["id"])


def discrepa(equipo, correccion, capturar):
    with capturar(execute=True):
        return como(equipo["obrero"]).post(
            f"/api/corrections/{correccion.pk}/dispute/",
            {"account": LO_QUE_ESCRIBE},
            format="json",
        )


@pytest.mark.django_db
def test_el_representante_recibe_el_aviso(company, equipo, django_capture_on_commit_callbacks):
    with tenant_context(company.id):
        repre = alguien(company, "repre", department=equipo["obras"], is_worker_representative=True)

    correccion = propone_la_empresa(company, equipo, django_capture_on_commit_callbacks)
    mail.outbox.clear()
    assert discrepa(equipo, correccion, django_capture_on_commit_callbacks).status_code == 200

    destinos = [dirección for correo in mail.outbox for dirección in correo.to]
    assert repre.email in destinos, f"nadie avisó a la representación legal: {destinos}"


@pytest.mark.django_db
def test_y_no_se_le_reenvia_lo_que_la_persona_escribio(
    company, equipo, django_capture_on_commit_callbacks
):
    """Puede contar por qué faltó a una hora, y eso es suyo.

    El art. 6.2 le da acceso al registro, así que puede consultarlo. Informar no
    es difundir.
    """
    with tenant_context(company.id):
        alguien(company, "repre", department=equipo["obras"], is_worker_representative=True)

    correccion = propone_la_empresa(company, equipo, django_capture_on_commit_callbacks)
    mail.outbox.clear()
    discrepa(equipo, correccion, django_capture_on_commit_callbacks)

    para_el_repre = [c for c in mail.outbox if "repre@example.com" in c.to]
    assert para_el_repre, "el control falla: no hay correo al representante que examinar"
    for correo in para_el_repre:
        assert LO_QUE_ESCRIBE not in correo.body
        assert "médico" not in correo.body
        # Sí dice de quién y de qué va, que es lo que el artículo pide.
        assert "Obrero" in correo.body


@pytest.mark.django_db
def test_sin_representantes_se_anota_el_hueco_y_no_se_manda_nada(
    company, equipo, django_capture_on_commit_callbacks
):
    """Decir que se informó a nadie sería peor que reconocer que falta."""
    correccion = propone_la_empresa(company, equipo, django_capture_on_commit_callbacks)
    mail.outbox.clear()
    discrepa(equipo, correccion, django_capture_on_commit_callbacks)

    correccion.refresh_from_db()
    assert "4.b" in correccion.representatives_notice
    assert correccion.representatives_notified_at is not None
    assert mail.outbox == []


@pytest.mark.django_db
def test_la_persona_sigue_recibiendo_lo_suyo(company, equipo, django_capture_on_commit_callbacks):
    """El control de que la sonda ve correos: sin él, un cero no dice nada."""
    mail.outbox.clear()
    propone_la_empresa(company, equipo, django_capture_on_commit_callbacks)

    destinos = [dirección for correo in mail.outbox for dirección in correo.to]
    assert equipo["obrero"].email in destinos


@pytest.mark.django_db
def test_que_falle_el_correo_no_tumba_la_discrepancia(
    company, equipo, django_capture_on_commit_callbacks, settings
):
    """Lo que el artículo protege es que quede constancia, no que salga un correo."""
    with tenant_context(company.id):
        alguien(company, "repre", department=equipo["obras"], is_worker_representative=True)

    correccion = propone_la_empresa(company, equipo, django_capture_on_commit_callbacks)
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "no.existe.invalido"
    settings.EMAIL_TIMEOUT = 1

    assert discrepa(equipo, correccion, django_capture_on_commit_callbacks).status_code == 200

    correccion.refresh_from_db()
    assert correccion.status == CorrectionStatus.AWAITING_EMPLOYEE
    assert correccion.employee_agreed is False
    assert LO_QUE_ESCRIBE in correccion.employee_dissent
