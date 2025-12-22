"""Reusable nested serializers for Payroll models.

This module provides predefined nested serializers to reduce duplication
across Payroll serializers. All nested serializers are read-only and provide
compact representations of related models.
"""

from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import (
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
)
from apps.payroll.models import KPIAssessmentPeriod

# Re-export HRM nested serializers for convenience
__all__ = [
    "EmployeeNestedSerializer",
    "DepartmentNestedSerializer",
    "KPIAssessmentPeriodNestedSerializer",
]


class KPIAssessmentPeriodNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for KPIAssessmentPeriod with formatted month."""

    month = serializers.SerializerMethodField()

    class Meta:
        model = KPIAssessmentPeriod
        fields = ["id", "month", "finalized"]
        read_only_fields = ["id", "month", "finalized"]

    def get_month(self, obj):
        """Return month in n/YYYY format (month without leading zero)."""
        return obj.month.strftime("%-m/%Y")
