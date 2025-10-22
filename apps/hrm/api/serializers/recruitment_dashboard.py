from rest_framework import serializers


class DashboardRealtimeDataSerializer(serializers.Serializer):
    """Serializer for dashboard realtime KPI data."""

    open_positions = serializers.IntegerField(help_text="Number of open recruitment positions")
    applicants_today = serializers.IntegerField(help_text="Number of applicants today")
    hires_today = serializers.IntegerField(help_text="Number of hires today")
    interviews_today = serializers.IntegerField(help_text="Number of interviews scheduled for today")


class ExperienceBreakdownSerializer(serializers.Serializer):
    """Serializer for experience level breakdown."""

    experience_range = serializers.CharField(help_text="Experience range (e.g., '0-1 years', '1-3 years')")
    count = serializers.IntegerField(help_text="Number of candidates in this experience range")


class SourceBreakdownSerializer(serializers.Serializer):
    """Serializer for recruitment source breakdown."""

    source_name = serializers.CharField(help_text="Recruitment source name")
    count = serializers.IntegerField(help_text="Number of candidates from this source")


class ChannelBreakdownSerializer(serializers.Serializer):
    """Serializer for recruitment channel breakdown."""

    channel_name = serializers.CharField(help_text="Recruitment channel name")
    count = serializers.IntegerField(help_text="Number of candidates from this channel")


class BranchBreakdownSerializer(serializers.Serializer):
    """Serializer for branch breakdown."""

    branch_name = serializers.CharField(help_text="Branch name")
    count = serializers.IntegerField(help_text="Number of hires for this branch")


class CostBreakdownSerializer(serializers.Serializer):
    """Serializer for cost breakdown by source/channel."""

    source_or_channel_name = serializers.CharField(help_text="Source or channel name")
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2, help_text="Total cost")
    avg_cost_per_hire = serializers.DecimalField(max_digits=15, decimal_places=2, help_text="Average cost per hire")


class HireRatioSerializer(serializers.Serializer):
    """Serializer for hire ratio statistics."""

    total_applicants = serializers.IntegerField(help_text="Total number of applicants")
    total_hires = serializers.IntegerField(help_text="Total number of hires")
    hire_ratio = serializers.FloatField(help_text="Hire ratio (hires/applicants)")


class DashboardChartDataSerializer(serializers.Serializer):
    """Serializer for dashboard chart data."""

    experience_breakdown = ExperienceBreakdownSerializer(many=True, help_text="Breakdown by experience level")
    source_breakdown = SourceBreakdownSerializer(many=True, help_text="Breakdown by recruitment source")
    channel_breakdown = ChannelBreakdownSerializer(many=True, help_text="Breakdown by recruitment channel")
    branch_breakdown = BranchBreakdownSerializer(many=True, help_text="Breakdown by branch")
    cost_breakdown = CostBreakdownSerializer(many=True, help_text="Cost breakdown by source/channel")
    hire_ratio = HireRatioSerializer(help_text="Overall hire ratio statistics")
