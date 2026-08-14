"""Que el esquema publicado cuente también cómo falla la API.

El esquema declaraba **solo el camino feliz**: 200, 201, 204 y poco más. Ni un
400, ni un 403, ni un 409 en ciento diecinueve operaciones, y ningún componente
que describiera la forma de un error.

Para un producto que vende su API como funcionalidad, eso es justo la mitad que
hace falta. Quien integra escribe el caso bueno leyendo el esquema y el caso
malo a base de provocar fallos y mirar qué sale, que es como se acaba
ramificando sobre textos traducidos en vez de sobre el `code`.

Lo peor es el 409. Este producto rechaza por regla de negocio con 409 y no con
400, a propósito ---400 es «lo has escrito mal» y 409 es «no se puede hacer»---
y sesenta y cinco operaciones pueden devolverlo. Sin documentarlo, un cliente
razonable trata el 409 como fallo transitorio y reintenta en bucle una operación
que nunca va a salir.

## Por qué un gancho y no ciento diecinueve anotaciones

Anotar cada vista a mano sería ponerlo hoy y perderlo mañana: la vista número
ciento veinte nacería sin ello y nadie lo notaría, porque un esquema incompleto
no rompe ninguna prueba. El gancho lo deriva de la propia operación, así que lo
que se añada después nace documentado. Mismo criterio que el paquete de idioma
del tema en el frontend.

Los códigos no se ponen todos a todo. Se ponen los que esa operación puede dar
de verdad, y eso se sabe mirándola: si lleva cuerpo puede haber un 400; si lleva
parámetro en la ruta puede haber un 404; si escribe puede haber un 409.
Declarar un 409 en un `GET` sería la otra forma de mentir.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

#: El sobre, tal cual lo escribe `apps.common.exceptions.api_exception_handler`.
#:
#: `code` es lo único con lo que se puede ramificar: `message` va traducido al
#: idioma de quien pregunta y cambia, y `details` depende del error. Que eso
#: quede dicho en el esquema es media razón de este módulo.
SOBRE_DE_ERROR = {
    "type": "object",
    "properties": {
        "error": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Código estable y legible por máquina. Es lo único sobre lo que "
                        "conviene ramificar: el mensaje va traducido al idioma de quien "
                        "pregunta y puede cambiar de redacción."
                    ),
                    "example": "punch_too_soon",
                },
                "message": {
                    "type": "string",
                    "description": "Explicación para una persona, en su idioma.",
                },
                "details": {
                    "type": "object",
                    "additionalProperties": True,
                    "description": (
                        "Lo que dependa del error. En un 400 de validación, los campos "
                        "que fallan y por qué."
                    ),
                },
            },
            "required": ["code", "message", "details"],
        }
    },
    "required": ["error"],
}

_REF = {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}


def _respuesta(descripcion: str) -> dict:
    return {"description": descripcion, **_REF}


#: Qué puede pasar, y cuándo. El texto importa: es lo que lee quien integra.
CUANDO_LLEVA_CUERPO = {
    "400": _respuesta("Los datos enviados no son válidos. `details` trae los campos que fallan."),
}
CUANDO_ESCRIBE = {
    "409": _respuesta(
        "La operación es correcta pero no se puede hacer: una regla de negocio lo "
        "impide. **No es un fallo transitorio y reintentarlo no cambia nada.** "
        "Ramifica por `code` (por ejemplo `already_resolved`, `punch_too_soon`, "
        "`overlapping_absence`) y enseña `message` a la persona."
    ),
}
CUANDO_HAY_PARAMETRO = {
    "404": _respuesta(
        "No existe, o no es de tu empresa. Las dos cosas contestan igual a propósito: "
        "distinguirlas confirmaría la existencia de datos ajenos."
    ),
}
SIEMPRE_QUE_HAY_SESION = {
    "401": _respuesta("Falta la credencial, o ha caducado."),
    "403": _respuesta("La credencial es válida pero no alcanza para esta operación."),
}
SIEMPRE = {
    "429": _respuesta("Demasiadas peticiones. `message` dice cuánto falta para poder reintentar."),
}

ESCRITURAS = {"post", "put", "patch", "delete"}


def documentar_los_errores(result, generator, request, public):
    """Gancho de posprocesado: añade a cada operación cómo puede fallar.

    Nunca pisa lo que la vista ya declare. Una vista que documenta su propio 409
    con un texto mejor que el genérico se queda con el suyo: esto rellena
    huecos, no impone.
    """
    result.setdefault("components", {}).setdefault("schemas", {})["Error"] = SOBRE_DE_ERROR

    for ruta, operaciones in result.get("paths", {}).items():
        lleva_parametro = "{" in ruta
        for metodo, operacion in operaciones.items():
            if metodo not in {"get", "post", "put", "patch", "delete"}:
                continue

            # `security` aparece en las operaciones que piden credencial y falta
            # en las abiertas. Lo comprobé al revés la primera vez y el esquema
            # salió declarando un 401 en la pantalla de entrar, que es imposible
            # por definición: son cinco ---salud, entrar, alta de empresa, pedir
            # contraseña y ponerla--- y ninguna puede quejarse de una credencial
            # que no pide.
            con_credencial = bool(operacion.get("security"))

            posibles: dict = {}
            if con_credencial:
                posibles |= SIEMPRE_QUE_HAY_SESION
            if operacion.get("requestBody"):
                posibles |= CUANDO_LLEVA_CUERPO
            if lleva_parametro:
                posibles |= CUANDO_HAY_PARAMETRO
            # El 409 solo donde puede darse. Las cuatro operaciones abiertas que
            # escriben ---alta, entrar, pedir contraseña, ponerla--- no lanzan
            # ninguna regla de negocio: comprobado leyendo sus vistas y sus
            # serializadores. Declararlo ahí sería la otra forma de mentir.
            if metodo in ESCRITURAS and con_credencial:
                posibles |= CUANDO_ESCRIBE
            posibles |= SIEMPRE

            respuestas = operacion.setdefault("responses", {})
            for codigo, cuerpo in posibles.items():
                respuestas.setdefault(codigo, cuerpo)

    return result


# --------------------------------------------------- los ámbitos de una aplicación


def _ambitos():
    from apps.tenants.applications import ApplicationScope

    return [(valor, str(etiqueta)) for valor, etiqueta in ApplicationScope.choices]


def _mapa_de_ambitos() -> dict[str, str]:
    """De qué ámbito pide cada ruta, sacado de las propias vistas.

    Se recorre el enrutador en vez de escribir la lista a mano por lo de
    siempre: una vista nueva con `required_scope` nacería sin documentarlo y
    nadie lo notaría, porque un esquema incompleto no rompe nada.
    """
    from django.urls import get_resolver

    def recorrer(resolver, prefijo=""):
        for patron in resolver.url_patterns:
            if hasattr(patron, "url_patterns"):
                yield from recorrer(patron, prefijo + str(patron.pattern))
            else:
                yield prefijo + str(patron.pattern), getattr(patron, "callback", None)

    mapa: dict[str, dict[str, str]] = {}
    for ruta, callback in recorrer(get_resolver()):
        vista = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        if getattr(vista, "required_scope", None) is None:
            continue

        # `api/app/people/<str:reference>/` -> `/api/app/people/{reference}/`
        limpia = "/" + re.sub(r"<[^:>]+:([^>]+)>", r"{\1}", ruta.replace("^", "").replace("$", ""))
        clave = limpia.rstrip("/") + "/"

        # Por método, no por vista, y esta es la parte que importa: hay vistas
        # que piden un ámbito distinto según lo que se haga. Leer una ficha y
        # borrarla no son el mismo permiso, y publicar `read:people` en el
        # DELETE diría que con permiso de lectura se puede dar de baja a alguien
        # ---peor que no documentarlo---.
        concreto = getattr(vista, "required_scope_for", None)
        por_metodo = {}
        for metodo in ("get", "post", "put", "patch", "delete"):
            if not callable(concreto):
                por_metodo[metodo] = str(vista.required_scope)
                continue
            fingida = type("Peticion", (), {"method": metodo.upper()})()
            try:
                por_metodo[metodo] = str(concreto(vista, fingida))
            except Exception:
                # A gritos y no en silencio. Caer al atributo de la clase es
                # justo cómo se publica la documentación equivocada que este
                # bloque existe para evitar, así que si `required_scope_for`
                # se rompe hay que enterarse: el esquema saldría diciendo que
                # con permiso de lectura se puede borrar a alguien.
                logger.exception(
                    "required_scope_for de %s falló para %s; el esquema publicará "
                    "el ámbito de la clase, que puede ser el equivocado",
                    vista.__name__,
                    metodo.upper(),
                )
                por_metodo[metodo] = str(vista.required_scope)
        mapa[clave] = por_metodo
    return mapa


def documentar_los_ambitos(result, generator, request, public):
    """Dice qué ámbitos existen y cuál hace falta para cada llamada.

    Los seis ámbitos se publicaban como una lista sin tipo ni valores: quien
    integraba tenía que adivinar las cadenas o leerse el código, y
    `validate_scopes` rechaza cualquier cosa que no sea una de las seis. Y
    ninguna operación decía cuál pide, así que la única forma de averiguarlo era
    llamar y recibir un 403.

    Es justo la parte del contrato que existe **para** integrar.
    """
    ambitos = _ambitos()
    forma = {
        "type": "array",
        "items": {"type": "string", "enum": [valor for valor, _e in ambitos]},
        "description": (
            "Permisos concedidos, uno a uno. Vacía significa que la aplicación no "
            "puede hacer nada. Valores:\n\n"
            + "\n".join(f"- `{valor}`: {etiqueta}" for valor, etiqueta in ambitos)
        ),
    }
    for nombre in ("Application", "ApplicationRequest", "PatchedApplicationRequest"):
        esquema = result.get("components", {}).get("schemas", {}).get(nombre)
        if esquema and "scopes" in esquema.get("properties", {}):
            esquema["properties"]["scopes"] = {**esquema["properties"]["scopes"], **forma}

    mapa = _mapa_de_ambitos()
    for ruta, operaciones in result.get("paths", {}).items():
        por_metodo = mapa.get(ruta)
        if not por_metodo:
            continue
        for metodo, operacion in operaciones.items():
            if metodo not in {"get", "post", "put", "patch", "delete"}:
                continue
            ambito = por_metodo.get(metodo)
            if not ambito:
                continue
            # En la descripción para quien lee, y como extensión para quien
            # genera un cliente: las dos cosas, porque se consume de las dos.
            operacion["x-required-scope"] = ambito
            aviso = (
                f"\n\n**Credencial de aplicación:** requiere el ámbito `{ambito}`. "
                "Sin él responde 403."
            )
            operacion["description"] = (operacion.get("description") or "").rstrip() + aviso

    return result
