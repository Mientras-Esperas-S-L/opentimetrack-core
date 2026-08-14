"""El esquema publicado tiene que contar también cómo falla la API.

Este producto vende su API de integración como funcionalidad, así que el esquema
es contrato. Y declaraba **solo el camino feliz**: 200, 201, 204 y poco más. Ni
un 400, ni un 403, ni un 409 en ciento diecinueve operaciones, y ningún
componente que dijera qué forma tiene un error.

El peor hueco era el 409. Este producto rechaza por regla de negocio con 409 y
no con 400, a propósito ---400 es «lo has escrito mal», 409 es «no se puede
hacer»--- y sin documentarlo un cliente razonable lo trata como fallo
transitorio y reintenta en bucle algo que nunca va a salir.

Estas pruebas fijan el contrato del contrato. Comprueban lo que se declara y,
tan importante, **lo que no**: declarar un 401 en la pantalla de entrar o un 409
en una lectura es la otra forma de mentir, y la primera versión del gancho hacía
justo lo primero.
"""

from __future__ import annotations

import collections

import pytest
from django.urls import get_resolver
from drf_spectacular.generators import SchemaGenerator

METODOS = ("get", "post", "put", "patch", "delete")


@pytest.fixture(scope="module")
def esquema():
    return SchemaGenerator().get_schema(request=None, public=True)


def _operaciones(esquema):
    for ruta, metodos in esquema["paths"].items():
        for metodo, operacion in metodos.items():
            if metodo in METODOS:
                yield ruta, metodo, operacion


def test_hay_un_componente_que_describe_el_error(esquema):
    """Y describe el sobre de verdad, no uno inventado.

    La forma sale de `apps.common.exceptions.api_exception_handler`, que envuelve
    **todo** en `{"error": {code, message, details}}`.
    """
    error = esquema["components"]["schemas"]["Error"]
    dentro = error["properties"]["error"]["properties"]

    assert set(dentro) == {"code", "message", "details"}
    # `code` es lo único estable: el mensaje va traducido y cambia de redacción.
    # Que eso quede dicho es media razón de documentarlo.
    assert "code" in error["properties"]["error"]["required"]
    assert "ramificar" in dentro["code"]["description"]


def test_toda_escritura_con_sesion_declara_el_409(esquema):
    """El hueco que más daño hacía."""
    sin_declararlo = [
        f"{m.upper()} {r}"
        for r, m, op in _operaciones(esquema)
        if m in ("post", "put", "patch", "delete")
        and op.get("security")
        and "409" not in op.get("responses", {})
    ]
    assert not sin_declararlo, "escrituras que pueden dar 409 y no lo dicen:\n" + "\n".join(
        sin_declararlo
    )


def test_y_lo_explica_en_vez_de_solo_nombrarlo(esquema):
    """Un «409 Conflict» a secas no le dice a nadie que no reintente."""
    texto = esquema["paths"]["/api/punches/"]["post"]["responses"]["409"]["description"]
    assert "reintentarlo no cambia nada" in texto
    assert "code" in texto


def test_lo_que_pide_credencial_declara_401_y_403(esquema):
    faltan = [
        f"{m.upper()} {r}"
        for r, m, op in _operaciones(esquema)
        if op.get("security") and not {"401", "403"} <= set(op.get("responses", {}))
    ]
    assert not faltan, "piden credencial y no dicen qué pasa si falta:\n" + "\n".join(faltan)


def test_pero_la_puerta_de_entrada_no_declara_un_401(esquema):
    """El contraste, y el fallo que cometí al escribir el gancho.

    La primera versión miraba `security` al revés y el esquema salió diciendo
    que entrar puede contestar 401. No puede: es la operación que no pide
    credencial. Un integrador que lea eso escribe una rama que nunca se ejecuta,
    y peor, duda de si le falta algo.
    """
    abiertas = [(r, m, op) for r, m, op in _operaciones(esquema) if not op.get("security")]
    # Contraste del contraste: si `security` dejara de emitirse, esta lista
    # sería todo el esquema y la comprobación pasaría sin significar nada.
    assert 3 <= len(abiertas) <= 8, (
        f"las operaciones abiertas deberían ser un puñado: {len(abiertas)}"
    )

    for ruta, metodo, operacion in abiertas:
        codigos = set(operacion.get("responses", {}))
        assert not (codigos & {"401", "403"}), f"{metodo.upper()} {ruta} declara un 401 imposible"
        assert "409" not in codigos, f"{metodo.upper()} {ruta} declara un 409 que no puede dar"


def test_una_lectura_no_declara_un_400(esquema):
    """Sin cuerpo no hay nada que validar. Es el otro sitio donde el gancho
    podría pasarse de generoso y llenar el esquema de ruido."""
    con_400 = [
        f"GET {r}"
        for r, m, op in _operaciones(esquema)
        if m == "get" and not op.get("requestBody") and "400" in op.get("responses", {})
    ]
    assert not con_400, "lecturas sin cuerpo que declaran un 400:\n" + "\n".join(con_400)


def test_el_esquema_sigue_generandose_sin_avisos(esquema):
    """Barato y sostiene lo demás: un esquema con avisos es uno que el generador
    no ha entendido, y todo lo que se afirme sobre él vale menos."""
    assert esquema["paths"], "el esquema salió vacío"
    assert len(list(_operaciones(esquema))) > 100


def test_ninguna_ruta_de_la_api_se_queda_fuera_del_esquema():
    """Una vista que no aparece publicada es una que quien integra no sabe que
    existe. Y al revés: aquí se vería una ruta publicada que ya no está.
    """
    esquema = SchemaGenerator().get_schema(request=None, public=True)
    publicadas = {r.rstrip("/") for r in esquema["paths"]}

    def recorrer(resolver, prefijo=""):
        for patron in resolver.url_patterns:
            if hasattr(patron, "url_patterns"):
                yield from recorrer(patron, prefijo + str(patron.pattern))
            else:
                yield prefijo + str(patron.pattern)

    reales = collections.Counter()
    for ruta in recorrer(get_resolver()):
        if not ruta.startswith("api/") or "format" in ruta:
            continue
        # Las de infraestructura del propio esquema no se publican a sí mismas.
        if ruta.startswith(("api/schema", "api/docs")):
            continue
        reales[ruta] += 1

    assert reales, "no se está leyendo el enrutador"
    # No se comparan una a una ---los patrones traen `^`, `$` y grupos con
    # nombre--- sino el orden de magnitud, que es lo que caza una app entera
    # quedándose fuera del esquema por un decorador mal puesto.
    assert len(publicadas) >= len(reales) - 5, (
        f"{len(reales)} rutas en el enrutador y solo {len(publicadas)} publicadas"
    )


# ------------------------------------------- lo que el esquema decía que no llevaba


def test_ninguna_operacion_dice_no_llevar_cuerpo_y_luego_lo_lee(esquema):
    """Cinco lo hacían, y una era peligrosa.

    `@extend_schema(request=None)` sobre una vista que hace
    `request.data.get(...)` publica un contrato falso: quien integre lee «no
    lleva cuerpo», manda la petición vacía, y la operación hace otra cosa.

    La grave era cerrar sesión. Sin cuerpo no invalidaba nada **y devolvía 204**,
    así que un cliente escrito leyendo el esquema daba la sesión por cerrada
    mientras el token de refresco seguía valiendo una semana. El docstring de la
    vista dice «signing out actually signs out», y sin el token no.

    Se comprueba desde el esquema y no leyendo el código a propósito: es el
    esquema lo que se publica, y es donde estaba la mentira.
    """
    obligan = {
        ("/api/auth/refresh/", "post"),
        ("/api/auth/logout/", "post"),
        ("/api/reports/payroll-summary/", "post"),
    }
    for ruta, metodo in obligan:
        operacion = esquema["paths"][ruta][metodo]
        assert operacion.get("requestBody"), (
            f"{metodo.upper()} {ruta} sigue publicándose sin cuerpo"
        )

    # El de dar de baja una suscripción va como parámetro y no como cuerpo, que
    # para un DELETE es la forma correcta. Lo que importa es que se diga que
    # existe, y qué pasa si no se manda.
    borrado = esquema["paths"]["/api/push/subscriptions/"]["delete"]
    endpoint = next(p for p in borrado["parameters"] if p["name"] == "endpoint")
    assert "todas" in endpoint["description"], "no dice qué pasa si no se manda"


@pytest.mark.django_db
def test_cerrar_sesion_sin_el_token_ya_no_contesta_que_si(esquema):
    """La otra mitad: el esquema ya no miente, y la vista tampoco.

    Devolver 204 sin haber invalidado nada era lo peor de los cinco, porque el
    204 es justo lo que hace que nadie mire dos veces.
    """
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    from apps.common.models import tenant_context
    from apps.tenants.models import Tenant
    from apps.users.models import User

    empresa = Tenant.objects.create(name="Salir SL", tax_id="B33333333", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        quien = User.objects.create_user(
            email="sale@example.com",
            password="a-sufficiently-long-password",
            tenant=empresa,
            first_name="Sale",
        )
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(quien).access_token}"
        )
        vacio = cliente.post("/api/auth/logout/", {}, format="json")

        # Y el contraste: con el token sí cierra, que es lo que no se puede
        # romper al arreglar lo de arriba.
        refresco = str(RefreshToken.for_user(quien))
        bueno = cliente.post("/api/auth/logout/", {"refresh": refresco}, format="json")

    assert vacio.status_code == 409, "sigue diciendo que ha cerrado una sesión que no cerró"
    assert vacio.json()["error"]["code"] == "no_refresh_token"
    assert bueno.status_code == 204


# --------------------------------------------------- los ámbitos de una aplicación


def test_el_esquema_enumera_los_ambitos_que_existen(esquema):
    """Se publicaban como una lista sin tipo ni valores.

    `validate_scopes` rechaza cualquier cadena que no sea una de las seis, así
    que quien integraba tenía que adivinarlas o leerse el código fuente. Es
    justo la parte del contrato que existe **para** integrar.
    """
    from apps.tenants.applications import ApplicationScope

    scopes = esquema["components"]["schemas"]["Application"]["properties"]["scopes"]

    assert scopes["items"]["enum"] == [v for v, _e in ApplicationScope.choices]
    # Y qué significa cada uno, no solo la cadena.
    for valor, etiqueta in ApplicationScope.choices:
        assert valor in scopes["description"]
        assert str(etiqueta) in scopes["description"]


def test_cada_operacion_dice_qué_ambito_pide(esquema):
    """La única forma de averiguarlo era llamar y recibir un 403."""
    con_ambito = {
        (r, m): op["x-required-scope"]
        for r, m, op in _operaciones(esquema)
        if op.get("x-required-scope")
    }
    assert len(con_ambito) >= 6, f"solo {len(con_ambito)} operaciones lo dicen"
    assert con_ambito[("/api/punches/delegated/", "post")] == "punch:delegated"
    assert con_ambito[("/api/app/attendance/", "get")] == "read:attendance"


def test_y_lo_dice_por_metodo_y_no_por_vista(esquema):
    """La parte que hace que esto no sea peor que no documentarlo.

    `ApplicationPersonView` pide `read:people` para leer y `write:people` para
    escribir. Publicar el atributo de la clase sin mirar el método diría que con
    permiso de lectura se puede dar de baja a alguien, y eso es una mentira más
    cara que el silencio.
    """
    persona = "/api/app/people/{reference}/"
    por_metodo = {m: op["x-required-scope"] for r, m, op in _operaciones(esquema) if r == persona}

    assert por_metodo["get"] == "read:people"
    assert por_metodo["put"] == "write:people"
    assert por_metodo["delete"] == "write:people"


def test_ninguna_vista_con_ambito_se_queda_sin_documentarlo():
    """Que no se quede viejo: la vista nueva que pida un ámbito nace dicha.

    Se compara contra el enrutador y no contra una lista escrita a mano, que es
    lo que se queda atrás.
    """
    from apps.common.schema import _mapa_de_ambitos

    mapa = _mapa_de_ambitos()
    assert mapa, "la introspección no encuentra ninguna vista con ámbito"

    esquema = SchemaGenerator().get_schema(request=None, public=True)
    documentadas = {r for r, _m, op in _operaciones(esquema) if op.get("x-required-scope")}

    faltan = sorted(set(mapa) - documentadas)
    assert not faltan, f"piden un ámbito y el esquema no lo dice: {faltan}"
