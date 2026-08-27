"""«SUB-1» y «sub-1» son la misma identidad, y el empuje ya no crea las dos.

`_resolve` busca la identidad del proveedor con `oidc_sub__iexact`, igual que
busca el correo y el número de empleado. La comprobación que impide pisar la
identidad de otro comparaba **exacto** --- dos líneas por debajo de las de correo y
número, que sí usaban `iexact`.

Medido antes de arreglarlo, empujando la misma identidad con la caja cambiada:

    SUB-1   -> 409 identity_taken
    sub-1   -> 201   crea otra persona
    Sub-1   -> 201   y otra

Tres personas con la misma identidad, y `_resolve` devolviendo la primera sin
decir que había más. No es como duplicar un número de empleado: `oidc_sub` es
«the immutable anchor» del acceso federado, así que con tres anclas iguales quien
entra por el proveedor de identidad cae en cualquiera de las tres --- que es lo
mismo que `users/backends.py` ya advierte del correo duplicado, «son la misma
persona duplicada, y el acceso entraría en cualquiera».

La mitad de este fichero es lo que no puede romperse: una identidad distinta se
sigue aceptando, y no tener identidad es lo normal en una empresa que no usa
proveedor.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.applications import Application, ApplicationCredential, ApplicationScope
from apps.tenants.models import Tenant
from apps.tenants.people_api import _resolve
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
MISMA = ["SUB-1", "sub-1", "Sub-1", " sub-1 "]


@pytest.fixture
def conector(db):
    t = Tenant.objects.create(name="Identidad SL", tax_id="B89898989", time_zone="Europe/Madrid")
    with tenant_context(t.id):
        User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=t,
            first_name="Je",
            last_name="Fa",
            role=Role.ADMIN,
        )
        app = Application.objects.create(
            tenant=t, name="Conector", scopes=[s.value for s in ApplicationScope]
        )
        _c, raw = ApplicationCredential.issue(app, label="x")
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        api.put(
            "/api/app/people/uno@example.com/",
            {"email": "uno@example.com", "first_name": "U", "last_name": "No", "oidc_sub": "SUB-1"},
            format="json",
        )
        yield api, t


@pytest.mark.parametrize("variante", MISMA)
@pytest.mark.django_db
def test_no_se_puede_empujar_la_misma_identidad_con_otra_caja(conector, variante):
    api, t = conector
    with tenant_context(t.id):
        correo = f"otra{abs(hash(variante)) % 9999}@example.com"
        r = api.put(
            f"/api/app/people/{correo}/",
            {"email": correo, "first_name": "O", "last_name": "Tra", "oidc_sub": variante},
            format="json",
        )

    assert r.status_code == 409, (
        f"«{variante}» es la misma identidad que «SUB-1» para todo lo que busca "
        f"personas, y se creó otra: {r.status_code}"
    )
    assert r.json()["error"]["code"] == "identity_taken", r.json()


@pytest.mark.django_db
def test_queda_una_sola_y_las_dos_cajas_llegan_a_ella(conector):
    """Lo que estaba en juego: que el ancla del acceso federado apunte a una."""
    api, t = conector
    with tenant_context(t.id):
        for variante in MISMA:
            correo = f"x{abs(hash(variante)) % 9999}@example.com"
            api.put(
                f"/api/app/people/{correo}/",
                {"email": correo, "first_name": "X", "last_name": "Y", "oidc_sub": variante},
                format="json",
            )
        assert User.objects.filter(oidc_sub__iexact="sub-1").count() == 1
        for variante in ["SUB-1", "sub-1", "Sub-1"]:
            assert _resolve(variante, t).email == "uno@example.com", variante


@pytest.mark.django_db
def test_otra_identidad_distinta_sigue_entrando(conector):
    """El contraste: no vaya a ser que ahora choque con cualquier cosa."""
    api, t = conector
    with tenant_context(t.id):
        r = api.put(
            "/api/app/people/dos@example.com/",
            {"email": "dos@example.com", "first_name": "D", "last_name": "Os", "oidc_sub": "SUB-2"},
            format="json",
        )

    assert r.status_code in (200, 201), r.json()


@pytest.mark.django_db
def test_y_no_tener_identidad_sigue_siendo_normal(conector):
    """Una empresa sin proveedor de identidad no pone `oidc_sub` a nadie, y dos
    personas sin identidad no chocan entre sí."""
    api, t = conector
    with tenant_context(t.id):
        for correo in ["sin1@example.com", "sin2@example.com"]:
            r = api.put(
                f"/api/app/people/{correo}/",
                {"email": correo, "first_name": "S", "last_name": "In"},
                format="json",
            )
            assert r.status_code in (200, 201), r.json()


@pytest.mark.django_db
def test_actualizar_a_la_misma_persona_no_choca_consigo_misma(conector):
    """Se rompe sola si la comprobación no se excluye a sí misma: el empuje
    repetido de la misma ficha es lo que hace un conector cada noche."""
    api, t = conector
    with tenant_context(t.id):
        r = api.put(
            "/api/app/people/uno@example.com/",
            {
                "email": "uno@example.com",
                "first_name": "Cambiado",
                "last_name": "No",
                "oidc_sub": "SUB-1",
            },
            format="json",
        )

    assert r.status_code in (200, 201), r.json()
