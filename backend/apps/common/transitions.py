"""Quedarse con una decisión, o llegar tarde. Nunca las dos cosas.

Toda decisión de este producto ---aprobar una ausencia, resolver una corrección,
autorizar unas horas extra--- es una transición de estado que solo puede ocurrir
una vez. Y todas se comprobaban igual: mirando el estado del objeto **que la
petición ya tenía cargado en memoria**.

Eso no protege de nada cuando dos responsables pulsan a la vez. Cada petición
cargó su copia antes de que ninguna escribiera, así que las dos ven `PENDING`,
las dos pasan la comprobación y las dos escriben. Probado sobre una ausencia: la
aprueba una, la rechaza la otra, y la fila queda en `REJECTED` con
`approved_by` puesto ---un registro que se contradice a sí mismo--- más una
entrada de aprobación y otra de rechazo en el rastro para la misma solicitud.

En un producto cuyo valor es que su registro se sostenga delante de una
inspección, eso no es un detalle de concurrencia: es el registro diciendo dos
cosas.

## Cómo lo arregla

`SELECT ... FOR UPDATE` sobre la fila, dentro de la transacción de la petición
---`ATOMIC_REQUESTS` está activado, así que el bloqueo dura hasta que termina---.
La segunda petición se queda esperando en el `select`, no en el `if`; cuando la
primera confirma, la segunda lee el estado **ya escrito** y se encuentra con que
llegó tarde.

Devuelve la fila recién leída y hay que trabajar con ella, no con la que traía
quien llama: la de antes está desactualizada por definición, que es justo el
problema.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError


def claim(
    modelo, pk, *, desde, code: str = "already_resolved", message=None, campo: str = "status"
):
    """Bloquea la fila y exige que siga en el estado de partida.

    `desde` admite un valor o varios: hay transiciones que salen de más de un
    sitio ---una corrección se puede aplicar tanto desde «pendiente» como desde
    «esperando a la persona»--- y exigir uno solo las rompería.
    """
    esperados = {desde} if isinstance(desde, str) else set(desde)

    fila = modelo.objects.select_for_update().get(pk=pk)
    if getattr(fila, campo) not in esperados:
        raise BusinessRuleError(
            code=code,
            message=message or _("This request has already been resolved."),
        )
    return fila
