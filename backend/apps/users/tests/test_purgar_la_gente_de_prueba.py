"""El comando que limpia lo que dejan las pruebas, y lo que se niega a limpiar.

Es mantenimiento del entorno de demostración: la suite de navegador da de alta gente
y la retira con la misma acción que usaría alguien de la empresa, pero esa acción se
niega cuando la persona dejó algo que explicar. Lo que se acumula hay que barrerlo, y
esto es la escoba.

Lo que se fija aquí es que la escoba **no barre de más**. Borra por un patrón de
correo, que es lo bastante tosco como para llevarse a quien no debe si nadie lo mira:

- fuera de `DEBUG` no corre, ni con `--hazlo`;
- sin `--hazlo` no toca nada, aunque tenga candidatas delante;
- a quien dejó rastro no lo toca **nunca**, que es la misma regla que aplica la API;
- y a quien no lleva la marca tampoco, por mucho que esté de baja.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Escoba SL", tax_id="B62626262", time_zone="Europe/Madrid")


def alguien(empresa, correo, *, activo=False):
    with tenant_context(empresa):
        return User.objects.create_user(
            email=correo,
            password="a-sufficiently-long-password",
            first_name="Quien",
            last_name="Sea",
            role=Role.EMPLOYEE,
            tenant=empresa,
            is_active=activo,
        )


@override_settings(DEBUG=False)
def test_fuera_de_debug_no_corre_ni_con_hazlo(empresa):
    marcada = alguien(empresa, "prueba.pmtc19cdh21wq@demo.local")

    with pytest.raises(CommandError, match="DEBUG"):
        call_command("purge_test_people", "--hazlo")

    assert User.objects.filter(pk=marcada.pk).exists()


@override_settings(DEBUG=True)
def test_en_seco_no_borra_aunque_haya_candidatas(empresa):
    marcada = alguien(empresa, "prueba.pmtc1whnblcmg@demo.local")

    call_command("purge_test_people")

    assert User.objects.filter(pk=marcada.pk).exists(), "el ensayo en seco ha borrado"


@override_settings(DEBUG=True)
def test_con_hazlo_retira_a_quien_lleva_la_marca_y_no_dejó_rastro(empresa):
    marcada = alguien(empresa, "bloque-pmtc2ki3cs3zd0@demo.local")

    call_command("purge_test_people", "--hazlo")

    assert not User.objects.filter(pk=marcada.pk).exists()


@override_settings(DEBUG=True)
def test_a_quien_dejó_rastro_no_lo_toca(empresa):
    """La misma regla que la API, y el motivo es el mismo: quien tiene una
    ausencia aprobada no es un alta equivocada. Es justo lo que deja
    `14-decidir-en-bloque` cada pasada, así que este caso no es hipotético."""
    con_ausencia = alguien(empresa, "bloque-pmtc3kkcuwz3l0@demo.local")
    with tenant_context(empresa):
        Absence.objects.create(
            tenant=empresa,
            employee=con_ausencia,
            absence_type=AbsenceType.VACATION,
            start_date=dt.date(2026, 3, 2),
            end_date=dt.date(2026, 3, 3),
            status=AbsenceStatus.APPROVED,
        )

    call_command("purge_test_people", "--hazlo")

    assert User.objects.filter(pk=con_ausencia.pk).exists(), "se ha llevado historial por delante"


@override_settings(DEBUG=True)
def test_a_quien_no_lleva_la_marca_no_lo_toca(empresa):
    """El contraste que hace que las de arriba signifiquen algo: si el patrón
    encajara con cualquiera, los cuatro casos anteriores pasarían igual y esto
    sería una escoba que se lleva la plantilla."""
    de_la_casa = alguien(empresa, "ana.perez@escoba.local")
    tambien = alguien(empresa, "rosa@vacia.local")

    call_command("purge_test_people", "--hazlo")

    assert User.objects.filter(pk=de_la_casa.pk).exists()
    assert User.objects.filter(pk=tambien.pk).exists(), "los sujetos fijos de la suite no se tocan"


@override_settings(DEBUG=True)
def test_a_quien_sigue_de_alta_no_lo_toca(empresa):
    activa = alguien(empresa, "prueba.pmtc4pr9ergxh@demo.local", activo=True)

    call_command("purge_test_people", "--hazlo")

    assert User.objects.filter(pk=activa.pk).exists(), "ha borrado a alguien que sigue de alta"
