import django_filters

from apps.hrm.models import RecruitmentRequest


class RecruitmentRequestFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentRequest model"""

    class Meta:
        model = RecruitmentRequest
        fields = {
            "name": ["icontains"],
            "code": ["icontains"],
            "status": ["exact", "in"],
            "recruitment_type": ["exact"],
            "department": ["exact"],
            "branch": ["exact"],
            "block": ["exact"],
            "proposer": ["exact"],
        }
