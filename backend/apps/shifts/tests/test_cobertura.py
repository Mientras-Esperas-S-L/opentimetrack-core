"""Qué turnos se quedaron sin nadie, y quién puede cogerlos.

Viene de una pregunta de Francisco: el cuadrante ya avisaba de que alguien se
fue o está de baja, y ahí se acababa. Avisar no es cubrir. Alguien tiene que
poner a otra persona en ese turno, y para eso había que salir de la revisión,
abrir el cuadrante y mirar ficha por ficha quién podía.

La distinción que sostiene todo el módulo es **duro contra blando**. Inviable
solo por lo que hace imposible el turno: no estar contratado ese día, tener una
ausencia que para el día entero, o estar ya en otro turno. Lo demás ---pasarse
de horas, quedarse sin las doce de descanso--- son avisos, porque son cosas que
a veces se hacen a sabiendas y quien cubre una baja a última hora necesita saber
el precio, no que se lo escondan. Un producto que solo ofrece candidatos
perfectos no ofrece a nadie el día que hay gripe.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import Absence, AbsenceStatus
from apps.common.models import tenant_context
from apps.shifts.coverage import DE_BAJA, SE_FUE, uncovered, who_can_cover
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
LUNES = date(2026, 9, 7)


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


def _persona(empresa, nombre, correo, **extra):
    return User.objects.create_user(
        email=correo, password=PASSWORD, tenant=empresa, first_name=nombre, **extra
    )


def _turno(empresa, quien, dia, desde="08:00", hasta="16:00"):
    return Shift.objects.create(
        tenant=empresa, employee=quien, day=dia, segments=[{"start": desde, "end": hasta}]
    )


@pytest.mark.django_db
def test_el_turno_de_quien_dejo_la_empresa_sale_como_hueco(empresa):
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        _turno(empresa, se_fue, LUNES)
        se_fue.contract_end = LUNES - timedelta(days=1)
        se_fue.is_active = False
        se_fue.save(update_fields=["contract_end", "is_active"])

        huecos = uncovered(company=empresa, first=LUNES, last=LUNES)

    assert len(huecos) == 1
    assert huecos[0].reason == SE_FUE


@pytest.mark.django_db
def test_el_turno_de_quien_esta_de_baja_tambien(empresa):
    """Y con su propio motivo, porque no se resuelve igual: quien se fue no
    vuelve y su turno hay que reasignarlo; quien está de baja vuelve, y a veces
    lo que se decide es no cubrirlo."""
    with tenant_context(empresa.id):
        marta = _persona(empresa, "Marta", "marta@example.com")
        _turno(empresa, marta, LUNES)
        Absence.objects.create(
            tenant=empresa,
            employee=marta,
            status=AbsenceStatus.APPROVED,
            start_date=LUNES,
            end_date=LUNES + timedelta(days=5),
        )

        huecos = uncovered(company=empresa, first=LUNES, last=LUNES)

    assert len(huecos) == 1
    assert huecos[0].reason == DE_BAJA


@pytest.mark.django_db
def test_una_ausencia_de_parte_del_dia_no_es_un_hueco(empresa):
    """El contraste que evita llenar el panel de huecos falsos.

    Ya está documentado en `_check_leave_clashes`: una persona en ERTE de
    reducción generaba veintiún avisos falsos en un mes, y un aviso que se
    equivoca veintitrés de treinta veces entierra los siete que aciertan. Esa
    gente **sí** tiene que estar en el cuadrante.
    """
    with tenant_context(empresa.id):
        quien = _persona(empresa, "Ana", "ana@example.com")
        _turno(empresa, quien, LUNES)
        Absence.objects.create(
            tenant=empresa,
            employee=quien,
            status=AbsenceStatus.APPROVED,
            start_date=LUNES,
            end_date=LUNES,
            reduction_share=40,
        )

        assert uncovered(company=empresa, first=LUNES, last=LUNES) == []


@pytest.mark.django_db
def test_un_cuadrante_sano_no_tiene_ningun_hueco(empresa):
    """El otro contraste. Sin él, todo lo de arriba pasaría igual si `uncovered`
    devolviera siempre todos los turnos."""
    with tenant_context(empresa.id):
        quien = _persona(empresa, "Ana", "ana@example.com")
        _turno(empresa, quien, LUNES)

        assert uncovered(company=empresa, first=LUNES, last=LUNES) == []


@pytest.mark.django_db
def test_quien_esta_libre_ese_dia_puede_cubrirlo(empresa):
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        libre = _persona(empresa, "Ana", "ana@example.com")
        turno = _turno(empresa, se_fue, LUNES)

        candidatos = who_can_cover(shift=turno, company=empresa)

    viables = [c for c in candidatos if c.viable]
    assert [c.employee.id for c in viables] == [libre.id]


@pytest.mark.django_db
def test_quien_ya_tiene_turno_ese_dia_no_puede(empresa):
    """Nadie está en dos sitios a la vez. Es de los bloqueos duros."""
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        ocupada = _persona(empresa, "Ana", "ana@example.com")
        _turno(empresa, ocupada, LUNES, "14:00", "22:00")
        turno = _turno(empresa, se_fue, LUNES)

        candidatos = who_can_cover(shift=turno, company=empresa)

    suyo = next(c for c in candidatos if c.employee.id == ocupada.id)
    assert suyo.viable is False
    assert suyo.blockers


@pytest.mark.django_db
def test_pasarse_de_horas_avisa_pero_no_veta(empresa):
    """La distinción que sostiene el módulo.

    Las horas por encima de lo contratado son complementarias (art. 12.5): son
    legales, se registran aparte, y a veces se hacen a sabiendas. Vetarlas
    dejaría el panel sin candidatos justo el día que hace falta cubrir algo.
    """
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        media_jornada = _persona(
            empresa, "Ana", "ana@example.com", contracted_hours=8, contracted_period="WEEK"
        )
        # Ya lleva la semana entera hecha.
        _turno(empresa, media_jornada, LUNES + timedelta(days=1))
        turno = _turno(empresa, se_fue, LUNES)

        candidatos = who_can_cover(shift=turno, company=empresa)

    suyo = next(c for c in candidatos if c.employee.id == media_jornada.id)
    assert suyo.viable is True, "pasarse de horas no puede ser un veto"
    assert suyo.warnings, "y tiene que decirlo"


@pytest.mark.django_db
def test_quedarse_sin_las_doce_horas_de_descanso_avisa(empresa):
    """Art. 34.3. También aviso: es un incumplimiento y hay que verlo, pero
    quien cubre una urgencia tiene que poder decidirlo sabiéndolo."""
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        de_noche = _persona(empresa, "Ana", "ana@example.com")
        # Sale a las 02:00 del lunes; el turno a cubrir empieza a las 08:00.
        _turno(empresa, de_noche, LUNES - timedelta(days=1), "18:00", "02:00")
        turno = _turno(empresa, se_fue, LUNES)

        candidatos = who_can_cover(shift=turno, company=empresa)

    suyo = next(c for c in candidatos if c.employee.id == de_noche.id)
    assert suyo.viable is True
    assert any("h" in str(a) for a in suyo.warnings), "no avisa del descanso corto"


@pytest.mark.django_db
def test_el_titular_no_se_ofrece_a_si_mismo(empresa):
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        turno = _turno(empresa, se_fue, LUNES)

        candidatos = who_can_cover(shift=turno, company=empresa)

    assert se_fue.id not in [c.employee.id for c in candidatos]


@pytest.mark.django_db
def test_los_viables_van_delante(empresa):
    """El orden es parte de la respuesta: quien mira esto decide con los
    primeros tres y no baja."""
    with tenant_context(empresa.id):
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        _persona(empresa, "Ocupada", "ocupada@example.com")
        _persona(empresa, "Libre", "libre@example.com")
        turno = _turno(empresa, se_fue, LUNES)
        ocupada = User.objects.get(email="ocupada@example.com")
        _turno(empresa, ocupada, LUNES, "14:00", "22:00")

        candidatos = who_can_cover(shift=turno, company=empresa)

    viables = [c.viable for c in candidatos]
    assert viables == sorted(viables, reverse=True), "los inviables se cuelan arriba"


# ------------------------------------------------------------------ el endpoint


def _como(quien):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(quien).access_token}")
    return cliente


@pytest.mark.django_db
def test_el_endpoint_devuelve_huecos_con_sus_candidatos(empresa):
    with tenant_context(empresa.id):
        jefa = _persona(empresa, "Luisa", "jefa@example.com", role=Role.ADMIN)
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        _persona(empresa, "Ana", "ana@example.com")
        _turno(empresa, se_fue, LUNES)
        se_fue.is_active = False
        se_fue.contract_end = LUNES - timedelta(days=1)
        se_fue.save(update_fields=["is_active", "contract_end"])

        respuesta = _como(jefa).get(
            "/api/shifts/coverage/", {"from": LUNES.isoformat(), "to": LUNES.isoformat()}
        )

    assert respuesta.status_code == 200, respuesta.json()
    huecos = respuesta.json()["uncovered"]
    assert len(huecos) == 1
    assert huecos[0]["reason"] == SE_FUE
    assert huecos[0]["employee_label"] == "Chelo"
    assert any(c["viable"] for c in huecos[0]["candidates"])


@pytest.mark.django_db
def test_quien_solo_ficha_no_puede_mirarlo(empresa):
    """No escribe nada, pero de cada compañero dice cuántas horas lleva esa
    semana y si está de baja. Eso no es asunto de quien solo ficha."""
    with tenant_context(empresa.id):
        curro = _persona(empresa, "Curro", "curro@example.com")

        respuesta = _como(curro).get(
            "/api/shifts/coverage/", {"from": LUNES.isoformat(), "to": LUNES.isoformat()}
        )

    assert respuesta.status_code == 403


# --------------------------------------------------------------- reasignar


@pytest.mark.django_db
def test_reasignar_mueve_el_turno_y_no_lo_duplica(empresa):
    """Una operación, no dos.

    La primera versión de la pantalla asignaba a la nueva y limpiaba a la
    anterior por separado. Ese orden tiene un fallo en medio que deja el turno
    duplicado, y el orden contrario lo deja borrado y sin nadie.
    """
    with tenant_context(empresa.id):
        jefa = _persona(empresa, "Luisa", "jefa@example.com", role=Role.ADMIN)
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        cubre = _persona(empresa, "Ana", "ana@example.com")
        turno = _turno(empresa, se_fue, LUNES)

        respuesta = _como(jefa).post(
            f"/api/shifts/{turno.id}/reassign/", {"employee": str(cubre.id)}, format="json"
        )

        assert respuesta.status_code == 200, respuesta.json()
        turno.refresh_from_db()
        assert turno.employee_id == cubre.id
        assert Shift.objects.filter(day=LUNES).count() == 1, "el turno se duplicó"


@pytest.mark.django_db
def test_no_se_puede_poner_a_alguien_dos_veces_el_mismo_dia(empresa):
    with tenant_context(empresa.id):
        jefa = _persona(empresa, "Luisa", "jefa@example.com", role=Role.ADMIN)
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        ocupada = _persona(empresa, "Ana", "ana@example.com")
        _turno(empresa, ocupada, LUNES, "14:00", "22:00")
        turno = _turno(empresa, se_fue, LUNES)

        respuesta = _como(jefa).post(
            f"/api/shifts/{turno.id}/reassign/", {"employee": str(ocupada.id)}, format="json"
        )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "already_rostered"


@pytest.mark.django_db
def test_reasignar_deja_rastro_de_quien_y_a_quien(empresa, django_capture_on_commit_callbacks):
    """El cuadrante no dejaba rastro de nada, y esta es la operación que más
    falta hace que lo deje: cambia quién trabaja qué día, y a veces se hace
    sabiendo que a quien lo coge se le quedan menos de doce horas de descanso."""
    from apps.audit.models import AuditLog

    with tenant_context(empresa.id):
        jefa = _persona(empresa, "Luisa", "jefa@example.com", role=Role.ADMIN)
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        cubre = _persona(empresa, "Ana", "ana@example.com")
        turno = _turno(empresa, se_fue, LUNES)

        with django_capture_on_commit_callbacks(execute=True):
            _como(jefa).post(
                f"/api/shifts/{turno.id}/reassign/", {"employee": str(cubre.id)}, format="json"
            )

        entradas = [e for e in AuditLog.objects.all() if e.changes.get("to_label")]

    assert entradas, "reasignar un turno no dejó rastro"
    assert entradas[0].changes["from_label"] == "Chelo"
    assert entradas[0].changes["to_label"] == "Ana"


@pytest.mark.django_db
def test_reasignar_es_de_quien_gestiona(empresa):
    with tenant_context(empresa.id):
        curro = _persona(empresa, "Curro", "curro@example.com")
        otro = _persona(empresa, "Otro", "otro@example.com")
        turno = _turno(empresa, otro, LUNES)

        respuesta = _como(curro).post(
            f"/api/shifts/{turno.id}/reassign/", {"employee": str(curro.id)}, format="json"
        )

    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_se_puede_reasignar_a_quien_incumple_algo_a_sabiendas(empresa):
    """A propósito, y es la decisión de diseño del módulo entero.

    `coverage` dice el precio con matices ---puede pero se pasa de horas, puede
    pero se queda sin descanso--- y aquí solo se podrían convertir en un sí o un
    no. Cubrir una baja incumpliendo algo a sabiendas es una decisión legítima
    de quien organiza; el producto le enseña el precio y deja constancia, no se
    lo impide.
    """
    with tenant_context(empresa.id):
        jefa = _persona(empresa, "Luisa", "jefa@example.com", role=Role.ADMIN)
        se_fue = _persona(empresa, "Chelo", "chelo@example.com")
        justo = _persona(
            empresa, "Ana", "ana@example.com", contracted_hours=8, contracted_period="WEEK"
        )
        _turno(empresa, justo, LUNES + timedelta(days=1))
        turno = _turno(empresa, se_fue, LUNES)

        respuesta = _como(jefa).post(
            f"/api/shifts/{turno.id}/reassign/", {"employee": str(justo.id)}, format="json"
        )

    assert respuesta.status_code == 200, "el producto no puede impedir una decisión de organización"
