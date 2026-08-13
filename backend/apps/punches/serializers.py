"""Serializers for clock events."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.punches.models import (
    FlexibilityMeasure,
    HoursNature,
    OvertimeSettlement,
    Punch,
    PunchInterval,
    PunchTrigger,
    WorkMode,
)


class PunchSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = Punch
        fields = [
            "id",
            "employee",
            "employee_name",
            "punch_type",
            "interval",
            "work_mode",
            "hours_nature",
            "overtime_settlement",
            "force_majeure",
            "flexibility_measure",
            "timestamp",
            "source",
            "source_display",
            "source_application",
            "trigger",
            "recorded_by",
            "device_id",
            "hash_integrity",
            "is_active",
            "voided_at",
        ]
        read_only_fields = fields


#: Lo que cabe en la evidencia de un fichaje, en caracteres del JSON serializado.
#:
#: El campo lo escribe una integración desde fuera y no tenía tope. Con seis mil
#: peticiones por hora de cupo, un conector con una fuga ---o uno honesto que
#: vuelca la traza GPS entera en cada fichaje--- llena la base sin hacer nada
#: prohibido, y esos fichajes viven cuatro años y salen en cada informe.
#:
#: Cuatro mil caracteres son de sobra para lo que el campo existe: unas
#: coordenadas, el nombre de una red, el identificador de un evento externo.
#: Quien necesite adjuntar más está guardando un fichero en el sitio equivocado.
EVIDENCE_MAX_CHARS = 4096


def validate_evidence(value):
    """Rechaza una evidencia desproporcionada, diciendo cuánto cabe."""
    import json

    if not value:
        return value
    tamaño = len(json.dumps(value, ensure_ascii=False))
    if tamaño > EVIDENCE_MAX_CHARS:
        raise serializers.ValidationError(
            _("The evidence is too large: %(size)s characters, and the limit is %(max)s.")
            % {"size": tamaño, "max": EVIDENCE_MAX_CHARS}
        )
    return value


class PunchWriteSerializer(serializers.Serializer):
    """What a client is allowed to send.

    Note what is missing: neither the timestamp nor the type. Accepting either
    would hand the client control over the legal record.
    """

    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    source = serializers.CharField(max_length=16, required=False, allow_blank=True)

    # How the punch was triggered, and its proof. The default is a person
    # pressing the button; a geofence or a network sends the real signal and its
    # evidence instead. Never the time --- that is still the server's.
    trigger = serializers.ChoiceField(
        choices=PunchTrigger.choices, required=False, default=PunchTrigger.MANUAL
    )
    evidence = serializers.JSONField(required=False, default=dict, validators=[validate_evidence])

    # Art. 3 of the pending decree. The client says *what kind* of span this is
    # and under what arrangement --- facts only the person can supply --- but
    # still never the time nor whether it opens or closes.
    interval = serializers.ChoiceField(
        choices=PunchInterval.choices, required=False, default=PunchInterval.WORK
    )
    work_mode = serializers.ChoiceField(
        choices=WorkMode.choices, required=False, allow_blank=True, default=""
    )
    hours_nature = serializers.ChoiceField(
        choices=HoursNature.choices, required=False, default=HoursNature.ORDINARY
    )
    overtime_settlement = serializers.ChoiceField(
        choices=OvertimeSettlement.choices, required=False, allow_blank=True, default=""
    )
    force_majeure = serializers.BooleanField(required=False, default=False)
    flexibility_measure = serializers.ChoiceField(
        choices=FlexibilityMeasure.choices, required=False, allow_blank=True, default=""
    )
