"""Texto que se lee igual que se guardó.

Unicode trae caracteres que no se ven y cambian lo que se lee. El más claro es
`U+202E`, RIGHT-TO-LEFT OVERRIDE: invierte todo lo que va detrás, así que
«Fiché a las 8‮00:41 sal y 00:9 a» **está guardado tal cual** y en pantalla
se lee «Fiché a las 8 a 9:00 y salí 14:00». Quien aprueba una corrección lee una
cosa y en el registro queda otra.

Eso importa aquí más que en otros productos. El art. 4.b del real decreto
pendiente pide que la persona y la empresa acuerden el cambio de un asiento, y el
acuerdo se da leyendo el motivo; su último inciso obliga a reflejar la
discrepancia de quien no está de acuerdo. Un texto que se lee distinto de como
está guardado rompe las dos cosas a la vez.

**Se rechaza en vez de limpiarse**, y es una decisión, no una comodidad. Limpiar
significaría editar lo que alguien escribió, y uno de los campos que pasa por
aquí es justamente la discrepancia que un trabajador hace constar. Quitarle
caracteres a eso ---aunque sean invisibles--- es corregir su declaración. Se
avisa y lo arregla quien lo escribió.

El mensaje llega como 400 porque `api_exception_handler` traduce las
`ValidationError` de modelo. Antes de eso salía un 500, que es como estuvo la
regla de «parte de un día es un día» hasta la vuelta 85.
"""

from __future__ import annotations

import unicodedata

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#: Los que sí tienen sentido en un texto escrito por una persona. El salto de
#: línea se queda: una observación de varias líneas es normal, y no engaña a
#: nadie sobre lo que dice.
PERMITIDOS = {"\n", "\r", "\t"}


def caracteres_que_enganan(texto: str) -> list[str]:
    """Los que no se ven y cambian lo que se lee, con su nombre Unicode.

    Dos categorías, y las dos por el mismo motivo:

    - **Cf**, «format»: las marcas bidireccionales (`U+202A`-`U+202E`,
      `U+2066`-`U+2069`), el espacio de ancho cero y la marca de orden de bytes.
      Ninguna dibuja nada; algunas reordenan lo que hay alrededor.
    - **Cc**, «control»: restos de copiar y pegar que en una tabla o un CSV
      pueden partir una fila. Salvo el salto de línea y el tabulador, que sí se
      usan.
    """
    return [c for c in texto if c not in PERMITIDOS and unicodedata.category(c) in {"Cf", "Cc"}]


def validate_texto_legible(valor: str) -> None:
    """Rechaza un texto que en pantalla no dice lo que tiene guardado."""
    if not valor:
        return

    culpables = caracteres_que_enganan(str(valor))
    if not culpables:
        return

    # Por su nombre y su número, porque son invisibles: decir «hay un carácter
    # raro» sobre un texto donde no se ve nada raro no ayuda a arreglarlo.
    nombres = []
    for c in dict.fromkeys(culpables):
        nombre = unicodedata.name(c, None) or _("unnamed control character")
        nombres.append(f"U+{ord(c):04X} ({nombre})")

    raise ValidationError(
        _(
            "This text contains characters that do not show up but change how it "
            "reads: %(chars)s. Delete them and write it again --- what is filed has "
            "to say the same as what is on screen."
        )
        % {"chars": ", ".join(nombres)},
        code="texto_enganoso",
    )
