"""Serializers for clock events."""

from __future__ import annotations

from rest_framework import serializers

from apps.punches.models import Punch


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
