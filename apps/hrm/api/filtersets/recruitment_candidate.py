import django_filters

from apps.hrm.models import RecruitmentCandidate


class RecruitmentCandidateFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentCandidate model"""

    class Meta:
        model = RecruitmentCandidate
        fields = {
            "name": ["icontains"],
            "code": ["icontains"],
            "email": ["icontains"],
            "phone": ["icontains"],
            "citizen_id": ["exact"],
            "status": ["exact", "in"],
            "recruitment_request": ["exact", "in"],
            "department": ["exact"],
            "branch": ["exact"],
            "block": ["exact"],
            "recruitment_source": ["exact"],
            "recruitment_channel": ["exact"],
            "referrer": ["exact"],
            "submitted_date": ["exact", "gte", "lte"],
            "onboard_date": ["exact", "gte", "lte"],
        }
