from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentRequest,
)
from libs import ColoredValueSerializer, FieldFilteringSerializerMixin


class JobDescriptionNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested job description references"""

    class Meta:
        model = JobDescription
        fields = ["id", "code", "title"]
        read_only_fields = ["id", "code", "title"]


class EmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references"""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname"]
        read_only_fields = ["id", "code", "fullname"]


class BranchNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested branch references"""

    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class BlockNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested block references"""

    class Meta:
        model = Block
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class DepartmentNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested department references"""

    class Meta:
        model = Department
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class RecruitmentRequestSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for RecruitmentRequest model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for job_description, branch, block,
    department, and proposer.

    Write operations (POST/PUT/PATCH) use _id fields to specify relationships.
    Note: branch_id and block_id are automatically set from department and should
    not be included in request body.
    """

    # Nested read-only serializers for full object representation
    job_description = JobDescriptionNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    proposer = EmployeeNestedSerializer(read_only=True)

    # Colored value fields
    colored_status = ColoredValueSerializer(read_only=True)
    colored_recruitment_type = ColoredValueSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    job_description_id = serializers.PrimaryKeyRelatedField(
        queryset=JobDescription.objects.all(),
        source="job_description",
        write_only=True,
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=False,
        allow_null=True,
    )
    proposer_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="proposer",
        write_only=True,
    )

    default_fields = [
        "id",
        "code",
        "name",
        "job_description",
        "job_description_id",
        "branch",
        "block",
        "department",
        "department_id",
        "proposer",
        "proposer_id",
        "recruitment_type",
        "status",
        "colored_status",
        "colored_recruitment_type",
        "proposed_salary",
        "number_of_positions",
    ]

    class Meta:
        model = RecruitmentRequest
        fields = [
            "id",
            "code",
            "name",
            "job_description",
            "job_description_id",
            "branch",
            "branch_id",
            "block",
            "block_id",
            "department",
            "department_id",
            "proposer",
            "proposer_id",
            "recruitment_type",
            "status",
            "colored_status",
            "colored_recruitment_type",
            "proposed_salary",
            "number_of_positions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "job_description",
            "branch",
            "block",
            "department",
            "proposer",
            "colored_status",
            "colored_recruitment_type",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "status": {"write_only": True},
            "recruitment_type": {"write_only": True},
        }

    def validate(self, attrs):
        """Validate recruitment request data.

        Note: branch and block are auto-set from department in the model,
        so we don't enforce validation here. The model's save method will
        handle setting these fields automatically.
        """
        # Validate number of positions
        number_of_positions = attrs.get("number_of_positions")
        if number_of_positions is not None and number_of_positions < 1:
            raise serializers.ValidationError({"number_of_positions": _("Number of positions must be at least 1.")})

        return attrs
