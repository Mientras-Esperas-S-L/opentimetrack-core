"""Basura contra cada campo de cada endpoint. Nada puede contestar un 500.

Un 400 es «lo has escrito mal» y un 500 es «se me ha roto», y la diferencia
importa por tres motivos: el primero es una respuesta y el segundo es una traza;
un 500 no dice qué corregir; y en la puerta de entrada, que es anónima, la traza
la provoca cualquiera desde Internet.

## Lo que encontró

Tres, y las tres del mismo tipo: **código que asume una cadena y corre antes de
que valide nadie**.

- `POST /api/auth/token/` con `{"email": 12}`. La peor: sin sesión, alcanzable
  desde fuera, y en la función que existe para **registrar los intentos
  fallidos** ---la forma de un ataque---. En vez de la línea del registro salía
  una traza, justo con la entrada que más se parece a un ataque.
- `POST /api/punches/` con `{"source": -1}`. `source_for` lee el cuerpo a pelo
  para decidir con qué origen se guarda el fichaje, antes del serializador.
- `POST /api/shifts/{id}/reassign/` con `{"employee": []}`. Recién escrito ese
  mismo día: un `filter(pk=...)` acepta lo que le den hasta que la base de datos
  se queja, y se queja con un `ValidationError` de Django que nadie captura.

## Por qué por campos y no a bulto

La primera versión mandaba diccionarios genéricos ---`{"employee": None,
"name": [], ...}`--- a todos los endpoints. Salieron 411 peticiones y setenta y
una «aceptadas», que parecía un hallazgo y no lo era: casi ninguna clave
coincidía con un campo de verdad, así que lo que medía era que DRF ignora lo
desconocido. Un vacío que se comprueba limpio por estar mirando al sitio
equivocado.

Esta versión saca los campos **del propio serializador**, así que crece sola
cuando alguien añade uno. Es la parte que la hace durar.
"""

from __future__ import annotations

# Sin `transaction=True`, y no es un detalle: ese modo vacía la base entre
# pruebas con TRUNCATE, y `audit_auditlog` lo rechaza por diseño ---uno de los
# tres disparadores que la hacen inmutable---. El desmontaje falla con
# «Database couldn't be flushed» y parece un problema de la prueba. La
# transacción normal de pytest-django deshace por rollback y no toca la tabla.

import collections
import json
from datetime import date, timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import Absence
from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"

#: Valores que ningún campo debería tragarse rompiéndose. No se comprueba que
#: los rechace ---algunos son válidos en algún campo--- sino que conteste algo.
VENENOS = [
    ("una lista", []),
    ("un objeto", {"a": 1}),
    ("nulo", None),
    ("un booleano", True),
    ("texto donde va otra cosa", "no-soy-valido"),
    ("un negativo enorme", -99999),
    ("cincuenta mil caracteres", "x" * 50_000),
    ("anidado", [[{"a": [None]}]]),
]


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Entradas SL", tax_id="B12345678", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Luisa",
            role=Role.ADMIN,
        )
        otro = User.objects.create_user(
            email="otro@example.com", password=PASSWORD, tenant=empresa, first_name="Curro"
        )
        hoy = date.today()
        yield {
            "empresa": empresa,
            "jefa": jefa,
            "otro": otro,
            "shift": Shift.objects.create(
                tenant=empresa,
                employee=otro,
                day=hoy + timedelta(days=3),
                segments=[{"start": "08:00", "end": "16:00"}],
            ),
            "pattern": ShiftPattern.objects.create(
                tenant=empresa, name="M", segments=[{"start": "08:00", "end": "16:00"}]
            ),
            "absence": Absence.objects.create(
                tenant=empresa,
                employee=otro,
                start_date=hoy + timedelta(days=20),
                end_date=hoy + timedelta(days=21),
            ),
        }


def _objetivos(mundo):
    """Ruta, método y de qué serializador salen los campos."""
    from apps.absences.views import AbsenceRequestSerializer
    from apps.punches.views import PunchSerializer
    from apps.shifts.views import AssignSerializer, ReassignSerializer, RulesSerializer, ShiftSerializer
    from apps.tenants.views import CompanySerializer, RecordArrangementSerializer
    from apps.users.serializers import DepartmentSerializer, UserWriteSerializer, WorkplaceSerializer

    turno = mundo["shift"].id
    return [
        ("POST", "/api/employees/", UserWriteSerializer),
        ("PATCH", f"/api/employees/{mundo['otro'].id}/", UserWriteSerializer),
        ("POST", "/api/departments/", DepartmentSerializer),
        ("POST", "/api/workplaces/", WorkplaceSerializer),
        ("POST", "/api/punches/", PunchSerializer),
        ("POST", "/api/absences/", AbsenceRequestSerializer),
        ("POST", "/api/shifts/", ShiftSerializer),
        ("PATCH", f"/api/shifts/{turno}/", ShiftSerializer),
        ("POST", "/api/shifts/assign/", AssignSerializer),
        ("POST", f"/api/shifts/{turno}/reassign/", ReassignSerializer),
        ("PATCH", "/api/working-time-rules/", RulesSerializer),
        ("PATCH", "/api/company/", CompanySerializer),
        ("PATCH", "/api/company/record-arrangement/", RecordArrangementSerializer),
    ]


#: Los que puede tocar cualquiera sin haber entrado. Van con sus campos a mano
#: porque no salen de un serializador con `get_fields()` utilizable, y porque
#: son los que más falta hace no olvidar.
SIN_SESION = {
    "/api/auth/token/": ["email", "password"],
    "/api/auth/register/": ["email", "password", "first_name", "company_name", "tax_id"],
    "/api/auth/password-reset/": ["email"],
    "/api/auth/set-password/": ["uid", "token", "password"],
    "/api/auth/refresh/": ["refresh"],
}


def _reventar(cliente, metodo, ruta, campos) -> tuple[list[str], collections.Counter]:
    fallos: list[str] = []
    codigos: collections.Counter = collections.Counter()
    for campo in campos:
        for etiqueta, veneno in VENENOS:
            # El cupo de intentos va por IP y lo comparten todas: sin esto, a la
            # quinta petición todo lo demás sale 429 y la prueba pasa por no
            # haber llegado a ningún sitio.
            cache.clear()
            try:
                respuesta = cliente.generic(
                    metodo, ruta, json.dumps({campo: veneno}), content_type="application/json"
                )
            except Exception as exc:  # noqa: BLE001 --- el cliente de pruebas relanza los 500
                fallos.append(f"{metodo} {ruta} · {campo} = {etiqueta} → {type(exc).__name__}")
                continue
            codigos[respuesta.status_code] += 1
            if respuesta.status_code >= 500:
                fallos.append(f"{respuesta.status_code} {metodo} {ruta} · {campo} = {etiqueta}")
    return fallos, codigos


@pytest.mark.django_db
def test_ningun_campo_de_la_api_contesta_un_500(mundo):
    cliente = APIClient()
    cliente.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(mundo['jefa']).access_token}"
    )

    fallos: list[str] = []
    codigos: collections.Counter = collections.Counter()
    campos_probados = 0

    with tenant_context(mundo["empresa"].id):
        for metodo, ruta, serializador in _objetivos(mundo):
            campos = list(serializador().get_fields())
            assert campos, f"{serializador.__name__} no declara campos: no se está probando nada"
            campos_probados += len(campos)
            unos, esos = _reventar(cliente, metodo, ruta, campos)
            fallos += unos
            codigos += esos

    # El contraste, y aquí es imprescindible: «cero 500» también sale si todo
    # contestó 403 o 404 sin llegar a mirar el cuerpo. Tiene que haber
    # validación de verdad ocurriendo, y eso son cuatrocientos.
    assert codigos[400] > 400, f"casi nada llegó a validarse: {dict(codigos)}"
    assert campos_probados > 60, f"solo {campos_probados} campos: falta algún objetivo"

    assert not fallos, "un 500 es una traza, no una respuesta:\n" + "\n".join(sorted(set(fallos)))


@pytest.mark.django_db
def test_la_puerta_de_entrada_tampoco(mundo):
    """Aparte porque es lo que puede tocar cualquiera desde Internet.

    Y porque el fallo que la trajo estaba justo aquí: `{"email": 12}` en
    `/api/auth/token/` reventaba dentro de la función que registra los intentos
    fallidos.
    """
    cliente = APIClient()  # sin credenciales, a propósito

    fallos: list[str] = []
    codigos: collections.Counter = collections.Counter()
    for ruta, campos in SIN_SESION.items():
        unos, esos = _reventar(cliente, "POST", ruta, campos)
        fallos += unos
        codigos += esos

    assert codigos[400] > 50, f"la puerta no está contestando: {dict(codigos)}"
    assert not fallos, "la puerta de entrada devuelve trazas:\n" + "\n".join(sorted(set(fallos)))
