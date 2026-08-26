"""Cambiar la contraseña no cerraba las sesiones abiertas.

Un testigo de acceso vive quince minutos; uno de refresco, **siete días** y
rotando --- mientras alguien lo use, se renueva solo. Así que una sesión abierta no
caduca por sí sola en ningún plazo útil, y los dos momentos en que eso importa
fallaban los dos.

**Cambiar la contraseña.** Es lo que hace quien cree que le han visto la clave o
ha perdido el móvil, y era exactamente lo que no servía: medido, ese dispositivo
seguía renovando la sesión y leyendo datos después del cambio. Recuperar la cuenta
no echaba a nadie.

**Dar de baja a una persona.** El acceso deja de valer al instante ---la
autenticación mira `is_active`--- pero el refresco sobrevivía. Y la baja es
reversible: al reincorporarla, la sesión de antes volvía a funcionar sin que
hubiera vuelto a escribir la contraseña. El móvil que llevaba cuando se fue seguía
dentro el día que volvió.

El mecanismo ya estaba puesto ---la rotación pone en la lista negra el refresco
usado--- y no se llamaba desde ninguno de los dos sitios.

Lo que **no** se revoca son los accesos ya emitidos: viven quince minutos a
propósito, y cortarlos exigiría consultar la base en cada petición. Es la ventana
que queda y se deja dicho aquí para que nadie la descubra creyendo que es un
olvido.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User
from apps.users.passwords import build_token

PASSWORD = "a-sufficiently-long-password"
NUEVA = "otra-clave-igual-de-larga-99"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con sesiones", tax_id="B19191919", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Equis",
        )


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Admin",
            last_name="Equis",
            role=Role.ADMIN,
        )


def dos_moviles(persona):
    """Dos sesiones abiertas de la misma persona: una se gasta y otra no.

    Hace falta porque comprobar «la sesión valía antes» **consume** la sesión: la
    rotación pone en la lista negra el refresco usado. Con una sola, el rechazo
    de después venía de eso y no de lo que se está midiendo --- y esta prueba
    pasaba en verde con el arreglo quitado.

    Así que el control se hace con una y la medición con la otra, que llega sin
    estrenar al momento que importa.
    """
    return str(RefreshToken.for_user(persona)), str(RefreshToken.for_user(persona))


def renovar(refresco):
    return APIClient().post("/api/auth/refresh/", {"refresh": refresco}, format="json")


def cambia_la_clave(persona):
    uid, testigo = build_token(persona)
    return APIClient().post(
        "/api/auth/set-password/",
        {"uid": uid, "token": testigo, "password": NUEVA},
        format="json",
    )


@pytest.mark.django_db
def test_el_movil_perdido_queda_fuera_al_cambiar_la_clave(company, quien):
    control, perdido = dos_moviles(quien)
    assert renovar(control).status_code == 200, "el control: la sesión valía antes"

    assert cambia_la_clave(quien).status_code == 200

    assert renovar(perdido).status_code == 409


@pytest.mark.django_db
def test_y_quien_cambia_la_clave_entra_sin_volver_a_escribirla(company, quien):
    """El control. Revocar después de emitir la nueva la habría matado también."""
    respuesta = cambia_la_clave(quien)

    assert respuesta.status_code == 200
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION="Bearer " + respuesta.data["access"])
    assert cliente.get("/api/auth/me/").status_code == 200
    assert renovar(respuesta.data["refresh"]).status_code == 200


@pytest.mark.django_db
def test_dar_de_baja_cierra_su_sesion(company, quien, admin):
    control, perdido = dos_moviles(quien)
    assert renovar(control).status_code == 200, "el control: la sesión valía antes"

    manda = APIClient()
    manda.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(admin).access_token))
    assert manda.delete(f"/api/employees/{quien.pk}/").status_code == 200

    assert renovar(perdido).status_code == 409


@pytest.mark.django_db
def test_reincorporarla_no_revive_la_sesion_de_antes(company, quien, admin):
    """Lo que hace concreto el caso: la baja es reversible."""
    _, perdido = dos_moviles(quien)
    manda = APIClient()
    manda.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(admin).access_token))
    manda.delete(f"/api/employees/{quien.pk}/")

    with tenant_context(company.id):
        quien.refresh_from_db()
        quien.is_active = True
        quien.save(update_fields=["is_active"])

    assert renovar(perdido).status_code == 409, (
        "el móvil que llevaba cuando se fue vuelve a entrar el día que la readmiten"
    )


@pytest.mark.django_db
def test_una_sesion_de_otra_persona_no_se_toca(company, quien, admin):
    """El otro control: revocar es por persona, no por empresa."""
    _, ajena = dos_moviles(admin)

    cambia_la_clave(quien)

    assert renovar(ajena).status_code == 200
