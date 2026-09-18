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
    #: El huso en el que esa persona vivió este instante: el de su centro de
    #: trabajo, o el de la empresa si no tiene.
    #:
    #: Va en el fichaje y no solo en la ficha de la persona porque un listado
    #: mezcla gente de varias delegaciones, y una hora sin su huso no dice a qué
    #: hora se fichó. Con una empresa en Madrid y una delegación en Las Palmas
    #: son sesenta minutos, y sesenta minutos cambian el día de un fichaje de
    #: las 23:30. Quien lee esto por la API ---una pantalla o un conector---
    #: no tiene otra forma de saberlo.
    time_zone = serializers.SerializerMethodField()
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    was_deferred = serializers.BooleanField(read_only=True)

    class Meta:
        model = Punch
        fields = [
            "id",
            "employee",
            "employee_name",
            "time_zone",
            "punch_type",
            "interval",
            "work_mode",
            "hours_nature",
            "overtime_settlement",
            "force_majeure",
            "flexibility_measure",
            "timestamp",
            # Las dos horas del fichaje hecho sin cobertura. Van juntas a propósito:
            # una sola no dice nada y el par es la prueba.
            "declared_at",
            "received_at",
            "was_deferred",
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

    def get_time_zone(self, obj) -> str:
        # El que se guardó con el fichaje. El de la persona solo para los
        # anteriores a que se guardara: leer una hora vieja con el huso de hoy
        # convierte un cambio de organización en un cambio del registro.
        return obj.time_zone or str(obj.employee.tzinfo)


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


#: Lo que hay que escribir para fichar por la puerta que no es la normal. Corto, pero
#: no vacío: la excepción se justifica, y ese texto llega al informe de Inspección.
EXCEPTION_REASON_MIN = 10


class PunchWriteSerializer(serializers.Serializer):
    """What a client is allowed to send.

    Note what is missing: the type. Inferring it here is what keeps a client from
    writing two openings in a row and calling the result a working day.

    The time is ours too, with the one exception this field carries: `declared_at`,
    for the punch that was made where there was no signal. It is not accepted on
    trust --- it has a window, and both times end up stored.
    """

    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    declared_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text=(
            "When the device says the punch happened, for one made offline and sent later. "
            "Leave it out for an ordinary punch: without it the server's own clock is used, "
            "and that is the normal case. Accepted only inside the company's grace period; "
            "the arrival time is recorded alongside it either way."
        ),
    )
    source = serializers.CharField(max_length=16, required=False, allow_blank=True)

    # How the punch was triggered, and its proof. The default is a person
    # pressing the button; a geofence or a network sends the real signal and its
    # evidence instead. Never the time --- that is still the server's.
    trigger = serializers.ChoiceField(
        choices=PunchTrigger.choices, required=False, default=PunchTrigger.MANUAL
    )
    evidence = serializers.JSONField(required=False, default=dict, validators=[validate_evidence])
    #: Solo se mira cuando la empresa dice que la puerta normal es la aplicación
    #: integrada. Ver `Tenant.punch_entry` y apps/punches/views.py.
    exception_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        help_text=(
            "Why you are clocking in here rather than through the usual application. "
            "Required when the company expects punches to come from an application."
        ),
    )

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
