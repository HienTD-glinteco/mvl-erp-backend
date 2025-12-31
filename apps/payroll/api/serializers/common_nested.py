"""Reusable nested serializers for Payroll models.

This module provides predefined nested serializers to reduce duplication
across Payroll serializers. All nested serializers are read-only and provide
compact representations of related models.
"""

from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.models import Employee
from apps.payroll.models import KPIAssessmentPeriod, SalaryPeriod

# Re-export HRM nested serializers for convenience
__all__ = [
    "BlockNestedSerializer",
    "BranchNestedSerializer",
    "DepartmentNestedSerializer",
    "EmployeeNestedSerializer",
    "PositionNestedSerializer",
    "EmployeeWithDetailsNestedSerializer",
    "KPIAssessmentPeriodNestedSerializer",
    "SalaryPeriodNestedSerializer",
]


class EmployeeWithDetailsNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for Employee with organizational details.

    Includes employee's block, branch, department, and position information.
    Used in payroll contexts where full employee context is needed.
    """

    block = BlockNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    position = PositionNestedSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "fullname",
            "block",
            "branch",
            "department",
            "position",
        ]
        read_only_fields = fields


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


class SalaryPeriodNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for SalaryPeriod with formatted month."""

    month = serializers.SerializerMethodField()

    class Meta:
        model = SalaryPeriod
        fields = ["id", "code", "month", "status"]
        read_only_fields = ["id", "code", "month", "status"]

    def get_month(self, obj):
        """Return month in n/YYYY format (month without leading zero)."""
        return obj.month.strftime("%-m/%Y")
