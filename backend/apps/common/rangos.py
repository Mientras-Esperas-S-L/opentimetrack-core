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

from datetime import date

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


def refuse_inverted_range(params) -> None:
    """Rechaza un periodo que acaba antes de empezar, en vez de contestar cero.

    No existe ninguna consulta legítima que vaya del 26 al 1: es siempre un dedo
    equivocado o un guion que arma las fechas al revés. Y devolver **cero filas
    sin decir nada** es la peor de las respuestas posibles, porque se lee como
    «no hubo actividad en ese periodo» ---en el rastro de auditoría, exactamente
    la conclusión contraria a la verdadera---.

    El producto ya rechazaba esto en el informe del art. 34.9 y en el cuadrante,
    cada uno por su cuenta y con este mismo mensaje. Faltaba en el filtro que
    comparten los listados de fichajes y del rastro, que es donde más barato es
    creerse el cero.

    Las fechas mal escritas no se tocan aquí: de eso ya se queja el propio
    `DateFilter`, y adelantarse solo cambiaría un mensaje bueno por otro.
    """
    desde, hasta = params.get("date_from"), params.get("date_to")
    if not desde or not hasta:
        return
    try:
        if date.fromisoformat(str(desde)) <= date.fromisoformat(str(hasta)):
            return
    except ValueError:
        return

    raise ValidationError(
        {"date_to": _("The end date cannot precede the start date.")},
        code="invalid",
    )


def refuse_unknown_params(params, conocidos) -> None:
    """Rechaza un parámetro que no existe, en los documentos que se entregan.

    Los desconocidos se ignoran, y en un listado eso es una molestia. En el
    informe del art. 34.9 es otra cosa: quien pide

        ?employe=<id de otra persona>       (una letra menos)

    recibe **200 y el registro de quien pregunta**, con su nombre dentro y su
    apellido en el nombre del fichero. Medido: `employe`, `employee_id` y `user`
    devolvían los tres el informe de quien llamaba en vez del pedido, y
    `date_form` o `dateto` devolvían el periodo por defecto. Un guion que
    descargue la plantilla entera con la errata genera una carpeta de documentos
    que no son de quien dicen ser.

    Es el mismo razonamiento que `refuse_wrong_period_names`, que se escribió
    para `from`/`to` y se quedó en esos dos nombres: «lo que se pone a
    disposición de la Inspección es el registro que se pidió, no otro».

    La lista es blanca y explícita, y solo se aplica aquí. En un listado
    corriente rechazar todo lo desconocido rompería a quien añade un parámetro
    inocuo para saltarse una caché; en un documento probatorio, un 400 es mejor
    respuesta que el registro de otra persona.
    """
    desconocidos = sorted(k for k in params if k not in conocidos)
    if not desconocidos:
        return

    validos = ", ".join(sorted(conocidos))
    raise ValidationError(
        {
            k: _(
                "«%(bad)s» is not read here, so asking with it would quietly give you "
                "a different document. This endpoint reads: %(good)s."
            )
            % {"bad": k, "good": validos}
            for k in desconocidos
        }
    )
