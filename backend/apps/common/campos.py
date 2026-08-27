"""Campos de serializador que aceptan lo que quiere decir lo que llega.

Por ahora uno: el decimal que no se pelea con los ceros de más.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import models
from rest_framework import serializers


class DecimalTolerante(serializers.DecimalField):
    """Un decimal que mira el **valor**, no cómo se escribió.

    `DecimalField` cuenta los decimales del `Decimal` tal como viene, no los
    significativos. Con `decimal_places=1` eso rechazaba `20.00` ---que es
    exactamente `20.0`--- con el mensaje «asegúrese de que no haya más de 1
    decimales», que además es cierto y no ayuda: tiene dos, y ninguno cuenta.

    Y lo hacía de forma asimétrica, que es lo que lo delata: `0020.0` pasaba y
    `20.00` no. Los ceros de la izquierda daban igual y los de la derecha no.

    Dos decimales es como formatea cualquiera que venga del mundo de las
    nóminas, así que una integración correcta se comía un 400 por escribir el
    mismo número de otra manera.

    Lo que **sí** se sigue rechazando es la precisión que no cabe: `20.55` no es
    `20.5`, y media hora es el grano con el que se pactan las jornadas. Se
    normaliza el valor y se valida lo que queda.
    """

    def to_internal_value(self, data):
        if isinstance(data, str | int | Decimal):
            try:
                numero = Decimal(str(data).strip())
            except InvalidOperation, ValueError:
                return super().to_internal_value(data)  # que se queje él, con su mensaje
            if numero.is_finite():
                # Entero: `normalize()` lo dejaría en notación exponencial
                # ---`Decimal('2E+1')`--- que es el mismo número escrito de una
                # tercera forma rara. Cuantizar es más claro.
                data = (
                    numero.quantize(Decimal(1))
                    if numero == numero.to_integral_value()
                    else numero.normalize()
                )
        return super().to_internal_value(data)


class DecimalesTolerantes:
    """Mixin para un `ModelSerializer`: sus decimales toleran los ceros de más.

    Va como mixin y no campo a campo para que sigan sacando `max_digits` y
    `decimal_places` del modelo. Declararlos a mano en cada serializador es lo
    que hace que un día dejen de coincidir con la columna.
    """

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.DecimalField: DecimalTolerante,
    }
