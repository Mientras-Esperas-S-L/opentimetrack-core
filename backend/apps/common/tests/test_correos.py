"""Los correos: en el idioma de quien los recibe, y con su nombre.

Un correo no tiene petición detrás, así que no hereda idioma de ningún sitio
sensato. De los cuatro que manda el producto, **solo uno lo activaba**: los
recordatorios de fichaje, con un comentario que explica exactamente por qué
---«para que no llegue en inglés a alguien que trabaja en castellano solo porque
lo mandó el cron»---. Los otros tres se habían quedado sin ello, y fallaban de
dos maneras distintas:

- **La invitación y la corrección** las dispara otra persona desde su sesión, así
  que salían en **el idioma de quien actuó**. Una empresa castellana pidiéndole
  conformidad a alguien que eligió catalán se la pedía en castellano, y de eso
  va justo el art. 4.b: que acepte o discrepe con conocimiento.
- **El restablecimiento de contraseña** llega sin sesión, así que no había ningún
  idioma activo y caía a `LANGUAGE_CODE`, dijera lo que dijera esa persona.

Y aparte, el que más se nota: el correo del enlace de cuenta saludaba **«Hola :»**.

## Por qué nadie lo había visto

`{% blocktranslate %}` no resuelve accesos a atributos, así que
`{{ user.first_name }}` dentro del bloque se renderiza vacío. Las otras tres
plantillas pasan un `first_name` plano y salen bien; esta era la única con la
forma que no funciona.

Llevaba así desde siempre porque **nada renderizaba estas plantillas**: las
pruebas comprobaban que el correo se manda y a quién, nunca qué pone. Es el
primer mensaje que recibe cualquier empleado nuevo.
"""

from __future__ import annotations

import re

import pytest
from django.core import mail
from django.template.loader import render_to_string
from django.utils import translation
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mixta(db):
    """Empresa castellana con alguien que eligió catalán. El caso que falla."""
    empresa = Tenant.objects.create(
        name="Mixta SL", tax_id="B60000001", time_zone="Europe/Madrid", language="es"
    )
    with tenant_context(empresa.id):
        yield {
            "empresa": empresa,
            "jefa": User.objects.create_user(
                email="jefa@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Luisa",
                role=Role.ADMIN,
            ),
            "catalan": User.objects.create_user(
                email="quim@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Quim",
                locale="ca",
            ),
        }


@pytest.mark.django_db
def test_la_invitacion_saluda_por_su_nombre(mixta):
    """«Hola :» era lo que leía todo empleado nuevo.

    Se comprueba sobre el correo que sale de verdad, no renderizando la
    plantilla a mano: el fallo estaba en cómo el código y la plantilla se
    entienden, así que probar una sin la otra no lo habría visto.
    """
    with tenant_context(mixta["empresa"].id):
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(mixta['jefa']).access_token}"
        )
        mail.outbox.clear()
        respuesta = cliente.post(f"/api/employees/{mixta['catalan'].id}/invite/")

    assert respuesta.status_code in (200, 204), respuesta.json()
    assert mail.outbox, "no se mandó ninguna invitación"
    assert "Quim" in mail.outbox[0].body, f"sigue sin nombre: {mail.outbox[0].body[:60]!r}"
    assert "Hola :" not in mail.outbox[0].body


@pytest.mark.django_db
def test_ninguna_plantilla_mete_un_atributo_dentro_de_blocktranslate():
    """La causa, no solo el síntoma.

    Es un error que no avisa: la plantilla renderiza, el correo sale, y el hueco
    va vacío. Basta con que alguien escriba `{{ user.first_name }}` en la
    siguiente plantilla para repetirlo.
    """
    import re
    from pathlib import Path

    from django.conf import settings

    malas = []
    for plantilla in sorted((Path(settings.BASE_DIR) / "templates" / "emails").glob("*.txt")):
        texto = plantilla.read_text()
        for bloque in re.findall(
            r"{%\s*blocktranslate.*?%}(.*?){%\s*endblocktranslate\s*%}", texto, re.S
        ):
            for variable in re.findall(r"{{\s*([\w.]+)\s*}}", bloque):
                if "." in variable:
                    malas.append(f"{plantilla.name}: {{{{ {variable} }}}}")

    # Contraste: si el patrón no encontrara ningún `blocktranslate`, esto pasaría
    # sin haber mirado nada.
    bloques = sum(
        len(re.findall(r"{%\s*blocktranslate", p.read_text()))
        for p in (Path(settings.BASE_DIR) / "templates" / "emails").glob("*.txt")
    )
    assert bloques >= 4, f"solo se encontraron {bloques} bloques: ¿cambió el formato?"

    assert not malas, (
        "`blocktranslate` no resuelve accesos a atributos y el hueco sale vacío:\n"
        + "\n".join(malas)
    )


@pytest.mark.django_db
def test_el_enlace_de_cuenta_va_en_el_idioma_de_quien_lo_recibe(mixta, settings):
    """Lo manda quien administra, y salía en el idioma de quien administra."""
    from apps.users.passwords import send_account_email

    with tenant_context(mixta["empresa"].id):
        # La sesión de quien actúa está en castellano, como en la vida real.
        with translation.override("es"):
            mail.outbox.clear()
            send_account_email(mixta["catalan"], base_url="http://x", invitation=True)
            en_catalan = mail.outbox[0].body

            mail.outbox.clear()
            send_account_email(mixta["jefa"], base_url="http://x", invitation=True)
            en_castellano = mail.outbox[0].body

    # Se comparan los cuerpos **sin el enlace**, que trae un testigo distinto en
    # cada llamada. La primera versión comparaba el cuerpo entero y fallaba por
    # eso y no por el idioma; la segunda intentó sacar la frase del catálogo con
    # `gettext`, y tampoco: ahí ese texto vive dentro de un `msgid` multilínea
    # que incluye el saludo, así que la frase suelta no existe como mensaje.
    def sin_enlace(texto: str) -> str:
        return re.sub(r"https?://\S+", "", texto).strip()

    esperado = {}
    for idioma in ("ca", "es"):
        with translation.override(idioma):
            esperado[idioma] = sin_enlace(
                render_to_string(
                    "emails/account_link.txt",
                    {
                        "first_name": "Quim" if idioma == "ca" else "Luisa",
                        "company": "Mixta SL",
                        "link": "",
                        "invitation": True,
                        "hours": 24,
                    },
                )
            )

    # Sin `if`. La primera versión era `if esperado_ca != esperado_es:` porque el
    # catálogo catalán no traducía este mensaje, con lo cual la prueba no
    # comprobaba nada. La salida no era escribir mejor el `if`: era traducirlo,
    # que además es lo que el producto necesitaba.
    assert esperado["ca"] != esperado["es"], "sin traducción no se distingue: traduce el mensaje"
    assert sin_enlace(en_catalan) == esperado["ca"], "salió en el idioma de quien lo mandó"
    assert sin_enlace(en_castellano) == esperado["es"]


@pytest.mark.django_db
def test_los_cuatro_envios_activan_un_idioma():
    """La comprobación que aguanta, y la que habría cazado esto.

    Comparar textos no sirve mientras los catálogos estén a medias: lo que se
    puede exigir hoy es que **todos** los sitios que mandan correo activen el
    idioma de quien lo recibe. Tres de los cuatro no lo hacían.
    """
    from pathlib import Path

    from django.conf import settings

    raiz = Path(settings.BASE_DIR) / "apps"
    sin_activar = []
    for fichero in raiz.rglob("*.py"):
        if "test" in fichero.parts or "migrations" in fichero.parts:
            continue
        texto = fichero.read_text()
        if "send_mail(" not in texto:
            continue
        if "translation.override" not in texto:
            sin_activar.append(str(fichero.relative_to(raiz)))

    # Contraste: si nada mandara correo, la lista estaría vacía por el motivo
    # equivocado.
    manda_correo = [
        str(f.relative_to(raiz))
        for f in raiz.rglob("*.py")
        if "test" not in f.parts and "migrations" not in f.parts and "send_mail(" in f.read_text()
    ]
    assert len(manda_correo) >= 3, f"solo {len(manda_correo)} ficheros mandan correo"

    assert not sin_activar, (
        "mandan correo sin activar el idioma de quien lo recibe, así que sale en "
        "el de quien actuó o en el de por defecto:\n" + "\n".join(sin_activar)
    )
