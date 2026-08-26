"""Un motivo que en pantalla dice otra cosa que en el registro.

`U+202E` ---RIGHT-TO-LEFT OVERRIDE--- invierte todo lo que va detrás. El motivo
de una corrección lo escribe quien la pide y lo lee quien la aprueba, así que con
esa marca dentro se aprueba una cosa y queda guardada otra.

No es un detalle de presentación. El art. 4.b del real decreto pendiente pide que
las dos partes acuerden el cambio de un asiento, y el acuerdo se da leyendo ese
motivo; su último inciso obliga a reflejar la discrepancia de quien no está de
acuerdo, que es otro campo de texto libre y el más delicado de todos.

Se rechaza en vez de limpiarse, y por eso: limpiar la discrepancia de un
trabajador es editar lo que hizo constar.

Lo que **no** se toca: acentos, eñes, emoji y saltos de línea. Un filtro que se
lleve por delante un texto normal se apaga a la semana.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
RLO = "‮"
ANCHO_CERO = "​"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Legible", tax_id="B90100001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Escribe",
        )
        User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )
        fichaje = Punch.objects.create(
            tenant=empresa,
            employee=quien,
            punch_type="IN",
            timestamp=timezone.now() - timedelta(hours=3),
            source="WEB",
        )
        yield {"empresa": empresa, "quien": quien, "fichaje": fichaje}


def pedir(quien, fichaje, motivo):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente.post(
        "/api/corrections/",
        {
            "target": str(fichaje.pk),
            "kind": "MODIFY",
            "proposed_timestamp": (fichaje.timestamp + timedelta(minutes=20)).isoformat(),
            "reason": motivo,
        },
        format="json",
    )


@pytest.mark.django_db
def test_un_motivo_con_la_marca_de_inversion_se_rechaza(mundo):
    # Guardado dice «a las 8», en pantalla se lee al revés a partir de la marca.
    respuesta = pedir(mundo["quien"], mundo["fichaje"], f"Fiche a las 8{RLO}00:41 sal y 00:9 a")

    assert respuesta.status_code == 400, "se guardaba un motivo que se lee distinto"
    cuerpo = respuesta.json()["error"]
    assert "reason" in cuerpo["details"]
    # El número del carácter en el mensaje: es invisible, así que sin decir cuál
    # es no hay manera de quitarlo.
    assert "202E" in str(cuerpo["details"]["reason"])


@pytest.mark.django_db
def test_y_el_espacio_de_ancho_cero_tambien(mundo):
    respuesta = pedir(mundo["quien"], mundo["fichaje"], f"Fic{ANCHO_CERO}he mal, era mas tarde")

    assert respuesta.status_code == 400
    assert "200B" in str(respuesta.json()["error"]["details"]["reason"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "motivo",
    [
        "Fiché mal, era más tarde",
        "Se me olvidó fichar al salir\nMe fui a las 18:00",
        "Reunión en Peñíscola 🙂",
        "Entré\ta las 8",
    ],
)
def test_un_motivo_normal_sigue_pasando(mundo, motivo):
    """Acentos, eñes, saltos de línea, tabuladores y emoji: nada de eso engaña."""
    assert pedir(mundo["quien"], mundo["fichaje"], motivo).status_code == 201, motivo


@pytest.mark.django_db
def test_la_discrepancia_del_trabajador_tampoco_se_puede_disfrazar(mundo):
    """El campo del art. 4.b, que es el que no se puede limpiar por detrás."""
    from django.core.exceptions import ValidationError

    from apps.punches.corrections import CorrectionKind, PunchCorrection

    with tenant_context(mundo["empresa"].id):
        correccion = PunchCorrection(
            tenant=mundo["empresa"],
            employee=mundo["quien"],
            target=mundo["fichaje"],
            kind=CorrectionKind.MODIFY,
            reason="Fiche mal",
            employee_dissent=f"No estoy de acuerdo{RLO} odreuca ed yotse",
        )
        with pytest.raises(ValidationError) as caido:
            correccion.full_clean()

    assert "employee_dissent" in caido.value.message_dict


@pytest.mark.django_db
def test_ni_el_nombre_de_una_persona(mundo):
    """Un nombre invertido en el PDF que se entrega es otro nombre."""
    cliente = APIClient(raise_request_exception=False)
    with tenant_context(mundo["empresa"].id):
        cliente.force_authenticate(user=User.objects.get(email="jefa@example.com"))

    respuesta = cliente.post(
        "/api/employees/",
        {
            "email": "nueva@example.com",
            "first_name": f"Ana{RLO}zereP anaicuL",
            "last_name": "Gomez",
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert "first_name" in respuesta.json()["error"]["details"]
