"""El plazo de conservación del registro, cumpliéndose solo.

El campo `record_retention_years` llevaba desde la vuelta 60 declarando una
política que nadie aplicaba, y su propio `help_text` lo decía: «nothing is
deleted automatically yet». Francisco lo aprobó el 27/08/2026 con una condición
---que no se lleve por delante historiales ni datos de la empresa--- y estas
pruebas son esa condición escrita.

Lo que se fija aquí:

- Se borra lo que pasó el plazo, y **solo** eso.
- El suelo de cuatro años del art. 34.9 ET se aplica **en el código que borra**,
  no solo en el formulario. Un número menor en la fila ---por shell, por
  importación--- no puede hacer que el producto borre lo que la ley obliga a
  tener.
- El corte es un **día entero en la zona de la empresa**. Cortar por instante
  parte una jornada y deja media, y media jornada no es un dato menos: es un
  dato **falso**, un día en que alguien parece haber trabajado cuatro horas.
- Ausencias, contratos y personas siguen ahí.
- Una corrección sin resolver **retiene** su fichaje, y se dice en voz alta.
- Queda rastro, y el rastro no se puede borrar.
"""

from __future__ import annotations

from datetime import date, datetime
from io import StringIO

import pytest
from django.core.management import call_command
from freezegun import freeze_time

from apps.absences.models import Absence, AbsenceStatus, AbsenceType
from apps.audit.models import AuditAction, AuditLog
from apps.common.models import tenant_context
from apps.punches.corrections import CorrectionKind, CorrectionStatus, PunchCorrection
from apps.punches.management.commands.purge_expired_records import first_day_kept
from apps.punches.models import CURRENT_HASH_VERSION, Punch, PunchSource
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"
AHORA = "2026-08-27 10:00:00"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Plazos SL", tax_id="B21212121", time_zone="Europe/Madrid"
    )


@pytest.fixture
def employee(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="pau@example.com", password=PASSWORD, tenant=company,
            first_name="Pau", last_name="Serra",
        )


def _punch(company, employee, *, when, kind="IN"):
    """Un fichaje escrito como se habría escrito ese día."""
    punch = Punch(
        tenant=company, employee=employee, punch_type=kind,
        timestamp=when, source=PunchSource.WEB,
    )
    punch.hash_version = CURRENT_HASH_VERSION
    punch.hash_integrity = punch.compute_hash()
    punch.save()
    return punch


def _madrid(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=Tenant(time_zone="Europe/Madrid").tzinfo)


def _purgar(**opciones):
    salida = StringIO()
    call_command("purge_expired_records", stdout=salida, **opciones)
    return salida.getvalue()


def _purgar_con_rastro(capturar, **opciones):
    """El asiento se guarda en `on_commit`, así que en pruebas no llega solo."""
    with capturar(execute=True):
        return _purgar(**opciones)


# --------------------------------------------------------- lo que sí se borra


@freeze_time(AHORA)
@pytest.mark.django_db
def test_borra_lo_que_paso_el_plazo_y_deja_lo_de_dentro(company, employee):
    viejo = _punch(company, employee, when=_madrid(2021, 5, 10))
    dentro = _punch(company, employee, when=_madrid(2023, 5, 10))

    salida = _purgar(tenant=company.tax_id)

    assert not Punch.objects_all_tenants.filter(pk=viejo.pk).exists()
    assert Punch.objects_all_tenants.filter(pk=dentro.pk).exists()
    assert "Deleted 1 events" in salida


@freeze_time(AHORA)
@pytest.mark.django_db
def test_en_seco_no_borra_nada_pero_lo_cuenta(company, employee):
    """El contraste que hace legible el «0» del caso normal."""
    viejo = _punch(company, employee, when=_madrid(2021, 5, 10))

    salida = _purgar(tenant=company.tax_id, dry_run=True)

    assert Punch.objects_all_tenants.filter(pk=viejo.pk).exists()
    assert "Would delete 1 events" in salida


@freeze_time(AHORA)
@pytest.mark.django_db
def test_una_empresa_de_baja_tambien_se_purga(company, employee):
    """El plazo no deja de correr porque la empresa deje de usar el producto, y
    esos son justamente los datos que ya no mira nadie."""
    viejo = _punch(company, employee, when=_madrid(2021, 5, 10))
    company.is_active = False
    company.save(update_fields=["is_active"])

    _purgar(tenant=company.tax_id)

    assert not Punch.objects_all_tenants.filter(pk=viejo.pk).exists()


# ------------------------------------------------------------ el suelo legal


@freeze_time(AHORA)
@pytest.mark.django_db
def test_el_suelo_de_cuatro_anos_se_aplica_aunque_la_fila_diga_menos(company, employee):
    """El serializador ya rechaza menos de cuatro, pero un número escrito por
    shell o por importación no pasó por él, y este es el código que borra."""
    Tenant.objects.filter(pk=company.pk).update(record_retention_years=1)
    company.refresh_from_db()
    assert company.record_retention_years == 1

    hace_dos_anos = _punch(company, employee, when=_madrid(2024, 5, 10))
    hace_cinco = _punch(company, employee, when=_madrid(2021, 5, 10))

    salida = _purgar(tenant=company.tax_id)

    assert Punch.objects_all_tenants.filter(pk=hace_dos_anos.pk).exists(), (
        "con el plazo declarado de 1 año se habría borrado un fichaje que la ley obliga a tener"
    )
    assert not Punch.objects_all_tenants.filter(pk=hace_cinco.pk).exists()
    assert "(4 years)" in salida


@freeze_time(AHORA)
@pytest.mark.django_db
def test_un_plazo_mas_largo_que_el_suelo_se_respeta(company, employee):
    company.record_retention_years = 6
    company.save(update_fields=["record_retention_years"])

    hace_cinco = _punch(company, employee, when=_madrid(2021, 5, 10))

    _purgar(tenant=company.tax_id)

    assert Punch.objects_all_tenants.filter(pk=hace_cinco.pk).exists()


# ------------------------------------------------- el corte es un día entero


@freeze_time(AHORA)
@pytest.mark.django_db
def test_el_ultimo_dia_que_se_guarda_se_guarda_entero(company, employee):
    """Lo que se evita: cortar a las 10:00 y dejar la tarde de ese día suelta.

    Un día con solo la salida registrada no es un dato incompleto, es un dato
    **falso**: se lee como una jornada de cuatro horas.
    """
    primer_dia = first_day_kept(company)
    assert primer_dia == date(2022, 8, 27)

    manana = _punch(company, employee, when=_madrid(2022, 8, 27, 8), kind="IN")
    tarde = _punch(company, employee, when=_madrid(2022, 8, 27, 17), kind="OUT")
    dia_antes = _punch(company, employee, when=_madrid(2022, 8, 26, 17))

    _purgar(tenant=company.tax_id)

    assert Punch.objects_all_tenants.filter(pk=manana.pk).exists()
    assert Punch.objects_all_tenants.filter(pk=tarde.pk).exists()
    assert not Punch.objects_all_tenants.filter(pk=dia_antes.pk).exists()


@freeze_time("2026-08-26 22:30:00")
@pytest.mark.django_db
def test_el_dia_es_el_de_la_empresa_no_el_del_servidor(db):
    """A las 22:30 UTC ya es el día 27 en Madrid (+02) y todavía el 26 en
    Canarias (+01). El corte se mueve con el calendario de cada empresa, que es
    el que aparece en sus documentos ---y de paso esto es lo que `date.today()`
    contesta mal para todos, porque contesta en UTC."""
    madrid = Tenant.objects.create(
        name="Madrid SL", tax_id="B31313131", time_zone="Europe/Madrid"
    )
    canarias = Tenant.objects.create(
        name="Canarias SL", tax_id="B41414141", time_zone="Atlantic/Canary"
    )

    assert first_day_kept(madrid) == date(2022, 8, 27)
    assert first_day_kept(canarias) == date(2022, 8, 26), (
        "en Canarias a las 00:30 de Madrid todavía es el día anterior"
    )


@pytest.mark.django_db
def test_un_29_de_febrero_conserva_un_dia_mas(company):
    """El año de destino puede no tener ese día. Se conserva de más, que es el
    lado por el que hay que equivocarse."""
    company.record_retention_years = 5
    with freeze_time("2028-02-29 12:00:00"):
        assert first_day_kept(company) == date(2023, 2, 28)


# ------------------------------------------------------- lo que no se toca


@freeze_time(AHORA)
@pytest.mark.django_db
def test_no_toca_ausencias_ni_personas(company, employee):
    """La condición que puso Francisco: que no se lleve por delante historiales.

    Una vacación de 2021 sigue siendo lo que explica un hueco en una nómina de
    2021, y la persona no se borra nunca ---`Punch.employee` es PROTECT, así que
    esto además comprueba que el borrado no va por delante de esa protección---.
    """
    with tenant_context(company.id):
        vieja = Absence.objects.create(
            tenant=company, employee=employee, absence_type=AbsenceType.VACATION,
            start_date=date(2021, 5, 10), end_date=date(2021, 5, 20),
            status=AbsenceStatus.APPROVED,
        )
    _punch(company, employee, when=_madrid(2021, 5, 10))

    _purgar(tenant=company.tax_id)

    assert Absence.objects_all_tenants.filter(pk=vieja.pk).exists()
    assert User.objects.filter(pk=employee.pk).exists()
    assert Punch.objects_all_tenants.filter(tenant=company).count() == 0


@freeze_time(AHORA)
@pytest.mark.django_db
def test_una_correccion_sin_resolver_retiene_su_fichaje_y_lo_dice(company, employee):
    """Un cambio que nadie resolvió no es un registro cerrado. Y un salto
    callado se leería como «ya está todo purgado»."""
    viejo = _punch(company, employee, when=_madrid(2021, 5, 10))
    with tenant_context(company.id):
        PunchCorrection.objects.create(
            tenant=company, employee=employee, target=viejo,
            kind=CorrectionKind.MODIFY, reason="La hora de salida no es la que fue",
            requested_by=employee, status=CorrectionStatus.PENDING,
        )

    salida = _purgar(tenant=company.tax_id)

    assert Punch.objects_all_tenants.filter(pk=viejo.pk).exists()
    assert "kept (open correction)" in salida
    assert "still open" in salida


@freeze_time(AHORA)
@pytest.mark.django_db
def test_una_correccion_ya_resuelta_no_bloquea_el_borrado(company, employee):
    """`PunchCorrection.target` es PROTECT: sin borrar antes la corrección, el
    borrado se plantaría con ProtectedError a mitad de la pasada."""
    viejo = _punch(company, employee, when=_madrid(2021, 5, 10))
    with tenant_context(company.id):
        cerrada = PunchCorrection.objects.create(
            tenant=company, employee=employee, target=viejo,
            kind=CorrectionKind.MODIFY, reason="Se resolvió hace tres años",
            requested_by=employee, status=CorrectionStatus.REJECTED,
        )

    _purgar(tenant=company.tax_id)

    assert not Punch.objects_all_tenants.filter(pk=viejo.pk).exists()
    assert not PunchCorrection.objects_all_tenants.filter(pk=cerrada.pk).exists()


# ------------------------------------------------------------------ el rastro


@freeze_time(AHORA)
@pytest.mark.django_db
def test_deja_rastro_de_lo_que_borro(company, employee, django_capture_on_commit_callbacks):
    """Lo único que quedará de aquellos días. Y no se puede borrar: la tabla es
    de solo añadir."""
    _punch(company, employee, when=_madrid(2021, 5, 10))
    _punch(company, employee, when=_madrid(2021, 5, 11))

    _purgar_con_rastro(django_capture_on_commit_callbacks, tenant=company.tax_id)

    asiento = AuditLog.objects.filter(tenant=company, action=AuditAction.RECORD_PURGED).get()
    assert asiento.changes["deleted"] == 2
    assert asiento.changes["kept_from"] == "2022-08-27"
    assert asiento.changes["applied_years"] == 4


@freeze_time(AHORA)
@pytest.mark.django_db
def test_sin_nada_que_borrar_no_deja_asiento_ni_miente(
    company, employee, django_capture_on_commit_callbacks
):
    """Un asiento por cada pasada diaria que no borró nada sería ruido, y el
    rastro es donde se busca lo que sí pasó."""
    _punch(company, employee, when=_madrid(2026, 5, 10))

    salida = _purgar_con_rastro(django_capture_on_commit_callbacks, tenant=company.tax_id)

    assert not AuditLog.objects.filter(tenant=company, action=AuditAction.RECORD_PURGED).exists()
    assert "Nothing past its period" in salida
