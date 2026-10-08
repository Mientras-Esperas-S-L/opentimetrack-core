"""Que un repetido se diga como un 400 con su motivo, y no como un 500.

La base ya impide los repetidos con sus `UniqueConstraint`, pero DRF solo
comprueba por su cuenta las que tienen todos sus campos en el serializador, y
casi todas llevan `tenant`, que no está en ninguno. Así que el repetido llegaba
hasta la base, saltaba un `IntegrityError` y la persona veía un error 500. Medido
el 08/10/2026 pulsando «Guardar» en todos los diálogos: departamento, centro,
turno, festivo y aplicación, al crear y al renombrar.

Se comprueban las restricciones **del propio modelo**, con el `validate` de
Django, que entiende también las condicionales (la de los festivos depende de si
hay centro). Así no hay una segunda lista de reglas que mantener al lado de la
de la base.
"""

from __future__ import annotations

import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class SinRepetidos:
    """Mezcla para un `ModelSerializer` cuyo modelo tenga `tenant`.

    `repetidos` dice, por nombre de restricción, en qué campo se cuenta el fallo
    y con qué palabras. Una restricción que no esté ahí se dice igual, sin campo
    y con un mensaje general: mejor eso que un 500.
    """

    repetidos: dict[str, tuple[str, str]] = {}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        modelo = self.Meta.model
        # Lo que quedaría guardado: lo que ya hay, con lo que llega encima.
        if self.instance is not None:
            candidato = copy.copy(self.instance)
        else:
            candidato = modelo()
            usuario = getattr(self.context.get("request"), "user", None)
            if getattr(usuario, "tenant_id", None) and hasattr(candidato, "tenant_id"):
                candidato.tenant_id = usuario.tenant_id
        campos = {f.name for f in modelo._meta.concrete_fields}
        for nombre, valor in attrs.items():
            if nombre in campos:
                setattr(candidato, nombre, valor)
        for restriccion in modelo._meta.constraints:
            if not isinstance(restriccion, UniqueConstraint):
                continue
            try:
                restriccion.validate(modelo, candidato)
            except DjangoValidationError:
                campo, mensaje = self.repetidos.get(
                    restriccion.name,
                    (
                        serializers.api_settings.NON_FIELD_ERRORS_KEY,
                        _("There is already one like this."),
                    ),
                )
                raise serializers.ValidationError({campo: [mensaje]}) from None
        return attrs
