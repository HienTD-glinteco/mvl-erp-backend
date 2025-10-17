import django_filters

from apps.hrm.models import RecruitmentCandidateContactLog


class RecruitmentCandidateContactLogFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentCandidateContactLog model"""

    method = django_filters.CharFilter(lookup_expr="icontains")
    recruitment_candidate = django_filters.NumberFilter(field_name="recruitment_candidate_id")
    employee = django_filters.NumberFilter(field_name="employee_id")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = RecruitmentCandidateContactLog
        fields = [
            "method",
            "recruitment_candidate",
            "employee",
            "date_from",
            "date_to",
        ]
