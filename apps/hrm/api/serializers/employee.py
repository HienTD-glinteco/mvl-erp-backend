from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.api.serializers import SimpleUserSerializer
from apps.hrm.models import Block, Branch, ContractType, Department, Employee, Position, RecruitmentCandidate
from apps.hrm.services.employee import create_position_change_event, create_state_change_event, create_transfer_event
from libs import ColoredValueSerializer, FieldFilteringSerializerMixin


class EmployeeBranchNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested branch references"""

    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class EmployeeBlockNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested block references"""

    class Meta:
        model = Block
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class EmployeeDepartmentNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested department references"""

    class Meta:
        model = Department
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class EmployeePositionNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested position references"""

    class Meta:
        model = Position
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class EmployeeContractTypeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested contract type references"""

    class Meta:
        model = ContractType
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]


class EmployeeRecruitmentCandidateNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested branch references"""

    class Meta:
        model = RecruitmentCandidate
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class EmployeeSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Employee model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for branch, block, department,
    position, contract_type, and user.
    Write operations (POST/PUT/PATCH) only require department_id and other writable fields.
    Branch and block are automatically set based on the department's organizational structure.
    """

    # Nested read-only serializers for full object representation
    branch = EmployeeBranchNestedSerializer(read_only=True)
    block = EmployeeBlockNestedSerializer(read_only=True)
    department = EmployeeDepartmentNestedSerializer(read_only=True)
    position = EmployeePositionNestedSerializer(read_only=True)
    contract_type = EmployeeContractTypeNestedSerializer(read_only=True)
    user = SimpleUserSerializer(read_only=True)
    recruitment_candidate = EmployeeRecruitmentCandidateNestedSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=True,
    )
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(),
        source="position",
        write_only=True,
        required=False,
        allow_null=True,
    )
    contract_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ContractType.objects.all(),
        source="contract_type",
        write_only=True,
        required=False,
        allow_null=True,
    )
    recruitment_candidate_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentCandidate.objects.all(),
        source="recruitment_candidate",
        write_only=True,
        required=False,
        allow_null=True,
    )

    # Colored value properties
    colored_code_type = ColoredValueSerializer(read_only=True)
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "code_type",
            "colored_code_type",
            "code",
            "avatar",
            "fullname",
            "attendance_code",
            "username",
            "email",
            "branch",
            "block",
            "department",
            "department_id",
            "position",
            "position_id",
            "contract_type",
            "contract_type_id",
            "start_date",
            "status",
            "colored_status",
            "resignation_start_date",
            "resignation_end_date",
            "resignation_reason",
            "note",
            "date_of_birth",
            "gender",
            "marital_status",
            "nationality",
            "ethnicity",
            "religion",
            "citizen_id",
            "citizen_id_issued_date",
            "citizen_id_issued_place",
            "phone",
            "personal_email",
            "tax_code",
            "place_of_birth",
            "residential_address",
            "permanent_address",
            "emergency_contact_name",
            "emergency_contact_phone",
            "user",
            "recruitment_candidate",
            "recruitment_candidate_id",
            "is_onboarding_email_sent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "branch",
            "block",
            "department",
            "position",
            "contract_type",
            "avatar",
            "nationality",
            "user",
            "recruitment_candidate",
            "colored_code_type",
            "colored_status",
            "is_onboarding_email_sent",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "status": {"write_only": True},
            "code_type": {"write_only": True},
        }

    def validate(self, attrs):
        """Validate employee data by delegating to model's clean() method.

        Note: Field-level validators (e.g., RegexValidator on citizen_id) are automatically
        run by DRF before this method is called, so we only need to call clean() here
        for business logic validation.
        """
        # Create a temporary instance with the provided data for validation
        instance = self.instance or Employee()

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

    def validate_attendance_code(self, value):
        """Validate attendance_code uniqueness."""
        # Check if attendance_code already exists (excluding current instance on update)
        queryset = Employee.objects.filter(attendance_code=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(_("An employee with this attendance code already exists."))

        return value

    def create(self, validated_data):
        """Create employee and generate initial work history record."""
        employee = super().create(validated_data)
        
        # Create initial status change work history record
        create_state_change_event(
            employee=employee,
            old_status=None,
            new_status=employee.status,
            effective_date=employee.start_date,
            note=_("Employee created"),
        )
        
        return employee

    def update(self, instance, validated_data):
        """Update employee and track changes in work history."""
        # Store old values before update
        old_status = instance.status
        old_position = instance.position
        old_department = instance.department
        
        # Perform the update
        employee = super().update(instance, validated_data)
        
        # Check for status change
        if old_status != employee.status:
            # Determine the effective date based on status
            if employee.status in [
                Employee.Status.RESIGNED,
                Employee.Status.MATERNITY_LEAVE,
                Employee.Status.UNPAID_LEAVE,
            ]:
                effective_date = employee.resignation_start_date or date.today()
                start_date = employee.resignation_start_date
                end_date = employee.resignation_end_date if employee.status == Employee.Status.MATERNITY_LEAVE else None
            else:
                effective_date = employee.start_date or date.today()
                start_date = None
                end_date = None
            
            create_state_change_event(
                employee=employee,
                old_status=old_status,
                new_status=employee.status,
                effective_date=effective_date,
                start_date=start_date,
                end_date=end_date,
            )
        
        # Check for department change (transfer)
        if old_department and old_department.id != employee.department.id:
            create_transfer_event(
                employee=employee,
                old_department=old_department,
                new_department=employee.department,
                old_position=old_position,
                new_position=employee.position,
                effective_date=date.today(),
            )
        # Check for position change (if department didn't change)
        elif old_position and employee.position and old_position.id != employee.position.id:
            create_position_change_event(
                employee=employee,
                old_position=old_position,
                new_position=employee.position,
                effective_date=date.today(),
            )
        
        return employee


class EmployeeBaseStatusActionSerializer(serializers.Serializer):
    """Base serializer for employee actions."""

    start_date = serializers.DateField(required=True)
    description = serializers.CharField(max_length=100, required=False)

    def __init__(self, instance=None, data=..., **kwargs):
        super().__init__(instance, data, **kwargs)
        self.employee: Employee = self.context.get("employee", None)
        self.employee_update_fields = []
        self.old_status = self.employee.status if self.employee else None

    def _validate_employee(self):
        try:
            self.employee.clean()
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, "error_dict"):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError({"non_field_errors": e.messages})

    def validate(self, attrs):
        self._validate_employee()
        return attrs

    def save(self, **kwargs):
        self.employee.save(update_fields=self.employee_update_fields)
        
        # Create work history record after save - to be implemented by subclasses
        self._create_work_history()
    
    def _create_work_history(self):
        """Override in subclasses to create appropriate work history records."""
        pass


class EmployeeActiveActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'active' action."""

    def validate(self, attrs):
        if self.employee.status == Employee.Status.ACTIVE:
            raise serializers.ValidationError({"status": _("Employee is already Active.")})

        self.employee.start_date = attrs["start_date"]
        self.employee.status = Employee.Status.ACTIVE
        self.employee_update_fields.extend(["start_date", "status"])
        self.validated_attrs = attrs
        return super().validate(attrs)
    
    def _create_work_history(self):
        """Create work history record for activation."""
        create_state_change_event(
            employee=self.employee,
            old_status=self.old_status,
            new_status=Employee.Status.ACTIVE,
            effective_date=self.validated_attrs["start_date"],
            note=self.validated_attrs.get("description", ""),
        )


class EmployeeReactiveActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'reactive' action."""

    is_seniority_retained = serializers.BooleanField(default=False, required=False)

    def validate(self, attrs):
        if self.employee.status == Employee.Status.ACTIVE:
            raise serializers.ValidationError({"status": _("Employee is already Active.")})

        self.employee.start_date = attrs["start_date"]
        self.employee.status = Employee.Status.ACTIVE
        self.employee_update_fields.extend(["start_date", "status"])
        self.validated_attrs = attrs
        return super().validate(attrs)
    
    def _create_work_history(self):
        """Create work history record for reactivation."""
        # Create a state change event for reactivation with retain_seniority flag
        from apps.hrm.models import EmployeeWorkHistory
        
        previous_data = {"status": self.old_status}
        
        old_status_display = _(self.old_status)
        new_status_display = _(Employee.Status.ACTIVE)
        detail = _("Status changed from {old_status} to {new_status} (Reactivated)").format(
            old_status=old_status_display, new_status=new_status_display
        )
        
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            date=self.validated_attrs["start_date"],
            status=Employee.Status.ACTIVE,
            retain_seniority=self.validated_attrs.get("is_seniority_retained", False),
            note=self.validated_attrs.get("description", ""),
            detail=detail,
            previous_data=previous_data,
        )


class EmployeeResignedActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'resigned' action."""

    resignation_reason = serializers.ChoiceField(choices=Employee.ResignationReason.choices, required=True)

    def validate(self, attrs):
        if self.employee.status in [
            Employee.Status.RESIGNED,
            Employee.Status.UNPAID_LEAVE,
            Employee.Status.MATERNITY_LEAVE,
        ]:
            raise serializers.ValidationError({"status": _("Employee is already in a resigned status.")})

        self.employee.resignation_start_date = attrs["start_date"]
        self.employee.status = Employee.Status.RESIGNED
        self.employee.resignation_reason = attrs["resignation_reason"]
        self.employee_update_fields.extend(["resignation_start_date", "status", "resignation_reason"])
        self.validated_attrs = attrs
        return super().validate(attrs)
    
    def _create_work_history(self):
        """Create work history record for resignation."""
        from apps.hrm.models import EmployeeWorkHistory
        
        previous_data = {"status": self.old_status}
        
        old_status_display = _(self.old_status)
        new_status_display = _(Employee.Status.RESIGNED)
        detail = _("Status changed from {old_status} to {new_status}").format(
            old_status=old_status_display, new_status=new_status_display
        )
        
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            date=self.validated_attrs["start_date"],
            status=Employee.Status.RESIGNED,
            from_date=self.employee.resignation_start_date,
            resignation_reason=self.validated_attrs["resignation_reason"],
            note=self.validated_attrs.get("description", ""),
            detail=detail,
            previous_data=previous_data,
        )


class EmployeeMaternityLeaveActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'maternity_leave' action."""

    end_date = serializers.DateField(required=True)

    def validate(self, attrs):
        if self.employee.status in [
            Employee.Status.RESIGNED,
            Employee.Status.UNPAID_LEAVE,
            Employee.Status.MATERNITY_LEAVE,
        ]:
            raise serializers.ValidationError({"status": _("Employee is already in a resigned status.")})

        self.employee.resignation_start_date = attrs["start_date"]
        self.employee.resignation_end_date = attrs["end_date"]
        self.employee.status = Employee.Status.MATERNITY_LEAVE
        self.employee.resignation_reason = None
        self.employee_update_fields.extend(
            ["resignation_start_date", "status", "resignation_start_date", "resignation_end_date"]
        )
        self.validated_attrs = attrs
        return super().validate(attrs)
    
    def _create_work_history(self):
        """Create work history record for maternity leave."""
        create_state_change_event(
            employee=self.employee,
            old_status=self.old_status,
            new_status=Employee.Status.MATERNITY_LEAVE,
            effective_date=self.validated_attrs["start_date"],
            start_date=self.employee.resignation_start_date,
            end_date=self.employee.resignation_end_date,
            note=self.validated_attrs.get("description", ""),
        )
