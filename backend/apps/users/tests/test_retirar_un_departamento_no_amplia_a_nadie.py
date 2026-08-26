"""Reorganizar no es repartir permisos.

`visible_people` estrecha a un responsable a los departamentos que le pusieron
al mando, y lee «al mando de nada» como «nada le estrecha». Eso es deliberado y
está razonado en `apps/common/scope.py`: la alternativa dejaría a un responsable
sin ver a nadie el día que la empresa se da de alta.

Retirar el único departamento que alguien dirigía lo deja en ese mismo estado
por otro camino, y ahí el efecto es el contrario del prudente. Medido sobre una
empresa viva antes de tocar nada:

| | Antes | Después de retirar su departamento |
|---|---|---|
| Alcance | 2 personas | todas |
| Fichajes que ve | 1 | 2 |
| Justificante de otro departamento | 404 | **200** |

Ese justificante puede ser un parte médico ---art. 9 del RGPD--- de alguien de
quien nunca respondió. Nadie tocó sus permisos, y el rastro de auditoría dice
«departamento borrado», no «pasa a leer toda la empresa».

Para la gente **del** departamento perderlo es ordenado: conservan todo y pierden
una etiqueta. Para quien **responde** de él es lo contrario, y esa asimetría es
lo que lo hacía fácil de pasar por alto --- el comentario de `WorkplaceViewSet`
dice que para un departamento `SET_NULL` «es una respuesta ordenada», pensando en
los miembros.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.common.scope import visible_people
from apps.punches.models import Punch, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con dos áreas", tax_id="B12121212", time_zone="Europe/Madrid"
    )


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


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


@pytest.fixture
def empresa(company):
    """Dos departamentos, una responsable al mando de uno solo."""
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        oficina = Department.objects.create(tenant=company, name="Oficina")
        jefa = alguien(company, "jefa", Role.MANAGER, obras)
        obras.managers.add(jefa)
        yield {
            "obras": obras,
            "oficina": oficina,
            "jefa": jefa,
            "admin": alguien(company, "admin", Role.ADMIN),
            "suyo": alguien(company, "suyo", dpto=obras),
            "ajeno": alguien(company, "ajeno", dpto=oficina),
        }


@pytest.mark.django_db
def test_no_se_retira_un_departamento_que_alguien_dirige(company, empresa):
    respuesta = como(empresa["admin"]).delete(f"/api/departments/{empresa['obras'].pk}/")

    assert respuesta.status_code == 409
    assert respuesta.data["error"]["code"] == "department_has_managers"
    assert Department.objects.filter(pk=empresa["obras"].pk).exists()


@pytest.mark.django_db
def test_y_su_alcance_sigue_siendo_el_suyo(company, empresa):
    """Lo que el rechazo protege, dicho en lo que la responsable puede leer."""
    with tenant_context(company.id):
        hoy = timezone.now().date()
        Punch.objects.create(
            tenant=company,
            employee=empresa["ajeno"],
            punch_type=PunchType.IN,
            timestamp=timezone.now() - timedelta(days=1),
        )
        parte = Absence.objects.create(
            tenant=company,
            employee=empresa["ajeno"],
            absence_type=AbsenceType.PAID_LEAVE,
            start_date=hoy,
            end_date=hoy,
            status=AbsenceStatus.APPROVED,
            justification=SimpleUploadedFile("parte.pdf", b"%PDF-1.7\n"),
        )

    como(empresa["admin"]).delete(f"/api/departments/{empresa['obras'].pk}/")

    with tenant_context(company.id):
        alcance = visible_people(empresa["jefa"])
    assert alcance is not None, "se ha quedado sin nada que la estreche"
    assert alcance.count() == 2

    ajeno = como(empresa["jefa"]).get(f"/api/absences/{parte.pk}/justification/")
    assert ajeno.status_code == 404, "alcanza un justificante de otro departamento"


@pytest.mark.django_db
def test_uno_sin_responsables_se_retira_sin_problema(company, empresa):
    """El control. Reorganizar tiene que seguir siendo posible."""
    with tenant_context(company.id):
        vacio = Department.objects.create(tenant=company, name="Se cerró")

    assert como(empresa["admin"]).delete(f"/api/departments/{vacio.pk}/").status_code == 204


@pytest.mark.django_db
def test_tener_miembros_no_lo_bloquea(company, empresa):
    """Perder el departamento es ordenado para quien está **en** él.

    Conservan todo y pierden una etiqueta, así que aquí `SET_NULL` sí vale y
    bloquearlo sería convertir una reorganización en un trámite.
    """
    respuesta = como(empresa["admin"]).delete(f"/api/departments/{empresa['oficina'].pk}/")

    assert respuesta.status_code == 204
    empresa["ajeno"].refresh_from_db()
    assert empresa["ajeno"].department_id is None
    assert empresa["ajeno"].is_active


@pytest.mark.django_db
def test_la_via_correcta_es_moverla_primero(company, empresa):
    """Y sigue abierta: es una decisión que alguien toma a propósito."""
    with tenant_context(company.id):
        empresa["obras"].managers.remove(empresa["jefa"])

    assert (
        como(empresa["admin"]).delete(f"/api/departments/{empresa['obras'].pk}/").status_code == 204
    )


@pytest.mark.django_db
def test_una_responsable_dada_de_baja_no_bloquea_nada(company, empresa):
    """Ya no lee nada, así que no hay alcance que ampliar."""
    with tenant_context(company.id):
        empresa["jefa"].is_active = False
        empresa["jefa"].save(update_fields=["is_active"])

    assert (
        como(empresa["admin"]).delete(f"/api/departments/{empresa['obras'].pk}/").status_code == 204
    )
