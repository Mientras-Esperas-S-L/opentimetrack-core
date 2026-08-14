"""Lo que cambia datos tiene que decir quién lo cambió.

El rastro de actividad es de lo que este producto vende, y estaba lleno para
unas cosas y vacío para otras. Salió barriendo las cincuenta y ocho operaciones
de escritura y mirando cuáles llaman a `record()`.

Casi todas las que faltaban lo hacen bien: entrar, salir, renovar la sesión y
recuperar la contraseña son mecánica de sesión ---y los intentos fallidos van al
registro de la aplicación a propósito, porque el rastro se escribe al confirmar
y una petición que falla no confirma nada---. Un fichaje tampoco se audita: el
fichaje **es** el registro, y auditarlo duplicaría la tabla.

Dos sí faltaban:

**El cuadrante.** `assign`, `paint` y `clear` podían repintar o **vaciar** un mes
entero de toda la plantilla sin que constara nadie. Y el cuadrante es contra lo
que se comparan los fichajes, así que un mes que desaparece sin autor es un
hueco que una inspección no puede reconstruir. Solo `reassign` dejaba rastro, y
porque se añadió esa misma mañana.

**El catálogo de permisos.** Cuánto da un permiso es lo que se le debe a la
plantilla: bajar el de matrimonio de quince días a diez cambia el derecho de
todo el mundo. No constaba quién ni desde qué cifra, y eso último es la mitad
que importa ---el convenio puede haber mejorado la legal, y bajarla después no
se distingue de corregir una errata---.

Una entrada por operación y no por turno: pintar un mes a veinte personas son
seiscientas filas, y seiscientas entradas idénticas no son un rastro sino ruido
que entierra el resto.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import LeaveType
from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(name="Rastro SL", tax_id="B80000001", time_zone="Europe/Madrid")
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
            "curro": User.objects.create_user(
                email="curro@example.com", password=PASSWORD, tenant=empresa, first_name="Curro"
            ),
            "patron": ShiftPattern.objects.create(
                tenant=empresa, name="Mañana", segments=[{"start": "08:00", "end": "16:00"}]
            ),
        }


def _como(quien):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(quien).access_token}")
    return cliente


@pytest.mark.django_db
def test_pintar_el_cuadrante_deja_constancia(mundo, django_capture_on_commit_callbacks):
    desde = date.today() + timedelta(days=30)
    hasta = desde + timedelta(days=6)

    with tenant_context(mundo["empresa"].id):
        with django_capture_on_commit_callbacks(execute=True):
            respuesta = _como(mundo["jefa"]).post(
                "/api/shifts/assign/",
                {
                    "employees": [str(mundo["curro"].id)],
                    "pattern": str(mundo["patron"].id),
                    "date_from": desde.isoformat(),
                    "date_to": hasta.isoformat(),
                },
                format="json",
            )
        assert respuesta.status_code == 201, respuesta.json()

        entradas = list(AuditLog.objects.filter(action=AuditAction.SHIFTS_ASSIGNED))

    assert len(entradas) == 1, "una entrada por operación, ni cero ni una por turno"
    assert entradas[0].changes["created"] == respuesta.json()["created"]
    assert entradas[0].changes["from"] == desde.isoformat()


@pytest.mark.django_db
def test_vaciar_el_cuadrante_dice_cuántos_se_llevó(mundo, django_capture_on_commit_callbacks):
    """De las tres del cuadrante, la que más falta hace: borra."""
    desde = date.today() + timedelta(days=30)
    hasta = desde + timedelta(days=6)

    with tenant_context(mundo["empresa"].id):
        cliente = _como(mundo["jefa"])
        cliente.post(
            "/api/shifts/assign/",
            {
                "employees": [str(mundo["curro"].id)],
                "pattern": str(mundo["patron"].id),
                "date_from": desde.isoformat(),
                "date_to": hasta.isoformat(),
            },
            format="json",
        )
        antes = Shift.objects.filter(employee=mundo["curro"]).count()
        assert antes > 0, "sin turnos que borrar esto no comprueba nada"

        with django_capture_on_commit_callbacks(execute=True):
            cliente.post(
                "/api/shifts/clear/",
                {
                    "employees": [str(mundo["curro"].id)],
                    "date_from": desde.isoformat(),
                    "date_to": hasta.isoformat(),
                },
                format="json",
            )

        entrada = AuditLog.objects.filter(action=AuditAction.SHIFTS_CLEARED).first()

    assert entrada is not None, "vaciar un mes no dejaba constancia de nadie"
    assert entrada.changes["removed"] == antes


@pytest.mark.django_db
def test_cambiar_lo_que_da_un_permiso_queda_con_la_cifra_de_antes(
    mundo, django_capture_on_commit_callbacks
):
    """Lo que importa no es que cambió, es **desde qué**.

    El convenio puede haber mejorado la cifra legal, y bajarla después no se
    distingue de corregir una errata si no consta de cuánto se venía.
    """
    with tenant_context(mundo["empresa"].id):
        tipo = LeaveType.objects.create(
            tenant=mundo["empresa"], code="", name="Matrimonio", amount=15, unit="DAYS_CALENDAR"
        )

        with django_capture_on_commit_callbacks(execute=True):
            respuesta = _como(mundo["jefa"]).patch(
                f"/api/leave-types/{tipo.id}/", {"amount": 10}, format="json"
            )
        assert respuesta.status_code == 200, respuesta.json()

        entrada = AuditLog.objects.filter(action=AuditAction.LEAVE_TYPE_CHANGED).first()

    assert entrada is not None, "cambiar lo que da un permiso no dejaba rastro"
    antes, despues = entrada.changes["amount"]
    assert antes.startswith("15") and despues.startswith("10")
    assert "Matrimonio" in entrada.target_label


@pytest.mark.django_db
def test_guardar_sin_cambiar_la_cifra_no_ensucia_el_rastro(
    mundo, django_capture_on_commit_callbacks
):
    """El contraste. Un rastro que anota cada pulsación de «Guardar» es uno que
    nadie lee, y entonces da igual lo que tenga dentro."""
    with tenant_context(mundo["empresa"].id):
        tipo = LeaveType.objects.create(
            tenant=mundo["empresa"], code="", name="Mudanza", amount=1, unit="DAYS_CALENDAR"
        )
        with django_capture_on_commit_callbacks(execute=True):
            _como(mundo["jefa"]).patch(
                f"/api/leave-types/{tipo.id}/", {"note": "Según convenio."}, format="json"
            )

        assert not AuditLog.objects.filter(action=AuditAction.LEAVE_TYPE_CHANGED).exists()


#: Escrituras que no dejan rastro **a propósito**, con el motivo. Cada una es una
#: decisión y no un olvido: si mañana alguien quita una de aquí, la prueba de
#: abajo se lo va a exigir.
SIN_RASTRO_A_PROPOSITO = {
    # Mecánica de sesión. Además el rastro se escribe al confirmar la
    # transacción, y una petición que falla no confirma: por eso los intentos
    # fallidos de entrada van al registro de la aplicación.
    "SignInView": "entrar no es un cambio en el registro de jornada",
    "SignOutView": "salir tampoco",
    "RefreshView": "renovar la sesión tampoco",
    "SignUpView": "el alta crea la empresa: todavía no hay a quién adscribir la entrada",
    "SignUpSerializer": "igual que SignUpView",
    "PasswordResetRequestView": "anotar quién lo pide sería una forma de averiguar quién existe",
    "PasswordSetView": "poner la contraseña propia no cambia el registro de nadie",
    # El fichaje **es** el registro. Auditarlo duplicaría la tabla, y su
    # procedencia ya viaja en el propio fichaje (`source`, `recorded_by`,
    # `source_application`).
    "PunchViewSet": "el fichaje es el registro; su procedencia va en el propio fichaje",
    "DelegatedPunchView": "igual: el fichaje delegado guarda quién lo registró",
    # Preferencias del aparato o de la persona sobre sí misma.
    "PushSubscriptionView": "un móvil apuntándose a los avisos",
    "MeView": "idioma y recordatorios propios",
    # El resumen de nómina **es** la evidencia de haberlo entregado.
    "PayrollSummaryView": "el resumen generado es la propia constancia",
    # Modelos y serializadores: la entrada la escribe la vista que los usa.
    "AuditLog": "la tabla del propio rastro, y es inmutable",
    "UserWriteSerializer": "lo anota UserViewSet",
    "DepartmentSerializer": "lo anota DepartmentViewSet",
}


def test_ninguna_escritura_nueva_nace_sin_rastro():
    """Que la lista de arriba no se quede vieja.

    Un endpoint que cambia datos y no deja constancia no rompe ninguna prueba ni
    se ve en la pantalla: solo se nota el día que alguien pregunta quién lo hizo
    y no hay respuesta. Así que olvidarse tiene que romper la construcción.

    Se mira por clase y no por método porque una vista suele auditar en
    `perform_create` lo que se pide por `create`.
    """
    raiz = pathlib.Path(__file__).resolve().parents[3] / "apps"
    escriben, auditan, hereda = {}, set(), {}

    for fichero in sorted(raiz.rglob("*.py")):
        if "test" in fichero.parts or "migrations" in fichero.parts:
            continue
        texto = fichero.read_text()
        if "class " not in texto:
            continue
        for cls in [n for n in ast.walk(ast.parse(texto)) if isinstance(n, ast.ClassDef)]:
            cuerpo = ast.unparse(cls)
            if "record(" in cuerpo:
                auditan.add(cls.name)
            hereda[cls.name] = {b.id for b in cls.bases if isinstance(b, ast.Name)}
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                deco = ast.unparse(fn.decorator_list).replace('"', "'") if fn.decorator_list else ""
                escribe = fn.name in {
                    "perform_create",
                    "perform_update",
                    "perform_destroy",
                    "create",
                    "update",
                    "destroy",
                } or ("@action" in deco and ("'post'" in deco or "'delete'" in deco))
                if not escribe and fn.name in {"post", "patch", "put", "delete"}:
                    escribe = "APIView" in ast.unparse(cls.bases)
                if escribe:
                    escriben.setdefault(cls.name, str(fichero.relative_to(raiz)))

    # Heredar de algo que audita cuenta: `StructureTrail` lleva el `record()` y
    # las cuatro vistas del armazón lo usan por herencia. Sin esto la sonda
    # pediría un `record()` que ya está, solo que una clase más arriba.
    for _ in range(3):  # tres niveles bastan y no se puede colgar
        auditan |= {c for c, bases in hereda.items() if bases & auditan}

    # Contraste: si la introspección fallara, no encontraría escrituras y esto
    # pasaría sin mirar nada.
    assert len(escriben) > 20, f"solo {len(escriben)} clases con escrituras: ¿se está leyendo algo?"
    assert "UserViewSet" in auditan, "no ve un `record()` que sí está"
    assert "WorkplaceViewSet" in auditan, "no ve un `record()` heredado que sí está"

    mudas = sorted(
        f"{ruta}::{nombre}"
        for nombre, ruta in escriben.items()
        if nombre not in auditan and nombre not in SIN_RASTRO_A_PROPOSITO
    )
    assert not mudas, (
        "cambian datos y no dejan constancia de quién. Añade el `record()`, o "
        "métela en SIN_RASTRO_A_PROPOSITO con su motivo:\n" + "\n".join(mudas)
    )
