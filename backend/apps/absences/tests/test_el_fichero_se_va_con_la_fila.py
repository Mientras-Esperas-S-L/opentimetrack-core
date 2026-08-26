"""Lo que se borra de la base tiene que irse también del almacén.

Django dejó de borrar ficheros al borrar filas en la 1.3, a propósito y por
buenas razones. La consecuencia, si nadie se ocupa, es un almacén que acumula
documentos sin nada que los apunte: ni fila, ni pantalla, ni comando. Solo
aparecen mirando el disco a mano.

Aquí eso es grave. Un justificante es a menudo un dato del art. 9 del RGPD ---
una citación, un informe de un familiar hospitalizado--- y la persona que retira
su solicitud está diciendo justamente que no quiere que se quede. Sin esto, la
empresa no puede atender una supresión (art. 17) ni cumplir su propio plazo de
conservación (art. 5.1.e), porque no hay nada que sepa que ese fichero existe.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.absences.models import AbsenceStatus, AbsenceType
from apps.absences.services import cancel_absence, request_absence
from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid")


@pytest.fixture
def ana(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="ana@example.com", password=PASSWORD, tenant=company, first_name="Ana"
        )


def con_justificante(company, person, dia=1):
    with tenant_context(company.id):
        return request_absence(
            employee=person,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 9, dia),
            end_date=date(2026, 9, dia),
            justification=SimpleUploadedFile(
                "citacion.pdf", b"%PDF-1.4 cita hospitalaria", "application/pdf"
            ),
        )


@pytest.mark.django_db
def test_retirar_la_solicitud_borra_su_justificante(
    company, ana, django_capture_on_commit_callbacks
):
    """Es el caso que lo motivó: se pide, se adjunta y se retira.

    El `capture` no es un adorno de la prueba: la limpieza va deliberadamente en
    `on_commit`, y dentro de una prueba nada confirma nunca. Sin él estaría
    comprobando que el fichero sigue ahí, que es lo contrario de lo que quiere.
    """
    absence = con_justificante(company, ana)
    ruta = absence.justification.name
    assert default_storage.exists(ruta)

    with django_capture_on_commit_callbacks(execute=True):
        cancel_absence(absence, cancelled_by=ana)

    assert not default_storage.exists(ruta)


@pytest.mark.django_db
def test_borrar_a_la_persona_se_lleva_sus_justificantes(
    company, ana, django_capture_on_commit_callbacks
):
    """Por cascada la fila desaparece igual, y el fichero se quedaba igual."""
    absence = con_justificante(company, ana)
    ruta = absence.justification.name
    assert default_storage.exists(ruta)

    with django_capture_on_commit_callbacks(execute=True), tenant_context(company.id):
        ana.absences.all().delete()

    assert not default_storage.exists(ruta)


@pytest.mark.django_db
def test_una_ausencia_sin_justificante_se_cancela_sin_ruido(company, ana):
    """La mayoría no llevan fichero. Cancelarlas no puede fallar por eso.

    Antes comprobaba además que la fila desaparecía. Desde la vuelta 92 se
    conserva marcada como cancelada ---cancelar la solicitud de otra persona está
    permitido, y una petición que se borra no deja saber que existió--- así que lo
    que aquí se defiende es lo otro: que no haya fichero no rompe nada.
    """
    with tenant_context(company.id):
        absence = request_absence(
            employee=ana,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 9, 10),
            end_date=date(2026, 9, 10),
        )

    cancel_absence(absence, cancelled_by=ana)

    with tenant_context(company.id):
        quedo = ana.absences.get(pk=absence.pk)
    assert quedo.status == AbsenceStatus.CANCELLED
    assert not quedo.justification


@pytest.mark.django_db
def test_borrar_en_bloque_tambien_se_los_lleva(company, ana, django_capture_on_commit_callbacks):
    """`QuerySet.delete()` no llama a `Model.delete()`, así que el borrado en
    masa se salta cualquier limpieza escrita en el modelo. Es la vía por la que
    entrarían una purga por retención o el borrado de una empresa."""
    primera = con_justificante(company, ana, dia=1)
    segunda = con_justificante(company, ana, dia=5)
    rutas = [primera.justification.name, segunda.justification.name]
    assert all(default_storage.exists(r) for r in rutas)

    with django_capture_on_commit_callbacks(execute=True), tenant_context(company.id):
        ana.absences.all().delete()

    assert not any(default_storage.exists(r) for r in rutas)


@pytest.mark.django_db
def test_el_justificante_que_se_sustituye_tambien_se_va(
    company, ana, tmp_path, settings, django_capture_on_commit_callbacks
):
    """Lo que faltaba: el fichero viejo cuando llega otro.

    Esta prueba resolvió el fichero que se queda al **borrar la fila**. Quedaba el
    otro camino y es el más frecuente ---sustituirlo--- porque Django asigna el
    nuevo y no toca el viejo: quien sube el justificante bueno después del equivocado
    dejaba el equivocado en el servidor para siempre, sin ninguna fila que lo
    apunte.

    Medido antes de arreglarlo, en la base de desarrollo: **4.391 huérfanos**
    frente a doce referenciados, unos mil por tanda. Todos justificantes, que es lo
    que el art. 9 llama dato sensible, y sin nada que sepa que existen no hay forma
    de atender una supresión (art. 17) ni de cumplir el plazo de conservación
    (art. 5.1.e).
    """
    settings.MEDIA_ROOT = str(tmp_path)
    with tenant_context(company.id):
        absence = request_absence(
            employee=ana,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 9, 20),
            end_date=date(2026, 9, 20),
            justification=SimpleUploadedFile("malo.pdf", b"%PDF-1.4\nmalo\n"),
        )
        equivocado = absence.justification.name
        assert default_storage.exists(equivocado)

        # El `capture`, por lo mismo que en la prueba de arriba: la limpieza va en
        # `on_commit` y dentro de una prueba nada confirma nunca.
        with django_capture_on_commit_callbacks(execute=True):
            absence.justification = SimpleUploadedFile("bueno.pdf", b"%PDF-1.4\nbueno\n")
            absence.save(update_fields=["justification"])
        bueno = absence.justification.name

    assert not default_storage.exists(equivocado), "el justificante sustituido se quedaba en disco"
    assert default_storage.exists(bueno), "y el nuevo tiene que estar"


@pytest.mark.django_db
def test_guardar_otra_cosa_no_se_lleva_el_justificante(company, ana, tmp_path, settings):
    """Lo que no puede romperse: solo se borra cuando el fichero **cambia**."""
    settings.MEDIA_ROOT = str(tmp_path)
    with tenant_context(company.id):
        absence = request_absence(
            employee=ana,
            company=company,
            absence_type=AbsenceType.PERSONAL,
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 21),
            justification=SimpleUploadedFile("citacion.pdf", b"%PDF-1.4\ncitacion\n"),
        )
        guardado = absence.justification.name

        absence.reason = "se corrige el motivo, no el fichero"
        absence.save(update_fields=["reason"])

    assert default_storage.exists(guardado), "un save de otro campo se llevó el justificante"
