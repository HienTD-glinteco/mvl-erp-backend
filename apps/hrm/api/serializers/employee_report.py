from rest_framework import serializers

from apps.hrm.constants import ExtendedReportPeriodType
from libs.drf.serializers import BaseStatisticsSerializer


class EmployeeCountBreakdownReportParamsSerializer(serializers.Serializer):
    """Parameters for employee count breakdown reports."""

    period_type = serializers.ChoiceField(
        choices=ExtendedReportPeriodType.choices,
        help_text="Period type for aggregation. Choices: 'week', 'month', 'quarter', or 'year'.",
    )
    from_date = serializers.DateField(help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
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
