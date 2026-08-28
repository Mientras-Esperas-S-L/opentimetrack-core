"""El contrato de relevo y la jubilación parcial, que son la misma pieza.

Los dos artículos se leen juntos o no se leen:

- **Art. 12.6**: quien se jubila parcialmente reduce su jornada entre un 25 % y
  un 50 %, o hasta un 75 % si el contrato de relevo es a jornada completa y de
  duración indefinida.
- **Art. 12.7**: el relevo se celebra para cubrir esa reducción, y «la duración
  de la jornada deberá ser, como mínimo, igual a la reducción de jornada
  acordada por el trabajador sustituido».

La cifra que el 12.7 compara **sale de la jubilación del otro**. Sin el vínculo
entre las dos personas no hay nada que comparar, y eso era lo que faltaba: la
maquinaria de reducir la jornada ya existía ---la puso el art. 37.6--- y no había
manera de decir a quién releva un contrato de relevo.

El tope que sube al 75 % es el ejemplo más claro de por qué van juntos: **el
mismo 60 % de reducción es correcto o no según cómo sea el contrato de otra
persona**.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import AbsenceStatus, LeaveType
from apps.absences.services import request_absence
from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.tenants.rules import WorkingTimeRules
from apps.users.models import HoursPeriod, Role, User, WorkingTimeRegime

PASSWORD = "a-sufficiently-long-password"

DESDE = date(2026, 8, 3)
HASTA = DESDE + timedelta(days=6)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="Relevo SL", tax_id="B27272727", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        seed_leave_types(empresa)
        reglas = WorkingTimeRules.for_company(empresa)
        reglas.weekly_hours = 40
        reglas.save(update_fields=["weekly_hours"])
    return empresa


def alguien(
    company, *, email, horas=40, regime=WorkingTimeRegime.FULL_TIME, hasta=None, releva=None
):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Quien",
        last_name=email.split("@")[0],
        role=Role.EMPLOYEE,
        regime=regime,
        contracted_hours=horas,
        contracted_period=HoursPeriod.WEEK,
        contract_end=hasta,
        relieves=releva,
    )


def se_jubila(company, quien, cuanto):
    ausencia = request_absence(
        employee=quien,
        company=company,
        leave_type=LeaveType.objects.get(code="es.partial_retirement"),
        start_date=DESDE - timedelta(days=30),
        end_date=DESDE + timedelta(days=700),
        reduction_share=cuanto,
    )
    ausencia.status = AbsenceStatus.APPROVED
    ausencia.save(update_fields=["status"])
    return ausencia


def codigos(company):
    return [f.code for f in review_roster(company=company, first=DESDE, last=HASTA)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cuanto", "avisa"),
    [(25, False), (50, False), (20, True), (60, True)],
    ids=["el mínimo", "el máximo", "por debajo del 25", "por encima del 50"],
)
def test_la_horquilla_del_articulo_126(company, cuanto, avisa):
    """Del 25 al 50 %, con los dos bordes dentro.

    Fuera de ahí se avisa y se registra igual: el acuerdo lo firman las partes y
    el convenio puede mejorar las condiciones.
    """
    with tenant_context(company.id):
        quien = alguien(company, email=f"jubila{cuanto}@example.com")
        se_jubila(company, quien, cuanto)
        assert ("partial_retirement_out_of_range" in codigos(company)) is avisa


@pytest.mark.django_db
def test_el_tope_sube_al_75_con_relevo_entero(company):
    """**La prueba que enseña por qué los dos artículos son una sola pieza.**

    El mismo 60 % de reducción está fuera de horquilla o dentro **según cómo sea
    el contrato de otra persona**: si quien releva lo hace a jornada completa y
    sin fecha de fin, el art. 12.6 permite llegar al 75 %.

    Un producto que mirara la jubilación por su cuenta no podría distinguir los
    dos casos, y acusaría a la mitad de las empresas que lo hacen bien.
    """
    with tenant_context(company.id):
        mayor = alguien(company, email="mayor@example.com")
        se_jubila(company, mayor, 60)

        # Sin nadie relevando: el 60 % se pasa del 50 %.
        assert "partial_retirement_out_of_range" in codigos(company)

        # Con relevo a jornada completa e indefinido, el tope es el 75 %.
        alguien(company, email="releva@example.com", horas=40, hasta=None, releva=mayor)
        assert "partial_retirement_out_of_range" not in codigos(company)


@pytest.mark.django_db
def test_un_relevo_temporal_no_sube_el_tope(company):
    """El contraste del anterior: el artículo pide **completa e indefinida**.

    Con fecha de fin, el tope se queda en el 50 % y el 60 % vuelve a avisar. Sin
    esto, «sube al 75 con relevo entero» y «sube al 75 con cualquier relevo» se
    verían igual.
    """
    with tenant_context(company.id):
        mayor = alguien(company, email="mayor2@example.com")
        se_jubila(company, mayor, 60)
        alguien(
            company,
            email="releva-temporal@example.com",
            horas=40,
            hasta=DESDE + timedelta(days=365),
            releva=mayor,
        )
        assert "partial_retirement_out_of_range" in codigos(company)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("horas_relevista", "avisa"),
    [(20, False), (24, False), (16, True)],
    ids=["justo lo que deja", "más de lo que deja", "menos de lo que deja"],
)
def test_el_relevista_cubre_al_menos_la_reduccion(company, horas_relevista, avisa):
    """Art. 12.7, y es el sentido del contrato.

    Quien se jubila al 50 % sobre 40 h deja de trabajar 20. El relevo tiene que
    cubrir al menos esas 20: con 16 se queda corto y hay cuatro horas que no
    hace nadie.
    """
    with tenant_context(company.id):
        mayor = alguien(company, email=f"mayor-{horas_relevista}@example.com")
        se_jubila(company, mayor, 50)
        alguien(
            company,
            email=f"releva-{horas_relevista}@example.com",
            horas=horas_relevista,
            regime=WorkingTimeRegime.PART_TIME,
            releva=mayor,
        )
        assert ("relief_hours_below_the_reduction" in codigos(company)) is avisa


@pytest.mark.django_db
def test_un_relevo_que_no_releva_a_nadie_lo_dice(company):
    """Sin jubilación registrada, la cifra del artículo no existe.

    Se dice en vez de callar: un contrato de relevo apuntado sobre alguien que
    no se ha jubilado parcialmente **no se puede comprobar**, y quedarse callado
    se lee como que está bien.
    """
    with tenant_context(company.id):
        nadie = alguien(company, email="sin-jubilar@example.com")
        alguien(company, email="releva-a-nadie@example.com", horas=20, releva=nadie)

        salidas = codigos(company)
        assert "relief_without_partial_retirement" in salidas
        # Y **no** el de las horas: no hay contra qué compararlas, y sacar los
        # dos avisos mandaría a arreglar una cifra que no se puede calcular.
        assert "relief_hours_below_the_reduction" not in salidas


@pytest.mark.django_db
def test_quien_no_releva_a_nadie_no_sale_en_esto(company):
    """El contraste que separa «tiene contrato de relevo» de «trabaja aquí».

    Sin él, los tres avisos podrían estar saliendo para toda la plantilla y las
    pruebas de arriba pasarían igual.
    """
    with tenant_context(company.id):
        alguien(company, email="normal@example.com")
        salidas = codigos(company)
        assert "relief_without_partial_retirement" not in salidas
        assert "relief_hours_below_the_reduction" not in salidas
        assert "partial_retirement_out_of_range" not in salidas


@pytest.mark.django_db
def test_no_se_cuela_la_jubilacion_de_la_empresa_de_al_lado(company):
    """`User.objects` no acota por empresa, y aquí las personas salen de ahí."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B28282828", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        seed_leave_types(vecina)
        suyo = alguien(vecina, email="mayor@vecina.example")
        se_jubila(vecina, suyo, 60)

    with tenant_context(company.id):
        propio = alguien(company, email="mayor-propio@example.com")
        se_jubila(company, propio, 60)

        avisos = review_roster(company=company, first=DESDE, last=HASTA)
        de_quien = {f.employee_id for f in avisos if f.code == "partial_retirement_out_of_range"}

        assert propio.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suyo.id not in de_quien
