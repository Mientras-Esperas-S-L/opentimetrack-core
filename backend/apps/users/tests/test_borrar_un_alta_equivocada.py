"""El alta equivocada, que hasta ahora no tenía salida.

Dar de baja no es borrar, y hace bien en no serlo: los fichajes de quien trabajó
aquí viven cuatro años y su ficha tiene que seguir explicándolos. Pero eso dejaba
sin salida el correo mal escrito, la persona duplicada y la que se creó en la
empresa que no era: solo se podían dar de baja, y se quedaban en la lista para
siempre. En la base de demostración llegaron a ser **946 de 969**.

Lo que se fija aquí es **cuándo se puede** y, sobre todo, cuándo no. Y la tercera
familia es la que no se ve: si esa persona **decidió** algo sobre otra ---aprobó
una ausencia, resolvió una corrección--- borrarla no falla, **vacía**. Esos campos
son `SET_NULL`, así que se quedan en silencio con «decidido por: nadie», y el art.
4.b pide que un cambio en el registro lleve nombre y apellidos.
"""

from __future__ import annotations

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.punches.models import CURRENT_HASH_VERSION, Punch, PunchSource
from apps.tenants.models import Tenant
from apps.users.erase import rastro_de
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(name="Altas SL", tax_id="B61616161", time_zone="Europe/Madrid")


@pytest.fixture
def jefa(empresa):
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            last_name="Uno",
            role=Role.ADMIN,
        )


@pytest.fixture
def otra_admin(empresa):
    """Una segunda, para que borrar a la primera no deje la empresa sin nadie."""
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="segunda@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Segunda",
            last_name="Dos",
            role=Role.ADMIN,
        )


@pytest.fixture
def equivocada(empresa):
    """El alta que no debería existir: se creó y nadie la usó."""
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="equivocada@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Equi",
            last_name="Vocada",
        )


def _como(quien):
    cliente = APIClient()
    cliente.force_authenticate(quien)
    return cliente


def _borrar(quien, a_quien):
    return _como(quien).post(f"/api/employees/{a_quien.id}/erase/", {}, format="json")


def _fichaje(empresa, persona):
    p = Punch(
        tenant=empresa,
        employee=persona,
        punch_type="IN",
        timestamp=dt.datetime(2026, 5, 4, 8, tzinfo=dt.UTC),
        source=PunchSource.WEB,
    )
    p.hash_version = CURRENT_HASH_VERSION
    p.hash_integrity = p.compute_hash()
    p.save()
    return p


# ------------------------------------------------------------------- el caso


@pytest.mark.django_db
def test_un_alta_equivocada_se_puede_retirar(jefa, equivocada):
    respuesta = _borrar(jefa, equivocada)

    assert respuesta.status_code == 200
    assert not User.objects.filter(pk=equivocada.pk).exists()


@pytest.mark.django_db
def test_queda_asiento_con_el_nombre_dentro(
    empresa, jefa, equivocada, django_capture_on_commit_callbacks
):
    """Es lo único que quedará de que esa persona existió, así que el nombre y el
    correo van **dentro** del apunte: después no habrá fila de la que sacarlos."""
    with django_capture_on_commit_callbacks(execute=True):
        _borrar(jefa, equivocada)

    asiento = AuditLog.objects.filter(tenant=empresa, action=AuditAction.PERSON_ERASED).get()
    assert asiento.target_label == "Equi Vocada"
    assert asiento.changes["email"] == "equivocada@example.com"
    assert asiento.actor_id == jefa.id


# --------------------------------------------------------- lo que lo impide


@pytest.mark.django_db
def test_con_un_fichaje_no_se_borra_y_dice_cuántos(empresa, jefa, equivocada):
    with tenant_context(empresa.id):
        _fichaje(empresa, equivocada)

    respuesta = _borrar(jefa, equivocada)

    assert respuesta.status_code == 409
    assert User.objects.filter(pk=equivocada.pk).exists()
    detalle = str(respuesta.data)
    assert "1" in detalle and "Equi Vocada" in detalle


@pytest.mark.django_db
def test_con_una_ausencia_tampoco(empresa, jefa, equivocada):
    """Se iría en cascada, en silencio. Una ausencia de 2021 sigue explicando un
    hueco en una nómina de 2021."""
    with tenant_context(empresa.id):
        Absence.objects.create(
            tenant=empresa,
            employee=equivocada,
            absence_type=AbsenceType.VACATION,
            start_date=dt.date(2026, 5, 4),
            end_date=dt.date(2026, 5, 6),
            status=AbsenceStatus.APPROVED,
        )

    assert _borrar(jefa, equivocada).status_code == 409
    assert User.objects.filter(pk=equivocada.pk).exists()


@pytest.mark.django_db
def test_haber_decidido_sobre_otra_persona_lo_impide(empresa, jefa, otra_admin, equivocada):
    """**La que no se ve.** `approved_by` es SET_NULL: borrarla no falla, deja la
    aprobación sin nombre. Y una aprobación sin nombre no vale como aprobación."""
    with tenant_context(empresa.id):
        Absence.objects.create(
            tenant=empresa,
            employee=equivocada,
            absence_type=AbsenceType.VACATION,
            start_date=dt.date(2026, 5, 4),
            end_date=dt.date(2026, 5, 6),
            status=AbsenceStatus.APPROVED,
            approved_by=jefa,
        )

    # A la que pidió la ausencia no se la puede borrar ---es suya---, y a **quien
    # la aprobó** tampoco, que es lo que esta prueba viene a fijar.
    respuesta = _borrar(otra_admin, jefa)

    assert respuesta.status_code == 409
    assert User.objects.filter(pk=jefa.pk).exists()
    assert "aprob" in str(respuesta.data).lower() or "approved" in str(respuesta.data).lower()


@pytest.mark.django_db
def test_no_se_puede_borrar_uno_mismo(jefa, otra_admin):
    """Igual que no se puede uno dar de baja: deshacerlo necesita a otra persona
    con el mismo permiso, y puede no haberla."""
    respuesta = _borrar(jefa, jefa)

    assert respuesta.status_code == 409
    assert User.objects.filter(pk=jefa.pk).exists()


@pytest.mark.django_db
def test_la_empresa_no_puede_quedarse_sin_administracion(empresa, jefa, equivocada):
    """Y por qué, que no es lo que parece.

    La primera versión de esta prueba daba dos perfiles de administración,
    borraba uno y comprobaba que el último no se podía borrar. Pasaba ---y
    seguía pasando con el guard de «no dejar la empresa sin nadie» **quitado**---
    porque el último borrado lo pedía esa misma persona sobre sí misma, y eso ya
    lo impide otra comprobación. Una prueba que pasa por el motivo equivocado no
    cubre nada.

    Lo que de verdad lo garantiza aquí es la combinación: **borrar es cosa de la
    administración** y **nadie puede borrarse a sí mismo**, así que para que
    alguien retire al último perfil de administración tendría que quedar otro que
    pudiera hacerlo, y entonces no era el último.

    El guard sigue llamándose ---cuesta una línea y protege si mañana se permite
    borrar a un perfil de responsable---, pero hoy es defensa en profundidad y no
    lo que sostiene esto. Escrito para que nadie lo quite creyendo que lo cubre
    esta prueba.
    """
    with tenant_context(empresa.id):
        equivocada.role = Role.ADMIN
        equivocada.save(update_fields=["role"])

        # Con dos, se puede retirar a una.
        jefa_id = jefa.pk
        assert _borrar(equivocada, jefa).status_code == 200
        assert not User.objects.filter(pk=jefa_id).exists()

        # Y la que queda no puede retirarse a sí misma, que es lo único que
        # dejaría a la empresa sin nadie.
        respuesta = _borrar(equivocada, equivocada)
        assert respuesta.status_code == 409
        assert "erase your own" in str(respuesta.data) or "propia" in str(respuesta.data).lower()
        assert User.objects.filter(pk=equivocada.pk).exists()


@pytest.mark.django_db
def test_una_persona_normal_no_puede_borrar_a_nadie(empresa, equivocada):
    with tenant_context(empresa.id):
        cualquiera = User.objects.create_user(
            email="peon@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Peón",
            last_name="Tres",
        )

    respuesta = _borrar(cualquiera, equivocada)

    assert respuesta.status_code in (403, 404)
    assert User.objects.filter(pk=equivocada.pk).exists()


@pytest.mark.django_db
def test_no_se_alcanza_a_la_empresa_de_al_lado(empresa, jefa):
    """El alcance de siempre: una persona de otra empresa responde como una que
    no existe, porque la diferencia diría quién trabaja allí."""
    otra = Tenant.objects.create(name="Vecina SL", tax_id="B71717171", time_zone="Europe/Madrid")
    with tenant_context(otra.id):
        suya = User.objects.create_user(
            email="suya@vecina.example",
            password=PASSWORD,
            tenant=otra,
            first_name="De",
            last_name="Enfrente",
        )

    assert _borrar(jefa, suya).status_code == 404
    assert User.objects.filter(pk=suya.pk).exists()


# ------------------------------------------------------------------ el conteo


@pytest.mark.django_db
def test_el_rastro_separa_lo_suyo_de_lo_que_decidio(empresa, jefa, equivocada):
    """Las dos familias se cuentan aparte porque se explican distinto: una dice
    «esta persona trabajó aquí», la otra «esta persona decidió sobre otras»."""
    with tenant_context(empresa.id):
        _fichaje(empresa, equivocada)
        Absence.objects.create(
            tenant=empresa,
            employee=jefa,
            absence_type=AbsenceType.VACATION,
            start_date=dt.date(2026, 5, 4),
            end_date=dt.date(2026, 5, 6),
            status=AbsenceStatus.APPROVED,
            approved_by=equivocada,
        )

        rastro = rastro_de(equivocada)

    assert sum(rastro.suyo.values()) == 1
    assert sum(rastro.decidido.values()) == 1
    assert rastro.hay


@pytest.mark.django_db
def test_quien_no_dejo_nada_no_tiene_rastro(empresa, equivocada):
    with tenant_context(empresa.id):
        rastro = rastro_de(equivocada)

    assert rastro.suyo == {}
    assert rastro.decidido == {}
    assert not rastro.hay
