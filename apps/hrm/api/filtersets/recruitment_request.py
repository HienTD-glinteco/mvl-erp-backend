import django_filters

from apps.hrm.models import RecruitmentRequest


class RecruitmentRequestFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentRequest model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=RecruitmentRequest.Status.choices)
    recruitment_type = django_filters.ChoiceFilter(choices=RecruitmentRequest.RecruitmentType.choices)
    department = django_filters.NumberFilter(field_name="department_id")
    branch = django_filters.NumberFilter(field_name="branch_id")
    block = django_filters.NumberFilter(field_name="block_id")
    proposer = django_filters.NumberFilter(field_name="proposer_id")

    class Meta:
        model = RecruitmentRequest
        fields = ["name", "code", "status", "recruitment_type", "department", "branch", "block", "proposer"]
