"""Leer la ayuda: qué se sirve, a quién y en qué idioma.

Lo que se fija aquí: que un artículo en una sección apagada no se sirva, que la
cuenta que administra la instalación pueda leerla ---no tiene empresa, y el resto del
servicio le contesta 403--- y que pedirla en un idioma sin escribir devuelva el
castellano en vez de un cajón vacío.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.help.models import HelpArticle, HelpBlock, HelpSection
from apps.tenants.models import Tenant
from apps.users.models import Role, User

pytestmark = pytest.mark.django_db


def _seccion(slug="fichar", language="es", activa=True):
    return HelpSection.objects.create(
        slug=slug, language=language, title=slug.title(), is_active=activa, order=1
    )


def _articulo(section, slug="fichar.general", language="es", publicado=True, titulo="Fichar"):
    article = HelpArticle.objects.create(
        slug=slug,
        language=language,
        section=section,
        title=titulo,
        summary="Cómo se ficha.",
        is_published=publicado,
    )
    HelpBlock.objects.create(
        article=article, order=1, kind=HelpBlock.Kind.PARAGRAPH, data={"text": "Se pulsa el botón."}
    )
    return article


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def quien_ficha(empresa):
    return User.objects.create_user(
        email="operario@acme.test", password="X" * 14, tenant=empresa, role=Role.EMPLOYEE
    )


@pytest.fixture
def instalacion(db):
    """La cuenta que administra la instalación: **sin empresa**."""
    return User.objects.create_superuser(
        email="instalacion@ejemplo.test", password="X" * 14, tenant=None
    )


def cliente(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_el_indice_trae_las_secciones_con_sus_articulos(quien_ficha):
    _articulo(_seccion())

    respuesta = cliente(quien_ficha).get(reverse("help-index"))

    assert respuesta.status_code == 200
    assert respuesta.data["sections"][0]["slug"] == "fichar"
    assert respuesta.data["sections"][0]["articles"][0]["title"] == "Fichar"


def test_una_seccion_apagada_no_sale(quien_ficha):
    """Existe, está publicado, y no se sirve. Lo contrario deja un artículo
    invisible sin decir por qué, que es lo que costó una tarde en el otro producto."""
    _articulo(_seccion(activa=False))

    indice = cliente(quien_ficha).get(reverse("help-index"))
    articulo = cliente(quien_ficha).get(reverse("help-article", args=["fichar.general"]))

    assert indice.data["sections"] == []
    assert articulo.status_code == 404


def test_una_seccion_sin_articulos_publicados_tampoco(quien_ficha):
    _articulo(_seccion(), publicado=False)

    respuesta = cliente(quien_ficha).get(reverse("help-index"))

    assert respuesta.data["sections"] == []


def test_el_articulo_trae_sus_bloques_en_orden(quien_ficha):
    article = _articulo(_seccion())
    HelpBlock.objects.create(
        article=article,
        order=2,
        kind=HelpBlock.Kind.CALLOUT,
        data={"text": "Ojo", "variant": "info"},
    )

    respuesta = cliente(quien_ficha).get(reverse("help-article", args=["fichar.general"]))

    assert respuesta.status_code == 200
    assert [b["kind"] for b in respuesta.data["blocks"]] == ["paragraph", "callout"]


def test_quien_administra_la_instalacion_puede_leerla(instalacion):
    """No tiene empresa, y el resto del servicio le contesta 403. La ayuda no."""
    _articulo(_seccion())

    respuesta = cliente(instalacion).get(reverse("help-index"))

    assert respuesta.status_code == 200
    assert respuesta.data["sections"]


def test_sin_sesion_no_se_lee():
    _articulo(_seccion())

    assert APIClient().get(reverse("help-index")).status_code == 401


def test_un_idioma_sin_escribir_cae_al_castellano(quien_ficha):
    _articulo(_seccion())

    respuesta = cliente(quien_ficha).get(reverse("help-index"), {"language": "gl"})

    assert respuesta.data["language"] == "es"
    assert respuesta.data["sections"]


def test_el_idioma_propio_manda_cuando_existe(quien_ficha):
    _articulo(_seccion())
    _articulo(_seccion(language="ca"), language="ca", titulo="Fitxar")

    respuesta = cliente(quien_ficha).get(reverse("help-index"), {"language": "ca"})

    assert respuesta.data["language"] == "ca"
    assert respuesta.data["sections"][0]["articles"][0]["title"] == "Fitxar"


def test_buscar_mira_el_titulo_el_resumen_y_el_texto(quien_ficha):
    _articulo(_seccion())

    api = cliente(quien_ficha)

    assert api.get(reverse("help-search"), {"q": "fichar"}).data["results"]
    assert api.get(reverse("help-search"), {"q": "botón"}).data["results"]
    assert api.get(reverse("help-search"), {"q": "cuadrante"}).data["results"] == []


def test_buscar_una_letra_no_devuelve_media_ayuda(quien_ficha):
    _articulo(_seccion())

    respuesta = cliente(quien_ficha).get(reverse("help-search"), {"q": "f"})

    assert respuesta.data["results"] == []
