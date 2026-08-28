"""Cada aviso del cuadrante cita un artículo, o consta por qué no lo cita.

`shifts/services.py` lo dice de sí mismo: «`basis` no es decoración: un aviso que
nadie puede rastrear a un artículo es» --- y ahí se apoya todo el enfoque del
producto, que avisa en vez de impedir. Un aviso sin base es una regañina.

`finding_citation` devuelve `Citation(basis="")` para un código que no conoce, en
silencio. El marco español tiene tres vacíos y **los tres están comentados**
---«sin cita a propósito», «es un error de planificación»---. El de la directiva,
que es lo que usa cualquier país no reconocido, tenía el mapa **entero vacío**:
los diecinueve avisos salían sin base, y los artículos estaban escritos diez
líneas más arriba, en las citas de las cifras.

Esta prueba no comprueba una lista de siete: comprueba que **de cada aviso hay
una decisión tomada**. Añadir uno nuevo al cuadrante obliga a citarlo o a
declararlo aquí con su motivo, que es lo que evita que esto vuelva a pasar
callando.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.legal import DIRECTIVE, FRAMEWORKS

#: Avisos de entrada mal formada, no de derecho laboral: no piden artículo.
DE_ENTRADA = {"no_days", "unknown_employee", "unknown_pattern"}

#: Sin cita **a propósito**, con el motivo. Si añades un aviso y lo pones aquí,
#: escribe por qué: es la diferencia entre una decisión y un olvido.
SIN_CITA = {
    "ES": {
        "no_agreed_weekly_hours": "falta el dato, no se incumple nada",
        "outside_the_contract": "error de planificación",
        "rostered_on_leave": "error de planificación, el más corriente que hay",
    },
    "": {
        "short_roster_notice": "la distribución irregular con preaviso es nacional",
        "over_contracted_hours": "horas complementarias, que la directiva no conoce",
        "worked_over_the_contract": "lo mismo, sobre lo fichado",
        "complementary_hours_cap": "el tope solo se comprueba donde el marco las define",
        "reduction_outside_the_right": "la horquilla de un octavo a la mitad es del ET",
        "remote_work_without_agreement": "la Ley 10/2021 es española",
        "training_hours_over_the_cap": "el tope 65/85 es del ET",
        "adaptation_answer_overdue": "el plazo de quince días es del ET",
        "partial_retirement_out_of_range": "la horquilla del 25 al 50 es del ET",
        "relief_hours_below_the_reduction": "el contrato de relevo es del ET",
        "relief_without_partial_retirement": "el contrato de relevo es del ET",
        "training_kind_not_stated": "los dos formativos son del ET",
        "remote_agreement_signed_late": "la Ley 10/2021 es española",
        "consecutive_night_weeks": "adición nacional del ET",
        "changeover_rest_owed": "adición del RD español de jornadas especiales",
        "minor_over_daily_limit": "lo regula la Directiva 94/33/CE, no esta",
        "minor_break_owed": "lo regula la Directiva 94/33/CE, no esta",
        "minor_night_work": "lo regula la Directiva 94/33/CE, no esta",
        "rostered_on_a_holiday": "los festivos los fija cada país",
        "no_agreed_weekly_hours": "falta el dato, no se incumple nada",
        "outside_the_contract": "error de planificación",
        "outside_the_season": "el fijo discontinuo es una figura del ET, no de la directiva",
        "rostered_on_leave": "error de planificación",
    },
}

MARCOS = [("ES", FRAMEWORKS["ES"]), ("", DIRECTIVE)]


def _codigos_del_cuadrante() -> set[str]:
    """Los `code=` que emite el repaso, leídos de su propio fichero.

    De la fuente y no de una lista escrita aquí: una lista se queda corta el día
    que alguien añade un aviso, que es exactamente el día que importa.
    """
    fuente = (Path(__file__).resolve().parents[2] / "shifts" / "services.py").read_text()
    return set(re.findall(r'code="([a-z_]+)"', fuente)) - DE_ENTRADA


def test_hay_avisos_que_leer():
    """El control: si la extracción se rompe, todo lo demás pasaría vacío."""
    codigos = _codigos_del_cuadrante()
    assert len(codigos) > 10, codigos
    assert "short_daily_rest" in codigos


@pytest.mark.parametrize(("pais", "marco"), MARCOS)
def test_de_cada_aviso_hay_una_decision(pais, marco):
    mudos = [
        codigo
        for codigo in sorted(_codigos_del_cuadrante())
        if not marco.finding_citation(codigo).basis and codigo not in SIN_CITA[pais]
    ]

    assert not mudos, (
        f"en «{marco.name}» estos avisos salen sin artículo y sin motivo escrito: "
        f"{mudos}. O se citan, o se declaran en SIN_CITA diciendo por qué"
    )


@pytest.mark.parametrize(("pais", "marco"), MARCOS)
def test_y_lo_declarado_sin_cita_sigue_sin_ella(pais, marco):
    """El contraste. Rellenar por rellenar es peor que no citar: apuntar a un
    artículo que no dice lo que el aviso dice es lo que un inspector desmonta."""
    for codigo, motivo in SIN_CITA[pais].items():
        assert not marco.finding_citation(codigo).basis, (
            f"«{codigo}» tiene cita en «{marco.name}» y aquí consta que no debía: {motivo}"
        )


def test_la_directiva_cita_lo_que_de_verdad_regula():
    """Y con el artículo correcto: los suelos de la 2003/88 están en sus propias
    citas de cifras, así que el aviso y la cifra tienen que apuntar al mismo."""
    esperado = {
        "short_daily_rest": "Art. 3",
        "short_weekly_rest": "Art. 5",
        "break_owed": "Art. 4",
        "weekly_hours_exceeded": "Art. 6.b",
        "worked_over_the_maximum": "Art. 6.b",
        "looks_like_night_work": "Art. 2.4",
        "night_worker_average": "Art. 8.a",
    }
    for codigo, articulo in esperado.items():
        base = DIRECTIVE.finding_citation(codigo).basis
        assert base.startswith(articulo), f"{codigo}: «{base}» no empieza por «{articulo}»"
        assert "2003/88" in base, f"{codigo}: «{base}» no dice de qué norma es"
