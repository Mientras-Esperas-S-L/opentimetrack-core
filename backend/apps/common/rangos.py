"""Cómo se pide un periodo, y qué pasa si se pide con otro nombre.

El mismo concepto se llama distinto en dos sitios de esta API: el periodo es
`date_from`/`date_to` en los informes y en el rastro, y `from`/`to` en las horas
extra. Quien automatiza una descarga acierta en uno y falla en el otro.

Y el fallo era **silencioso**, que es lo que lo hace grave: los parámetros
desconocidos se ignoran, así que pedir un año con `from`/`to` devolvía 200 con el
periodo por defecto ---los últimos treinta días--- sin decir nada. El documento
lleva su periodo escrito dentro, pero quien lo genera desde un guion no lo lee, y
lo que se pone a disposición de la Inspección es el registro del periodo que se
pidió (art. 34.9), no de otro.

Se contesta 400 con el nombre bueno. Aceptarlos como alias sería más cómodo y
dejaría dos nombres vivos para siempre.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

#: El nombre equivocado más probable, y el bueno. Son los que usa de verdad otro
#: endpoint de este mismo producto, así que no es un despiste hipotético.
ALIAS_DEL_PERIODO = {"from": "date_from", "to": "date_to"}


def refuse_wrong_period_names(params) -> None:
    """Rechaza `from`/`to` en vez de contestar con un periodo que no se pidió."""
    equivocados = {
        malo: bueno
        for malo, bueno in ALIAS_DEL_PERIODO.items()
        if malo in params and bueno not in params
    }
    if not equivocados:
        return

    raise ValidationError(
        {
            malo: _(
                "The period is asked for as «%(good)s» here. Written like this it "
                "would be ignored, and you would get the default period instead of "
                "the one you asked for."
            )
            % {"good": bueno}
            for malo, bueno in equivocados.items()
        }
    )
