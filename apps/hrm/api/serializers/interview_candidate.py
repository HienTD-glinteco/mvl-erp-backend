from rest_framework import serializers

from apps.hrm.models import InterviewCandidate, InterviewSchedule, RecruitmentCandidate
from libs import FieldFilteringSerializerMixin


class InterviewCandidateRecruitmentCandidateNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment candidate references in InterviewCandidate"""

    class Meta:
        model = RecruitmentCandidate
        fields = ["id", "code", "name", "citizen_id", "email", "phone"]
        read_only_fields = ["id", "code", "name", "citizen_id", "email", "phone"]


class InterviewCandidateInterviewScheduleNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested interview schedule references in InterviewCandidate"""

    class Meta:
        model = InterviewSchedule
        fields = ["id", "title", "interview_type", "location", "time"]
        read_only_fields = ["id", "title", "interview_type", "location", "time"]


class InterviewCandidateSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for InterviewCandidate model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.
    """

    # Nested read-only serializers for full object representation
    recruitment_candidate = InterviewCandidateRecruitmentCandidateNestedSerializer(read_only=True)
    interview_schedule = InterviewCandidateInterviewScheduleNestedSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    recruitment_candidate_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentCandidate.objects.all(),
        source="recruitment_candidate",
        write_only=True,
    )
    interview_schedule_id = serializers.PrimaryKeyRelatedField(
        queryset=InterviewSchedule.objects.all(),
        source="interview_schedule",
        write_only=True,
    )

    default_fields = [
        "id",
        "recruitment_candidate",
        "recruitment_candidate_id",
        "interview_schedule",
        "interview_schedule_id",
        "interview_time",
        "email_sent_at",
    ]

    class Meta:
        model = InterviewCandidate
        fields = [
            "id",
            "recruitment_candidate",
            "recruitment_candidate_id",
            "interview_schedule",
            "interview_schedule_id",
            "interview_time",
            "email_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "recruitment_candidate",
            "interview_schedule",
            "created_at",
            "updated_at",
        ]
