"""El crédito horario de la representación legal (art. 68.e ET).

«Un crédito de horas mensuales retribuidas cada uno de los miembros del comité o
delegado de personal **en cada centro de trabajo**», con una escala por tamaño:
quince horas hasta cien personas, veinte hasta doscientas cincuenta, treinta hasta
quinientas, treinta y cinco hasta setecientas cincuenta y cuarenta de ahí en
adelante.

**Por centro y no por empresa**, que es lo que más se confunde y lo que estas
pruebas fijan. El comité es del centro: una empresa de seiscientas personas
repartidas en cuatro naves de ciento cincuenta da veinte horas a cada
representante, no treinta y cinco. Contarlo por empresa le daría a cada uno
quince horas de más al mes, y nadie lo notaría hasta una inspección.

**Es un suelo.** «Podrá pactarse en convenio colectivo la acumulación de horas»,
y ampliarlo es corriente: la cifra de la empresa manda cuando la ha puesto, y la
escala entra cuando no. Por debajo se avisa, que es lo que hace un suelo.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.absences.models import LeaveType
from apps.absences.representation import FUNCIONES_DE_REPRESENTACION, representation_hours
from apps.common.models import tenant_context
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import User, Workplace

PASSWORD = "a-sufficiently-long-password"
MIRANDO = date(2026, 8, 24)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )


def centro(company, nombre):
    with tenant_context(company.id):
        return Workplace.objects.create(tenant=company, name=nombre)


def gente(company, cuantos, *, workplace=None, desde=0):
    with tenant_context(company.id):
        return [
            User.objects.create_user(
                email=f"p{desde + i}@example.com",
                password=PASSWORD,
                tenant=company,
                first_name=f"P{desde + i}",
                workplace=workplace,
            )
            for i in range(cuantos)
        ]


def representante(company, workplace=None, email="rep@example.com"):
    with tenant_context(company.id):
        return User.objects.create_user(
            email=email,
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Representa",
            workplace=workplace,
            is_worker_representative=True,
        )


@pytest.mark.parametrize(
    ("plantilla", "horas"),
    [
        (1, 15),
        (40, 15),
        (100, 15),
        (101, 20),
        (250, 20),
        (251, 30),
        (500, 30),
        (501, 35),
        (750, 35),
        (751, 40),
        (5000, 40),
    ],
)
def test_la_escala_del_articulo(plantilla, horas):
    """Los cinco tramos, y **los bordes de cada uno**, que es donde se falla.

    El artículo dice «hasta cien» y «de ciento uno a doscientos cincuenta»: cien
    va en el primer tramo y ciento uno en el segundo. Un `<` donde va un `<=`
    mueve a todo el mundo un escalón y no se nota en ningún caso redondo.

    Sin base de datos y sin crear plantillas: la escala es aritmética pura, y
    probar el tramo de setecientas cincuenta y una personas dando de alta a
    setecientas cincuenta y una tardaba minuto y medio para comprobar una
    comparación. Que la cuenta salga del centro correcto se prueba aparte, con
    la gente justa.
    """
    from apps.legal.es import ESPANA

    assert ESPANA.representation.hours_for(plantilla) == horas


@pytest.mark.django_db
def test_se_cuenta_el_centro_y_no_la_empresa(company):
    """**La prueba que más vale de este fichero.**

    Seiscientas personas en cuatro naves de ciento cincuenta. Por centro son
    veinte horas; por empresa serían treinta y cinco. Quince horas al mes de más
    para cada representante, todos los meses, sin que nadie lo note.
    """
    with tenant_context(company.id):
        # Cuatro naves de sesenta: doscientas cuarenta en la empresa. Por centro
        # son quince horas, por empresa serían veinte. Las cifras son pequeñas
        # para que la prueba sea rápida; el salto de tramo es el mismo.
        naves = [centro(company, f"Nave {i}") for i in range(4)]
        quien = representante(company, naves[0])
        for i, nave in enumerate(naves):
            gente(company, 60 - (1 if i == 0 else 0), workplace=nave, desde=i * 200)

        credito = representation_hours(quien, company)
        assert credito["headcount"] == 60, "cuenta su nave, no las cuatro"
        assert credito["hours"] == 15
        assert credito["by_workplace"] is True

        # Y el contraste, en la misma prueba porque es la misma frase: contando
        # la empresa entera saldría el tramo siguiente.
        from apps.legal.es import ESPANA

        assert ESPANA.representation.hours_for(240) == 20


@pytest.mark.django_db
def test_sin_centro_se_cuenta_la_empresa_y_se_dice(company):
    """Una cifra con su salvedad es un dato; una sin ella es un hecho que puede fallar.

    Sin centro asignado no hay tramo que mirar sin inventarlo. Se cuenta la
    empresa entera ---que es lo más parecido--- y se marca que se ha hecho, para
    que quien lo lea sepa de dónde sale.
    """
    with tenant_context(company.id):
        quien = representante(company, None)
        gente(company, 3)

        credito = representation_hours(quien, company)
        assert credito["by_workplace"] is False, "y se dice que la cuenta es de la empresa"
        assert credito["headcount"] == 4
        assert credito["hours"] == 15


@pytest.mark.django_db
def test_quien_no_es_representante_no_tiene_credito(company):
    """**El contraste.** El permiso está en el catálogo de todas las empresas.

    Sin esta condición, cualquiera tendría quince horas al mes de un crédito que
    no le corresponde, y el saldo se lo enseñaría.
    """
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="normal@example.com", password=PASSWORD, tenant=company, first_name="Quien"
        )
        assert representation_hours(quien, company) is None


@pytest.mark.django_db
def test_el_saldo_del_permiso_usa_la_escala(company):
    """Sin esto la cifra existe y no llega a ninguna pantalla.

    El catálogo trae el permiso sin cuantía ---la escala depende del centro y el
    catálogo no tiene dónde guardar eso--- así que el tope sale de aquí.
    """
    from apps.absences.catalogue import seed_leave_types
    from apps.absences.usage import leave_usage

    with tenant_context(company.id):
        seed_leave_types(company)
        sitio = centro(company, "Nave")
        quien = representante(company, sitio)
        gente(company, 150, workplace=sitio)

        tipo = LeaveType.objects.get(code=FUNCIONES_DE_REPRESENTACION)
        assert tipo.amount is None, "el catálogo no trae cuantía, y por eso hace falta la escala"

        uso = leave_usage(quien, tipo, company, MIRANDO)
        assert uso.allowance == 20


@pytest.mark.django_db
def test_la_cifra_de_la_empresa_manda_cuando_la_hay(company):
    """El convenio amplía este crédito a menudo, y forzar el suelo quitaría horas."""
    from apps.absences.catalogue import seed_leave_types
    from apps.absences.usage import leave_usage

    with tenant_context(company.id):
        seed_leave_types(company)
        sitio = centro(company, "Nave")
        quien = representante(company, sitio)
        gente(company, 40, workplace=sitio)

        tipo = LeaveType.objects.get(code=FUNCIONES_DE_REPRESENTACION)
        tipo.amount = 25
        tipo.save(update_fields=["amount"])

        assert leave_usage(quien, tipo, company, MIRANDO).allowance == 25


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("puestas", "avisa"),
    [(25, False), (15, False), (10, True)],
    ids=["mejora el convenio", "justo el suelo", "por debajo"],
)
def test_se_avisa_cuando_la_cifra_puesta_baja_del_suelo(company, puestas, avisa):
    """Un suelo que no se comprueba no es un suelo."""
    from apps.absences.catalogue import seed_leave_types

    with tenant_context(company.id):
        seed_leave_types(company)
        sitio = centro(company, "Nave")
        representante(company, sitio)
        gente(company, 40, workplace=sitio)

        tipo = LeaveType.objects.get(code=FUNCIONES_DE_REPRESENTACION)
        tipo.amount = puestas
        tipo.save(update_fields=["amount"])

        codigos = [
            f.code
            for f in review_roster(company=company, first=MIRANDO, last=MIRANDO + timedelta(days=6))
        ]
        assert ("representation_credit_below_the_floor" in codigos) is avisa


@pytest.mark.django_db
def test_sin_representantes_no_se_avisa_de_nada(company):
    """El contraste del anterior, y no es el mismo.

    El permiso está en el catálogo de todas las empresas, así que una cifra baja
    en una empresa sin representación no le quita horas a nadie. Avisar ahí sería
    ruido para siempre.
    """
    from apps.absences.catalogue import seed_leave_types

    with tenant_context(company.id):
        seed_leave_types(company)
        sitio = centro(company, "Nave")
        gente(company, 40, workplace=sitio)

        tipo = LeaveType.objects.get(code=FUNCIONES_DE_REPRESENTACION)
        tipo.amount = 5
        tipo.save(update_fields=["amount"])

        codigos = [
            f.code
            for f in review_roster(company=company, first=MIRANDO, last=MIRANDO + timedelta(days=6))
        ]
        assert "representation_credit_below_the_floor" not in codigos
