"""«Que lo decida otra» solo vale si esa otra puede verlo.

`someone_else_could_decide` contaba a cualquier responsable o administradora
activa. Contar no es poder: desde que una responsable lee solo los departamentos
que lleva, la que existe puede no alcanzar a la persona del caso.

El bloqueo que salía de ahí, medido por la API:

- la única administradora pide corregir un fichaje suyo,
- **409** al intentar resolverlo ella, porque «existe otra»,
- **404** cuando lo intenta esa otra, porque no la ve.

Un asiento del registro mal, sin manera de arreglarlo: art. 34.9 pide que sea
fiable y el art. 4.b que la corrección se pueda tramitar. La excepción de la
administradora en solitario existía justo para esto y no llegaba a aplicarse,
porque preguntaba por la existencia y no por el alcance.

Lo que **no** puede pasar es que esto afloje la separación de las cuatro manos,
así que la mitad de este fichero son los casos donde tiene que seguir negándose.
"""

from __future__ import annotations

import pytest

from apps.common.four_eyes import someone_else_could_decide
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


def empresa(nif, *, acotado=True):
    return Tenant.objects.create(
        name=f"Empresa {nif}",
        tax_id=nif,
        time_zone="Europe/Madrid",
        country="ES",
        managers_see_whole_company=not acotado,
    )


def persona(company, nombre, rol=Role.EMPLOYEE, departamento=None):
    return User.objects.create_user(
        email=f"{nombre.lower()}@{company.tax_id}.local",
        password=PASSWORD,
        tenant=company,
        first_name=nombre,
        last_name="Equis",
        role=rol,
        department=departamento,
    )


@pytest.mark.django_db
def test_una_responsable_de_otro_departamento_no_cuenta_como_segunda_persona():
    company = empresa("B88888891")
    with tenant_context(company.id):
        oficina = Department.objects.create(tenant=company, name="Oficina")
        sola = persona(company, "Sola", Role.ADMIN)
        otra = persona(company, "Otra", Role.MANAGER, oficina)
        oficina.managers.add(otra)

        # Existe, pero no alcanza a la administradora: no pertenece a Oficina.
        assert not someone_else_could_decide(company=company, decider=sola, subject=sola)


@pytest.mark.django_db
def test_pero_si_la_dirige_de_verdad_si_cuenta():
    company = empresa("B88888892")
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        oficina = Department.objects.create(tenant=company, name="Oficina")
        jefa = persona(company, "Jefa", Role.ADMIN, obras)
        resp = persona(company, "Resp", Role.MANAGER, oficina)
        # Lleva Obras desde un despacho de Oficina: el departamento al que se
        # pertenece y el que se dirige son ejes distintos, a propósito.
        obras.managers.add(resp)

        assert someone_else_could_decide(company=company, decider=jefa, subject=jefa)


@pytest.mark.django_db
def test_con_dos_administradoras_se_sigue_negando():
    """La línea que no se cruza: esto no puede aflojar las cuatro manos."""
    company = empresa("B88888893")
    with tenant_context(company.id):
        una = persona(company, "Una", Role.ADMIN)
        persona(company, "Dos", Role.ADMIN)

        assert someone_else_could_decide(company=company, decider=una, subject=una)


@pytest.mark.django_db
def test_y_con_el_acotado_apagado_cualquier_responsable_vale():
    company = empresa("B88888894", acotado=False)
    with tenant_context(company.id):
        oficina = Department.objects.create(tenant=company, name="Oficina")
        sola = persona(company, "Sola", Role.ADMIN)
        otra = persona(company, "Otra", Role.MANAGER, oficina)
        oficina.managers.add(otra)

        # Ahí toda responsable lee la empresa entera, así que sí puede decidir.
        assert someone_else_could_decide(company=company, decider=sola, subject=sola)


@pytest.mark.django_db
def test_quien_no_esta_en_ningun_departamento_solo_lo_alcanza_una_administradora():
    company = empresa("B88888895")
    with tenant_context(company.id):
        obras = Department.objects.create(tenant=company, name="Obras")
        suelta = persona(company, "Suelta", Role.ADMIN)
        resp = persona(company, "Resp", Role.MANAGER, obras)
        obras.managers.add(resp)

        assert not someone_else_could_decide(company=company, decider=suelta, subject=suelta)

        persona(company, "Segunda", Role.ADMIN)
        assert someone_else_could_decide(company=company, decider=suelta, subject=suelta)


@pytest.mark.django_db
def test_una_baja_no_cuenta():
    """Lo que ya valía: quien no está activa no es una segunda persona."""
    company = empresa("B88888896")
    with tenant_context(company.id):
        una = persona(company, "Una", Role.ADMIN)
        dos = persona(company, "Dos", Role.ADMIN)
        dos.is_active = False
        dos.save(update_fields=["is_active"])

        assert not someone_else_could_decide(company=company, decider=una, subject=una)


@pytest.mark.django_db
def test_el_bloqueo_entero_por_la_api(django_capture_on_commit_callbacks):
    """409 a quien puede verla y 404 a quien tiene que decidir: no la resolvía nadie."""
    from datetime import timedelta

    from django.utils import timezone
    from rest_framework.test import APIClient

    from apps.punches.corrections import CorrectionStatus, PunchCorrection
    from apps.punches.models import Punch

    company = empresa("B88888897")
    with tenant_context(company.id):
        oficina = Department.objects.create(tenant=company, name="Oficina")
        sola = persona(company, "Sola", Role.ADMIN)
        otra = persona(company, "Otra", Role.MANAGER, oficina)
        oficina.managers.add(otra)

        cuando = timezone.now() - timedelta(hours=3)
        fichaje = Punch.objects.create(
            tenant=company, employee=sola, punch_type="IN", timestamp=cuando, source="WEB"
        )

    def como(quien):
        cliente = APIClient()
        cliente.force_authenticate(user=quien)
        return cliente

    with django_capture_on_commit_callbacks(execute=True):
        pedida = como(sola).post(
            "/api/corrections/",
            {
                "target": str(fichaje.pk),
                "kind": "MODIFY",
                "proposed_timestamp": (cuando + timedelta(minutes=20)).isoformat(),
                "reason": "me equivoqué al fichar",
            },
            format="json",
        )
    assert pedida.status_code == 201, pedida.content
    cual = pedida.json()["id"]

    # La responsable sigue sin verla, y eso está bien: no responde por ella.
    assert como(otra).post(f"/api/corrections/{cual}/approve/").status_code == 404

    # Y ahora la administradora sí puede, porque no hay nadie más que pueda.
    with django_capture_on_commit_callbacks(execute=True):
        resuelta = como(sola).post(f"/api/corrections/{cual}/approve/")
    assert resuelta.status_code == 200, resuelta.content

    with tenant_context(company.id):
        correccion = PunchCorrection.objects.get(pk=cual)
    assert correccion.status != CorrectionStatus.PENDING, "el asiento se quedaba sin arreglar"
