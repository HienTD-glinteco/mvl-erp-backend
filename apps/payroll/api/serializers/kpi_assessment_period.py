from rest_framework import serializers

from apps.payroll.models import KPIAssessmentPeriod


class KPIAssessmentPeriodSerializer(serializers.ModelSerializer):
    """Serializer for KPIAssessmentPeriod model."""

    class Meta:
        model = KPIAssessmentPeriod
        fields = [
            "id",
            "month",
            "kpi_config_snapshot",
            "finalized",
            "created_by",
            "updated_by",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


class KPIAssessmentPeriodListSerializer(serializers.ModelSerializer):
    """List serializer for KPIAssessmentPeriod model."""

    employee_count = serializers.SerializerMethodField()
    department_count = serializers.SerializerMethodField()

    class Meta:
        model = KPIAssessmentPeriod
        fields = [
            "id",
            "month",
            "finalized",
            "employee_count",
            "department_count",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def get_employee_count(self, obj):
        """Get count of employee assessments in this period."""
        return obj.employee_assessments.count()

    def get_department_count(self, obj):
        """Get count of department assessments in this period."""
        return obj.department_assessments.count()
