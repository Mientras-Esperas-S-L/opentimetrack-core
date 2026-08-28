"""Cuándo se aplica la Ley 10/2021, y qué exige cuando se aplica.

El art. 1 no regula «el teletrabajo»: fija el **umbral de aplicación**. Trabajo a
distancia de al menos el 30 % de la jornada en un periodo de referencia de tres
meses. Por debajo se trabaja desde casa y la ley no entra; por encima entra
entera, y lo primero que pide es acuerdo por escrito y **previo** (art. 5.1).

Lo que el producto ya tenía era la mitad buena: cada fichaje dice si ese tramo
fue presencial o a distancia (art. 3.e). Lo que faltaba era la cuenta y lo que la
cuenta implica.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType, WorkMode
from apps.punches.remote import _tres_meses_antes, remote_share
from apps.shifts.services import review_roster
from apps.tenants.models import Tenant
from apps.users.models import RemoteWorkAgreement, User

PASSWORD = "a-sufficiently-long-password"

#: Un lunes, y el día desde el que se mira.
LUNES = date(2026, 8, 3)
MIRANDO = date(2026, 8, 28)


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="A distancia SL", tax_id="B22222222", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def quien(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="remota@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Rita",
            last_name="Mota",
        )


def trabaja(company, quien, day, horas, modo):
    entra = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=6)
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra,
        punch_type=PunchType.IN,
        work_mode=modo,
    )
    Punch.objects.create(
        tenant=company,
        employee=quien,
        timestamp=entra + timedelta(hours=horas),
        punch_type=PunchType.OUT,
    )


def una_semana(company, quien, *, dias_en_casa, semana=LUNES):
    """Cinco días de ocho horas, con los primeros en casa."""
    for offset in range(5):
        trabaja(
            company,
            quien,
            semana + timedelta(days=offset),
            8,
            WorkMode.REMOTE if offset < dias_en_casa else WorkMode.ONSITE,
        )


def codigos(company, first=LUNES, last=MIRANDO):
    return [f.code for f in review_roster(company=company, first=first, last=last)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dias_en_casa", "share", "aplica"),
    [
        (0, 0, False),
        (1, 20, False),
        (2, 40, True),
        (5, 100, True),
    ],
    ids=["nunca", "un día de cinco", "dos de cinco", "siempre"],
)
def test_el_umbral_del_treinta_por_ciento(company, quien, dias_en_casa, share, aplica):
    """Dos días de cinco son el 40 %: la ley aplica. Uno es el 20 %: no.

    El borde de un día de cinco está a propósito debajo del umbral, y el de dos
    encima: entre ellos está la frontera que decide si a esta empresa le hace
    falta un acuerdo firmado o no le hace falta nada.
    """
    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=dias_en_casa)

        cuenta = remote_share(employee=quien, company=company, day=MIRANDO)
        assert cuenta["share"] == share
        assert cuenta["law_applies"] is aplica


@pytest.mark.django_db
def test_sin_nada_trabajado_no_se_contesta_cero(company, quien):
    """Cero de cero no es «el 0 % a distancia»: es que no hay con qué responder.

    Un 0 % dicho sobre una ventana vacía se lee como un hecho ---«esta persona
    no teletrabaja»--- cuando lo cierto es que no consta nada.
    """
    with tenant_context(company.id):
        assert remote_share(employee=quien, company=company, day=MIRANDO) is None


@pytest.mark.django_db
def test_pasar_del_umbral_sin_acuerdo_avisa(company, quien):
    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=3)
        assert "remote_work_without_agreement" in codigos(company)


@pytest.mark.django_db
def test_con_acuerdo_no_avisa(company, quien):
    """El contraste. Sin él, «avisa a quien no tiene acuerdo» y «avisa a todo el
    que teletrabaja» se ven exactamente igual."""
    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=3)
        RemoteWorkAgreement.objects.create(
            tenant=company,
            employee=quien,
            signed_on=date(2026, 7, 1),
            starts_on=date(2026, 7, 15),
        )

        salidas = codigos(company)
        assert "remote_work_without_agreement" not in salidas
        assert "remote_agreement_signed_late" not in salidas


@pytest.mark.django_db
def test_firmarlo_tarde_es_otro_aviso(company, quien):
    """El art. 5.1 pide que el acuerdo sea **previo**.

    Va aparte de «falta acuerdo» porque no se arregla igual: una firma no se
    puede correr hacia atrás, y mandar a quien tiene el papel a que lo firme
    sería mandarle a resolver un problema que no es el suyo.
    """
    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=3)
        RemoteWorkAgreement.objects.create(
            tenant=company,
            employee=quien,
            signed_on=date(2026, 8, 10),
            starts_on=date(2026, 7, 15),
        )

        salidas = codigos(company)
        assert "remote_agreement_signed_late" in salidas
        # Y no los dos a la vez: tiene acuerdo, el problema es la fecha.
        assert "remote_work_without_agreement" not in salidas


@pytest.mark.django_db
def test_un_acuerdo_que_ya_terminó_no_ampara(company, quien):
    """Amparar con un acuerdo caducado sería peor que no mirar ninguno."""
    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=3)
        RemoteWorkAgreement.objects.create(
            tenant=company,
            employee=quien,
            signed_on=date(2025, 1, 1),
            starts_on=date(2025, 1, 15),
            ends_on=date(2025, 12, 31),
        )

        assert "remote_work_without_agreement" in codigos(company)


@pytest.mark.django_db
def test_no_se_mira_a_quien_no_ha_teletrabajado(company, quien):
    """Quien no ha marcado ni un tramo a distancia no entra en la cuenta.

    Sin este recorte habría que hacer la suma de los tres meses para toda la
    plantilla en cada revisión de cuadrante, y la respuesta sería «0 %» para casi
    todos. La prueba fija el recorte, no solo el rendimiento: alguien que nunca
    teletrabaja no debe aparecer en un aviso sobre teletrabajo.
    """
    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=0)
        assert "remote_work_without_agreement" not in codigos(company)


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company, quien):
    """Como en el tope de complementarias: `User.objects` no acota por empresa."""
    vecina = Tenant.objects.create(
        name="La de al lado", tax_id="B23232323", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(vecina.id):
        suya = User.objects.create_user(
            email="suya@vecina.example", password=PASSWORD, tenant=vecina, first_name="Ajena"
        )
        una_semana(vecina, suya, dias_en_casa=5)

    with tenant_context(company.id):
        una_semana(company, quien, dias_en_casa=5)
        avisos = review_roster(company=company, first=LUNES, last=MIRANDO)
        de_quien = {f.employee_id for f in avisos if f.code == "remote_work_without_agreement"}

        assert quien.id in de_quien, "el aviso de la propia empresa tiene que salir"
        assert suya.id not in de_quien


@pytest.mark.parametrize(
    ("desde", "esperado"),
    [
        (date(2026, 8, 28), date(2026, 5, 28)),
        (date(2026, 3, 15), date(2025, 12, 15)),  # cruza el año
        (date(2026, 5, 31), date(2026, 2, 28)),  # el 31 de febrero no existe
        (date(2028, 5, 31), date(2028, 2, 29)),  # y en bisiesto llega al 29
    ],
    ids=["normal", "cruza el año", "31 de mayo", "31 de mayo bisiesto"],
)
def test_tres_meses_atras_sin_inventarse_fechas(desde, esperado):
    """El 31 de mayo menos tres meses no es el 31 de febrero.

    Restar noventa días habría sido más corto y habría dado el 2 de marzo, que
    no es «tres meses antes» de nada: la ley habla de meses y los meses duran lo
    que duran. Se retrocede al último día del mes que toque, que es lo que hace
    cualquiera con un calendario delante.
    """
    assert _tres_meses_antes(desde) == esperado
