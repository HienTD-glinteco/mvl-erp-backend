from django_filters import rest_framework as filters

from apps.hrm.models import InterviewCandidate


class InterviewCandidateFilterSet(filters.FilterSet):
    """FilterSet for InterviewCandidate model"""

    recruitment_candidate_id = filters.NumberFilter(field_name="recruitment_candidate__id")
    interview_schedule_id = filters.NumberFilter(field_name="interview_schedule__id")
    interview_time_after = filters.DateTimeFilter(field_name="interview_time", lookup_expr="gte")
    interview_time_before = filters.DateTimeFilter(field_name="interview_time", lookup_expr="lte")
    email_sent = filters.BooleanFilter(field_name="email_sent_at", lookup_expr="isnull", exclude=True)

    class Meta:
        model = InterviewCandidate
        fields = [
            "recruitment_candidate_id",
            "interview_schedule_id",
            "interview_time_after",
            "interview_time_before",
            "email_sent",
        ]
