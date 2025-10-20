from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)
from libs import ColoredValueSerializer, FieldFilteringSerializerMixin


class RecruitmentRequestNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment request references"""

    class Meta:
        model = RecruitmentRequest
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]


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


class RecruitmentSourceNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment source references"""

    class Meta:
        model = RecruitmentSource
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]


class RecruitmentChannelNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment channel references"""

    class Meta:
        model = RecruitmentChannel
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]


class RecruitmentCandidateSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for RecruitmentCandidate model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for recruitment_request, branch, block,
    department, recruitment_source, recruitment_channel, and referrer.

    Write operations (POST/PUT/PATCH) use _id fields to specify relationships.
    Note: branch_id, block_id, and department_id are automatically set from
    recruitment_request and should not be included in request body.
    The referrer field is hidden from request body and only updated via custom action.
    """

    # Nested read-only serializers for full object representation
    recruitment_request = RecruitmentRequestNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    recruitment_source = RecruitmentSourceNestedSerializer(read_only=True)
    recruitment_channel = RecruitmentChannelNestedSerializer(read_only=True)
    referrer = EmployeeNestedSerializer(read_only=True)

    # Colored value field
    colored_status = ColoredValueSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    recruitment_request_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentRequest.objects.all(),
        source="recruitment_request",
        write_only=True,
    )
    recruitment_source_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentSource.objects.all(),
        source="recruitment_source",
        write_only=True,
    )
    recruitment_channel_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentChannel.objects.all(),
        source="recruitment_channel",
        write_only=True,
    )

    default_fields = [
        "id",
        "code",
        "name",
        "citizen_id",
        "email",
        "phone",
        "recruitment_request",
        "recruitment_request_id",
        "branch",
        "block",
        "department",
        "recruitment_source",
        "recruitment_source_id",
        "recruitment_channel",
        "recruitment_channel_id",
        "years_of_experience",
        "submitted_date",
        "status",
        "colored_status",
        "onboard_date",
        "note",
        "referrer",
    ]

    class Meta:
        model = RecruitmentCandidate
        fields = [
            "id",
            "code",
            "name",
            "citizen_id",
            "email",
            "phone",
            "recruitment_request",
            "recruitment_request_id",
            "branch",
            "block",
            "department",
            "recruitment_source",
            "recruitment_source_id",
            "recruitment_channel",
            "recruitment_channel_id",
            "years_of_experience",
            "submitted_date",
            "status",
            "colored_status",
            "onboard_date",
            "note",
            "referrer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "recruitment_request",
            "branch",
            "block",
            "department",
            "recruitment_source",
            "recruitment_channel",
            "referrer",
            "colored_status",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "status": {"write_only": True},
        }

    def validate(self, attrs):
        """Validate recruitment candidate data by delegating to model's clean() method

        Note: Field-level validators (e.g., RegexValidator on citizen_id) are automatically
        run by DRF before this method is called, so we only need to call clean() here
        for business logic validation.
        """
        # Create a temporary instance with the provided data for validation
        instance = self.instance or RecruitmentCandidate()

        # Apply attrs to the instance
        for attr, value in attrs.items():
            setattr(instance, attr, value)

        # Call model's clean() method to perform business logic validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, "error_dict"):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError({"non_field_errors": e.messages})

        return attrs


class UpdateReferrerSerializer(serializers.Serializer):
    """Serializer for updating referrer field only"""

    referrer_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        required=False,
        allow_null=True,
    )
