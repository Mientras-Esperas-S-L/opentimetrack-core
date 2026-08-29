"""`User.objects` no filtra por empresa, y hay que acordarse siempre.

Es el único manager del proyecto que no lo hace, y es a propósito: al entrar
todavía no se sabe de qué empresa es quien llama. La contrapartida es que cada
uso tiene que poner `tenant=` a mano, y olvidarlo no rompe nada visible ---la
pantalla funciona, las pruebas pasan, los datos que se cuelan son plausibles---.

Cazado el 14/08/2026 con una sonda de aislamiento, en dos sitios escritos ese
mismo día, los dos del cuadrante:

- `coverage.py`: el panel de cobertura ofrecía como candidatos a cubrir un turno
  a la plantilla **de todos los clientes de la plataforma**, con nombre y UUID.
- `shifts/views.py`: `reassign` aceptaba uno de esos UUID y enlazaba el turno,
  escribiendo además el nombre de esa persona en el rastro de otra empresa.

Encadenaban: el primero repartía los identificadores que el segundo necesitaba.
Sus vecinas `assign` y `clear` sí llevaban el filtro; las dos nuevas no, y la
diferencia no se ve leyendo el diff.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.clock import local_today
from apps.common.models import tenant_context
from apps.shifts.coverage import who_can_cover
from apps.shifts.models import Shift, ShiftPattern
from apps.tenants.models import Tenant
from apps.users.models import Role, User


@pytest.fixture
def dos_empresas(db):
    """Dos clientes distintos de la misma plataforma. No se conocen de nada."""
    acme = Tenant.objects.create(name="ACME", tax_id="B80000010", time_zone="Europe/Madrid")
    globex = Tenant.objects.create(name="Globex", tax_id="B80000011", time_zone="Europe/Madrid")

    with tenant_context(acme.id):
        jefa = User.objects.create_user(
            email="jefa@acme.example", password="x" * 20, tenant=acme, role=Role.ADMIN
        )
        chelo = User.objects.create_user(
            email="chelo@acme.example", password="x" * 20, tenant=acme, first_name="Chelo"
        )
        patron = ShiftPattern.objects.create(
            tenant=acme, name="Tarde", segments=[{"start": "14:00", "end": "22:00"}]
        )
        turno = Shift.objects.create(
            tenant=acme,
            employee=chelo,
            day=local_today(acme) + timedelta(days=20),
            pattern=patron,
            segments=patron.segments,
        )

    with tenant_context(globex.id):
        secreta = User.objects.create_user(
            email="secreta@globex.example",
            password="x" * 20,
            tenant=globex,
            first_name="Secreta",
            last_name="DeGlobex",
        )

    return {
        "acme": acme,
        "globex": globex,
        "jefa": jefa,
        "chelo": chelo,
        "turno": turno,
        "secreta": secreta,
    }


def _como(quien):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(quien).access_token}")
    return cliente


@pytest.mark.django_db
def test_quien_puede_cubrir_no_ofrece_gente_de_otra_empresa(dos_empresas):
    with tenant_context(dos_empresas["acme"].id):
        candidatos = who_can_cover(shift=dos_empresas["turno"], company=dos_empresas["acme"])

    nombres = {c.employee.get_full_name() or c.employee.email for c in candidatos}
    assert "Secreta DeGlobex" not in nombres, "el panel ofrecía la plantilla de otro cliente"
    # Contraste: si la función devolviera lista vacía por cualquier motivo, la
    # comprobación de arriba pasaría sin comprobar nada.
    assert nombres, "sin candidatos, esta prueba no está mirando nada"


@pytest.mark.django_db
def test_reasignar_a_alguien_de_otra_empresa_no_cuela(dos_empresas):
    with tenant_context(dos_empresas["acme"].id):
        respuesta = _como(dos_empresas["jefa"]).post(
            f"/api/shifts/{dos_empresas['turno'].id}/reassign/",
            {"employee": str(dos_empresas["secreta"].id)},
            format="json",
        )
        assert respuesta.status_code >= 400, respuesta.json()

        dos_empresas["turno"].refresh_from_db()
        assert dos_empresas["turno"].employee_id == dos_empresas["chelo"].id

    # Y el contraste: con alguien de la propia empresa sí funciona, así que el
    # 4xx de arriba es por la empresa y no porque el endpoint esté roto.
    with tenant_context(dos_empresas["acme"].id):
        otra = User.objects.create_user(
            email="otra@acme.example",
            password="x" * 20,
            tenant=dos_empresas["acme"],
            first_name="Otra",
        )
        ok = _como(dos_empresas["jefa"]).post(
            f"/api/shifts/{dos_empresas['turno'].id}/reassign/",
            {"employee": str(otra.id)},
            format="json",
        )
        assert ok.status_code == 200, ok.json()


#: Usos de `User.objects` que **no** llevan `tenant=` con razón. La clave es la
#: ruta relativa **completa** y un trozo del texto de la llamada; la razón, el
#: valor.
#:
#: Por ruta completa y no por nombre de fichero, y esto no es quisquillosidad:
#: la primera versión tenía la clave `"views.py"` para eximir el `views.py` de
#: usuarios, y con eso eximía también a `shifts/views.py`, que era **justo donde
#: estaba la fuga**. Una sonda con esa exención se habría escrito, habría pasado
#: en verde y no habría visto el fallo que la motivó.
SIN_EMPRESA_A_PROPOSITO = {
    ("users/backends.py", "lookup"): "autenticar: todavía no se sabe de qué empresa es",
    ("users/backends.py", "pk=user_id"): "recuperar la sesión por su propio id",
    ("users/views.py", "email__iexact"): "recuperar contraseña va por correo, sin empresa",
    (
        "users/views.py",
        "pk=quien, is_active=True",
    ): "renovar la sesión es anónimo: el token trae el id y todavía no hay empresa",
    ("common/scope.py", "pk=user.pk"): "uno mismo, no hay nada que fugar",
    ("common/management/commands/seed_demo.py", ""): "comando de demostración, no una petición",
    (
        "users/management/commands/backfill_department_history.py",
        "",
    ): "estrena el historial de adscripción en todas las empresas a la vez, y por eso no acota",
    (
        "users/management/commands/purge_test_people.py",
        "",
    ): "barre el entorno de demostración entero, y no hay petición de la que sacar la empresa",
}


def test_ningun_user_objects_nuevo_se_olvida_de_la_empresa():
    """Que no vuelva a pasar, que es el único remedio de verdad.

    Olvidar el `tenant=` no rompe ninguna prueba ni se ve en la pantalla: la
    respuesta llega, tiene la forma correcta y los datos son plausibles. Solo se
    nota si alguien se para a mirar de quién son.
    """
    raiz = pathlib.Path(__file__).resolve().parents[3] / "apps"
    culpables, vistos = [], 0

    for fichero in sorted(raiz.rglob("*.py")):
        partes = set(fichero.parts)
        if partes & {"tests", "migrations"} or fichero.name.startswith("test_"):
            continue
        arbol = ast.parse(fichero.read_text())

        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Attribute):
                continue
            if nodo.func.attr not in {"filter", "get", "exclude"}:
                continue
            # `User.objects.<algo>(...)`, y nada más.
            duenno = nodo.func.value
            if not (
                isinstance(duenno, ast.Attribute)
                and duenno.attr == "objects"
                and isinstance(duenno.value, ast.Name)
                and duenno.value.id == "User"
            ):
                continue

            vistos += 1
            texto = ast.unparse(nodo)
            if "tenant" in texto:
                continue
            ruta = str(fichero.relative_to(raiz))
            if any(ruta == r and trozo in texto for r, trozo in SIN_EMPRESA_A_PROPOSITO):
                continue
            culpables.append(f"{ruta}:{nodo.lineno}  {texto[:90]}")

    # Contraste del instrumento: tiene que estar viendo los usos legítimos, o no
    # está recorriendo nada y su silencio no significa nada.
    assert vistos > 15, f"solo {vistos} usos de `User.objects`: ¿está leyendo el proyecto?"

    assert not culpables, (
        "`User.objects` no filtra por empresa: estos usos pueden devolver gente de "
        "otro cliente. Añade `tenant=`, o mete el fichero en SIN_EMPRESA_A_PROPOSITO "
        "con su motivo:\n" + "\n".join(culpables)
    )
