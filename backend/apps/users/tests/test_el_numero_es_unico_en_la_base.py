"""La base también trata «EMP-9» y «emp-9» como el mismo número.

La vuelta 118 lo arregló en el alta por API: `validate_employee_id` compara con
`iexact`, igual que los dos sitios que resuelven una referencia ---la puerta de
integración y el fichaje delegado---. Pero la restricción de la base seguía
comparando exacto, así que por shell, por importación o por cualquier camino que
no pase por el serializador se podían crear las dos. Y entonces una puerta
resolvía una al azar y la otra se plantaba con «la referencia coincide con más de
una persona», para todo el mundo.

Ahora el índice es sobre `Lower(employee_id)`, así que la base misma lo impide.

La migración que lo cambia **se niega antes de tocar nada** si encuentra números
que chocan, y dice cuáles: la empresa, el número y las personas con su correo.
Comprobado en caliente creando un choque a propósito ---se plantó y la base quedó
sin migrar--- porque una defensa que no se ha visto saltar no está puesta.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(
        name="Numero Base SL", tax_id="B13131313", time_zone="Europe/Madrid"
    )


def _persona(empresa, correo, numero):
    return User.objects.create_user(
        email=correo, password=PASSWORD, tenant=empresa,
        first_name="N", last_name="N", employee_id=numero,
    )


@pytest.mark.parametrize("variante", ["EMP-9", "emp-9", "Emp-9", "eMp-9"])
@pytest.mark.django_db
def test_la_base_rechaza_el_mismo_numero_con_otra_caja(empresa, variante):
    """Sin pasar por el serializador: esto es la red de debajo."""
    with tenant_context(empresa.id):
        _persona(empresa, "primera@example.com", "EMP-9")

        with pytest.raises(IntegrityError), transaction.atomic():
            _persona(empresa, f"otra{abs(hash(variante)) % 999}@example.com", variante)


@pytest.mark.django_db
def test_un_numero_distinto_entra_sin_problema(empresa):
    """El contraste: la restricción no puede volverse un muro."""
    with tenant_context(empresa.id):
        _persona(empresa, "primera@example.com", "EMP-9")
        _persona(empresa, "segunda@example.com", "EMP-10")

        assert User.objects.filter(tenant=empresa).exclude(employee_id="").count() == 2


@pytest.mark.django_db
def test_varias_personas_sin_numero_no_chocan(empresa):
    """Numerar es opcional, y el vacío no puede chocar consigo mismo: eso es lo
    que hace la condición del índice, y romperla dejaría a una empresa que no
    numera con una sola persona dada de alta."""
    with tenant_context(empresa.id):
        for correo in ["sin1@example.com", "sin2@example.com", "sin3@example.com"]:
            _persona(empresa, correo, "")

        assert User.objects.filter(tenant=empresa, employee_id="").count() == 3


@pytest.mark.django_db
def test_dos_empresas_pueden_usar_el_mismo_numero(empresa):
    """La otra mitad de la condición: el número es único **dentro** de la
    empresa. Dos clientes distintos numeran desde el uno."""
    otra = Tenant.objects.create(
        name="Otra SL", tax_id="B14141414", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        _persona(empresa, "aqui@example.com", "EMP-1")
    with tenant_context(otra.id):
        _persona(otra, "alli@example.com", "EMP-1")

    assert User.objects.filter(employee_id__iexact="emp-1").count() == 2
