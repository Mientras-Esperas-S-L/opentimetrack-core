"""Pasarle Obras a otra responsable no deja a la primera leyendo la empresa entera.

La vuelta 73 cerró una puerta a este estado: borrar un departamento que tiene
responsables responde 409. Quedaban dos más, y las dos contestaban 200:

- quitar a la responsable de la lista de `managers`, y
- **entregarle el departamento a otra**, que es la reorganización de toda la
  vida --- «Ana ya no lleva Obras, ahora lo lleva Berta».

Las dos acababan igual: Ana pasaba de leer a su cuadrilla a leer a toda la
plantilla, incluidas las bajas de la gente de oficina. Quitarle algo se lo
ampliaba.

La causa no estaba en el endpoint sino en `visible_people`, que trataba *no
llevar ningún departamento* y *aquí todavía no se ha decidido nada* como el mismo
estado. El día que la empresa se da de alta son lo mismo; en cuanto alguien lleva
un departamento, dejan de serlo. Eso es lo que distingue ahora, y por eso las
tres puertas quedan cerradas de una vez sin impedir ninguna de las tres
operaciones: las tres siguen permitidas, y ninguna reparte permisos.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.common.scope import visible_people
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Mudanzas",
        tax_id="B84848484",
        time_zone="Europe/Madrid",
        managers_see_whole_company=False,
    )
    with tenant_context(empresa.id):
        obras = Department.objects.create(tenant=empresa, name="Obras")
        oficina = Department.objects.create(tenant=empresa, name="Oficina")

        def persona(email, nombre, rol=Role.EMPLOYEE, departamento=None):
            return User.objects.create_user(
                email=email,
                password=PASSWORD,
                tenant=empresa,
                first_name=nombre,
                last_name="Equis",
                role=rol,
                department=departamento,
            )

        hecho = {
            "empresa": empresa,
            "obras": obras,
            "oficina": oficina,
            "ana": persona("ana@example.com", "Ana", Role.MANAGER, obras),
            "berta": persona("berta@example.com", "Berta", Role.MANAGER, oficina),
            "peon": persona("peon@example.com", "Peón", departamento=obras),
            "administrativa": persona("adm@example.com", "Admin", departamento=oficina),
            "jefa_total": persona("jefa@example.com", "Jefa", Role.ADMIN),
        }
        obras.managers.add(hecho["ana"])
        # Berta lleva Oficina desde el principio: la empresa ya usa el mecanismo,
        # que es justo lo que separa este caso del día uno.
        oficina.managers.add(hecho["berta"])
        yield hecho


def como(persona):
    cliente = APIClient()
    cliente.force_authenticate(user=persona)
    return cliente


def lo_que_ve(persona):
    persona.refresh_from_db()
    alcance = visible_people(persona)
    return "toda la empresa" if alcance is None else sorted(p.first_name for p in alcance)


@pytest.mark.django_db
def test_de_partida_ana_lee_su_cuadrilla(mundo):
    with tenant_context(mundo["empresa"].id):
        assert lo_que_ve(mundo["ana"]) == ["Ana", "Peón"]


@pytest.mark.django_db
def test_entregarle_el_departamento_a_otra_no_amplia_a_la_primera(mundo):
    """La reorganización de toda la vida, que es la que más se hace."""
    respuesta = como(mundo["jefa_total"]).patch(
        f"/api/departments/{mundo['obras'].pk}/",
        {"managers": [str(mundo["berta"].pk)]},
        format="json",
    )
    assert respuesta.status_code == 200, respuesta.content

    with tenant_context(mundo["empresa"].id):
        assert lo_que_ve(mundo["ana"]) == ["Ana"]
        # Y Berta sí se lleva lo que le han dado.
        assert lo_que_ve(mundo["berta"]) == ["Admin", "Ana", "Berta", "Peón"]


@pytest.mark.django_db
def test_quitarla_de_la_lista_tampoco(mundo):
    respuesta = como(mundo["jefa_total"]).patch(
        f"/api/departments/{mundo['obras'].pk}/", {"managers": []}, format="json"
    )
    assert respuesta.status_code == 200, respuesta.content

    with tenant_context(mundo["empresa"].id):
        assert lo_que_ve(mundo["ana"]) == ["Ana"]


@pytest.mark.django_db
def test_y_por_la_api_deja_de_ver_a_la_gente_de_oficina(mundo):
    """Lo mismo desde fuera: el alcance es la lista que de verdad se sirve."""
    cliente = como(mundo["ana"])
    antes = {p["first_name"] for p in cliente.get("/api/employees/").json()["results"]}
    assert antes == {"Ana", "Peón"}

    como(mundo["jefa_total"]).patch(
        f"/api/departments/{mundo['obras'].pk}/",
        {"managers": [str(mundo["berta"].pk)]},
        format="json",
    )

    despues = {p["first_name"] for p in cliente.get("/api/employees/").json()["results"]}
    assert despues == {"Ana"}, "quitarle el departamento le ha ampliado el alcance"


@pytest.mark.django_db
def test_pero_el_dia_uno_se_sigue_viendo_todo(mundo):
    """La concesión que el diseño defiende, y que no se puede romper al arreglar esto.

    Mientras **nadie** lleve ningún departamento, no se ha decidido nada y una
    responsable sigue viendo a todo el mundo: lo contrario es un producto que el
    primer día parece vacío, y lo que se hace entonces es apagar el alcance, no
    descubrir los departamentos.
    """
    with tenant_context(mundo["empresa"].id):
        mundo["obras"].managers.clear()
        mundo["oficina"].managers.clear()

        assert lo_que_ve(mundo["ana"]) == "toda la empresa"
        assert lo_que_ve(mundo["berta"]) == "toda la empresa"


@pytest.mark.django_db
def test_y_una_empresa_sin_departamentos_tampoco_se_estrecha(mundo):
    with tenant_context(mundo["empresa"].id):
        Department.objects.filter(tenant=mundo["empresa"]).delete()
        assert lo_que_ve(mundo["ana"]) == "toda la empresa"


@pytest.mark.django_db
def test_la_pantalla_de_ajustes_dice_cual_de_las_dos_cosas_significa(mundo):
    """El aviso de responsables sueltos decía siempre «ve a toda la empresa».

    Desde el arreglo eso solo es verdad mientras nadie lleve ningún
    departamento; pasado ese momento significa lo contrario ---no ve a nadie---,
    y un aviso que dice lo contrario de lo que pasa es peor que no tenerlo. Cuál
    de los dos es lo dice el servidor, para que la regla no viva en dos sitios.
    """
    cliente = como(mundo["jefa_total"])

    cuerpo = cliente.get("/api/company/").json()
    assert cuerpo["department_scoping_in_use"] is True
    assert cuerpo["managers_without_department"] == []

    # Ana cede Obras: pasa a estar suelta, y suelta aquí significa que no ve a nadie.
    cliente.patch(
        f"/api/departments/{mundo['obras'].pk}/",
        {"managers": [str(mundo["berta"].pk)]},
        format="json",
    )
    cuerpo = cliente.get("/api/company/").json()
    assert cuerpo["department_scoping_in_use"] is True
    assert [m["name"] for m in cuerpo["managers_without_department"]] == ["Ana Equis"]

    # Y si nadie lleva nada, vuelve a significar lo de siempre.
    with tenant_context(mundo["empresa"].id):
        mundo["obras"].managers.clear()
        mundo["oficina"].managers.clear()
    cuerpo = cliente.get("/api/company/").json()
    assert cuerpo["department_scoping_in_use"] is False
    assert sorted(m["name"] for m in cuerpo["managers_without_department"]) == [
        "Ana Equis",
        "Berta Equis",
    ]
