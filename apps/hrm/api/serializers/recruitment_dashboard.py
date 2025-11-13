from rest_framework import serializers

from libs.drf.serializers import BaseStatisticsSerializer


class DashboardRealtimeDataSerializer(serializers.Serializer):
    """Serializer for dashboard realtime KPI data."""

    open_positions = serializers.IntegerField(help_text="Number of open recruitment positions")
    applicants_today = serializers.IntegerField(help_text="Number of applicants today")
    hires_today = serializers.IntegerField(help_text="Number of hires today")
    interviews_today = serializers.IntegerField(help_text="Number of interviews scheduled for today")
    employees_today = serializers.IntegerField(
        help_text="Number of currently active employees (Active or Onboarding status)"
    )


class ExperienceBreakdownSerializer(serializers.Serializer):
    """Serializer for experience level breakdown."""

    label = serializers.CharField(help_text="Experience type label (e.g., Has experience, No experience)")
    count = serializers.IntegerField(help_text="Number of candidates in this experience type")
    percentage = serializers.FloatField(help_text="Percent of candidates in this experience type")


class BranchBreakdownSerializer(serializers.Serializer):
    """Serializer for branch breakdown."""

    branch_name = serializers.CharField(help_text="Branch name")
    count = serializers.IntegerField(help_text="Number of hires for this branch")
    percentage = serializers.FloatField(help_text="Percent of hires for this branch")


class CostBreakdownByCategorySerializer(serializers.Serializer):
    """Serializer for cost breakdown by source type."""

    source_type = serializers.CharField(help_text="Source type")
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2, help_text="Total cost")
    percentage = serializers.FloatField(help_text="Percent of cost per hire")


class CostBreakdownByBranchItemSerializer(serializers.Serializer):
    total_cost = serializers.FloatField(help_text="Total cost")
    total_hires = serializers.IntegerField(help_text="Number of hires")
    avg_cost = serializers.FloatField(help_text="Average cost")


class CostBreakdownByBranchSerializer(BaseStatisticsSerializer):
    """Serializer for cost breakdown by branches."""

    statistics = serializers.ListField(child=CostBreakdownByBranchItemSerializer())


class CostBreakdownByBranchAggregrationSerializer(serializers.Serializer):
    months = serializers.ListField(child=serializers.CharField(), help_text="List of month keys")
    branch_names = serializers.ListField(child=serializers.CharField(), help_text="List of all branch names in order")
    data = CostBreakdownByBranchSerializer(many=True)


class SourceTypeBreakdownSerializer(serializers.Serializer):
    """Serializer for recruitment source breakdown."""

    source_type = serializers.CharField(help_text="Source type")
    count = serializers.IntegerField(help_text="Number of candidates from this source type")
    percentage = serializers.FloatField(help_text="Percent of candidates from this source type")


class SourceTypesMonthlyTrendsAggregationSerializer(BaseStatisticsSerializer):
    statistics = serializers.ListField(child=serializers.IntegerField())


class SourceTypesMonthlyTrendsSerializer(serializers.Serializer):
    """
    Serializer for monthly trends of candidate sources.

    Represents the number of candidates from each recruitment source type for a specific month.
    """

    months = serializers.ListField(child=serializers.CharField(), help_text="List of month keys")
    source_type_names = serializers.ListField(
        child=serializers.CharField(), help_text="List of all source type names in order"
    )
    data = SourceTypesMonthlyTrendsAggregationSerializer(
        many=True,
        help_text="List of monthly data with month key and source type statistics",
    )


class DashboardChartDataSerializer(serializers.Serializer):
    """Serializer for dashboard chart data."""

    experience_breakdown = ExperienceBreakdownSerializer(many=True, help_text="Breakdown by experience level")
    branch_breakdown = BranchBreakdownSerializer(many=True, help_text="Breakdown by branch")
    cost_breakdown = CostBreakdownByCategorySerializer(many=True, help_text="Cost breakdown by source type")
    cost_by_branches = CostBreakdownByBranchAggregrationSerializer(help_text="Cost breakdown by branches")
    source_type_breakdown = SourceTypeBreakdownSerializer(many=True, help_text="Source type breakdown")
    monthly_trends = SourceTypesMonthlyTrendsSerializer(
        help_text="Monthly trends showing the number of candidates from each recruitment source type for every month",
    )


class DashboardChartFilterSerializer(serializers.Serializer):
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
