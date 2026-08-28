"""Las vacaciones que quedan sin disfrutar cuando el contrato termina.

Las vacaciones no se pagan: «no podrán ser sustituidas por compensación
económica» (art. 38.1 ET). La excepción es esta ---el contrato se extingue y ya
no hay cuándo disfrutarlas--- y entonces los días devengados y no disfrutados se
compensan en el finiquito. La otra dirección existe igual: quien disfrutó más de
lo que devengó tiene esos días descontados.

**Días, no dinero.** Lo que vale un día depende del salario, de los complementos
y del prorrateo de pagas: eso es una nómina y está fuera de lo que hace este
producto. Los días sí los sabe el registro, son los que hace falta llevar al
finiquito, y hasta ahora había que contarlos a mano mirando el calendario.

Y el detalle que cambia la cifra: **lo pendiente no resta**. Una solicitud sin
decidir no está disfrutada ni liquidada. Restarla daría un número a pagar más
bajo que el real, así que se cuenta aparte y se dice cuántos días son.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.absences.services import leave_settlement
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"

#: Veintidós días naturales al año, que hace la cuenta directa: medio año son
#: once. En días laborables la proporción es la misma pero cuesta más leerla.
AL_ANO = 22


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="ACME Ltd",
        tax_id="B11111111",
        time_zone="Europe/Madrid",
        annual_leave_days=AL_ANO,
        leave_days_are_working_days=False,
    )


def alguien(company, *, email, empieza=None, termina=None):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        tenant=company,
        first_name="Quien",
        last_name="Se va",
        contract_start=empieza,
        contract_end=termina,
    )


def vacaciones(company, quien, desde, hasta, estado=AbsenceStatus.APPROVED):
    return Absence.objects.create(
        tenant=company,
        employee=quien,
        absence_type=AbsenceType.VACATION,
        start_date=desde,
        end_date=hasta,
        status=estado,
    )


@pytest.mark.django_db
def test_sin_fecha_de_fin_no_hay_nada_que_liquidar(company):
    """**El contraste de todo lo demás.**

    Mientras el contrato siga no hay liquidación: quedan meses para disfrutar
    esos días, y enseñar «te quedan 11 por liquidar» a quien está en plantilla
    es decirle que se va.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="fija@example.com", empieza=date(2020, 1, 1))
        assert leave_settlement(quien, company) is None


@pytest.mark.django_db
def test_los_dias_devengados_y_no_disfrutados_se_liquidan(company):
    """Medio año trabajado son once días, y sin coger ninguno se liquidan once."""
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="medio@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        liq = leave_settlement(quien, company)

        assert liq["until"] == "2026-06-30"
        assert liq["entitled"] == 11
        assert liq["taken"] == 0
        assert liq["days"] == 11
        assert liq["citation"] == "Art. 38.1 ET"


@pytest.mark.django_db
def test_lo_disfrutado_se_descuenta(company):
    """Diez días cogidos de once devengados dejan uno por liquidar."""
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="casi@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        vacaciones(company, quien, date(2026, 3, 2), date(2026, 3, 11))  # 10 naturales

        liq = leave_settlement(quien, company)
        assert liq["entitled"] == 11
        assert liq["taken"] == 10
        assert liq["days"] == 1


@pytest.mark.django_db
def test_quien_disfruto_de_mas_sale_en_negativo(company):
    """**La dirección que nadie mira hasta que aparece en la nómina.**

    Coger las vacaciones enteras en enero y marcharse en junio es corriente y
    perfectamente legítimo, y deja días disfrutados por encima de lo devengado.
    Se descuentan en la liquidación, así que hay que decirlo antes de que
    aparezca como una sorpresa en el finiquito.

    Un producto que solo supiera contar hacia arriba daría cero aquí, que se lee
    como «no hay nada que ajustar» y es lo contrario de lo que pasa.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="pasado@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        vacaciones(company, quien, date(2026, 1, 5), date(2026, 1, 26))  # 22 naturales

        liq = leave_settlement(quien, company)
        assert liq["entitled"] == 11
        assert liq["taken"] == 22
        assert liq["days"] == -11


@pytest.mark.django_db
def test_lo_pendiente_no_resta_y_se_cuenta_aparte(company):
    """Una solicitud sin decidir no está disfrutada ni liquidada.

    El saldo normal sí la resta, y hace bien: enseñar como disponibles unos días
    que alguien ya ha pedido es como dos personas acaban reservando el mismo
    puente. Pero para la liquidación esa resta da una cifra a pagar **más baja
    que la real**, porque esos días o se disfrutan o se pagan, y todavía no ha
    pasado ninguna de las dos cosas.

    Van aparte, con su número, que es lo que quien gestiona tiene que resolver
    antes de cerrar el finiquito.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="pendiente@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        vacaciones(company, quien, date(2026, 6, 1), date(2026, 6, 5), AbsenceStatus.PENDING)

        liq = leave_settlement(quien, company)
        assert liq["taken"] == 0
        assert liq["days"] == 11, "los pendientes no bajan lo que hay que liquidar"
        assert liq["pending"] == 5


@pytest.mark.django_db
def test_se_devenga_hasta_el_fin_del_contrato_y_no_hasta_hoy(company):
    """Una liquidación que cambia sola con el calendario no vale para nada.

    Quien se fue en junio de 2025 devengó once días, y eso es un hecho cerrado:
    consultarlo hoy tiene que dar once, no lo que dé el periodo de este año.
    Mirando «hoy» el contrato de 2025 no toca el periodo de 2026, así que la
    liquidación saldría **cero** y parecería que no hay nada que pagar.

    La primera versión de esta prueba comparaba dos fechas dentro del mismo año
    y pasaba con el error puesto: las dos caían en el mismo periodo de cómputo,
    así que daba igual cuál se usara. Pasaba por el sitio equivocado.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="antiguo@example.com",
            empieza=date(2025, 1, 1),
            termina=date(2025, 6, 30),
        )
        liq = leave_settlement(quien, company)
        assert liq["until"] == "2025-06-30"
        assert liq["entitled"] == 11, "el devengo es el de su periodo, no el de este año"
        assert liq["days"] == 11


@pytest.mark.django_db
def test_la_unidad_viaja_con_la_cifra(company):
    """«Once días» significa cosas distintas en laborables y en naturales.

    Es la misma equivocación que dejó a todo el mundo sin vacaciones en octubre,
    en una cifra que además va a un finiquito.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="unidad@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        assert leave_settlement(quien, company)["working_days"] is False

        company.leave_days_are_working_days = True
        company.save(update_fields=["leave_days_are_working_days"])
        assert leave_settlement(quien, company)["working_days"] is True


@pytest.mark.django_db
def test_no_se_cuela_nadie_de_la_empresa_de_al_lado(company):
    """`User.objects` no acota por empresa, y una liquidación es de una persona."""
    vecina = Tenant.objects.create(
        name="La de al lado",
        tax_id="B44444444",
        time_zone="Europe/Madrid",
        annual_leave_days=AL_ANO,
        leave_days_are_working_days=False,
    )
    with tenant_context(vecina.id):
        suyo = alguien(
            vecina,
            email="suyo@vecina.example",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        vacaciones(vecina, suyo, date(2026, 3, 2), date(2026, 3, 11))

    with tenant_context(company.id):
        propio = alguien(
            company,
            email="propio@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 6, 30),
        )
        # Sin coger ninguno: si las de la vecina se colaran, restarían diez.
        assert leave_settlement(propio, company)["taken"] == 0


@pytest.mark.django_db
def test_una_fecha_hipotetica_contesta_sin_tocar_a_nadie(company):
    """«Si el contrato terminara ese día, ¿cuánto quedaría?».

    Es la pregunta que se hace de verdad: quien prepara una baja escribe una
    fecha y quiere el número **antes** de guardarla. Contestando solo con la
    fecha ya guardada, la cifra aparece después de guardar, cerrar la ficha y
    volver a abrirla, que es cuando ya no sirve para decidir.

    Y no cambia el contrato de nadie: la fecha se pone en una copia en memoria.
    """
    with tenant_context(company.id):
        quien = alguien(company, email="hipotesis@example.com", empieza=date(2026, 1, 1))
        assert leave_settlement(quien, company) is None, "sin fecha, nada que liquidar"

        liq = leave_settlement(quien, company, until=date(2026, 6, 30))
        assert liq["until"] == "2026-06-30"
        assert liq["days"] == 11

        # **En memoria, sin releer de la base.** La primera versión hacía
        # `refresh_from_db()` y pasaba aunque la función mutara a la persona:
        # como nunca se guarda, releer la devolvía a `None` de todas formas y la
        # comprobación no miraba lo que decía. Lo que importa es que quien llamó
        # se quede con el objeto que traía, porque va a seguir usándolo.
        assert quien.contract_end is None, "preguntar no puede haberle puesto fecha de fin"
        quien.refresh_from_db()
        assert quien.contract_end is None


@pytest.mark.django_db
def test_la_hipotesis_manda_sobre_la_fecha_guardada(company):
    """El contraste del anterior: si `until` se ignorara, los dos darían lo mismo.

    Con fin guardado en diciembre y la hipótesis en junio, la respuesta tiene que
    ser la de junio. Sin esto, escribir una fecha nueva en la ficha enseñaría el
    número de la vieja, que es peor que no enseñar ninguno.
    """
    with tenant_context(company.id):
        quien = alguien(
            company,
            email="dos@example.com",
            empieza=date(2026, 1, 1),
            termina=date(2026, 12, 31),
        )
        assert leave_settlement(quien, company)["days"] == 22
        assert leave_settlement(quien, company, until=date(2026, 6, 30))["days"] == 11
