from rest_framework import serializers

from apps.payroll.models import KPIAssessmentPeriod


class KPIAssessmentPeriodGenerateSerializer(serializers.Serializer):
    """Serializer for generating KPI assessments."""

    month = serializers.CharField(
        max_length=7,
        help_text="Month in YYYY-MM format (e.g., 2025-12)",
    )


class KPIAssessmentPeriodGenerateResponseSerializer(serializers.Serializer):
    """Response serializer for generate action."""

    message = serializers.CharField(help_text="Success message")
    period_id = serializers.IntegerField(help_text="ID of the created/existing period")
    month = serializers.CharField(help_text="Month of the period in YYYY-MM format")
    employee_assessments_created = serializers.IntegerField(help_text="Number of employee assessments created")
    department_assessments_created = serializers.IntegerField(help_text="Number of department assessments created")


class KPIAssessmentPeriodFinalizeResponseSerializer(serializers.Serializer):
    """Response serializer for finalize action."""

    message = serializers.CharField(help_text="Success message")
    employees_set_to_c = serializers.IntegerField(help_text="Number of employees set to grade C")
    departments_validated = serializers.IntegerField(help_text="Number of departments with valid unit control")
    departments_invalid = serializers.IntegerField(help_text="Number of departments with invalid unit control")


class KPIAssessmentPeriodSummarySerializer(serializers.Serializer):
    """Response serializer for summary action."""

    total_departments = serializers.IntegerField(help_text="Total number of departments")
    departments_finished = serializers.IntegerField(
        help_text="Number of departments where all employees have been graded"
    )
    departments_not_finished = serializers.IntegerField(
        help_text="Number of departments with at least one ungraded employee"
    )
    departments_not_valid_control = serializers.IntegerField(
        help_text="Number of departments that do not pass unit control validation"
    )


class KPIAssessmentPeriodSerializer(serializers.ModelSerializer):
    """Serializer for KPIAssessmentPeriod model."""

    month = serializers.SerializerMethodField()

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
            "month",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_month(self, obj):
        """Return month in YYYY-MM format."""
        return obj.month.strftime("%Y-%m")


class KPIAssessmentPeriodListSerializer(serializers.ModelSerializer):
    """List serializer for KPIAssessmentPeriod model."""

    month = serializers.SerializerMethodField()
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
            "month",
            "created_at",
            "updated_at",
        ]

    def get_month(self, obj):
        """Return month in YYYY-MM format."""
        return obj.month.strftime("%Y-%m")

    def get_employee_count(self, obj):
        """Get count of employee assessments in this period."""
        return obj.employee_assessments.count()

    def get_department_count(self, obj):
        """Get count of department assessments in this period."""
        return obj.department_assessments.count()
