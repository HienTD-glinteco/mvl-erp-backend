from rest_framework import serializers

from libs.drf.serializers import BaseStatisticsSerializer


class DashboardRealtimeDataSerializer(serializers.Serializer):
    """Serializer for dashboard realtime KPI data."""

    open_positions = serializers.IntegerField(help_text="Number of open recruitment positions")
    applicants_today = serializers.IntegerField(help_text="Number of applicants today")
    hires_today = serializers.IntegerField(help_text="Number of hires today")
    interviews_today = serializers.IntegerField(help_text="Number of interviews scheduled for today")


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
    months = serializers.ListField(child=serializers.CharField())
    data = CostBreakdownByBranchSerializer(many=True)


class SourceTypeBreakdownSerializer(serializers.Serializer):
    """Serializer for recruitment source breakdown."""

    source_type = serializers.CharField(help_text="Source type")
    count = serializers.IntegerField(help_text="Number of candidates from this source type")
    percentage = serializers.FloatField(help_text="Percent of candidates from this source type")


class SourceTypesMonthlyTrendsSerializer(serializers.Serializer):
    """
    Serializer for monthly trends of candidate sources.

    Represents the number of candidates from each recruitment source type for a specific month.
    """

    month = serializers.CharField(help_text="Month in MM/YYYY format (e.g., 10/2025)")
    referral_source = serializers.IntegerField(
        help_text="Number of candidates referred by employees (referral program)"
    )
    marketing_channel = serializers.IntegerField(
        help_text="Number of candidates from marketing channels (ads, social media, etc.)"
    )
    job_website_channel = serializers.IntegerField(help_text="Number of candidates from job websites/portals")
    recruitment_department_source = serializers.IntegerField(
        help_text="Number of candidates sourced directly by the recruitment department"
    )
    returning_employee = serializers.IntegerField(help_text="Number of candidates who are returning employees")


class DashboardChartDataSerializer(serializers.Serializer):
    """Serializer for dashboard chart data."""

    experience_breakdown = ExperienceBreakdownSerializer(many=True, help_text="Breakdown by experience level")
    branch_breakdown = BranchBreakdownSerializer(many=True, help_text="Breakdown by branch")
    cost_breakdown = CostBreakdownByCategorySerializer(many=True, help_text="Cost breakdown by source type")
    cost_by_branches = CostBreakdownByBranchAggregrationSerializer(help_text="Cost breakdown by branches")
    source_type_breakdown = SourceTypeBreakdownSerializer(many=True, help_text="Source type breakdown")
    monthly_trends = SourceTypesMonthlyTrendsSerializer(
        many=True,
        help_text="Monthly trends showing the number of candidates from each recruitment source type for every month",
    )


class DashboardChartFilterSerializer(serializers.Serializer):
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
