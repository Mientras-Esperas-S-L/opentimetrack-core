"""Dos pulsaciones seguidas son un dedo, no dos hechos.

El tipo de un fichaje se deduce del estado, así que dos peticiones seguidas no
crean dos entradas: crean **una entrada y una salida**. Medido el 13/08/2026 en
la propia pantalla de fichar, con milisegundo y medio entre las dos: el día
quedaba con cero segundos trabajados y en estado «fuera», y quien había pulsado
se iba convencido de haber fichado.

No hace falta mala suerte para provocarlo. Un doble toque en un móvil, una
pantalla que tarda y se vuelve a pulsar, o un cliente que reintenta cuando la
petición ya había llegado. Con guantes y a pie de obra, es un martes cualquiera.

La comprobación vive en el servicio y no en la pantalla, y por eso las pruebas
también: el botón se desactiva mientras la petición viaja, pero eso no cubre el
toque más rápido que el repintado, ni dos pestañas, ni un terminal, ni un
conector --- y todos escriben por la misma puerta.
"""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from apps.common.exceptions import BusinessRuleError
from apps.common.models import tenant_context
from apps.punches.models import PunchInterval, PunchType
from apps.punches.services import build_day_status, register_punch
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def marta(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="marta@example.com", password=PASSWORD, tenant=company, first_name="Marta"
        )


@pytest.mark.django_db
def test_el_segundo_toque_seguido_se_rechaza(company, marta):
    """El caso exacto que dejaba el día en cero."""
    with tenant_context(company.id), freeze_time("2026-08-13 08:00:00"):
        primero = register_punch(employee=marta, company=company)

        with pytest.raises(BusinessRuleError) as caido:
            register_punch(employee=marta, company=company)

        assert caido.value.code == "punch_too_soon"

        # Y lo que importa: la entrada sigue en pie y la jornada, abierta.
        estado = build_day_status(marta, company)
        assert primero.punch_type == PunchType.IN
        assert estado.state == "WORKING"


@pytest.mark.django_db
def test_pasados_unos_segundos_se_puede_fichar_la_salida(company, marta):
    """La ventana es corta a propósito: no puede estorbar a nadie.

    Quien sale y se lo piensa mejor vuelve a entrar en diez segundos, y tiene
    que poder. La protección es para el dedo, no para la persona.
    """
    with tenant_context(company.id):
        with freeze_time("2026-08-13 08:00:00"):
            register_punch(employee=marta, company=company)
        with freeze_time("2026-08-13 08:00:10"):
            salida = register_punch(employee=marta, company=company)

            # Dentro del reloj congelado, no fuera. `build_day_status` mira
            # **hoy**, y con la comprobación fuera «hoy» era el día real: la
            # prueba pasaba todo el día que se escribió y se ponía roja a
            # medianoche, diciendo NOT_STARTED con toda la razón.
            assert salida.punch_type == PunchType.OUT
            assert build_day_status(marta, company).state == "OFF"


@pytest.mark.django_db
def test_una_pausa_no_choca_con_la_jornada(company, marta):
    """La ventana es por tipo de intervalo, igual que la deducción del tipo.

    Empezar una pausa justo después de abrir la jornada es raro pero legítimo
    ---y sobre todo, no es el mismo botón--- así que no puede tomarse por un
    doble toque. Si esto se rompiera, alguien que abre el día y se va al café
    se encontraría con que no puede marcar la pausa.
    """
    with tenant_context(company.id), freeze_time("2026-08-13 08:00:00"):
        register_punch(employee=marta, company=company, interval=PunchInterval.WORK)
        pausa = register_punch(employee=marta, company=company, interval=PunchInterval.BREAK)

        assert pausa.punch_type == PunchType.IN
        assert build_day_status(marta, company).state == "ON_BREAK"


@pytest.mark.django_db
def test_dos_personas_a_la_vez_no_se_estorban(company, marta):
    """La ventana es de cada persona, no del sistema.

    Un terminal compartido en la puerta de la nave recibe a la plantilla entera
    en el mismo minuto. Si la protección fuera global, el segundo en llegar no
    podría fichar --- que es peor que el fallo que arregla.
    """
    with tenant_context(company.id), freeze_time("2026-08-13 08:00:00"):
        hugo = User.objects.create_user(
            email="hugo@example.com", password=PASSWORD, tenant=company, first_name="Hugo"
        )

        de_marta = register_punch(employee=marta, company=company)
        de_hugo = register_punch(employee=hugo, company=company)

        assert de_marta.punch_type == PunchType.IN
        assert de_hugo.punch_type == PunchType.IN


@pytest.mark.django_db
def test_el_rechazo_no_deja_rastro_en_el_registro(company, marta):
    """Un intento rechazado no es un fichaje.

    Importa para el art. 34.9: el registro guarda lo que pasó, y lo que pasó
    fue una pulsación, no dos. Si el segundo intento dejara una fila anulada, un
    inspector vería un hueco que tendría que explicarse.
    """
    from apps.punches.models import Punch

    with tenant_context(company.id), freeze_time("2026-08-13 08:00:00"):
        register_punch(employee=marta, company=company)
        with pytest.raises(BusinessRuleError):
            register_punch(employee=marta, company=company)

        assert Punch.objects.filter(employee=marta).count() == 1
