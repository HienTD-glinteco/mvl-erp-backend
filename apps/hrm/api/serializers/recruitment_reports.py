from rest_framework import serializers

from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
    StaffGrowthReport,
)


class StaffGrowthReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated staff growth report data (week/month periods)."""

    period_type = serializers.CharField(read_only=True, help_text="Period type: week or month")
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    branch = serializers.IntegerField(read_only=True, allow_null=True)
    branch_name = serializers.CharField(read_only=True, allow_null=True)
    block = serializers.IntegerField(read_only=True, allow_null=True)
    block_name = serializers.CharField(read_only=True, allow_null=True)
    department = serializers.IntegerField(read_only=True, allow_null=True)
    department_name = serializers.CharField(read_only=True, allow_null=True)
    num_introductions = serializers.IntegerField(read_only=True)
    num_returns = serializers.IntegerField(read_only=True)
    num_new_hires = serializers.IntegerField(read_only=True)
    num_transfers = serializers.IntegerField(read_only=True)
    num_resignations = serializers.IntegerField(read_only=True)


class RecruitmentSourceReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated recruitment source report data (nested format)."""

    period_type = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    sources = serializers.ListField(child=serializers.DictField(), read_only=True)
    data = serializers.ListField(child=serializers.DictField(), read_only=True)


class RecruitmentChannelReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated recruitment channel report data (nested format)."""

    period_type = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    channels = serializers.ListField(child=serializers.DictField(), read_only=True)
    data = serializers.ListField(child=serializers.DictField(), read_only=True)


class RecruitmentCostReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated recruitment cost report data (week/month periods)."""

    period_type = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    branch = serializers.IntegerField(read_only=True, allow_null=True)
    branch_name = serializers.CharField(read_only=True, allow_null=True)
    block = serializers.IntegerField(read_only=True, allow_null=True)
    block_name = serializers.CharField(read_only=True, allow_null=True)
    department = serializers.IntegerField(read_only=True, allow_null=True)
    department_name = serializers.CharField(read_only=True, allow_null=True)
    category = serializers.CharField(read_only=True)
    category_display = serializers.CharField(read_only=True)
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    num_hired = serializers.IntegerField(read_only=True)
    avg_cost_per_hire = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)


class HiredCandidateReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated hired candidate report data (week/month periods)."""

    period_type = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    branch = serializers.IntegerField(read_only=True, allow_null=True)
    branch_name = serializers.CharField(read_only=True, allow_null=True)
    block = serializers.IntegerField(read_only=True, allow_null=True)
    block_name = serializers.CharField(read_only=True, allow_null=True)
    department = serializers.IntegerField(read_only=True, allow_null=True)
    department_name = serializers.CharField(read_only=True, allow_null=True)
    source_type = serializers.CharField(read_only=True)
    source_type_display = serializers.CharField(read_only=True)
    num_candidates_hired = serializers.IntegerField(read_only=True)
    num_experienced = serializers.IntegerField(read_only=True)
    num_no_experience = serializers.IntegerField(read_only=True)
    children = serializers.ListField(child=serializers.DictField(), read_only=True, required=False)


class ReferralCostDetailSerializer(serializers.Serializer):
    """Serializer for referral cost detail report data."""

    month = serializers.CharField(read_only=True)
    department_name = serializers.CharField(read_only=True)
    employee_code = serializers.CharField(read_only=True)
    employee_name = serializers.CharField(read_only=True)
    num_referrals = serializers.IntegerField(read_only=True)
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)


class ReferralCostSummarySerializer(serializers.Serializer):
    """Serializer for referral cost summary report data."""

    month = serializers.CharField(read_only=True)
    department_name = serializers.CharField(read_only=True)
    total_referrals = serializers.IntegerField(read_only=True)
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    details = ReferralCostDetailSerializer(many=True, read_only=True)
