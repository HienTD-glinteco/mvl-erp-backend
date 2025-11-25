import secrets
from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.api.serializers import EmployeeSerializer
from apps.hrm.models import (
    Employee,
    EmployeeWorkHistory,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)
from libs import ColoredValueSerializer, FieldFilteringSerializerMixin

from .common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    RecruitmentChannelNestedSerializer,
    RecruitmentRequestNestedSerializer,
    RecruitmentSourceNestedSerializer,
)


class RecruitmentCandidateEmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references with department"""

    department = DepartmentNestedSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname", "department"]
        read_only_fields = ["id", "code", "fullname", "department"]


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
    referrer = RecruitmentCandidateEmployeeNestedSerializer(read_only=True)
    employee = EmployeeNestedSerializer(read_only=True)

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
        "employee",
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
            "employee",
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
            "employee",
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


class CandidateToEmployeeSerializer(serializers.Serializer):
    """Serializer for converting a recruitment candidate to an employee.

    This serializer validates the request data and handles the business logic
    for converting a candidate to an employee.
    """

    code_type = serializers.ChoiceField(
        choices=Employee.CodeType.choices,
        required=True,
        help_text=_("Employee type code (MV, CTV, or OS)"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate: RecruitmentCandidate = self.context.get("candidate", None)

    def validate(self, attrs):
        """Validate conversion from candidate to employee."""
        if not self.candidate:
            raise serializers.ValidationError({"non_field_errors": [_("Candidate not found in context.")]})

        # Check if candidate is already converted
        if self.candidate.employee:
            raise serializers.ValidationError(
                {"non_field_errors": [_("This candidate has already been converted to an employee.")]}
            )

        # Check if email already exists in Employee
        if Employee.objects.filter(email=self.candidate.email).exists():
            raise serializers.ValidationError({"email": [_("An employee with this email already exists.")]})

        # Check if citizen_id already exists in Employee
        if Employee.objects.filter(citizen_id=self.candidate.citizen_id).exists():
            raise serializers.ValidationError({"citizen_id": [_("An employee with this citizen ID already exists.")]})

        # Generate random 6-digit attendance code
        attendance_code = str(secrets.randbelow(900000) + 100000)  # nosec B311

        # Prepare employee data from candidate
        # Note: recruitment_candidate_id links the Employee to this candidate (Employee -> Candidate)
        # and candidate.employee links the candidate to the Employee (Candidate -> Employee)
        employee_data = {
            "code_type": attrs["code_type"],
            "fullname": self.candidate.name,
            "username": self.candidate.email,
            "email": self.candidate.email,
            "department_id": self.candidate.department_id,
            "start_date": date.today(),
            "attendance_code": attendance_code,
            "status": Employee.Status.ONBOARDING,
            "citizen_id": self.candidate.citizen_id,
            "phone": self.candidate.phone,
            "recruitment_candidate_id": self.candidate.id,
        }

        # Create employee using serializer
        serializer = EmployeeSerializer(data=employee_data)
        serializer.is_valid(raise_exception=True)

        attrs["employee_serializer"] = serializer

        return attrs

    def create(self, validated_data):
        """Create an employee from the candidate data."""
        employee_serializer: EmployeeSerializer = validated_data["employee_serializer"]
        employee = employee_serializer.save()

        # Link the candidate to the employee
        self.candidate.employee = employee
        self.candidate.save(update_fields=["employee"])

        # Update the automatically created work history to include candidate info
        work_history = EmployeeWorkHistory.objects.filter(employee=employee).first()
        if work_history:
            work_history.note = _("Converted from recruitment candidate {code}").format(code=self.candidate.code)
            work_history.save(update_fields=["note"])

        return employee
