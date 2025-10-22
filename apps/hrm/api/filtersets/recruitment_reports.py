import django_filters

from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
    StaffGrowthReport,
)


class StaffGrowthReportFilterSet(django_filters.FilterSet):
    """FilterSet for StaffGrowthReport."""

    report_date_after = django_filters.DateFilter(field_name="report_date", lookup_expr="gte")
    report_date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte")
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")

    class Meta:
        model = StaffGrowthReport
        fields = [
            "report_date_after",
            "report_date_before",
            "branch",
            "block",
            "department",
        ]


class RecruitmentSourceReportFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentSourceReport."""

    report_date_after = django_filters.DateFilter(field_name="report_date", lookup_expr="gte")
    report_date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte")
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")
    recruitment_source = django_filters.NumberFilter(field_name="recruitment_source")

    class Meta:
        model = RecruitmentSourceReport
        fields = [
            "report_date_after",
            "report_date_before",
            "branch",
            "block",
            "department",
            "recruitment_source",
        ]


class RecruitmentChannelReportFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentChannelReport."""

    report_date_after = django_filters.DateFilter(field_name="report_date", lookup_expr="gte")
    report_date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte")
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")
    recruitment_channel = django_filters.NumberFilter(field_name="recruitment_channel")

    class Meta:
        model = RecruitmentChannelReport
        fields = [
            "report_date_after",
            "report_date_before",
            "branch",
            "block",
            "department",
            "recruitment_channel",
        ]


class RecruitmentCostReportFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentCostReport."""

    report_date_after = django_filters.DateFilter(field_name="report_date", lookup_expr="gte")
    report_date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte")
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")
    recruitment_source = django_filters.NumberFilter(field_name="recruitment_source")
    recruitment_channel = django_filters.NumberFilter(field_name="recruitment_channel")

    class Meta:
        model = RecruitmentCostReport
        fields = [
            "report_date_after",
            "report_date_before",
            "branch",
            "block",
            "department",
            "recruitment_source",
            "recruitment_channel",
        ]


class HiredCandidateReportFilterSet(django_filters.FilterSet):
    """FilterSet for HiredCandidateReport."""

    report_date_after = django_filters.DateFilter(field_name="report_date", lookup_expr="gte")
    report_date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte")
    branch = django_filters.NumberFilter(field_name="branch")
    block = django_filters.NumberFilter(field_name="block")
    department = django_filters.NumberFilter(field_name="department")
    source_type = django_filters.CharFilter(field_name="source_type")
    employee = django_filters.NumberFilter(field_name="employee")

    class Meta:
        model = HiredCandidateReport
        fields = [
            "report_date_after",
            "report_date_before",
            "branch",
            "block",
            "department",
            "source_type",
            "employee",
        ]
