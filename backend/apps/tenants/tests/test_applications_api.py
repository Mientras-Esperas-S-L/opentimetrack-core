"""Authorising an application, and what that key can and cannot do.

The models were built, the scopes existed, the delegated punch endpoint was
live --- and there was no route to create an application or issue it a
credential. It could only be done from a Django shell, which means a terminal
at the gate needed somebody with database access to set up.

Everything here is about the credential, because that is what a credential is:
a way into the company's records that is not a person and does not expire on
its own.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.tenants.models import Application, ApplicationCredential, ApplicationScope, Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111")


def make(company, email, role=Role.ADMIN):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email, password=PASSWORD, tenant=company, first_name=email[:3], role=role
        )


@pytest.fixture
def as_admin(company):
    client = APIClient()
    client.force_authenticate(make(company, "admin@acme.test"))
    return client


def authorise(client, **extra):
    return client.post(
        reverse("application-list"),
        {"name": "Terminal de obra", "scopes": [ApplicationScope.PUNCH_DELEGATED], **extra},
        format="json",
    )


# ------------------------------------------------------------------ creating


@pytest.mark.django_db
def test_an_application_can_be_authorised_from_the_api(as_admin):
    response = authorise(as_admin)

    assert response.status_code == 201
    assert response.data["scopes"] == [ApplicationScope.PUNCH_DELEGATED]
    assert response.data["is_active"] is True


@pytest.mark.django_db
def test_an_application_with_no_permissions_is_refused(as_admin):
    """It could do nothing, which is not a state anybody means to create: it is
    a form somebody submitted before finishing."""
    response = authorise(as_admin, scopes=[])

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_permission_that_does_not_exist_is_refused(as_admin):
    """A typo would otherwise be stored and silently grant nothing, which looks
    exactly like a permission that does not work."""
    response = authorise(as_admin, scopes=["punch:everything"])

    assert response.status_code == 400


@pytest.mark.django_db
def test_only_an_administrator_may_authorise_one(company):
    """A manager runs the panel; handing out keys to the records is not part of
    that."""
    manager = make(company, "jefa@acme.test", Role.MANAGER)
    client = APIClient()
    client.force_authenticate(manager)

    assert authorise(client).status_code == 403


# --------------------------------------------------------------- the token


@pytest.mark.django_db
def test_the_token_comes_back_once_and_works(as_admin, company):
    application = authorise(as_admin).data

    issued = as_admin.post(
        reverse("application-credentials", args=[application["id"]]),
        {"label": "Tableta del almacén"},
        format="json",
    )

    assert issued.status_code == 201
    token = issued.data["token"]
    assert token.startswith("ott_app_")

    # And it authenticates. A token that comes back and does not work is worse
    # than none: somebody wires up a terminal and debugs the wrong thing.
    with tenant_context(company.id):
        make(company, "operario@acme.test", Role.EMPLOYEE)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_IDEMPOTENCY_KEY="alta-terminal")
    punch = client.post(
        "/api/punches/delegated/", {"employee_ref": "operario@acme.test"}, format="json"
    )

    assert punch.status_code == 201
    assert punch.data["source"] == "DELEGATED"


@pytest.mark.django_db
def test_the_token_is_never_returned_again(as_admin):
    """Stored hashed, so it cannot be. The interface says so; this is the check
    that it is true rather than merely claimed."""
    application = authorise(as_admin).data
    as_admin.post(reverse("application-credentials", args=[application["id"]]), {}, format="json")

    body = as_admin.get(reverse("application-detail", args=[application["id"]])).json()

    # On the keys, not on the text: `token_hint` contains the substring
    # "token" and a naive check would pass whatever the response held.
    assert len(body["credentials"]) == 1
    assert "token" not in body["credentials"][0]
    # Only the last characters, enough to tell two apart and useless alone.
    assert len(body["credentials"][0]["token_hint"]) <= 8


@pytest.mark.django_db
def test_revoking_a_credential_stops_it_without_touching_the_others(as_admin, company):
    """The point of allowing several: rotation without downtime. Issue the new
    one, swap it over, revoke the old."""
    application = authorise(as_admin).data
    old = as_admin.post(
        reverse("application-credentials", args=[application["id"]]), {}, format="json"
    ).data
    new = as_admin.post(
        reverse("application-credentials", args=[application["id"]]), {}, format="json"
    ).data

    revoked = as_admin.post(
        reverse("application-revoke-credential", args=[application["id"], old["id"]])
    )

    assert revoked.status_code == 204

    with tenant_context(company.id):
        make(company, "operario@acme.test", Role.EMPLOYEE)

    # Cada credencial ficha su propia operación: la cabecera es obligatoria y
    # compartir clave haría que la segunda leyera el fichaje de la primera.
    dead = APIClient()
    dead.credentials(
        HTTP_AUTHORIZATION=f"Bearer {old['token']}", HTTP_IDEMPOTENCY_KEY="con-la-vieja"
    )
    alive = APIClient()
    alive.credentials(
        HTTP_AUTHORIZATION=f"Bearer {new['token']}", HTTP_IDEMPOTENCY_KEY="con-la-nueva"
    )

    assert (
        dead.post(
            "/api/punches/delegated/", {"employee_ref": "operario@acme.test"}, format="json"
        ).status_code
        == 401
    )
    assert (
        alive.post(
            "/api/punches/delegated/", {"employee_ref": "operario@acme.test"}, format="json"
        ).status_code
        == 201
    )


# --------------------------------------------------------------- withdrawing


@pytest.mark.django_db
def test_removing_an_application_deactivates_it_and_kills_its_keys(as_admin, company):
    """Not deleted. What it recorded stays attributable to it, and removing the
    row would leave those clock events pointing at nobody."""
    application = authorise(as_admin).data
    credential = as_admin.post(
        reverse("application-credentials", args=[application["id"]]), {}, format="json"
    ).data

    response = as_admin.delete(reverse("application-detail", args=[application["id"]]))

    assert response.status_code == 204
    with tenant_context(company.id):
        stored = Application.objects.get(pk=application["id"])
        assert not stored.is_active
        assert ApplicationCredential.objects.get(pk=credential["id"]).revoked_at is not None


@pytest.mark.django_db
def test_a_revoked_application_cannot_be_given_a_new_key(as_admin):
    """Otherwise revoking is a suggestion."""
    application = authorise(as_admin).data
    as_admin.delete(reverse("application-detail", args=[application["id"]]))

    response = as_admin.post(
        reverse("application-credentials", args=[application["id"]]), {}, format="json"
    )

    assert response.status_code == 409


# ------------------------------------------------------------------- the trail


@pytest.mark.django_db
def test_authorising_and_revoking_are_recorded(
    as_admin, company, django_capture_on_commit_callbacks
):
    """Both are changes to who can reach the records, which is the one category
    the trail exists for."""
    with django_capture_on_commit_callbacks(execute=True):
        application = authorise(as_admin).data
    with django_capture_on_commit_callbacks(execute=True):
        as_admin.delete(reverse("application-detail", args=[application["id"]]))

    with tenant_context(company.id):
        actions = set(
            AuditLog.objects.filter(target_type="application").values_list("action", flat=True)
        )

    assert AuditAction.APPLICATION_CREATED in actions
    assert AuditAction.APPLICATION_REVOKED in actions


# ------------------------------------------------------------------ the scopes


@pytest.mark.django_db
def test_the_grantable_permissions_come_from_the_server(as_admin):
    """So the interface cannot drift from what the API accepts. A list copied
    into the frontend goes stale the first time somebody adds a scope."""
    body = as_admin.get(reverse("application-scopes")).json()

    values = {row["value"] for row in body}
    assert values == set(ApplicationScope.values)
    assert all(row["label"] for row in body)


@pytest.mark.django_db
def test_la_recien_autorizada_sale_la_primera(as_admin, company):
    """Quien acaba de autorizar una aplicación tiene que verla.

    El listado va de cincuenta en cincuenta. Ordenado por nombre ---que era el
    orden--- una aplicación nueva caía donde le tocase alfabéticamente, y en una
    empresa con más de cincuenta se iba a la segunda página: quedaba autorizada,
    invisible, y sin forma de emitirle el testigo ni de revocarla desde la
    pantalla.
    """
    with tenant_context(company.id):
        for nombre in ("Aaa terminal", "Bbb lector", "Zzz puerta"):
            Application.objects.create(tenant=company, name=nombre)

    respuesta = as_admin.post(
        reverse("application-list"),
        {"name": "Mmm recien autorizada", "scopes": [ApplicationScope.READ_PEOPLE]},
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.data

    nombres = [fila["name"] for fila in as_admin.get(reverse("application-list")).data["results"]]
    assert nombres[0] == "Mmm recien autorizada", f"la nueva no sale la primera: {nombres}"


@pytest.mark.django_db
def test_lo_revocado_baja_pero_no_desaparece(as_admin, company):
    """Una aplicación revocada ya no abre nada, pero registró fichajes.

    Por eso se desactiva en vez de borrarse, y por eso baja al final en vez de
    estorbar arriba: lo que se mira a diario es lo que sigue teniendo acceso.
    """
    with tenant_context(company.id):
        viva = Application.objects.create(tenant=company, name="Zzz sigue activa")
        muerta = Application.objects.create(tenant=company, name="Aaa ya no vale")

    assert as_admin.delete(reverse("application-detail", args=[muerta.pk])).status_code == 204

    filas = as_admin.get(reverse("application-list")).data["results"]
    nombres = [fila["name"] for fila in filas]
    assert nombres.index(str(viva.name)) < nombres.index(str(muerta.name)), nombres
    assert str(muerta.name) in nombres, "la revocada ha desaparecido del listado"


@pytest.mark.django_db
def test_el_listado_dice_cuantas_hay_aunque_no_quepan(as_admin, company):
    """Con más de una página, `count` es lo que impide creer que están todas."""
    with tenant_context(company.id):
        Application.objects.bulk_create(
            Application(tenant=company, name=f"App {numero:03d}") for numero in range(55)
        )

    cuerpo = as_admin.get(reverse("application-list")).data
    assert cuerpo["count"] == 55
    assert len(cuerpo["results"]) == 50
    assert cuerpo["next"], "el listado no ofrece la página siguiente"
