from rest_framework import serializers

from apps.hrm.constants import ReportPeriodType

from .employee import EmployeeSerializer
from .recruitment_expense import RecruitmentExpenseSerializer


# Parameter Serializers for input validation and OpenAPI documentation


class StaffGrowthReportParametersSerializer(serializers.Serializer):
    """Parameters for staff growth report."""

    period = serializers.ChoiceField(
        choices=[("week", "Week"), ("month", "Month")],
        default="month",
        help_text="Period type: 'week' or 'month'",
    )
    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Filter by branch ID")
    block = serializers.IntegerField(required=False, help_text="Filter by block ID")
    department = serializers.IntegerField(required=False, help_text="Filter by department ID")


class RecruitmentSourceReportParametersSerializer(serializers.Serializer):
    """Parameters for recruitment source report."""

    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Filter by branch ID")
    block = serializers.IntegerField(required=False, help_text="Filter by block ID")
    department = serializers.IntegerField(required=False, help_text="Filter by department ID")


class RecruitmentChannelReportParametersSerializer(serializers.Serializer):
    """Parameters for recruitment channel report."""

    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Filter by branch ID")
    block = serializers.IntegerField(required=False, help_text="Filter by block ID")
    department = serializers.IntegerField(required=False, help_text="Filter by department ID")


class RecruitmentCostReportParametersSerializer(serializers.Serializer):
    """Parameters for recruitment cost report."""

    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Filter by branch ID")
    block = serializers.IntegerField(required=False, help_text="Filter by block ID")
    department = serializers.IntegerField(required=False, help_text="Filter by department ID")


class HiredCandidateReportParametersSerializer(serializers.Serializer):
    """Parameters for hired candidate report."""

    period = serializers.ChoiceField(
        choices=[("week", "Week"), ("month", "Month")],
        default="month",
        help_text="Period type: 'week' or 'month'",
    )
    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Filter by branch ID")
    block = serializers.IntegerField(required=False, help_text="Filter by block ID")
    department = serializers.IntegerField(required=False, help_text="Filter by department ID")


class ReferralCostReportParametersSerializer(serializers.Serializer):
    """Parameters for referral cost report - always restricted to single month."""

    month = serializers.RegexField(
        regex=r'^\d{4}-\d{2}$',
        required=False,
        help_text="Month in YYYY-MM format (default: current month)",
    )


class StaffGrowthReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated staff growth report data (week/month periods)."""

    period_type = serializers.ChoiceField(read_only=True, choices=ReportPeriodType.choices)
    label = serializers.CharField(
        read_only=True,
        help_text=(
            "Period label.\n"
            "For week: (DD/MM - DD/MM), where the first day is Monday and the last day is Sunday (e.g., 12/05 - 18/05).\n"
            "For month: 'Month MM/YYYY' (e.g., Month 05/2025)."
        ),
    )
    num_introductions = serializers.IntegerField(read_only=True)
    num_returns = serializers.IntegerField(read_only=True)
    num_new_hires = serializers.IntegerField(read_only=True)
    num_transfers = serializers.IntegerField(read_only=True)
    num_resignations = serializers.IntegerField(read_only=True)


class BaseRecruitmentReportStatisticsSerializer(serializers.Serializer):
    type = serializers.CharField()
    name = serializers.CharField()
    statistics = serializers.ListField(child=serializers.IntegerField())


class RecruitmentReportBlockItemSerializer(BaseRecruitmentReportStatisticsSerializer):
    children = serializers.ListField(child=BaseRecruitmentReportStatisticsSerializer())


class RecruitmentReportBranchItemSerializer(BaseRecruitmentReportStatisticsSerializer):
    children = serializers.ListField(child=RecruitmentReportBlockItemSerializer())


class RecruitmentSourceReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated recruitment source report data (nested format)."""

    sources = serializers.ListField(child=serializers.CharField(), read_only=True, help_text="A list of source names")
    data = serializers.ListField(child=RecruitmentReportBranchItemSerializer(), read_only=True)


class RecruitmentChannelReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated recruitment channel report data (nested format)."""

    sources = serializers.ListField(child=serializers.CharField(), read_only=True, help_text="A list of channel names")
    data = serializers.ListField(child=RecruitmentReportBranchItemSerializer(), read_only=True)


class RecruitmentCostSourceMonthSerializer(serializers.Serializer):
    total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    count = serializers.IntegerField(read_only=True)
    avg = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)


class RecruitmentCostSourceSerializer(serializers.Serializer):
    source_type = serializers.CharField(read_only=True)
    months = serializers.ListField(child=RecruitmentCostSourceMonthSerializer())


class RecruitmentCostReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated recruitment cost report data (week/month periods)."""

    months = serializers.ListField(child=serializers.CharField(), help_text="A list of months including Total.")
    data = serializers.ListField(child=RecruitmentCostSourceSerializer())


class HiredCandidateSourceTypeSerializer(BaseRecruitmentReportStatisticsSerializer):
    children = serializers.ListField(child=BaseRecruitmentReportStatisticsSerializer())


class HiredCandidateReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated hired candidate report data (week/month periods)."""

    period_type = serializers.ChoiceField(read_only=True, choices=ReportPeriodType.choices)
    sources = serializers.ListField(child=serializers.CharField(), read_only=True, help_text="A list of source names")
    data = serializers.ListField(child=HiredCandidateSourceTypeSerializer(), read_only=True)


class ReferralCostEmployeeSerializer(RecruitmentExpenseSerializer):
    referee = EmployeeSerializer(read_only=True)
    referrer = EmployeeSerializer(read_only=True)


class ReferralCostDepartmentSerializer(serializers.Serializer):
    name = serializers.CharField()
    items = serializers.ListField(child=ReferralCostEmployeeSerializer())


class ReferralCostReportAggregatedSerializer(serializers.Serializer):
    """Serializer for aggregated referral cost report data."""

    data = serializers.ListField(child=ReferralCostDepartmentSerializer())
    summary_total = serializers.DecimalField(max_digits=15, decimal_places=0)
