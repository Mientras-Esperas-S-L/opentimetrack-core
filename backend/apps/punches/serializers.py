"""Serializers for clock events."""

from __future__ import annotations

from rest_framework import serializers

from apps.punches.models import (
    FlexibilityMeasure,
    HoursNature,
    OvertimeSettlement,
    Punch,
    PunchInterval,
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
            "recorded_by",
            "device_id",
            "hash_integrity",
            "is_active",
            "voided_at",
        ]
        read_only_fields = fields


class PunchWriteSerializer(serializers.Serializer):
    """What a client is allowed to send.

    Note what is missing: neither the timestamp nor the type. Accepting either
    would hand the client control over the legal record.
    """

    device_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    source = serializers.CharField(max_length=16, required=False, allow_blank=True)

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
