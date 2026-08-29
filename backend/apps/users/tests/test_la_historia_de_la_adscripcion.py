"""En qué departamento estaba alguien cuando hizo esas horas.

La persona lleva su departamento **actual** en una columna, y para casi todo eso
es lo correcto: el alcance de quien gestiona, las colas de decisión, el resumen
de hoy. Quien lleva hoy un departamento necesita el histórico de la gente que
lleva hoy, no el de quien ya no.

Donde no vale es en un documento **de un periodo**. El informe del art. 34.9 se
puede pedir por departamento, y ese filtro leía la adscripción de hoy: pedir
«julio, Jardinería» después de una reorganización de septiembre devolvía la
plantilla de septiembre. Con las personas equivocadas, en un documento que puede
acabar en una inspección.

**Y el historial empieza el día que se estrena.** Del pasado no hay dato ---nadie
guardó los cambios anteriores--- y ponerle a cada asignación una fecha inventada
sería afirmar algo que no consta. Por eso la primera va sin fecha de inicio, que
significa «no consta desde cuándo» y cuenta para cualquier periodo: exactamente
como se comportaba el producto antes.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.adscription import people_in_department
from apps.users.models import Department, DepartmentAssignment, User

PASSWORD = "a-sufficiently-long-password"
JULIO = (date(2026, 7, 1), date(2026, 7, 31))


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def mundo(company):
    with tenant_context(company.id):
        jardin = Department.objects.create(tenant=company, name="Jardinería")
        obra = Department.objects.create(tenant=company, name="Obras")
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            department=jardin,
        )
        yield {"jardin": jardin, "obra": obra, "quien": quien}


def mover(quien, department, *, el_dia):
    """Cambia de departamento y fija las fechas del tramo, para la prueba.

    Ordenando por `created_at` y no por `id`: la clave es un UUID, así que
    `order_by("id")` da un orden **aleatorio**. La primera versión de estas
    pruebas lo hacía y pasaba por casualidad, hasta que le tocaron otros UUID.
    """
    quien.department = department
    quien.save(update_fields=["department"])
    # La señal anota con el día de hoy; para las pruebas se fija el que toca.
    ultimo = DepartmentAssignment.objects.filter(employee=quien).order_by("-created_at").first()
    ultimo.starts_on = el_dia
    ultimo.save(update_fields=["starts_on"])
    anterior = (
        DepartmentAssignment.objects.filter(employee=quien, ends_on__isnull=False)
        .order_by("-id")
        .first()
    )
    if anterior:
        anterior.ends_on = el_dia
        anterior.save(update_fields=["ends_on"])


@pytest.mark.django_db
def test_al_darse_de_alta_queda_su_adscripcion(company, mundo):
    """Y **sin fecha de inicio**: no consta desde cuándo estaba ahí.

    Poner la de hoy diría que empezó hoy, y poner la del contrato diría que lleva
    desde entonces. Ninguna de las dos consta, y las dos se leerían como un
    hecho.
    """
    with tenant_context(company.id):
        tramos = list(DepartmentAssignment.objects.filter(employee=mundo["quien"]))
        assert len(tramos) == 1
        assert tramos[0].department_id == mundo["jardin"].id
        assert tramos[0].starts_on is None
        assert tramos[0].ends_on is None


@pytest.mark.django_db
def test_cambiar_de_departamento_cierra_el_anterior(company, mundo):
    """Dos asignaciones abiertas pondrían a alguien en dos sitios a la vez."""
    with tenant_context(company.id):
        mover(mundo["quien"], mundo["obra"], el_dia=date(2026, 9, 1))

        tramos = list(
            DepartmentAssignment.objects.filter(employee=mundo["quien"]).order_by("created_at")
        )
        assert len(tramos) == 2
        assert tramos[0].department_id == mundo["jardin"].id
        assert tramos[0].ends_on == date(2026, 9, 1)
        assert tramos[1].department_id == mundo["obra"].id
        assert tramos[1].starts_on == date(2026, 9, 1)
        assert tramos[1].ends_on is None


@pytest.mark.django_db
def test_el_informe_de_julio_cuenta_con_quien_estaba_en_julio(company, mundo):
    """**El caso que trae todo esto.**

    Quien estuvo en Jardinería hasta septiembre sale en el informe de julio de
    Jardinería, aunque hoy esté en Obras. Leyendo la columna actual no salía, y
    el documento tenía un hueco que nadie iba a notar.
    """
    with tenant_context(company.id):
        quien = mundo["quien"]
        mover(quien, mundo["obra"], el_dia=date(2026, 9, 1))
        gente = list(User.objects.filter(tenant=company))

        en_jardin = people_in_department(gente, str(mundo["jardin"].id), *JULIO)
        assert quien in en_jardin, "en julio estaba en Jardinería"

        en_obra = people_in_department(gente, str(mundo["obra"].id), *JULIO)
        assert quien not in en_obra, "en julio todavía no estaba en Obras"


@pytest.mark.django_db
def test_y_el_de_octubre_cuenta_con_el_departamento_nuevo(company, mundo):
    """El contraste, y no es simétrico: sin él, un filtro que devolviera siempre
    el departamento antiguo pasaría la prueba de arriba."""
    with tenant_context(company.id):
        quien = mundo["quien"]
        mover(quien, mundo["obra"], el_dia=date(2026, 9, 1))
        gente = list(User.objects.filter(tenant=company))
        octubre = (date(2026, 10, 1), date(2026, 10, 31))

        assert quien in people_in_department(gente, str(mundo["obra"].id), *octubre)
        assert quien not in people_in_department(gente, str(mundo["jardin"].id), *octubre)


@pytest.mark.django_db
def test_sin_historial_se_lee_la_columna_de_siempre(company, mundo):
    """Lo que había antes de este módulo, para quien no tenga ni un tramo.

    Un informe al que le falta una persona no cumple el art. 34.9. Ante la duda,
    la adscripción actual, que es lo que el producto ha hecho siempre.
    """
    with tenant_context(company.id):
        quien = mundo["quien"]
        DepartmentAssignment.objects.filter(employee=quien).delete()
        gente = list(User.objects.filter(tenant=company))

        assert quien in people_in_department(gente, str(mundo["jardin"].id), *JULIO)


@pytest.mark.django_db
def test_una_asignacion_sin_fecha_cuenta_para_cualquier_periodo(company, mundo):
    """«No consta desde cuándo» no puede dejar a nadie fuera de un periodo viejo.

    Es la asignación con la que arranca todo el mundo el día que se estrena el
    historial, y si no contara para atrás, el primer informe de un periodo
    anterior saldría vacío.
    """
    with tenant_context(company.id):
        gente = list(User.objects.filter(tenant=company))
        antiguo = (date(2020, 1, 1), date(2020, 1, 31))

        assert mundo["quien"] in people_in_department(gente, str(mundo["jardin"].id), *antiguo)


@pytest.mark.django_db
def test_guardar_sin_tocar_el_departamento_no_crea_tramos(company, mundo):
    """La señal corre en cada guardado, y un `last_login` no muda a nadie."""
    with tenant_context(company.id):
        quien = mundo["quien"]
        antes = DepartmentAssignment.objects.filter(employee=quien).count()

        quien.first_name = "Otro"
        quien.save(update_fields=["first_name"])
        quien.save()  # y un guardado entero, que sí lo comprueba

        assert DepartmentAssignment.objects.filter(employee=quien).count() == antes


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company, mundo):
    """`User.objects` no acota por empresa, y aquí las personas llegan en lista."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B22222222", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        suyo_dep = Department.objects.create(tenant=vecina, name="Jardinería")
        suyo = User.objects.create_user(
            email="suyo@vecina.example",
            password=PASSWORD,
            tenant=vecina,
            first_name="Ajeno",
            department=suyo_dep,
        )

    with tenant_context(company.id):
        gente = list(User.objects.filter(tenant=company))
        dentro = people_in_department(gente, str(mundo["jardin"].id), *JULIO)

        assert mundo["quien"] in dentro
        assert suyo not in dentro
