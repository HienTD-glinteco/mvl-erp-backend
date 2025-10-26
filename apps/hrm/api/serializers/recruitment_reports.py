import calendar
from datetime import date

from rest_framework import serializers

from apps.hrm.constants import ReportPeriodType

from .employee import EmployeeSerializer
from .recruitment_expense import RecruitmentExpenseSerializer

# Parameter Serializers for input validation and OpenAPI documentation


class StaffGrowthReportParametersSerializer(serializers.Serializer):
    """Parameters for staff growth report."""

    period_type = serializers.ChoiceField(
        choices=ReportPeriodType.choices,
        default=ReportPeriodType.MONTH.value,
        help_text="Period type for aggregation. Choices: 'week' or 'month'.",
    )
    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class RecruitmentSourceReportParametersSerializer(serializers.Serializer):
    """Parameters for recruitment source report."""

    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class RecruitmentChannelReportParametersSerializer(serializers.Serializer):
    """Parameters for recruitment channel report."""

    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class RecruitmentCostReportParametersSerializer(serializers.Serializer):
    """Parameters for recruitment cost report."""

    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class HiredCandidateReportParametersSerializer(serializers.Serializer):
    """Parameters for hired candidate report."""

    period_type = serializers.ChoiceField(
        choices=ReportPeriodType.choices,
        default=ReportPeriodType.MONTH.value,
        help_text="Period type for aggregation. Choices: 'week' or 'month'.",
    )
    from_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    to_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")


class ReferralCostReportParametersSerializer(serializers.Serializer):
    """Parameters for referral cost report - always restricted to single month."""

    month = serializers.RegexField(
        regex=r"^\d{2}/\d{4}$",
        required=False,
        help_text="Month in MM/YYYY format (default: current month)",
    )
    branch = serializers.IntegerField(required=False, help_text="Branch ID to filter")
    block = serializers.IntegerField(required=False, help_text="Block ID to filter")
    department = serializers.IntegerField(required=False, help_text="Department ID to filter")

    def validate(self, attrs):
        # Transform month (MM/YYYY) to from_date, to_date
        month_str = attrs.get("month")
        if month_str:
            try:
                month, year = map(int, month_str.split("/"))
                from_date = date(year, month, 1)
                last_day = calendar.monthrange(year, month)[1]
                to_date = date(year, month, last_day)
                attrs["from_date"] = from_date
                attrs["to_date"] = to_date
            except Exception:
                raise serializers.ValidationError({"month": "Invalid month format. Use MM/YYYY."})
        return attrs


# Report Response Serializers


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

    channels = serializers.ListField(
        child=serializers.CharField(), read_only=True, help_text="A list of channel names"
    )
    data = serializers.ListField(child=RecruitmentReportBranchItemSerializer(), read_only=True)


class RecruitmentCostSourceMonthSerializer(serializers.Serializer):
    total = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, help_text="Total recruitment cost for the period."
    )
    count = serializers.IntegerField(read_only=True, help_text="Number of hires for the period.")
    avg = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, help_text="Average cost per hire for the period."
    )


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
    name = serializers.CharField(help_text="Department name.")
    items = serializers.ListField(
        child=ReferralCostEmployeeSerializer(), help_text="List of referral expenses for this department."
    )


class ReferralCostReportAggregatedSerializer(serializers.Serializer):
    """
    Serializer for aggregated referral cost report data.
    data: List of departments, each with referral expenses and employees.
    summary_total: Total referral cost for the selected month and filters.
    """

    data = serializers.ListField(
        child=ReferralCostDepartmentSerializer(), help_text="List of departments with referral expenses."
    )
    summary_total = serializers.DecimalField(
        max_digits=15, decimal_places=0, help_text="Total referral cost for the report."
    )
