"""El backfill que activa la reducción en la lactancia ya copiada.

El catálogo se copia una vez y después **la copia de la empresa es la verdad**:
`seed_leave_types` añade lo que falta y no toca nunca lo que hay. Es la decisión
correcta ---lo que una empresa tiene es lo que su convenio dice--- y significa que
corregir un dato del marco no llega solo a quien ya lo copió.

**La razón por la que este comando existe pese a ese principio:** ninguna empresa
decidió que la lactancia no pudiera reducir la jornada. Lo heredaron de un dato
nuestro que estaba mal, y activar una posibilidad no cambia ninguna ausencia ya
registrada.

**Y la razón por la que estas pruebas existen:** la primera versión del comando
usaba `LeaveType.objects`, que filtra por el contexto de empresa. Un comando
corre sin contexto, así que contaba **cero filas**, decía «0 actualizadas ·
comprobado» y se quedaba tan ancha. Un backfill que mira donde no es se ve
exactamente igual que uno que no tenía nada que hacer, y eso es lo peor que puede
hacer un backfill: dar el parte de que todo está bien.
"""

from __future__ import annotations

import pytest
from django.core.management import CommandError, call_command

from apps.absences.catalogue import seed_leave_types
from apps.absences.models import LeaveType
from apps.common.models import tenant_context
from apps.tenants.models import Tenant

LACTANCIA = "es.breastfeeding"


def empresa_con_catalogo(nombre, cif):
    empresa = Tenant.objects.create(
        name=nombre, tax_id=cif, time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        seed_leave_types(empresa)
    return empresa


def como_antes(empresa):
    """Deja su lactancia como la copió el catálogo viejo."""
    LeaveType.objects_all_tenants.filter(tenant=empresa, code=LACTANCIA).update(
        can_reduce_the_day=False
    )


def puede_reducir(empresa):
    return LeaveType.objects_all_tenants.get(tenant=empresa, code=LACTANCIA).can_reduce_the_day


@pytest.mark.django_db
def test_lo_arregla_en_todas_las_empresas(capsys):
    """**Todas, y sin contexto de empresa.**

    Aquí es donde se cazó el fallo: con el manager que filtra por contexto, un
    comando ve cero filas y no toca nada en ninguna parte.
    """
    una = empresa_con_catalogo("Una SL", "B11111111")
    otra = empresa_con_catalogo("Otra SL", "B22222222")
    como_antes(una)
    como_antes(otra)

    call_command("backfill_breastfeeding_reduction")

    assert puede_reducir(una) is True
    assert puede_reducir(otra) is True
    assert "2 actualizadas" in capsys.readouterr().out


@pytest.mark.django_db
def test_sin_catalogo_se_niega_en_vez_de_decir_que_no_habia_nada(capsys):
    """**La prueba que este fichero existe para tener.**

    Sin ninguna fila de lactancia, «nada que hacer» y «no estoy viendo el
    catálogo» dan exactamente la misma salida tranquilizadora. Se distinguen a la
    fuerza: si no hay ni una fila, el comando falla.
    """
    Tenant.objects.create(
        name="Sin catálogo", tax_id="B33333333", time_zone="Europe/Madrid", country="ES"
    )
    with pytest.raises(CommandError, match="Ni una fila"):
        call_command("backfill_breastfeeding_reduction")


@pytest.mark.django_db
def test_no_pisa_lo_que_una_empresa_puso_a_mano(capsys):
    """Solo toca lo que sigue como se copió.

    Correr esto dos veces no puede tener efectos distintos, y una empresa que ya
    lo tenía puesto no tiene por qué enterarse.
    """
    una = empresa_con_catalogo("Una SL", "B11111111")
    como_antes(una)

    call_command("backfill_breastfeeding_reduction")
    call_command("backfill_breastfeeding_reduction")

    assert puede_reducir(una) is True
    assert "0 actualizadas" in capsys.readouterr().out


@pytest.mark.django_db
def test_el_ensayo_no_toca_nada(capsys):
    """`--dry-run` cuenta y se va."""
    una = empresa_con_catalogo("Una SL", "B11111111")
    como_antes(una)

    call_command("backfill_breastfeeding_reduction", "--dry-run")

    assert puede_reducir(una) is False
    assert "1 de lactancia sin poder reducir" in capsys.readouterr().out
