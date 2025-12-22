from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    ContractNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
)
from apps.hrm.constants import EmployeeType, ExtendedReportPeriodType
from apps.hrm.models import Block, EmployeeWorkHistory
from libs.drf.serializers import BaseStatisticsSerializer


class EmployeeCountBreakdownReportParamsSerializer(serializers.Serializer):
    """Parameters for employee count breakdown reports."""

    period_type = serializers.ChoiceField(
        choices=ExtendedReportPeriodType.choices,
        help_text="Period type for aggregation. Choices: 'week', 'month', 'quarter', or 'year'.",
    )
    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    block_type = serializers.ChoiceField(
        required=False,
        choices=Block.BlockType.choices,
        help_text="Block type to filter. Choices: 'support' or 'business'.",
    )
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class EmployeeStatusBreakdownReportBlockItemSerializer(BaseStatisticsSerializer):
    """Block-level item for employee status breakdown report with nested departments."""

    children = serializers.ListField(child=BaseStatisticsSerializer())


class EmployeeStatusBreakdownReportBranchItemSerializer(BaseStatisticsSerializer):
    """Branch-level item for employee status breakdown report with nested blocks."""

    children = serializers.ListField(child=EmployeeStatusBreakdownReportBlockItemSerializer())


class EmployeeStatusBreakdownReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated employee status breakdown report data."""

    time_headers = serializers.ListField(child=serializers.CharField(), help_text="Time period headers")
    data = serializers.ListField(child=EmployeeStatusBreakdownReportBranchItemSerializer())


class EmployeeResignedReasonSummaryParamsSerializer(serializers.Serializer):
    """Parameters for employee resigned reason summary report."""

    from_date = serializers.DateField(
        required=False, help_text="Start date (YYYY-MM-DD). Default: 1st of current month"
    )
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD). Default: today")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    block_type = serializers.ChoiceField(
        required=False,
        choices=Block.BlockType.choices,
        help_text="Block type to filter. Choices: 'support' or 'business'.",
    )
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class ResignedReasonItemSerializer(serializers.Serializer):
    """Single resignation reason with count and percentage."""

    code = serializers.CharField(help_text="Resignation reason code")
    label = serializers.CharField(help_text="Resignation reason display label")
    count = serializers.IntegerField(help_text="Number of resignations for this reason")
    percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, help_text="Percentage of total resignations (0-100)"
    )


class EmployeeResignedReasonSummarySerializer(serializers.Serializer):
    """Serializer for employee resigned reason summary report response."""

    total_resigned = serializers.IntegerField(help_text="Total resigned employees in the period")
    from_date = serializers.DateField(help_text="Start date of the report range")
    to_date = serializers.DateField(help_text="End date of the report range")
    filters = serializers.DictField(help_text="Applied filters (branch, block, department, block_type)")
    reasons = ResignedReasonItemSerializer(
        many=True, help_text="List of resignation reasons with counts and percentages"
    )


class EmployeeTypeConversionReportSerializer(serializers.ModelSerializer):
    """Serializer for Employee Type Conversion Report."""

    contract = ContractNestedSerializer(read_only=True)
    employee = EmployeeNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    old_employee_type = serializers.ChoiceField(choices=EmployeeType.choices, read_only=True)
    new_employee_type = serializers.ChoiceField(choices=EmployeeType.choices, read_only=True)

    class Meta:
        model = EmployeeWorkHistory
        fields = [
            "id",
            "contract",
            "employee",
            "branch",
            "block",
            "department",
            "old_employee_type",
            "new_employee_type",
            "date",
            "from_date",
            "to_date",
            "note",
        ]


class EmployeeTypeConversionDepartmentItemSerializer(serializers.Serializer):
    """Department-level item for employee type conversion report."""

    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    type = serializers.CharField(default="department")
    children = serializers.ListField(child=EmployeeTypeConversionReportSerializer())


class EmployeeTypeConversionBlockItemSerializer(serializers.Serializer):
    """Block-level item for employee type conversion report."""

    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    type = serializers.CharField(default="block")
    children = serializers.ListField(child=EmployeeTypeConversionDepartmentItemSerializer())


class EmployeeTypeConversionBranchItemSerializer(serializers.Serializer):
    """Branch-level item for employee type conversion report."""

    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    type = serializers.CharField(default="branch")
    children = serializers.ListField(child=EmployeeTypeConversionBlockItemSerializer())
