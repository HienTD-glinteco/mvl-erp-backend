from django_filters import rest_framework as filters

from apps.hrm.models import InterviewSchedule


class InterviewScheduleFilterSet(filters.FilterSet):
    """FilterSet for InterviewSchedule model"""

    title = filters.CharFilter(lookup_expr="icontains")
    recruitment_request_id = filters.NumberFilter(field_name="recruitment_request__id")
    recruitment_candidate_id = filters.NumberFilter(field_name="interview_candidates__recruitment_candidate_id")
    interview_type = filters.ChoiceFilter(choices=InterviewSchedule.InterviewType.choices)
    location = filters.CharFilter(lookup_expr="icontains")
    time_after = filters.DateTimeFilter(field_name="time", lookup_expr="gte")
    time_before = filters.DateTimeFilter(field_name="time", lookup_expr="lte")

    class Meta:
        model = InterviewSchedule
        fields = [
            "title",
            "recruitment_request_id",
            "recruitment_candidate_id",
            "interview_type",
            "location",
            "time_after",
            "time_before",
        ]
