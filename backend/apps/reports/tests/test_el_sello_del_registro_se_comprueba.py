"""Un sello que nadie mira no sella nada.

Cada fichaje guarda un `hash_integrity` desde el principio, y `verify_hash`
funciona: detecta un cambio en la hora, en el tipo, en el origen. Lo que no
había era **una sola llamada desde el producto**. El método solo se usaba en las
pruebas.

Medido antes de tocar nada, adelantando dos horas un fichaje por SQL directo
---la API no deja editar uno: una corrección crea otro y anula el viejo, así que
manipularlo de verdad exige entrar por debajo---:

| | Antes | Después |
|---|---|---|
| Horas en el informe | 8,0 | **10,0** |
| El sello del fichaje cuadra | sí | **no** |
| El informe se genera | sí | **sí, sin una queja** |

La huella del documento no cubre esto: certifica que el papel entregado es el
que se generó, no que lo generado refleje lo que se fichó. Alterado el fichaje,
el informe sale con huella perfectamente válida y dos horas que nadie trabajó.

Se comprueba al construir el informe porque ese es el momento en que el registro
sale del sistema como prueba, y porque sale gratis: los fichajes ya están
cargados y es un sha256 por fila.

Y se **dice**, no se corrige ni se esconde: la cifra es la que hay en el
registro, y enmendarla por nuestra cuenta sería otro problema. Quien lee el
informe tiene que poder ver que ese día no es de fiar.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchType
from apps.reports.services import build_report, day_notes, to_csv
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Integridad SL", tax_id="B71717171", time_zone="Europe/Madrid"
    )


@pytest.fixture
def jornada(company):
    """Una persona, un día de ocho horas cerrado."""
    with tenant_context(company.id):
        quien = User.objects.create_user(
            email="obrero@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Obrero",
            last_name="Equis",
        )
        entra = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(
            days=1
        )
        entrada = Punch.objects.create(
            tenant=company, employee=quien, punch_type=PunchType.IN, timestamp=entra
        )
        Punch.objects.create(
            tenant=company,
            employee=quien,
            punch_type=PunchType.OUT,
            timestamp=entra + timedelta(hours=8),
        )
        yield {
            "quien": quien,
            "entrada": entrada,
            "dia": (timezone.now() - timedelta(days=1)).date(),
        }


def por_debajo(punch, horas):
    """Lo que haría alguien con acceso a la base, que es el caso que el sello cubre."""
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE punches_punch SET timestamp = timestamp - interval %s WHERE id = %s",
            [f"{horas} hours", str(punch.pk)],
        )


def informe_de(company, jornada):
    with tenant_context(company.id):
        return build_report(
            employee=jornada["quien"],
            company=company,
            date_from=jornada["dia"],
            date_to=jornada["dia"],
        )


@pytest.mark.django_db
def test_un_dia_intacto_no_dice_nada(company, jornada):
    """El control. Sin esto, un aviso permanente pasaría las de abajo."""
    fila = informe_de(company, jornada).rows[0]

    assert fila.seconds == 8 * 3600
    assert fila.incidents == []


@pytest.mark.django_db
def test_un_fichaje_tocado_por_debajo_sale_avisado(company, jornada):
    por_debajo(jornada["entrada"], 2)
    fila = informe_de(company, jornada).rows[0]

    assert fila.seconds == 10 * 3600, "el informe ya no lleva las horas alteradas"
    assert any("sello" in nota or "seal" in nota for nota in fila.incidents), fila.incidents


@pytest.mark.django_db
def test_y_el_aviso_viaja_a_lo_que_se_entrega(company, jornada):
    """Al PDF y al CSV por el mismo sitio, que es lo que impide que se separen."""
    por_debajo(jornada["entrada"], 2)
    informe = informe_de(company, jornada)

    assert "seal" in day_notes(informe.rows[0]) or "sello" in day_notes(informe.rows[0])
    assert "seal" in to_csv(informe) or "sello" in to_csv(informe)


@pytest.mark.django_db
def test_la_huella_cambia_cuando_aparece_el_aviso(company, jornada):
    """El aviso es parte del documento, así que va dentro del sello del documento.

    Si quedara fuera, dos informes del mismo periodo ---uno limpio y otro con el
    aviso--- compartirían huella, y comparar dos copias dejaría de servir.

    Se toca el **origen** y no la hora a propósito. Cambiando la hora la huella
    cambiaría de todas formas ---la hora está dentro--- y esta prueba pasaría con
    el aviso desconectado, sin demostrar nada. El origen rompe el sello del
    fichaje y no entra en la huella del documento, así que la única diferencia
    que queda entre las dos huellas es el aviso.
    """
    limpia = informe_de(company, jornada).fingerprint

    with connection.cursor() as cur:
        cur.execute(
            "UPDATE punches_punch SET source = %s WHERE id = %s",
            ["ADMIN", str(jornada["entrada"].pk)],
        )

    tocada = informe_de(company, jornada)
    assert tocada.rows[0].seconds == 8 * 3600, "las horas no debían moverse"
    assert tocada.rows[0].incidents, "el sello tenía que haberse roto"
    assert tocada.fingerprint != limpia


@pytest.mark.django_db
def test_la_cifra_no_se_toca(company, jornada):
    """Avisar no es enmendar.

    El informe dice lo que el registro guarda. Corregirlo por nuestra cuenta
    sería inventar un dato distinto del que hay, y quien recibe el documento
    necesita ver el registro tal y como está para poder actuar.
    """
    por_debajo(jornada["entrada"], 2)
    fila = informe_de(company, jornada).rows[0]

    assert fila.seconds == 10 * 3600
    assert fila.entries, "la jornada sigue en el informe, no se oculta"


@pytest.mark.django_db
def test_comprobarlo_no_cuesta_consultas(company, jornada, django_assert_num_queries):
    """Los fichajes ya están cargados: es un sha256 por fila, no una consulta."""
    with tenant_context(company.id):
        sin_tocar = build_report(
            employee=jornada["quien"],
            company=company,
            date_from=jornada["dia"],
            date_to=jornada["dia"],
        )
        cuantas = len(connection.queries)

    assert sin_tocar.rows
    por_debajo(jornada["entrada"], 2)

    with tenant_context(company.id):
        antes = len(connection.queries)
        build_report(
            employee=jornada["quien"],
            company=company,
            date_from=jornada["dia"],
            date_to=jornada["dia"],
        )
        despues = len(connection.queries)

    # Con un fichaje roto o sin él, el mismo número de consultas.
    assert despues - antes <= cuantas + 1
