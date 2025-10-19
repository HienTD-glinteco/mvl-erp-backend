from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.hrm.models import (
    Employee,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)
from libs import FieldFilteringSerializerMixin


class RecruitmentExpenseRecruitmentRequestNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment request references in expense context"""

    class Meta:
        model = RecruitmentRequest
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]
        ref_name = "RecruitmentExpenseRecruitmentRequestNested"


class RecruitmentExpenseEmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references in expense context"""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname"]
        read_only_fields = ["id", "code", "fullname"]
        ref_name = "RecruitmentExpenseEmployeeNested"


class RecruitmentExpenseRecruitmentSourceNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment source references in expense context"""

    class Meta:
        model = RecruitmentSource
        fields = ["id", "code", "name", "allow_referral"]
        read_only_fields = ["id", "code", "name", "allow_referral"]
        ref_name = "RecruitmentExpenseRecruitmentSourceNested"


class RecruitmentExpenseRecruitmentChannelNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested recruitment channel references in expense context"""

    class Meta:
        model = RecruitmentChannel
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]
        ref_name = "RecruitmentExpenseRecruitmentChannelNested"


class RecruitmentExpenseSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for RecruitmentExpense model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for recruitment_source, recruitment_channel,
    recruitment_request, referee, and referrer.

    Write operations (POST/PUT/PATCH) use _id fields to specify relationships.
    """

    # Nested read-only serializers for full object representation
    recruitment_source = RecruitmentExpenseRecruitmentSourceNestedSerializer(read_only=True)
    recruitment_channel = RecruitmentExpenseRecruitmentChannelNestedSerializer(read_only=True)
    recruitment_request = RecruitmentExpenseRecruitmentRequestNestedSerializer(read_only=True)
    referee = RecruitmentExpenseEmployeeNestedSerializer(read_only=True)
    referrer = RecruitmentExpenseEmployeeNestedSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
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
    recruitment_request_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentRequest.objects.all(),
        source="recruitment_request",
        write_only=True,
    )
    referee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="referee",
        write_only=True,
        required=False,
        allow_null=True,
    )
    referrer_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="referrer",
        write_only=True,
        required=False,
        allow_null=True,
    )

    # Computed field
    avg_cost = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    default_fields = [
        "id",
        "date",
        "recruitment_source",
        "recruitment_source_id",
        "recruitment_channel",
        "recruitment_channel_id",
        "recruitment_request",
        "recruitment_request_id",
        "num_candidates_participated",
        "total_cost",
        "num_candidates_hired",
        "avg_cost",
        "referee",
        "referee_id",
        "referrer",
        "referrer_id",
        "activity",
        "note",
    ]

    class Meta:
        model = RecruitmentExpense
        fields = [
            "id",
            "date",
            "recruitment_source",
            "recruitment_source_id",
            "recruitment_channel",
            "recruitment_channel_id",
            "recruitment_request",
            "recruitment_request_id",
            "num_candidates_participated",
            "total_cost",
            "num_candidates_hired",
            "avg_cost",
            "referee",
            "referee_id",
            "referrer",
            "referrer_id",
            "activity",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "recruitment_source",
            "recruitment_channel",
            "recruitment_request",
            "referee",
            "referrer",
            "avg_cost",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate recruitment expense data by delegating to model's clean() method"""
        # Create a temporary instance with the provided data for validation
        instance = self.instance or RecruitmentExpense()

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
