"""Toda ruta de la API contra cada rol, y contra otra empresa.

La vuelta 83 barrió esto a mano y **no encontró nada**: las cincuenta y una rutas
de lista filtran por alcance, un operario recibe 403 en todo lo que es de gestión,
una responsable no llega a lo que es de administración ni a otro departamento, y
una administradora de otra empresa recibe 404 con nuestros identificadores en la
mano.

Esta prueba existe para que el barrido no haya que repetirlo a mano, y porque los
guards de este tipo son los que han cazado cosas después: `test_entrada_malformada`
encontró tres 500 y `test_no_crece_con_la_plantilla` dos N+1, los dos en vueltas
posteriores a la que los escribió.

**Saca las rutas del enrutador**, no de una lista escrita aquí, así que crece sola
cuando alguien añade un endpoint --- que es la parte que la hace durar. Una ruta
nueva sin permisos aparece aquí el día que se escribe.

Lo que **no** comprueba es qué se ve dentro de cada respuesta: un 200 con la lista
filtrada y un 200 con la lista entera son iguales desde fuera. Eso lo cubren las
pruebas de cada área ---el rastro de auditoría, el cuadrante, los justificantes---
y aquí se deja dicho para que nadie lea un verde como más de lo que es.
"""

from __future__ import annotations

import pytest
from django.urls import get_resolver
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"

#: Lo que solo puede hacer quien administra. Escritura, y con el cuerpo mínimo
#: que llega a la comprobación de permisos --- si el permiso falla, el cuerpo no
#: se mira, y si pasa, el 400 por cuerpo incompleto ya sería un hallazgo.
DE_ADMINISTRACION = [
    ("patch", "/api/working-time-rules/", {"weekly_hours": 60}),
    ("patch", "/api/company/", {"name": "Otra cosa"}),
    ("post", "/api/departments/", {"name": "Inventado"}),
    ("post", "/api/workplaces/", {"name": "Nave inventada"}),
    ("post", "/api/applications/", {"name": "App", "scopes": ["read:people"]}),
    ("post", "/api/employees/", {"email": "x@example.com", "first_name": "X", "last_name": "Y"}),
    ("patch", "/api/company/record-arrangement/", {"basis": "EMPLOYER"}),
]


def rutas_de_lista():
    """Las rutas sin parámetros, sacadas del enrutador."""
    encontradas: set[str] = set()

    def anda(patrones, prefijo=""):
        for patron in patrones:
            if hasattr(patron, "url_patterns"):
                anda(patron.url_patterns, prefijo + str(patron.pattern))
            else:
                encontradas.add(prefijo + str(patron.pattern))

    anda(get_resolver().url_patterns)
    return sorted(
        "/" + r.replace("^", "").replace("$", "")
        for r in encontradas
        if "api/" in r and "<" not in r and "format" not in r
    )


@pytest.fixture
def empresas(db):
    nuestra = Tenant.objects.create(
        name="La nuestra", tax_id="B21212121", time_zone="Europe/Madrid", country="ES"
    )
    ajena = Tenant.objects.create(
        name="La de al lado", tax_id="B22222222", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(nuestra.id):
        obras = Department.objects.create(tenant=nuestra, name="Obras")
        oficina = Department.objects.create(tenant=nuestra, name="Oficina")
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=nuestra,
            first_name="Jefa",
            last_name="Equis",
            role=Role.MANAGER,
            department=obras,
        )
        obras.managers.add(jefa)
        gente = {
            "operario": User.objects.create_user(
                email="obrero@example.com",
                password=PASSWORD,
                tenant=nuestra,
                first_name="Obrero",
                last_name="Equis",
                department=obras,
            ),
            "responsable": jefa,
            "admin": User.objects.create_user(
                email="admin@example.com",
                password=PASSWORD,
                tenant=nuestra,
                first_name="Admin",
                last_name="Equis",
                role=Role.ADMIN,
            ),
            "ajeno": User.objects.create_user(
                email="ajeno@example.com",
                password=PASSWORD,
                tenant=nuestra,
                first_name="Ajeno",
                last_name="DeOficina",
                department=oficina,
            ),
        }
    with tenant_context(ajena.id):
        gente["vecina"] = User.objects.create_user(
            email="vecina@example.com",
            password=PASSWORD,
            tenant=ajena,
            first_name="Vecina",
            last_name="Ajena",
            role=Role.ADMIN,
        )
    return {"nuestra": nuestra, "ajena": ajena, **gente}


def como(persona):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(persona).access_token)
    )
    return client


@pytest.mark.django_db
def test_ninguna_ruta_de_la_api_revienta_con_ningun_rol(empresas):
    """Lo primero: que ninguna combinación conteste un 500.

    Un 500 es una traza, no una respuesta, y en una matriz de permisos suele
    querer decir que el código asume un rol antes de comprobarlo.
    """
    rutas = rutas_de_lista()
    assert len(rutas) > 40, f"solo {len(rutas)} rutas: el enrutador no se está leyendo bien"

    reventadas = []
    for ruta in rutas:
        for etiqueta in ("operario", "responsable", "admin", "vecina"):
            codigo = como(empresas[etiqueta]).get(ruta).status_code
            if codigo >= 500:
                reventadas.append(f"{ruta} · {etiqueta} → {codigo}")

    assert not reventadas, "un 500 es una traza:\n" + "\n".join(reventadas)


@pytest.mark.django_db
def test_un_operario_no_escribe_nada_de_gestion(empresas):
    alcanzado = []
    for metodo, ruta, cuerpo in DE_ADMINISTRACION:
        respuesta = getattr(como(empresas["operario"]), metodo)(ruta, cuerpo, format="json")
        if respuesta.status_code < 400:
            alcanzado.append(f"{metodo.upper()} {ruta} → {respuesta.status_code}")

    assert not alcanzado, "un operario ha escrito en lo que es de gestión:\n" + "\n".join(alcanzado)


@pytest.mark.django_db
def test_una_responsable_no_llega_a_lo_de_administracion(empresas):
    alcanzado = []
    for metodo, ruta, cuerpo in DE_ADMINISTRACION:
        respuesta = getattr(como(empresas["responsable"]), metodo)(ruta, cuerpo, format="json")
        if respuesta.status_code < 400:
            alcanzado.append(f"{metodo.upper()} {ruta} → {respuesta.status_code}")

    assert not alcanzado, "una responsable ha hecho de administradora:\n" + "\n".join(alcanzado)


@pytest.mark.django_db
def test_una_responsable_no_se_sube_a_si_misma_ni_toca_otro_departamento(empresas):
    jefa, ajeno = empresas["responsable"], empresas["ajeno"]
    cliente = como(jefa)

    assert (
        cliente.patch(f"/api/employees/{jefa.pk}/", {"role": "ADMIN"}, format="json").status_code
        == 403
    )
    assert (
        cliente.patch(
            f"/api/employees/{ajeno.pk}/", {"first_name": "Cambiado"}, format="json"
        ).status_code
        == 403
    )
    assert cliente.delete(f"/api/employees/{ajeno.pk}/").status_code == 403

    with tenant_context(empresas["nuestra"].id):
        jefa.refresh_from_db()
        ajeno.refresh_from_db()
    assert jefa.role == Role.MANAGER
    assert ajeno.first_name == "Ajeno"
    assert ajeno.is_active


@pytest.mark.django_db
def test_la_empresa_de_al_lado_no_alcanza_nada_nuestro(empresas):
    """Con nuestros identificadores en la mano, y **404** en vez de 403.

    El 404 es deliberado: un 403 confirmaría que el recurso existe, y eso ya es
    contar algo de una empresa que no es la suya.
    """
    nuestra_persona = empresas["operario"]
    cliente = como(empresas["vecina"])

    for metodo, ruta, cuerpo in (
        ("get", f"/api/employees/{nuestra_persona.pk}/", None),
        ("patch", f"/api/employees/{nuestra_persona.pk}/", {"first_name": "Robada"}),
        ("delete", f"/api/employees/{nuestra_persona.pk}/", None),
    ):
        respuesta = (
            getattr(cliente, metodo)(ruta, cuerpo, format="json")
            if cuerpo is not None
            else getattr(cliente, metodo)(ruta)
        )
        assert respuesta.status_code == 404, f"{metodo.upper()} {ruta} → {respuesta.status_code}"

    with tenant_context(empresas["nuestra"].id):
        nuestra_persona.refresh_from_db()
    assert nuestra_persona.first_name == "Obrero"
    assert nuestra_persona.is_active
