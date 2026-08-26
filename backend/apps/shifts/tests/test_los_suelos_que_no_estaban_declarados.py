"""El aviso existía y le faltaban los suelos.

La vuelta 77 hizo que la API avise cuando una regla se sale del límite que fija
un artículo. Ese aviso lee `floor` y `ceiling` del marco legal, y de los catorce
campos con cita **solo cuatro los tenían declarados**: los otros diez pasaban sin
que nadie dijera nada.

Y no era información que faltase averiguar: la nota de cada cita **ya la
explica** con todas las letras. «Quince minutos cuando la jornada continuada
excede de seis horas.» «Hasta el 30 %, y el convenio puede subirlo al 60 %.»
«Cinco días de preaviso.» «Cuatro años como mínimo.» El dato estaba escrito en
prosa al lado del campo que debía llevarlo como número.

Lo que **no** se declara, y por qué:

- `annual_leave_days`: el mínimo del art. 38.1 son treinta días **naturales**, que
  en jornada de cinco días son veintidós laborables. La unidad depende de cómo lo
  lleve la empresa, así que un suelo de treinta avisaría en falso a quien lo
  tenga en laborables --- y avisar en falso es la forma de que nadie lea los avisos.
- `max_open_hours` y las tolerancias de entrada y salida: no hay artículo detrás.
  Son decisiones de la empresa sobre su propio funcionamiento.
- `correction_consent_days`: el art. 4.b **no fija plazo**, y declararle un suelo
  sería atribuirle un número que no dice. Lleva su propio aviso, abajo.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Con reglas", tax_id="B13131313", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="admin@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Admin",
            last_name="Equis",
            role=Role.ADMIN,
        )


def cambia(admin, **cuerpo):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(admin).access_token)
    )
    return client.patch("/api/working-time-rules/", cuerpo, format="json")


@pytest.mark.parametrize(
    ("campo", "valor", "articulo", "en_el_mensaje"),
    [
        # Quince minutos, art. 34.4.
        ("break_minutes", 0, "Art. 34.4 ET", "15"),
        # Y desde seis horas: pedirlo más tarde deja sin descanso a quien la ley
        # se lo da.
        ("break_after_hours", 24, "Art. 34.4 ET", "6"),
        # El 60 y no el 30: por encima del 30 hace falta convenio, y el producto
        # no puede saber si lo hay.
        ("complementary_hours_share", 95, "Art. 12.5.c ET", "60"),
        ("roster_notice_days", 0, "Art. 34.2 ET", "5"),
    ],
)
@pytest.mark.django_db
def test_cada_suelo_avisa_con_su_articulo(company, admin, campo, valor, articulo, en_el_mensaje):
    respuesta = cambia(admin, **{campo: valor})

    assert respuesta.status_code == 200, "se avisa, no se impide"
    avisos = respuesta.data["warnings"]
    assert [a["field"] for a in avisos] == [campo], avisos
    assert avisos[0]["basis"] == articulo
    assert en_el_mensaje in avisos[0]["message"], avisos[0]["message"]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("break_minutes", 30),
        ("break_after_hours", 4),
        ("complementary_hours_share", 45),
        ("roster_notice_days", 15),
    ],
)
@pytest.mark.django_db
def test_dentro_de_la_ley_no_se_dice_nada(company, admin, campo, valor):
    """Los controles. Un aviso que sale siempre no lo lee nadie."""
    respuesta = cambia(admin, **{campo: valor})

    assert respuesta.status_code == 200
    assert respuesta.data["warnings"] == []


@pytest.mark.django_db
def test_un_plazo_de_cero_dias_es_no_pedir_consentimiento(company, admin):
    """El art. 4.b no fija plazo, y el cero no es un plazo corto: es ninguno.

    La empresa propone y aplica en el mismo segundo, sin dar ocasión de aceptar
    ni de discrepar. Pedir el consentimiento y no esperarlo es no pedirlo.
    """
    respuesta = cambia(admin, correction_consent_days=0)

    assert respuesta.status_code == 200
    avisos = respuesta.data["warnings"]
    assert [a["field"] for a in avisos] == ["correction_consent_days"]
    assert "4.b" in avisos[0]["basis"]
    # Sin buscar palabras del mensaje: está traducido, y una aserción sobre el
    # texto inglés se rompe en cuanto se compilan los catálogos ---que es lo que
    # pasó al escribir esto---. Lo que importa es que hay un aviso, de qué campo
    # y con qué artículo.
    assert avisos[0]["message"], "el aviso no dice nada"


@pytest.mark.django_db
def test_un_plazo_normal_no_avisa(company, admin):
    assert cambia(admin, correction_consent_days=7).data["warnings"] == []


@pytest.mark.django_db
def test_las_vacaciones_no_llevan_suelo_a_proposito(company, admin):
    """Porque la unidad depende de la empresa, y un aviso falso vale menos que ninguno.

    Treinta días naturales son veintidós laborables. Con un suelo de treinta,
    quien lo lleve en laborables recibiría un aviso cada vez que toca el campo,
    diciéndole que incumple algo que cumple.
    """
    from apps.legal import for_company

    cita = for_company(company).citations["annual_leave_days"]

    assert cita.floor is None
    assert "naturales" in cita.note, "la nota tiene que explicar la unidad"


@pytest.mark.django_db
def test_la_conservacion_se_rechaza_en_su_endpoint(company, admin):
    """Ahí no se avisa: se impide, y con razón.

    El art. 34.9 son cuatro años y no admite pacto a la baja, así que el suelo
    va como validación y no como advertencia. Se prueba aquí para que quede
    dicho por qué este campo no aparece entre los de arriba.
    """
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(admin).access_token)
    )

    respuesta = client.patch("/api/company/", {"record_retention_years": 1}, format="json")

    assert respuesta.status_code == 400
    assert "34.9" in str(respuesta.data)
    company.refresh_from_db()
    assert company.record_retention_years == 4
