"""Serializers for SalaryPeriod model."""

from rest_framework import serializers

from apps.payroll.models import SalaryPeriod


class SalaryPeriodListSerializer(serializers.ModelSerializer):
    """List serializer for SalaryPeriod with summary information."""

    class Meta:
        model = SalaryPeriod
        fields = [
            "id",
            "code",
            "month",
            "status",
            "standard_working_days",
            "total_employees",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SalaryPeriodSerializer(serializers.ModelSerializer):
    """Detail serializer for SalaryPeriod."""

    class Meta:
        model = SalaryPeriod
        fields = [
            "id",
            "code",
            "month",
            "salary_config_snapshot",
            "status",
            "standard_working_days",
            "total_employees",
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
            "standard_working_days",
            "total_employees",
            "completed_at",
            "completed_by",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


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


class SalaryPeriodStatisticsSerializer(serializers.Serializer):
    """Statistics serializer for SalaryPeriod."""

    pending_count = serializers.IntegerField()
    ready_count = serializers.IntegerField()
    hold_count = serializers.IntegerField()
    delivered_count = serializers.IntegerField()
    total_gross_income = serializers.DecimalField(max_digits=20, decimal_places=0)
    total_net_salary = serializers.DecimalField(max_digits=20, decimal_places=0)
