"""En qué idioma se contesta a cada quien.

El orden lo fija `LocaleAndTimeZoneMiddleware`: primero lo que haya elegido la
persona, luego lo que haya declarado su empresa, y si ninguna de las dos dice
nada, lo que negocie Django con la petición.

Lo que estas pruebas cazaron: **la mitad de la empresa no funcionaba**. El
middleware leía `company.settings["language"]`, una clave de un JSON que nadie
escribe nunca ---la única aparición de esa clave en todo el código era esa
lectura---, mientras el idioma de la empresa vive en `Tenant.language`, columna
de verdad, con sus `choices`, su `default`, y la que escribe la pantalla de
ajustes. Una empresa catalana llevaba desde siempre recibiendo castellano.

No saltó antes porque la web manda `Accept-Language` por su cuenta y el
`LocaleMiddleware` de Django lo respeta: por el navegador se veía bien. Se
rompía justo donde no hay navegador ---los correos, las tareas de fondo,
cualquier integración---, que es donde nadie estaba mirando. El aviso vale más
que el fallo: una comprobación hecha desde la interfaz habría dado verde.

Se prueba con el mensaje del doble toque porque está traducido a los cuatro
idiomas y sale de un sitio real, no de un `gettext` fabricado para la ocasión.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: El del doble toque. Traducido en es, ca y gl.
EN_CASTELLANO = "Acabas de fichar. Mira la pantalla antes de volver a pulsar."


def _mensaje_del_doble_toque(persona) -> str:
    """Ficha dos veces seguidas y devuelve el texto del 409.

    Sin cabecera `Accept-Language` a propósito: con ella el `LocaleMiddleware`
    de Django resuelve por su cuenta y esta prueba no estaría mirando lo que
    dice mirar.
    """
    # Con un JWT de verdad, no con `force_authenticate`: ese deja el
    # `request.user` de Django sin tocar, así que ni el middleware ni la clase
    # de permiso ven a nadie y la prueba mediría otra cosa. Es el error que se
    # cometió al escribirla y el que destapó el fallo de fondo.
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(persona).access_token}")
    cliente.post("/api/punches/", {"kind": "IN"}, format="json")
    respuesta = cliente.post("/api/punches/", {"kind": "IN"}, format="json")

    assert respuesta.status_code == 409, respuesta.json()
    return respuesta.json()["error"]["message"]


def _empresa(idioma: str, sufijo: str) -> Tenant:
    return Tenant.objects.create(
        name=f"Empresa {sufijo}",
        tax_id=f"B{sufijo}",
        time_zone="Europe/Madrid",
        language=idioma,
    )


@pytest.mark.django_db
def test_una_empresa_catalana_recibe_catalan():
    """El fallo original, tal cual: la empresa lo declara y no pasaba nada."""
    empresa = _empresa("ca", "11111111")
    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="qui@example.com", password=PASSWORD, tenant=empresa
        )
        mensaje = _mensaje_del_doble_toque(persona)

    assert mensaje != EN_CASTELLANO, "sigue contestando en castellano a una empresa catalana"
    assert mensaje


@pytest.mark.django_db
def test_una_empresa_castellana_sigue_recibiendo_castellano():
    """El contraste. Sin esto, la de arriba pasaría igual si el middleware
    activara catalán para todo el mundo, que es otra forma de estar roto."""
    empresa = _empresa("es", "22222222")
    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="quien@example.com", password=PASSWORD, tenant=empresa
        )
        mensaje = _mensaje_del_doble_toque(persona)

    assert mensaje == EN_CASTELLANO


@pytest.mark.django_db
def test_lo_que_elige_la_persona_gana_a_lo_que_dice_su_empresa():
    """La otra mitad del orden, que sí funcionaba.

    Va aquí porque las dos mitades leen sitios distintos y romper una no rompe
    la otra: si esto no se comprobara, el arreglo de la de la empresa podría
    haberse llevado esta por delante sin que nada lo dijera.
    """
    empresa = _empresa("es", "33333333")
    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="ela@example.com", password=PASSWORD, tenant=empresa, locale="gl"
        )
        mensaje = _mensaje_del_doble_toque(persona)

    assert mensaje != EN_CASTELLANO, "la elección de la persona no gana a la de su empresa"


@pytest.mark.django_db
def test_sin_nadie_que_opine_se_contesta_en_castellano():
    """Ni la persona ni la empresa dicen nada: manda `LANGUAGE_CODE`.

    Es el suelo del que dependen los catálogos a medias: lo que no está
    traducido cae al castellano y no al inglés en que se escriben los `msgid`.
    """
    empresa = Tenant.objects.create(
        name="Sin idioma", tax_id="B44444444", time_zone="Europe/Madrid", language=""
    )
    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="nadie@example.com", password=PASSWORD, tenant=empresa
        )
        mensaje = _mensaje_del_doble_toque(persona)

    assert mensaje == EN_CASTELLANO


@pytest.mark.django_db
def test_la_clave_del_json_ya_no_la_lee_nadie():
    """Que el sitio equivocado deje de funcionar también se comprueba.

    Si alguien vuelve a poner `settings["language"]` creyendo que es de ahí de
    donde se lee, esto lo dice. Y de paso documenta cuál de los dos sitios es
    el bueno, que es la pregunta que se tardó en contestar.
    """
    empresa = Tenant.objects.create(
        name="Con el JSON", tax_id="B55555555", time_zone="Europe/Madrid", language=""
    )
    empresa.settings = {"language": "ca"}
    empresa.save(update_fields=["settings"])

    with tenant_context(empresa.id):
        persona = User.objects.create_user(
            email="json@example.com", password=PASSWORD, tenant=empresa
        )
        mensaje = _mensaje_del_doble_toque(persona)

    assert mensaje == EN_CASTELLANO, "el idioma se está leyendo del JSON otra vez"
