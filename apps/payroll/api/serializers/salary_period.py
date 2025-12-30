"""Serializers for SalaryPeriod model."""

from rest_framework import serializers

from apps.payroll.models import SalaryPeriod
from libs import ColoredValueSerializer


class SalaryPeriodListSerializer(serializers.ModelSerializer):
    """List serializer for SalaryPeriod with summary information."""

    colored_status = ColoredValueSerializer(source="get_colored_status", read_only=True)
    month = serializers.SerializerMethodField()

    class Meta:
        model = SalaryPeriod
        fields = [
            "id",
            "code",
            "month",
            "status",
            "colored_status",
            "standard_working_days",
            "total_employees",
            "pending_count",
            "ready_count",
            "hold_count",
            "delivered_count",
            "proposal_deadline",
            "kpi_assessment_deadline",
            "employees_need_recovery",
            "employees_with_penalties",
            "employees_paid_penalties",
            "employees_with_travel",
            "employees_need_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_colored_status(self, obj):
        """Get colored status value."""
        return obj.get_colored_value("status")

    def get_month(self, obj):
        """Return month in n/YYYY format (month without leading zero)."""
        return obj.month.strftime("%-m/%Y")


class SalaryPeriodSerializer(serializers.ModelSerializer):
    """Detail serializer for SalaryPeriod."""

    colored_status = ColoredValueSerializer(source="get_colored_status", read_only=True)
    month = serializers.SerializerMethodField()

    class Meta:
        model = SalaryPeriod
        fields = [
            "id",
            "code",
            "month",
            "salary_config_snapshot",
            "status",
            "colored_status",
            "standard_working_days",
            "total_employees",
            "pending_count",
            "ready_count",
            "hold_count",
            "delivered_count",
            "total_gross_income",
            "total_net_salary",
            "proposal_deadline",
            "kpi_assessment_deadline",
            "employees_need_recovery",
            "employees_with_penalties",
            "employees_paid_penalties",
            "employees_with_travel",
            "employees_need_email",
            "completed_at",
            "completed_by",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "code",
            "salary_config_snapshot",
            "status",
            "colored_status",
            "standard_working_days",
            "total_employees",
            "pending_count",
            "ready_count",
            "hold_count",
            "delivered_count",
            "total_gross_income",
            "total_net_salary",
            "employees_need_recovery",
            "employees_with_penalties",
            "employees_paid_penalties",
            "employees_with_travel",
            "employees_need_email",
            "completed_at",
            "completed_by",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def get_colored_status(self, obj):
        """Get colored status value."""
        return obj.get_colored_value("status")

    def get_month(self, obj):
        """Return month in n/YYYY format (month without leading zero)."""
        return obj.month.strftime("%-m/%Y")


class SalaryPeriodCreateSerializer(serializers.ModelSerializer):
    """Create serializer for SalaryPeriod."""

    class Meta:
        model = SalaryPeriod
        fields = ["month"]

    def validate_month(self, value):
        """Validate that month is first day of month."""
        if value.day != 1:
            raise serializers.ValidationError("Month must be the first day of the month")

        # Check if period already exists for this month
        if SalaryPeriod.objects.filter(month=value).exists():
            raise serializers.ValidationError("Salary period already exists for this month")

        return value

    def create(self, validated_data):
        """Create salary period with config snapshot."""
        from apps.payroll.models import SalaryConfig

        # Get latest salary config
        salary_config = SalaryConfig.objects.first()
        if not salary_config:
            raise serializers.ValidationError("No salary configuration found")

        # Create period with config snapshot
        validated_data["salary_config_snapshot"] = salary_config.config

        return super().create(validated_data)


class SalaryPeriodCreateAsyncSerializer(serializers.Serializer):
    """Serializer for creating salary period asynchronously."""

    month = serializers.CharField(max_length=7, help_text="Month in n/YYYY format (e.g., 1/2025, 12/2025)")
    proposal_deadline = serializers.DateField(
        required=False, allow_null=True, help_text="Deadline for proposals (default: 2nd of next month)"
    )
    kpi_assessment_deadline = serializers.DateField(
        required=False, allow_null=True, help_text="Deadline for KPI assessments (default: 5th of next month)"
    )

    def validate_month(self, value):
        """Validate month format and convert to YYYY-MM."""
        from datetime import date

        try:
            # Parse n/YYYY format
            month, year = value.split("/")
            month = int(month)
            year = int(year)

            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")

            target_month = date(year, month, 1)
        except (ValueError, AttributeError):
            raise serializers.ValidationError("Invalid month format. Use n/YYYY (e.g., 1/2025, 12/2025)")

        # Check if period already exists
        if SalaryPeriod.objects.filter(month=target_month).exists():
            raise serializers.ValidationError("Salary period already exists for this month")

        # Check if previous period is completed
        previous_periods = SalaryPeriod.objects.filter(month__lt=target_month).order_by("-month")
        if previous_periods.exists() and previous_periods.first().status != SalaryPeriod.Status.COMPLETED:
            raise serializers.ValidationError(
                f"Previous period {previous_periods.first().month.strftime('%-m/%Y')} is not completed yet"
            )

        # Return in YYYY-MM format for task
        return f"{year}-{month:02d}"


class SalaryPeriodUpdateDeadlinesSerializer(serializers.Serializer):
    """Serializer for updating salary period deadlines."""

    proposal_deadline = serializers.DateField(required=False, allow_null=True, help_text="Deadline for proposals")
    kpi_assessment_deadline = serializers.DateField(
        required=False, allow_null=True, help_text="Deadline for KPI assessments"
    )


class TaskStatusSerializer(serializers.Serializer):
    """Serializer for Celery task status."""

    task_id = serializers.CharField()
    state = serializers.CharField()
    result = serializers.JSONField(required=False)
    meta = serializers.JSONField(required=False)


class SalaryPeriodCreateResponseSerializer(serializers.Serializer):
    """Response serializer for salary period creation."""

    task_id = serializers.CharField(help_text="Celery task ID for tracking the creation process")
    status = serializers.CharField(help_text="Task creation status")
    message = serializers.CharField(help_text="Human-readable message about the task")


class SalaryPeriodRecalculateResponseSerializer(serializers.Serializer):
    """Response serializer for salary period recalculation."""

    task_id = serializers.CharField(help_text="Celery task ID for tracking the recalculation process")
    status = serializers.CharField(help_text="Task creation status")
    message = serializers.CharField(help_text="Human-readable message about the task")
