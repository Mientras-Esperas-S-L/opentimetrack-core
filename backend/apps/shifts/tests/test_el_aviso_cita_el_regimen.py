"""Un aviso de cifra apartada dice bajo qué régimen trabaja la empresa.

La pantalla de ajustes avisa cuando una cifra se sale del suelo o del techo que
fija un artículo: poner el descanso entre jornadas en diez horas se contesta con
«10.0 está por debajo de las 12 que fija el Art. 34.3 ET».

Para casi cualquier empresa eso está bien dicho. Para una de transporte se lee
como una acusación, porque el RD 1561/1995 **aparta esa cifra en su sector**:
diez horas ahí pueden ser exactamente lo que toca. Desde la vuelta anterior la
empresa puede declarar su régimen, y lo que faltaba era que el aviso lo usara.

Tres decisiones que se ven mejor en las pruebas que en el código:

1. **El aviso no se calla.** El real decreto no quita el límite del art. 34.3,
   lo aparta en artículos concretos. Silenciarlo por tener régimen declarado
   sería decirle a la empresa que ahí no hay nada que comprobar.
2. **No se dice qué artículo.** Habría que mapear trece regímenes contra cada
   cifra, y una cita equivocada es peor que ninguna: se lee bien y señala a la
   ley que no es. El sitio para la cita exacta ya existe y es la ficha de
   convenio.
3. **Sin régimen declarado la frase no aparece**, que es el contraste de todo lo
   demás.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.tenants.rules import SpecialRegime, WorkingTimeRules
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
RUTA = "/api/working-time-rules/"


@pytest.fixture
def company(db):
    return Tenant.objects.create(
        name="Transportes SL", tax_id="B43434343", time_zone="Europe/Madrid", country="ES"
    )


@pytest.fixture
def admin(company):
    with tenant_context(company.id):
        yield User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=company,
            first_name="Quien",
            last_name="Manda",
            role=Role.ADMIN,
        )


def declara(company, regimen):
    with tenant_context(company.id):
        reglas = WorkingTimeRules.for_company(company)
        reglas.special_regime = regimen
        reglas.save(update_fields=["special_regime"])


def avisa(admin, **campos):
    cliente = APIClient()
    cliente.force_authenticate(admin)
    respuesta = cliente.patch(RUTA, campos, format="json")
    assert respuesta.status_code == 200, respuesta.data
    return respuesta.data["warnings"]


@pytest.mark.django_db
def test_con_regimen_declarado_el_aviso_lo_nombra(company, admin):
    """El caso que trae a esta prueba: transporte y un descanso de diez horas."""
    declara(company, SpecialRegime.ROAD_TRANSPORT)
    avisos = avisa(admin, daily_rest_hours=10)

    assert len(avisos) == 1, avisos
    mensaje = avisos[0]["message"]
    # El límite sigue citado: es de dónde sale la comparación.
    assert "34.3" in mensaje
    # Y ahora también el porqué.
    assert "1561/1995" in mensaje
    assert "carretera" in mensaje.lower() or "transport" in mensaje.lower()


@pytest.mark.django_db
def test_sin_regimen_declarado_no_se_dice_nada_del_sector(company, admin):
    """**El contraste.** Sin declararlo, la frase no aparece.

    Añadirla siempre sería peor que no añadirla: le estaría diciendo a una
    oficina que su descanso corto quizá lo ampare un real decreto de sectores
    que no es el suyo.
    """
    declara(company, SpecialRegime.NONE)
    avisos = avisa(admin, daily_rest_hours=10)

    assert len(avisos) == 1, avisos
    mensaje = avisos[0]["message"]
    assert "34.3" in mensaje, "el aviso del límite tiene que seguir saliendo"
    assert "1561/1995" not in mensaje


@pytest.mark.django_db
def test_el_aviso_no_se_calla_por_tener_regimen(company, admin):
    """Con régimen declarado sigue habiendo aviso, y por el mismo campo.

    Esta prueba parece la misma que la primera y comprueba otra cosa: que el
    número de avisos no baja. Si algún día alguien decide que en transporte no
    hace falta avisar del descanso, esto se pone rojo antes de que la decisión
    llegue a un cliente.
    """
    declara(company, SpecialRegime.ROAD_TRANSPORT)
    con = avisa(admin, daily_rest_hours=10)

    declara(company, SpecialRegime.NONE)
    sin = avisa(admin, daily_rest_hours=9)

    assert [a["field"] for a in con] == [a["field"] for a in sin] == ["daily_rest_hours"]


@pytest.mark.django_db
def test_una_cifra_dentro_del_limite_no_avisa_de_nada(company, admin):
    """El contraste de que los avisos salen del límite y no del régimen.

    Declarar un régimen no genera avisos por sí solo. Doce horas es exactamente
    lo que pide el art. 34.3, y ahí no hay nada que decir ni con sector ni sin
    él.
    """
    declara(company, SpecialRegime.ROAD_TRANSPORT)
    assert avisa(admin, daily_rest_hours=12) == []


@pytest.mark.django_db
def test_tambien_cuando_la_cifra_se_pasa_del_techo(company, admin):
    """Las dos ramas, la del suelo y la del techo.

    El primer parche solo tocó la del suelo, que era la del caso que tenía
    delante. Un techo con la mitad del arreglo se habría quedado callado sin que
    nadie lo notara: las dos ramas escriben mensajes distintos.
    """
    declara(company, SpecialRegime.FARMING)
    avisos = avisa(admin, weekly_hours=45)

    assert len(avisos) == 1, avisos
    assert "1561/1995" in avisos[0]["message"]


@pytest.mark.django_db
def test_los_trece_regimenes_tienen_nombre_que_mostrar(company, admin):
    """Ninguno se queda sin etiqueta, que saldría como una frase a medias.

    El nombre del régimen entra en el mensaje. Uno sin traducir o sin etiqueta
    daría «trabaja en régimen de , y el RD...», que es de las cosas que un
    cliente enseña en una reunión.

    El descanso va alternando entre diez y once horas a propósito: la pantalla
    avisa **solo de lo que acaba de cambiar** ---y hace bien, repetir en cada
    respuesta lo que la empresa decidió hace meses es ruido---, así que mandar
    dos veces el mismo diez no habría dado ningún aviso que mirar.
    """
    for i, regimen in enumerate(SpecialRegime):
        if not regimen.value:
            continue
        declara(company, regimen)
        avisos = avisa(admin, daily_rest_hours=10 + i % 2)
        assert avisos, f"{regimen.value}: ningún aviso que comprobar"
        mensaje = avisos[0]["message"]
        assert str(regimen.label) in mensaje, f"{regimen.value} no sale nombrado"
        assert "  " not in mensaje, f"{regimen.value} deja un hueco vacío"
