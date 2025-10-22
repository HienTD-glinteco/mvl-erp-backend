import django_filters

from apps.hrm.models import RecruitmentCandidate


class RecruitmentCandidateFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentCandidate model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")
    citizen_id = django_filters.CharFilter(lookup_expr="exact")
    status = django_filters.MultipleChoiceFilter(choices=RecruitmentCandidate.Status.choices)
    recruitment_request = django_filters.BaseInFilter(field_name="recruitment_request_id")
    department = django_filters.NumberFilter(field_name="department_id")
    branch = django_filters.NumberFilter(field_name="branch_id")
    block = django_filters.NumberFilter(field_name="block_id")
    recruitment_source = django_filters.NumberFilter(field_name="recruitment_source_id")
    recruitment_channel = django_filters.NumberFilter(field_name="recruitment_channel_id")
    referrer = django_filters.NumberFilter(field_name="referrer_id")
    submitted_date_from = django_filters.DateFilter(field_name="submitted_date", lookup_expr="gte")
    submitted_date_to = django_filters.DateFilter(field_name="submitted_date", lookup_expr="lte")
    onboard_date_from = django_filters.DateFilter(field_name="onboard_date", lookup_expr="gte")
    onboard_date_to = django_filters.DateFilter(field_name="onboard_date", lookup_expr="lte")

    class Meta:
        model = RecruitmentCandidate
        fields = [
            "name",
            "code",
            "email",
            "phone",
            "citizen_id",
            "status",
            "recruitment_request",
            "department",
            "branch",
            "block",
            "recruitment_source",
            "recruitment_channel",
            "referrer",
            "submitted_date_from",
            "submitted_date_to",
            "onboard_date_from",
            "onboard_date_to",
        ]
