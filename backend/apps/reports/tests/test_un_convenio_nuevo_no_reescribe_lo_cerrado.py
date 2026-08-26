"""Cambiar cómo se cuenta no puede mover un periodo ya cerrado.

Dos reglas deciden **qué dice el registro**: si la pausa cuenta como trabajo
(art. 34.4 ET) y cuánto aguanta abierta una jornada. Se leían siempre con el
valor de hoy, así que cambiarlas reescribía el pasado --- medido en la vuelta 94,
un abril terminado pasaba de 7:00 a 8:00 h, y un turno de noche bien fichado
pasaba a «entrada sin salida» con cero horas.

Que esas reglas cambien es legítimo: salen del convenio. Que el cambio alcance
hacia atrás, no, porque el art. 34.9 quiere el registro fiable y un asiento que se
relee distinto según el convenio de hoy no lo es.

**Solo estas dos llevan fecha.** Las otras dieciséis ---descanso diario, tope de
horas extra, preaviso del cuadrante--- deciden si el registro *cumple*, no lo que
dice, y deben recalcularse con lo vigente hoy: si un convenio nuevo mejora el
descanso, se quiere ver qué días de antes no lo cumplirían.

**La fecha la declara quien cambia la regla**, porque sale del convenio y el
sistema no puede saberla. Poner «desde hoy» por su cuenta sería tomar una decisión
laboral que no le toca.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.models import Punch
from apps.tenants.models import Tenant
from apps.tenants.rules import ComputationRuleChange, WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def mundo(db):
    empresa = Tenant.objects.create(
        name="Con convenio", tax_id="B91900001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Equis",
            role=Role.ADMIN,
        )
        quien = User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Trabaja",
        )
        # 15 de abril: entra a las 08:00, pausa de 13:00 a 14:00, sale a las 17:00.
        entrada = datetime(2026, 4, 15, 6, 0, tzinfo=UTC)
        for tipo, horas, tramo in (
            ("IN", 0, "WORK"),
            ("OUT", 5, "WORK"),
            ("IN", 5, "BREAK"),
            ("OUT", 6, "BREAK"),
            ("IN", 6, "WORK"),
            ("OUT", 9, "WORK"),
        ):
            Punch.objects.create(
                tenant=empresa,
                employee=quien,
                punch_type=tipo,
                interval=tramo,
                timestamp=entrada + timedelta(hours=horas),
                source="WEB",
                time_zone="Europe/Madrid",
            )
        yield {"empresa": empresa, "jefa": jefa, "quien": quien}


def como(quien):
    cliente = APIClient(raise_request_exception=False)
    cliente.force_authenticate(user=quien)
    return cliente


def fila_de_abril(mundo):
    respuesta = como(mundo["jefa"]).get(
        "/api/reports/working-time/"
        f"?date_from=2026-04-10&date_to=2026-04-20&employee={mundo['quien'].pk}&format=csv"
    )
    assert respuesta.status_code == 200, respuesta.content
    filas = [
        linea
        for linea in respuesta.content.decode("utf-8-sig", "replace").splitlines()
        if "2026-04-15" in linea
    ]
    assert filas, "el día no salía en el informe"
    return filas[0]


@pytest.mark.django_db
def test_cambiar_como_se_cuenta_exige_decir_desde_cuando(mundo):
    respuesta = como(mundo["jefa"]).patch(
        "/api/working-time-rules/", {"break_counts_as_work": True}, format="json"
    )

    assert respuesta.status_code == 400, "se podía cambiar el cómputo sin fecha de efecto"
    assert "effective_from" in respuesta.json()["error"]["details"]


@pytest.mark.django_db
def test_declarado_desde_julio_abril_no_se_mueve(mundo):
    antes = fila_de_abril(mundo)
    assert "07:00" in antes, f"la pausa tenía que salir descontada: {antes}"

    respuesta = como(mundo["jefa"]).patch(
        "/api/working-time-rules/",
        {
            "break_counts_as_work": True,
            "effective_from": "2026-07-01",
            "effective_note": "convenio de 2026",
        },
        format="json",
    )
    assert respuesta.status_code == 200, respuesta.content

    assert fila_de_abril(mundo) == antes, "el convenio nuevo reescribió un abril ya cerrado"


@pytest.mark.django_db
def test_y_a_partir_de_la_fecha_si_cuenta(mundo):
    """Lo otro que tiene que pasar: el cambio sirve para lo que viene."""
    with tenant_context(mundo["empresa"].id):
        # Un día de agosto, con la misma jornada y su pausa.
        entrada = datetime(2026, 8, 12, 6, 0, tzinfo=UTC)
        for tipo, horas, tramo in (
            ("IN", 0, "WORK"),
            ("OUT", 5, "WORK"),
            ("IN", 5, "BREAK"),
            ("OUT", 6, "BREAK"),
            ("IN", 6, "WORK"),
            ("OUT", 9, "WORK"),
        ):
            Punch.objects.create(
                tenant=mundo["empresa"],
                employee=mundo["quien"],
                punch_type=tipo,
                interval=tramo,
                timestamp=entrada + timedelta(hours=horas),
                source="WEB",
                time_zone="Europe/Madrid",
            )

    como(mundo["jefa"]).patch(
        "/api/working-time-rules/",
        {"break_counts_as_work": True, "effective_from": "2026-07-01"},
        format="json",
    )

    respuesta = como(mundo["jefa"]).get(
        "/api/reports/working-time/"
        f"?date_from=2026-08-10&date_to=2026-08-14&employee={mundo['quien'].pk}&format=csv"
    )
    fila = next(
        linea
        for linea in respuesta.content.decode("utf-8-sig", "replace").splitlines()
        if "2026-08-12" in linea
    )
    assert "08:00" in fila, f"desde julio la pausa cuenta, así que son ocho horas: {fila}"


@pytest.mark.django_db
def test_el_primer_cambio_deja_anclado_como_se_contaba_antes(mundo):
    """Sin el ancla, el arreglo no serviría de nada.

    Los días anteriores a la fecha declarada no encuentran ninguna vigencia y
    caerían en las reglas de hoy --- que son justo las que se acaban de cambiar.
    """
    como(mundo["jefa"]).patch(
        "/api/working-time-rules/",
        {"break_counts_as_work": True, "effective_from": "2026-07-01"},
        format="json",
    )

    with tenant_context(mundo["empresa"].id):
        vigencias = list(
            ComputationRuleChange.objects.filter(tenant=mundo["empresa"]).order_by("effective_from")
        )

    assert len(vigencias) == 2, [str(v.effective_from) for v in vigencias]
    # La primera rige desde siempre, con los valores de antes.
    assert vigencias[0].effective_from == date.min
    assert vigencias[0].break_counts_as_work is False
    assert vigencias[1].effective_from == date(2026, 7, 1)
    assert vigencias[1].break_counts_as_work is True
    # Y con nombre y apellidos: un cambio que mueve horas no puede ser anónimo.
    assert vigencias[1].recorded_by_id == mundo["jefa"].pk


@pytest.mark.django_db
def test_las_demas_reglas_no_piden_fecha(mundo):
    """Son valoración, no registro: se recalculan con lo vigente hoy, a propósito."""
    respuesta = como(mundo["jefa"]).patch(
        "/api/working-time-rules/", {"daily_rest_hours": 11}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.content
    with tenant_context(mundo["empresa"].id):
        assert not ComputationRuleChange.objects.filter(tenant=mundo["empresa"]).exists()


@pytest.mark.django_db
def test_sin_ningun_cambio_declarado_todo_se_lee_como_siempre(mundo):
    """Esto no reescribe nada al llegar: sin vigencias, las reglas de hoy."""
    with tenant_context(mundo["empresa"].id):
        assert not ComputationRuleChange.objects.filter(tenant=mundo["empresa"]).exists()
        reglas = WorkingTimeRules.for_company(mundo["empresa"])
        assert reglas.break_counts_as_work is False

    assert "07:00" in fila_de_abril(mundo)
