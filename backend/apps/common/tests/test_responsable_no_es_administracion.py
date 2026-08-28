"""Un responsable no es administración, y hay cosas que solo puede la segunda.

El barrido de aislamiento ya cubría tres cortes ---sin sesión, entre empresas, y
operario contra responsable--- y dejaba fuera el cuarto: **responsable contra
administración**. Es una distinción real del producto y con consecuencias:
emitir la credencial de una aplicación es repartir una llave a los registros de
la empresa entera, y cambiar las reglas de jornada mueve el suelo contra el que
se mide todo lo demás.

Salió limpio. Veintiuna operaciones de administración correctamente negadas a un
responsable, y catorce de las suyas que sigue pudiendo hacer. Esto no arregla
nada: **es la guarda**. La próxima vista que se añada con la clase de permiso
equivocada se cae aquí, y ese error no se ve mirando la pantalla porque el menú
ya oculta lo que no toca ---ocultar un enlace no es un permiso---.

## El contraste no es opcional

«Veintiún 403» también sale si quien prueba no es responsable de verdad ---un rol
mal puesto en el montaje y todo se niega igual---. Por eso la segunda mitad
comprueba que ese mismo cliente **sí** puede hacer lo suyo. Si las dos listas
dieran 403, la prueba estaría verde sin haber probado nada.

## Y la lista no puede quedarse vieja

La tercera prueba deriva del código las rutas que tienen algo que ver con
administración ---por su clase de permiso o por sobrescribir `get_permissions`---
y exige que cada una esté nombrada aquí. Es el mismo truco que sostiene el
barrido de aislamiento: olvidarse tiene que romper la construcción, no pasar en
silencio.
"""

from __future__ import annotations

import collections
import json
import zoneinfo
from datetime import timedelta

import pytest
from django.urls import get_resolver
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import LeaveType
from apps.common.clock import local_today
from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User, Workplace

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(name="Roles SL", tax_id="B20000001", time_zone="Europe/Madrid")
    with tenant_context(empresa.id):
        yield {
            "empresa": empresa,
            "responsable": User.objects.create_user(
                email="resp@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name="Rosa",
                role=Role.MANAGER,
            ),
            "curro": User.objects.create_user(
                email="curro@example.com", password=PASSWORD, tenant=empresa, first_name="Curro"
            ),
            "departamento": Department.objects.create(tenant=empresa, name="Dep"),
            "centro": Workplace.objects.create(
                tenant=empresa, name="Cen", time_zone="Europe/Madrid"
            ),
            "patron": ShiftPattern.objects.create(
                tenant=empresa, name="M", segments=[{"start": "08:00", "end": "16:00"}]
            ),
            "turno": Shift.objects.create(
                tenant=empresa,
                employee=User.objects.get(email="curro@example.com"),
                day=local_today(empresa) + timedelta(days=5),
                segments=[{"start": "08:00", "end": "16:00"}],
            ),
            "permiso": LeaveType.objects.filter(tenant=empresa).first(),
        }


def _solo_administracion(m):
    """Lo que, según el código, no puede un responsable."""
    curro, dep, cen, pat = m["curro"].id, m["departamento"].id, m["centro"].id, m["patron"].id
    permiso = m["permiso"].id if m["permiso"] else "00000000-0000-0000-0000-000000000000"
    return [
        # Quién está en la empresa y con qué llaves.
        ("POST", "/api/employees/", {"email": "nuevo@example.com", "first_name": "N"}),
        ("PATCH", f"/api/employees/{curro}/", {"first_name": "Cambiado"}),
        ("DELETE", f"/api/employees/{curro}/", None),
        # Mandar la invitación es dar una vía de entrada a los registros.
        ("POST", f"/api/employees/{curro}/invite/", {}),
        ("POST", "/api/applications/", {"name": "App"}),
        # La lista de permisos que se le pueden dar a una aplicación. Va aquí y
        # no en las exclusiones porque es información sobre qué llaves existen,
        # y quien no puede repartir ninguna no la necesita.
        ("GET", "/api/applications/scopes/", None),
        # El suelo contra el que se mide todo lo demás.
        ("PATCH", "/api/company/", {"name": "Otra"}),
        ("PATCH", "/api/company/record-arrangement/", {"basis": "COLLECTIVE", "reference": "X"}),
        ("PATCH", "/api/working-time-rules/", {"weekly_hours": 39}),
        # El catálogo de permisos y el calendario.
        ("POST", "/api/leave-types/seed/", {}),
        ("POST", "/api/leave-types/", {"name": "Inventado", "code": "X", "amount": 1}),
        ("PATCH", f"/api/leave-types/{permiso}/", {"amount": 99}),
        ("POST", "/api/holidays/", {"day": "2027-01-06", "name": "Reyes"}),
        # La estructura de la empresa.
        ("POST", "/api/departments/", {"name": "Nuevo"}),
        ("PATCH", f"/api/departments/{dep}/", {"name": "Cambiado"}),
        ("DELETE", f"/api/departments/{dep}/", None),
        ("POST", "/api/workplaces/", {"name": "Nuevo", "time_zone": "Europe/Madrid"}),
        ("PATCH", f"/api/workplaces/{cen}/", {"name": "Cambiado"}),
        ("DELETE", f"/api/workplaces/{cen}/", None),
        (
            "POST",
            "/api/shift-patterns/",
            {"name": "T", "segments": [{"start": "14:00", "end": "22:00"}]},
        ),
        ("PATCH", f"/api/shift-patterns/{pat}/", {"name": "Cambiado"}),
        ("DELETE", f"/api/shift-patterns/{pat}/", None),
        # Cuándo se llama a trabajar a un fijo discontinuo (art. 16). Un
        # responsable organiza dentro de la temporada; decidir cuál **es** la
        # temporada es decidir cuándo se le espera a alguien, y eso va con el
        # contrato, no con el cuadrante.
        (
            "POST",
            "/api/activity-periods/",
            {"employee": str(curro), "start_date": "2027-06-01"},
        ),
        # El acuerdo de trabajo a distancia (Ley 10/2021). Un responsable
        # organiza el trabajo; firmar el acuerdo que dice desde cuándo alguien
        # trabaja en su casa es de quien lleva los contratos.
        (
            "POST",
            "/api/remote-work-agreements/",
            {"employee": str(curro), "signed_on": "2027-01-15", "starts_on": "2027-02-01"},
        ),
    ]


def _lo_suyo(m):
    """Lo que un responsable SÍ tiene que poder: organizar y decidir."""
    curro, turno = str(m["curro"].id), m["turno"].id
    manana = (local_today(m["curro"]) + timedelta(days=20)).isoformat()
    return [
        ("GET", "/api/employees/", None),
        ("GET", "/api/company/", None),
        ("GET", "/api/working-time-rules/", None),
        ("GET", "/api/leave-types/", None),
        ("GET", "/api/audit/", None),
        ("GET", "/api/audit/export/", None),
        ("GET", "/api/overtime/", None),
        ("GET", "/api/absences/pending/", None),
        ("GET", "/api/reports/payroll-summary/", None),
        ("GET", "/api/shifts/review/?from=2026-09-01&to=2026-09-30", None),
        ("GET", "/api/shifts/coverage/?from=2026-09-01&to=2026-09-30", None),
        (
            "POST",
            "/api/shifts/",
            {"employee": curro, "day": manana, "segments": [{"start": "08:00", "end": "16:00"}]},
        ),
        ("POST", f"/api/shifts/{turno}/reassign/", {"employee": curro}),
        ("POST", "/api/shifts/clear/", {"employee": curro, "days": []}),
    ]


def _como(quien):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(quien).access_token}")
    return cliente


@pytest.mark.django_db
def test_un_responsable_no_puede_hacer_lo_de_administracion(mundo):
    cliente = _como(mundo["responsable"])
    fugas: list[str] = []
    codigos: collections.Counter = collections.Counter()

    with tenant_context(mundo["empresa"].id):
        for metodo, ruta, cuerpo in _solo_administracion(mundo):
            respuesta = cliente.generic(
                metodo, ruta, json.dumps(cuerpo or {}), content_type="application/json"
            )
            codigos[respuesta.status_code] += 1
            # 404 y 405 valen: la ruta no existe para este rol o el método no se
            # sirve. Lo que no puede haber es que la operación salga adelante.
            if respuesta.status_code not in (403, 404, 405):
                fugas.append(f"{respuesta.status_code} {metodo} {ruta}")

    assert sum(codigos.values()) > 15, f"la lista se ha quedado corta: {dict(codigos)}"
    assert not fugas, "un responsable pudo hacer cosas de administración:\n" + "\n".join(fugas)


@pytest.mark.django_db
def test_pero_sigue_pudiendo_hacer_la_suya(mundo):
    """El contraste, y sin él la de arriba no prueba nada.

    Veintiún 403 también salen si quien prueba no es responsable de verdad. Esto
    fija que el mismo cliente sí organiza el cuadrante, lee la plantilla y llega
    a las colas de decisión.
    """
    cliente = _como(mundo["responsable"])
    negados: list[str] = []

    with tenant_context(mundo["empresa"].id):
        for metodo, ruta, cuerpo in _lo_suyo(mundo):
            respuesta = cliente.generic(
                metodo, ruta, json.dumps(cuerpo or {}), content_type="application/json"
            )
            if respuesta.status_code == 403:
                negados.append(f"{metodo} {ruta}")

    assert not negados, "a un responsable se le niega su propio trabajo:\n" + "\n".join(negados)


#: Rutas con control de administración que este barrido **no** ejercita, con el
#: motivo. Cada entrada es una decisión, no un olvido.
FUERA_A_PROPOSITO = {
    # Necesitan una aplicación creada primero, y crearla ya se comprueba arriba:
    # si un responsable no puede crear ninguna, no llega a sus credenciales.
    "api/^applications/(?P<pk>[^/.]+)/$",
    "api/^applications/(?P<pk>[^/.]+)/credentials/$",
    "api/^applications/(?P<pk>[^/.]+)/credentials/(?P<credential>[^/.]+)/revoke/$",
    # Lecturas que cualquiera de la empresa hace, incluida la plantilla. Su
    # corte no es por rol sino por a quién pertenece la fila, y de eso se ocupa
    # el barrido de aislamiento.
    "api/^shifts/$",
    "api/^shifts/(?P<pk>[^/.]+)/$",
    "api/^shifts/today/$",
    "api/^shifts/roster/$",
    "api/^shifts/assign/$",
    "api/^shifts/paint/$",
    "api/^holidays/$",
    "api/^holidays/(?P<pk>[^/.]+)/$",
    "api/^leave-types/$",
    "api/^leave-types/usage/$",
    "api/^audit/$",
    "api/^audit/export/$",
    "api/^audit/(?P<pk>[^/.]+)/$",
    "api/overtime/",
    "api/holiday-recoveries/",
}


@pytest.mark.django_db
def test_ninguna_ruta_con_control_de_rol_se_queda_sin_barrer():
    """Que la lista de arriba no se quede vieja.

    Una vista nueva con la clase de permiso equivocada no se ve en la pantalla
    ---el menú ya oculta lo que no toca, y ocultar un enlace no es un permiso---
    así que el único sitio donde puede saltar es aquí. Olvidarse tiene que
    romper la construcción.
    """

    def recorrer(resolver, prefijo=""):
        for patron in resolver.url_patterns:
            if hasattr(patron, "url_patterns"):
                yield from recorrer(patron, prefijo + str(patron.pattern))
            else:
                yield prefijo + str(patron.pattern), getattr(patron, "callback", None)

    con_control = set()
    for ruta, callback in recorrer(get_resolver()):
        if not ruta.startswith("api/") or "format" in ruta:
            continue
        vista = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        if vista is None:
            continue
        clases = [c.__name__ for c in getattr(vista, "permission_classes", [])]
        # Por la clase, o por resolverlo a mano: `get_permissions` es justo donde
        # se decide caso por caso, y donde es más fácil equivocarse.
        if any("Admin" in c for c in clases) or "get_permissions" in vista.__dict__:
            con_control.add(ruta)

    # Contraste: si la introspección fallara, esto saldría vacío y la
    # comprobación de abajo pasaría sin mirar nada.
    assert len(con_control) > 15, f"la introspección no encuentra las vistas: {con_control}"

    mundo_falso = {
        # Con zona, porque `_lo_suyo` construye una fecha con `local_today` y
        # esta prueba solo quiere las **rutas**: el doble tiene que fingir lo
        # justo para que la lista se pueda montar.
        "curro": type("X", (), {"id": "1", "tzinfo": zoneinfo.ZoneInfo("Europe/Madrid")})(),
        "departamento": type("X", (), {"id": "1"})(),
        "centro": type("X", (), {"id": "1"})(),
        "patron": type("X", (), {"id": "1"})(),
        "turno": type("X", (), {"id": "1"})(),
        "permiso": None,
    }
    nombradas = {
        ruta.split("?")[0]
        for _m, ruta, _c in _solo_administracion(mundo_falso) + _lo_suyo(mundo_falso)
    }

    def esta_nombrada(patron: str) -> bool:
        if patron in FUERA_A_PROPOSITO:
            return True
        # `api/^employees/(?P<pk>…)/$` se cubre con `/api/employees/<algo>/`.
        base = patron.replace("api/", "/api/").replace("^", "").replace("$", "")
        raiz = base.split("(?P<")[0]
        return any(nombrada.startswith(raiz) for nombrada in nombradas)

    sin_barrer = sorted(r for r in con_control if not esta_nombrada(r))
    assert not sin_barrer, (
        "estas rutas tienen control de rol y nadie comprueba qué hace un "
        "responsable con ellas. Añádelas al barrido, o a FUERA_A_PROPOSITO con "
        f"su motivo: {sin_barrer}"
    )
