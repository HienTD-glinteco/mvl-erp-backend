from rest_framework import serializers

from apps.hrm.models import Employee, RecruitmentCandidate, RecruitmentCandidateContactLog
from libs import FieldFilteringSerializerMixin


class RecruitmentCandidateContactLogEmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references in contact log context"""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname"]
        read_only_fields = ["id", "code", "fullname"]
        ref_name = "RecruitmentCandidateContactLogEmployeeNested"


class RecruitmentCandidateNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment candidate references"""

    class Meta:
        model = RecruitmentCandidate
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]


class RecruitmentCandidateContactLogSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for RecruitmentCandidateContactLog model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for employee and recruitment_candidate.

    Write operations (POST/PUT/PATCH) use _id fields to specify relationships.
    """

    # Nested read-only serializers for full object representation
    employee = RecruitmentCandidateContactLogEmployeeNestedSerializer(read_only=True)
    recruitment_candidate = RecruitmentCandidateNestedSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
    )
    recruitment_candidate_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentCandidate.objects.all(),
        source="recruitment_candidate",
        write_only=True,
    )

    default_fields = [
        "id",
        "employee",
        "employee_id",
        "date",
        "method",
        "note",
        "recruitment_candidate",
        "recruitment_candidate_id",
    ]

    class Meta:
        model = RecruitmentCandidateContactLog
        fields = [
            "id",
            "employee",
            "employee_id",
            "date",
            "method",
            "note",
            "recruitment_candidate",
            "recruitment_candidate_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "recruitment_candidate",
            "created_at",
            "updated_at",
        ]
