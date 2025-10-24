from rest_framework import serializers

from apps.hrm.models import Employee, InterviewSchedule, RecruitmentCandidate, RecruitmentRequest
from libs import FieldFilteringSerializerMixin


class InterviewScheduleRecruitmentRequestNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment request references in InterviewSchedule"""

    position_title = serializers.CharField(source="job_description.position_title", read_only=True)

    class Meta:
        model = RecruitmentRequest
        fields = ["id", "code", "name", "position_title"]
        read_only_fields = ["id", "code", "name", "position_title"]


class InterviewScheduleRecruitmentCandidateNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment candidate references in InterviewSchedule"""

    class Meta:
        model = RecruitmentCandidate
        fields = ["id", "code", "name", "citizen_id", "email", "phone"]
        read_only_fields = ["id", "code", "name", "citizen_id", "email", "phone"]


class InterviewScheduleEmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references in InterviewSchedule"""

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    block_name = serializers.CharField(source="block.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_name = serializers.CharField(source="position.name", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname", "branch_name", "block_name", "department_name", "position_name"]
        read_only_fields = ["id", "code", "fullname", "branch_name", "block_name", "department_name", "position_name"]


class InterviewScheduleSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for InterviewSchedule model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for recruitment_request and interviewers.

    Write operations (POST/PUT/PATCH) use _id fields to specify relationships.
    Note: interviewers are not included in request body for create/update.
    They should be managed via custom action (update_interviewers).
    """

    # Nested read-only serializers for full object representation
    recruitment_request = InterviewScheduleRecruitmentRequestNestedSerializer(read_only=True)
    interviewers = InterviewScheduleEmployeeNestedSerializer(many=True, read_only=True)

    # Write-only field for POST/PUT/PATCH operations
    recruitment_request_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentRequest.objects.all(),
        source="recruitment_request",
        write_only=True,
    )

    # Computed field
    number_of_candidates = serializers.SerializerMethodField()

    default_fields = [
        "id",
        "title",
        "recruitment_request",
        "recruitment_request_id",
        "interview_type",
        "location",
        "time",
        "note",
        "interviewers",
        "number_of_candidates",
    ]

    class Meta:
        model = InterviewSchedule
        fields = [
            "id",
            "title",
            "recruitment_request",
            "recruitment_request_id",
            "interview_type",
            "location",
            "time",
            "note",
            "interviewers",
            "number_of_candidates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "recruitment_request",
            "interview_candidates",
            "interviewers",
            "number_of_candidates",
            "created_at",
            "updated_at",
        ]

    def get_number_of_candidates(self, obj: InterviewSchedule) -> int:
        """Get the count of recruitment candidates"""
        return obj.interview_candidates.count()


class UpdateInterviewersSerializer(serializers.Serializer):
    """Serializer for updating interviewers in interview schedule"""

    interviewer_ids = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        many=True,
        required=True,
    )
