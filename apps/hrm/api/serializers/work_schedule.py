from rest_framework import serializers

from apps.hrm.models import WorkSchedule


class WorkScheduleSerializer(serializers.ModelSerializer):
    """Serializer for WorkSchedule model."""

    morning_time = serializers.ReadOnlyField()
    noon_time = serializers.ReadOnlyField()
    afternoon_time = serializers.ReadOnlyField()

    class Meta:
        model = WorkSchedule
        fields = [
            "id",
            "weekday",
            "morning_time",
            "noon_time",
            "afternoon_time",
            "allowed_late_minutes",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "morning_time",
            "noon_time",
            "afternoon_time",
            "created_at",
            "updated_at",
        ]
