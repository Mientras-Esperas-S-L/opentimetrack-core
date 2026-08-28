"""Las tres reducciones que faltaban, y en qué se diferencian entre sí.

El inventario las agrupaba como una sola cosa ---«van sobre la misma
maquinaria»--- y es cierto: las tres se piden con **cuánto se reduce** y sus
fechas, y el cuadrante pasa a medir contra la jornada reducida. Esa maquinaria es
la del art. 37.6 y ya estaba.

Lo que **no** es común, y es la razón de que esto tenga pruebas propias:

- **El art. 37.5 concede dos derechos distintos**, y uno se cobra y el otro no:
  una hora de ausencia retribuida, y una reducción de hasta dos horas «con la
  disminución proporcional del salario». Son dos entradas del catálogo porque
  `paid` no puede decir las dos cosas a la vez.
- **En el párrafo tercero del art. 37.6 la mitad es el mínimo**, no el máximo. En
  el mismo artículo, la guarda legal va «entre un octavo y la mitad». Aplicarle
  aquel rango convertiría el ejercicio normal de este derecho ---reducir un
  60 %--- en un aviso de incumplimiento.
- **El art. 37.8 no tiene rango.** Lo concreta quien lo ejerce, y no hay cifra
  que comprobar. Tampoco pide justificante: la acreditación se hace ante quien
  corresponde, no colgando un documento en una herramienta de fichaje.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import Absence, AbsenceStatus, LeaveType
from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

PREMATURO_HORA = "es.premature_birth_hour"
PREMATURO_REDUCCION = "es.premature_birth_reduction"
ENFERMEDAD_GRAVE = "es.serious_illness_care"
VIOLENCIA_REDUCCION = "es.gender_violence_reduction"
VIOLENCIA_SUSPENSION = "es.gender_violence_suspension"
GUARDA_LEGAL = "es.childcare_reduced_hours"

MIRANDO = date(2026, 8, 24)


@pytest.fixture
def company(db):
    empresa = Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        seed_leave_types(empresa)
    return empresa


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="quien@example.com", password=PASSWORD, tenant=company, first_name="Quien"
        )


def permiso(company, code):
    with tenant_context(company.id):
        return LeaveType.objects.get(code=code)


def reduce(company, quien, code, share):
    return Absence.objects.create(
        tenant=company,
        employee=quien,
        leave_type=permiso(company, code),
        start_date=MIRANDO,
        end_date=MIRANDO + timedelta(days=30),
        reduction_share=share,
        status=AbsenceStatus.APPROVED,
    )


def codigos(company):
    return [
        f.code
        for f in review_roster(company=company, first=MIRANDO, last=MIRANDO + timedelta(days=6))
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "code",
    [PREMATURO_REDUCCION, ENFERMEDAD_GRAVE, VIOLENCIA_REDUCCION],
    ids=["prematuro", "enfermedad grave", "violencia"],
)
def test_las_tres_pueden_reducir_la_jornada(company, code):
    """La maquinaria común: sin esto no se pueden ejercer, que es como estaban."""
    assert permiso(company, code).can_reduce_the_day is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "code",
    [PREMATURO_REDUCCION, ENFERMEDAD_GRAVE, VIOLENCIA_REDUCCION],
    ids=["prematuro", "enfermedad grave", "violencia"],
)
def test_las_tres_las_pide_quien_trabaja(company, code):
    """Son derechos de la persona, no decisiones de la empresa.

    Con `initiated_by="COMPANY"` se registrarían en firme sin pasar por nadie, y
    eso sería la empresa decidiendo cómo ejerce alguien su derecho.
    """
    assert permiso(company, code).initiated_by == "PERSON"


@pytest.mark.django_db
def test_la_hora_del_prematuro_se_cobra_y_la_reduccion_no(company):
    """**El motivo de que el art. 37.5 sean dos entradas y no una.**

    El artículo concede una hora de ausencia y, «asimismo», una reducción de
    hasta dos horas «con la disminución proporcional del salario». Una sola
    entrada tendría que elegir un valor de `paid` y mentiría en la mitad de los
    casos: o convierte en gratis una hora que se cobra, o al revés.
    """
    assert permiso(company, PREMATURO_HORA).paid is True
    assert permiso(company, PREMATURO_HORA).can_reduce_the_day is False
    assert permiso(company, PREMATURO_REDUCCION).paid is False
    assert permiso(company, PREMATURO_REDUCCION).can_reduce_the_day is True


@pytest.mark.django_db
def test_la_reduccion_por_violencia_no_pide_justificante(company):
    """La acreditación no se hace colgando un documento en el fichaje.

    Pedirlo aquí convertiría el ejercicio del derecho en una declaración de algo
    íntimo delante de quien aprueba las ausencias. Es el mismo criterio por el
    que el producto rechaza los partes de baja.
    """
    assert permiso(company, VIOLENCIA_REDUCCION).needs_justification is False


@pytest.mark.django_db
def test_la_reduccion_y_la_suspension_por_violencia_son_distintas(company):
    """El contraste: ya existía la suspensión, y no es esto.

    La del art. 45.1.n es para quien **deja de trabajar**; la del art. 37.8, para
    quien sigue trabajando con la jornada reducida o reordenada. Dar la primera
    por buena para la segunda dejaría sin cubrir el caso más frecuente.
    """
    suspension = permiso(company, VIOLENCIA_SUSPENSION)
    assert suspension.can_reduce_the_day is False
    assert suspension.basis.startswith("Art. 45")
    assert permiso(company, VIOLENCIA_REDUCCION).basis.startswith("Art. 37.8")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("share", "avisa"),
    [(60, False), (50, False), (30, True)],
    ids=["más de la mitad", "la mitad justa", "se queda corta"],
)
def test_en_la_enfermedad_grave_la_mitad_es_el_minimo(company, quien, share, avisa):
    """**El matiz que distingue los dos párrafos del mismo artículo.**

    «Al menos la mitad», dice el párrafo tercero. Reducir un 60 % es
    exactamente lo que concede; un 30 % se queda corto de lo que la ley da, y
    quien lo firma probablemente no lo sabe.
    """
    with tenant_context(company.id):
        reduce(company, quien, ENFERMEDAD_GRAVE, share)
        assert ("serious_illness_reduction_too_small" in codigos(company)) is avisa


@pytest.mark.django_db
def test_el_aviso_de_la_guarda_legal_no_le_aplica(company, quien):
    """**El contraste que evita el falso positivo más caro de esta vuelta.**

    El chequeo de la guarda legal avisa fuera del rango de un octavo a la mitad.
    Una reducción del 60 % por enfermedad grave se sale de ese rango por arriba,
    así que si aquel aviso no estuviera atado a su código, el ejercicio normal de
    este derecho saldría marcado como incumplimiento.
    """
    with tenant_context(company.id):
        reduce(company, quien, ENFERMEDAD_GRAVE, 60)
        assert "reduction_outside_the_right" not in codigos(company)


@pytest.mark.django_db
def test_y_el_de_la_enfermedad_grave_no_le_aplica_a_la_guarda_legal(company, quien):
    """El contraste del anterior, en la otra dirección.

    Una guarda legal del 25 % es perfectamente normal ---cabe entre un octavo y
    la mitad--- y no puede salir marcada por «quedarse corta de la mitad».
    """
    with tenant_context(company.id):
        reduce(company, quien, GUARDA_LEGAL, 25)
        assert "serious_illness_reduction_too_small" not in codigos(company)


@pytest.mark.django_db
def test_la_reduccion_por_violencia_no_tiene_cifra_que_comprobar(company, quien):
    """El art. 37.8 no da rango: lo concreta quien lo ejerce.

    Inventarle un mínimo o un máximo sería ponerle a este derecho un límite que
    la ley no le pone, y encima a costa de quien lo está ejerciendo.
    """
    with tenant_context(company.id):
        reduce(company, quien, VIOLENCIA_REDUCCION, 70)
        salen = codigos(company)
        assert "serious_illness_reduction_too_small" not in salen
        assert "reduction_outside_the_right" not in salen
