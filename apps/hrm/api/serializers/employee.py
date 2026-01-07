from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.transaction import atomic
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.api.serializers import NationalitySerializer, SimpleUserSerializer
from apps.core.models.nationality import Nationality
from apps.files.api.serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.files.models import FileModel
from apps.hrm.constants import EmployeeType
from apps.hrm.models import (
    BankAccount,
    Block,
    Branch,
    Contract,
    Decision,
    Department,
    Employee,
    EmployeeWorkHistory,
    Position,
    RecruitmentCandidate,
)
from apps.hrm.services.employee import (
    create_position_change_event,
    create_state_change_event,
    create_transfer_event,
)
from apps.hrm.tasks.timesheets import recalculate_timesheets
from libs import ColoredValueSerializer, FieldFilteringSerializerMixin

from .common_nested import BankNestedSerializer


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


class EmployeeRecruitmentCandidateNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested branch references"""

    class Meta:
        model = RecruitmentCandidate
        fields = ["id", "name", "code", "years_of_experience"]
        read_only_fields = ["id", "name", "code", "years_of_experience"]


class EmployeeBankAccountNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested bank account references"""

    bank = BankNestedSerializer(read_only=True)

    class Meta:
        model = BankAccount
        fields = ["id", "account_number", "account_name", "bank"]
        read_only_fields = fields


class EmployeeSerializer(FileConfirmSerializerMixin, FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Employee model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for branch, block, department,
    position, and user.
    Write operations (POST/PUT/PATCH) only require department_id and other writable fields.
    Branch and block are automatically set based on the department's organizational structure.
    """

    # Nested read-only serializers for full object representation
    branch = EmployeeBranchNestedSerializer(read_only=True)
    block = EmployeeBlockNestedSerializer(read_only=True)
    department = EmployeeDepartmentNestedSerializer(read_only=True)
    position = EmployeePositionNestedSerializer(read_only=True)
    user = SimpleUserSerializer(read_only=True)
    recruitment_candidate = EmployeeRecruitmentCandidateNestedSerializer(read_only=True)
    avatar = FileSerializer(read_only=True)
    citizen_id_file = FileSerializer(read_only=True)
    default_bank_account = EmployeeBankAccountNestedSerializer(read_only=True)
    nationality = NationalitySerializer(read_only=True)

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
    recruitment_candidate_id = serializers.PrimaryKeyRelatedField(
        queryset=RecruitmentCandidate.objects.all(),
        source="recruitment_candidate",
        write_only=True,
        required=False,
        allow_null=True,
    )
    citizen_id_file_id = serializers.PrimaryKeyRelatedField(
        queryset=FileModel.objects.all(),
        source="citizen_id_file",
        write_only=True,
        required=False,
        allow_null=True,
    )
    nationality_id = serializers.PrimaryKeyRelatedField(
        queryset=Nationality.objects.all(),
        source="nationality",
        write_only=True,
        required=False,
        allow_null=True,
    )

    # Colored value properties
    colored_code_type = ColoredValueSerializer(read_only=True)
    colored_status = ColoredValueSerializer(read_only=True)

    file_confirm_fields = ["avatar", "citizen_id_file"]

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
            "employee_type",
            "branch",
            "block",
            "department",
            "department_id",
            "default_bank_account",
            "position",
            "position_id",
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
            "citizen_id_file",
            "citizen_id_file_id",
            "phone",
            "personal_email",
            "tax_code",
            "place_of_birth",
            "nationality_id",
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
            "employee_type",
            "position",
            "nationality",
            "user",
            "recruitment_candidate",
            "citizen_id_file",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store original values when instance exists
        if self.instance and isinstance(self.instance, Employee):
            self._original_status = self.instance.status
            self._original_position = self.instance.position
            self._original_department = self.instance.department
        else:
            self._original_status = None
            self._original_position = None
            self._original_department = None

    def validate(self, attrs):
        """Validate employee data by delegating to model's clean() method.

        Also checks for restricted field modifications during updates.

        Note: Field-level validators (e.g., RegexValidator on citizen_id) are automatically
        run by DRF before this method is called, so we only need to call clean() here
        for business logic validation.
        """
        # Check for restricted field modifications during updates
        if self.instance:
            restricted_fields = {
                "department": "transfer",
                "position": "transfer",
                "status": "active/reactive/resigned/maternity_leave",
                "branch": "auto-set from department",
                "block": "auto-set from department",
            }

            errors = {}
            for field, action in restricted_fields.items():
                if field in attrs:
                    # Only raise error if the value is actually changing
                    old_value = getattr(self.instance, field, None)
                    new_value = attrs[field]
                    if old_value != new_value:
                        errors[field] = _(
                            "This field cannot be updated directly. Use the '{action}' action endpoint instead."
                        ).format(action=action)

            if errors:
                raise serializers.ValidationError(errors)

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
        """Update employee and track changes in work history.

        Note: Restricted field validation is performed in validate() method.
        """
        # Use stored original values before update
        old_status = self._original_status
        old_position = self._original_position
        old_department = self._original_department

        # Perform the update
        employee = super().update(instance, validated_data)

        # Create work history events for changes
        self._create_update_work_history_events(employee, old_status, old_position, old_department)

        return employee

    def _create_update_work_history_events(self, employee, old_status, old_position, old_department):
        """Create work history events based on what changed during update."""
        # Check for status change
        if old_status != employee.status:
            # Determine the effective date based on status
            if employee.status in Employee.Status.get_leave_statuses():
                effective_date = employee.resignation_start_date or timezone.localdate()
                start_date = employee.resignation_start_date
                end_date = (
                    employee.resignation_end_date if employee.status == Employee.Status.MATERNITY_LEAVE else None
                )
            else:
                effective_date = employee.start_date or timezone.localdate()
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
        if old_department and employee.department and old_department.id != employee.department.id:
            create_transfer_event(
                employee=employee,
                old_department=old_department,
                new_department=employee.department,
                old_position=old_position,
                new_position=employee.position,
                effective_date=timezone.localdate(),
            )
        # Check for position change (if department didn't change)
        elif old_position and employee.position and old_position.id != employee.position.id:
            create_position_change_event(
                employee=employee,
                old_position=old_position,
                new_position=employee.position,
                effective_date=timezone.localdate(),
            )


class EmployeeDecisionMixin(serializers.Serializer):
    decision_id = serializers.PrimaryKeyRelatedField(
        queryset=Decision.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_decision_id(self, value):
        if value and value.signing_status != Decision.SigningStatus.ISSUED:
            raise serializers.ValidationError(_("The selected decision must be in 'Issued' status."))
        return value


class EmployeeBaseStatusActionSerializer(EmployeeDecisionMixin, serializers.Serializer):
    """Base serializer for employee actions."""

    start_date = serializers.DateField(required=True)
    description = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)

    def __init__(self, instance=None, data=..., **kwargs):
        super().__init__(instance, data, **kwargs)
        self.employee: Employee = self.context.get("employee", None)
        self.employee_update_fields = []
        self.old_status = self.employee.status if self.employee else None

    def validate_start_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(_("Start date cannot be in the future."))
        return value

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

    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True),
        required=True,
    )
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.filter(is_active=True),
        required=True,
    )

    def validate(self, attrs):
        if self.employee.status != Employee.Status.ONBOARDING:
            raise serializers.ValidationError(
                {"status": _("Only employees with 'Onboarding' status can be activated.")}
            )

        self.employee.start_date = attrs["start_date"]
        self.employee.status = Employee.Status.ACTIVE
        self.employee.department = attrs["department_id"]
        self.employee.position = attrs["position_id"]

        # Explicitly update block and branch from department to ensure data consistency
        if self.employee.department:
            self.employee.block = self.employee.department.block
            self.employee.branch = self.employee.department.branch

        self.employee_update_fields.extend(["start_date", "status", "department", "position", "block", "branch"])
        return super().validate(attrs)

    def _create_work_history(self):
        """Create work history record for activation."""
        department = self.validated_data["department_id"]
        position = self.validated_data["position_id"]
        extra_detail = _("Assigned to {department} - {position}").format(
            department=department.name,
            position=position.name,
        )

        create_state_change_event(
            employee=self.employee,
            old_status=self.old_status,
            new_status=Employee.Status.ACTIVE,
            effective_date=self.validated_data["start_date"],
            note=self.validated_data.get("description", ""),
            extra_detail=extra_detail,
            decision=self.validated_data.get("decision_id"),
        )


class EmployeeReactiveActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'reactive' action."""

    is_seniority_retained = serializers.BooleanField(default=False, required=False)

    def validate_start_date(self, value):
        value = super().validate_start_date(value)
        if value < self.employee.resignation_start_date:
            raise serializers.ValidationError(
                _("Start date cannot be earlier than the resignation start date of {date}.").format(
                    date=self.employee.resignation_start_date
                )
            )
        return value

    def validate(self, attrs):
        if self.employee.status != Employee.Status.RESIGNED:
            raise serializers.ValidationError(
                {"status": _("Only employees with 'Resigned' status can be reactivated.")}
            )

        # Store resignation data before modifying employee
        if self.old_status == Employee.Status.RESIGNED:
            self._old_resignation_start_date = self.employee.resignation_start_date
            self._old_resignation_reason = self.employee.resignation_reason

        self.employee.start_date = attrs["start_date"]
        self.employee.status = Employee.Status.ACTIVE
        self.employee_update_fields.extend(["start_date", "status"])
        return super().validate(attrs)

    def _create_work_history(self):
        """Create work history record for reactivation.

        Creates a RETURN_TO_WORK event if previous status was RESIGNED,
        otherwise creates a CHANGE_STATUS event.
        """
        # Only create RETURN_TO_WORK event if previous status was RESIGNED
        if self.old_status == Employee.Status.RESIGNED:
            previous_data = {
                "status": self.old_status,
                "resignation_start_date": str(self._old_resignation_start_date)
                if self._old_resignation_start_date
                else None,
                "resignation_reason": self._old_resignation_reason,
            }

            old_status_display = _(Employee.Status.RESIGNED.label)
            new_status_display = _(Employee.Status.ACTIVE.label)
            detail = _(
                "Employee returned to work from resigned status. Status changed from {old_status} to {new_status}."
            ).format(old_status=old_status_display, new_status=new_status_display)

            if self.validated_data.get("is_seniority_retained", False):
                detail += " " + _("Seniority retained from previous employment period.")

            EmployeeWorkHistory.objects.create(
                employee=self.employee,
                name=EmployeeWorkHistory.EventType.RETURN_TO_WORK,
                date=self.validated_data["start_date"],
                status=Employee.Status.ACTIVE,
                retain_seniority=self.validated_data.get("is_seniority_retained", False),
                note=self.validated_data.get("description", ""),
                detail=detail,
                previous_data=previous_data,
                decision=self.validated_data.get("decision_id"),
            )
        else:
            # For other statuses (MATERNITY_LEAVE, UNPAID_LEAVE), use CHANGE_STATUS event
            previous_data = {"status": self.old_status}

            old_status_display = _(self.old_status)
            new_status_display = _(Employee.Status.ACTIVE)
            detail = _("Status changed from {old_status} to {new_status} (Reactivated)").format(
                old_status=old_status_display, new_status=new_status_display
            )

            EmployeeWorkHistory.objects.create(
                employee=self.employee,
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                date=self.validated_data["start_date"],
                status=Employee.Status.ACTIVE,
                retain_seniority=self.validated_data.get("is_seniority_retained", False),
                note=self.validated_data.get("description", ""),
                detail=detail,
                previous_data=previous_data,
                decision=self.validated_data.get("decision_id"),
            )


class EmployeeResignedActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'resigned' action."""

    resignation_reason = serializers.ChoiceField(choices=Employee.ResignationReason.choices, required=True)

    def validate_start_date(self, value):
        value = super().validate_start_date(value)
        if value < self.employee.start_date:
            raise serializers.ValidationError(
                _(
                    "Resignation start date cannot be earlier than the employee's start date or latest comeback start date."
                )
            )
        return value

    def validate(self, attrs):
        if self.employee.status not in [
            Employee.Status.ACTIVE,
            Employee.Status.MATERNITY_LEAVE,
            Employee.Status.UNPAID_LEAVE,
        ]:
            raise serializers.ValidationError(
                {"status": _("Employee must be in an active or leave status to resign.")}
            )

        self.employee.resignation_start_date = attrs["start_date"]
        self.employee.status = Employee.Status.RESIGNED
        self.employee.resignation_reason = attrs["resignation_reason"]
        self.employee_update_fields.extend(["resignation_start_date", "status", "resignation_reason"])
        self._old_start_date = self.employee.start_date
        return super().validate(attrs)

    def _create_work_history(self):
        """Create work history record for resignation."""
        previous_data = {
            "status": self.old_status,
            "start_date": str(self._old_start_date) if self._old_start_date else None,
            "end_date": str(self.validated_data["start_date"]),
        }

        old_status_display = _(self.old_status)
        new_status_display = _(Employee.Status.RESIGNED)
        detail = _("Status changed from {old_status} to {new_status}").format(
            old_status=old_status_display, new_status=new_status_display
        )

        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            date=self.validated_data["start_date"],
            status=Employee.Status.RESIGNED,
            from_date=self.validated_data["start_date"],
            resignation_reason=self.validated_data["resignation_reason"],
            note=self.validated_data.get("description", ""),
            detail=detail,
            previous_data=previous_data,
            decision=self.validated_data.get("decision_id"),
        )


class EmployeeMaternityLeaveActionSerializer(EmployeeBaseStatusActionSerializer):
    """Serializer for the 'maternity_leave' action."""

    end_date = serializers.DateField(required=True)

    def __init__(self, instance=None, data=..., **kwargs):
        super().__init__(instance, data, **kwargs)
        self._is_reactivated = False

    def validate(self, attrs):
        if self.employee.status not in [Employee.Status.ACTIVE, Employee.Status.UNPAID_LEAVE]:
            raise serializers.ValidationError(
                {"status": _("Only active or unpaid leave employees can go on maternity leave.")}
            )

        end_date = attrs["end_date"]
        if end_date < timezone.now().date():
            self.employee.status = Employee.Status.ACTIVE
            self._is_reactivated = True
        else:
            self.employee.status = Employee.Status.MATERNITY_LEAVE

        self.employee.resignation_start_date = attrs["start_date"]
        self.employee.resignation_end_date = end_date
        self.employee.resignation_reason = None
        self.employee_update_fields.extend(["resignation_start_date", "resignation_end_date", "status"])
        return super().validate(attrs)

    def _create_work_history(self):
        """Create work history record for maternity leave."""
        create_state_change_event(
            employee=self.employee,
            old_status=self.old_status,
            new_status=Employee.Status.MATERNITY_LEAVE,
            effective_date=self.validated_data["start_date"],
            start_date=self.validated_data["start_date"],
            end_date=self.validated_data["end_date"],
            note=self.validated_data.get("description", ""),
            decision=self.validated_data.get("decision_id"),
        )
        if self._is_reactivated:
            create_state_change_event(
                employee=self.employee,
                old_status=Employee.Status.MATERNITY_LEAVE,
                new_status=Employee.Status.ACTIVE,
                effective_date=self.validated_data["end_date"],
                note=_("Maternity leave ended, employee returned to work."),
            )


class EmployeeTransferActionSerializer(EmployeeDecisionMixin, serializers.Serializer):
    """Serializer for the 'transfer' action."""

    date = serializers.DateField(required=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=True,
    )
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(),
        required=True,
    )
    note = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, instance=None, data=..., **kwargs):
        super().__init__(instance, data, **kwargs)
        self.employee: Employee = self.context.get("employee", None)
        self.employee_update_fields = []
        self.old_department = self.employee.department if self.employee else None
        self.old_position = self.employee.position if self.employee else None

    def validate(self, attrs):
        """Validate transfer data."""
        department = attrs["department_id"]
        position = attrs["position_id"]

        # Update employee's department and position
        self.employee.department = department
        self.employee.position = position
        self.employee_update_fields.extend(["department", "position", "block", "branch"])

        # Validate using model's clean method
        try:
            self.employee.clean()
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, "error_dict"):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError({"non_field_errors": e.messages})

        return attrs

    def save(self, **kwargs):
        """Save employee transfer and create work history record."""
        self.employee.save(update_fields=self.employee_update_fields)

        # Create work history record for transfer
        create_transfer_event(
            employee=self.employee,
            old_department=self.old_department,
            new_department=self.employee.department,
            old_position=self.old_position,
            new_position=self.employee.position,
            effective_date=self.validated_data["date"],
            note=self.validated_data.get("note", ""),
            decision=self.validated_data.get("decision_id"),
        )


class EmployeeChangeTypeActionSerializer(EmployeeDecisionMixin, serializers.Serializer):
    """Serializer for the 'change_employee_type' action.

    Fields:
      - date: Event effective date
      - employee_type: EmployeeType choice
      - note: optional description
    """

    date = serializers.DateField(required=True)
    employee_type = serializers.ChoiceField(choices=EmployeeType.choices, required=True)

    note = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.employee: Employee = self.context.get("employee", None)
        self.old_employee_type = self.employee.employee_type if self.employee else None

    def validate_date(self, effective_date):
        """Validate effective date."""
        today = timezone.localdate()
        start_of_month = today.replace(day=1)

        if effective_date < start_of_month:
            raise serializers.ValidationError(
                _("Effective date must be greater than or equal to the first day of the current month.")
            )

        if effective_date > today:
            raise serializers.ValidationError(_("Effective date cannot be in the future."))
        return effective_date

    def validate_employee_type(self, employee_type):
        """Validate that the new employee_type is different from the current one."""
        if self.employee and employee_type == self.employee.employee_type:
            raise serializers.ValidationError(_("The new employee type must be different from the current type."))
        return employee_type

    def validate(self, attrs):
        effective_date = attrs["date"]

        # Prevent setting effective date less than latest history date
        latest_history = (
            self.employee.work_histories.filter(name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE)
            .order_by("-from_date")
            .first()
            if self.employee
            else None
        )
        # Compare only using from_date
        if latest_history and latest_history.from_date and effective_date < latest_history.from_date:
            raise serializers.ValidationError(
                {"date": _("Effective date cannot be earlier than the latest work history date.")}
            )

        # Assign new employee_type and validate model
        self.employee.employee_type = attrs["employee_type"]

        try:
            self.employee.clean()
        except DjangoValidationError as e:
            if hasattr(e, "error_dict"):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError({"non_field_errors": e.messages})

        return attrs

    @atomic
    def save(self, **kwargs):
        """Save employee and create a work history change record via signal."""
        # Set context for signal to create EmployeeWorkHistory
        self.employee._change_type_signal_context = {
            "effective_date": self.validated_data["date"],
            "note": self.validated_data.get("note", ""),
            "decision": self.validated_data.get("decision_id"),
        }

        self.employee.save(update_fields=["employee_type", "updated_at"])

        # Trigger timesheet recalculation
        recalculate_timesheets.delay(employee_id=self.employee.id, start_date_str=str(self.validated_data["date"]))


class EmployeeAvatarSerializer(FileConfirmSerializerMixin, serializers.Serializer):
    """
    Serializer for updating employee avatar.

    Uses FileConfirmSerializerMixin to automatically handle file confirmation
    and assignment to the employee.avatar field.

    Expected request format:
    {
        "files": {
            "avatar": "file-token-from-presign-response"
        }
    }
    """

    file_confirm_fields = ["avatar"]

    class Meta:
        fields: list[str] = []

    def update(self, instance, validated_data):
        """
        Update method required by DRF Serializer.

        The actual avatar assignment is handled by FileConfirmSerializerMixin
        in the save() method, so we just return the instance here.
        """
        return instance


class EmployeeExportXLSXSerializer(serializers.ModelSerializer):
    """Serializer for exporting Employee data to Excel.

    This serializer flattens related objects and provides additional computed fields
    for comprehensive employee data export.
    """

    # Index field (will be computed in the view)
    no = serializers.SerializerMethodField(read_only=True, label=_("No."))

    # Related fields
    contract_type = serializers.SerializerMethodField(read_only=True, label=_("Contract Type"))
    position__name = serializers.CharField(source="position.name", read_only=True, label=_("Position"))
    branch__name = serializers.CharField(source="branch.name", read_only=True, label=_("Branch"))
    block__name = serializers.CharField(source="block.name", read_only=True, label=_("Block"))
    department__name = serializers.CharField(source="department.name", read_only=True, label=_("Department"))

    # Latest EmployeeWorkHistory fields
    latest_work_history_resignation_reason = serializers.SerializerMethodField(
        read_only=True, label=_("Resignation Reason")
    )
    latest_work_history_from_date = serializers.SerializerMethodField(read_only=True, label=_("Resignation Date"))

    # Default BankAccount fields (using is_primary field per actual model implementation)
    default_bank_name = serializers.SerializerMethodField(read_only=True, label=_("Bank Name"))
    default_bank_account_number = serializers.SerializerMethodField(read_only=True, label=_("Bank Account Number"))

    # Emergency contact combined field
    emergency_contact = serializers.SerializerMethodField(read_only=True, label=_("Emergency Contact"))

    # Nationality name
    nationality__name = serializers.CharField(source="nationality.name", read_only=True, label=_("Nationality"))

    def get_no(self, obj: Employee):
        """Get the index number from context (1-based)."""
        # This will be set from the view when preparing the data
        return getattr(obj, "_export_index", "")

    def get_contract_type(self, obj: Employee):
        """Get the contract type name of the active contract."""
        active_contract = obj.contracts.filter(status=Contract.ContractStatus.ACTIVE).first()
        if active_contract and active_contract.contract_type:
            return active_contract.contract_type.name
        return ""

    def get_latest_work_history_resignation_reason(self, obj: Employee):
        """Get resignation_reason from the latest EmployeeWorkHistory record."""
        latest_history = obj.work_histories.order_by("-date", "-created_at").first()
        if latest_history and latest_history.resignation_reason:
            return latest_history.get_resignation_reason_display()
        return ""

    def get_latest_work_history_from_date(self, obj: Employee):
        """Get from_date from the latest EmployeeWorkHistory record."""
        latest_history = obj.work_histories.order_by("-date", "-created_at").first()
        if latest_history and latest_history.from_date:
            return latest_history.from_date.isoformat()
        return ""

    def get_default_bank_name(self, obj: Employee):
        """Get bank name from the default BankAccount."""
        if obj.default_bank_account and obj.default_bank_account.bank:
            return obj.default_bank_account.bank.name
        return ""

    def get_default_bank_account_number(self, obj: Employee):
        """Get account number from the default BankAccount."""
        if obj.default_bank_account:
            return obj.default_bank_account.account_number
        return ""

    def get_emergency_contact(self, obj: Employee):
        """Get emergency contact as 'name - phone' format."""
        if obj.emergency_contact_name and obj.emergency_contact_phone:
            return f"{obj.emergency_contact_name} - {obj.emergency_contact_phone}"
        elif obj.emergency_contact_name:
            return obj.emergency_contact_name
        elif obj.emergency_contact_phone:
            return obj.emergency_contact_phone
        return ""

    class Meta:
        model = Employee
        fields = [
            "no",
            "code",
            "fullname",
            "attendance_code",
            "status",
            "start_date",
            "latest_work_history_resignation_reason",
            "latest_work_history_from_date",
            "contract_type",
            "position__name",
            "branch__name",
            "block__name",
            "department__name",
            "phone",
            "personal_email",
            "email",
            "default_bank_name",
            "default_bank_account_number",
            "tax_code",
            "emergency_contact",
            "gender",
            "date_of_birth",
            "place_of_birth",
            "marital_status",
            "ethnicity",
            "religion",
            "nationality__name",
            "citizen_id",
            "citizen_id_issued_date",
            "citizen_id_issued_place",
            "residential_address",
            "permanent_address",
            "username",
            "note",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "code": {"label": _("Employee Code")},
            "fullname": {"label": _("Full Name")},
            "attendance_code": {"label": _("Attendance Code")},
            "status": {"label": _("Status")},
            "start_date": {"label": _("Start Date")},
            "phone": {"label": _("Phone")},
            "personal_email": {"label": _("Personal Email")},
            "email": {"label": _("Email")},
            "tax_code": {"label": _("Tax Code")},
            "gender": {"label": _("Gender")},
            "date_of_birth": {"label": _("Date of Birth")},
            "place_of_birth": {"label": _("Place of Birth")},
            "marital_status": {"label": _("Marital Status")},
            "ethnicity": {"label": _("Ethnicity")},
            "religion": {"label": _("Religion")},
            "citizen_id": {"label": _("Citizen ID")},
            "citizen_id_issued_date": {"label": _("ID Issued Date")},
            "citizen_id_issued_place": {"label": _("ID Issued Place")},
            "residential_address": {"label": _("Residential Address")},
            "permanent_address": {"label": _("Permanent Address")},
            "username": {"label": _("Login Username")},
            "note": {"label": _("Notes")},
        }


class EmployeeDropdownSerializer(serializers.ModelSerializer):
    """Serializer for Employee dropdowns with minimal fields."""

    # Nested read-only serializers for full object representation
    branch = EmployeeBranchNestedSerializer(read_only=True)
    block = EmployeeBlockNestedSerializer(read_only=True)
    department = EmployeeDepartmentNestedSerializer(read_only=True)
    position = EmployeePositionNestedSerializer(read_only=True)
    avatar = FileSerializer(read_only=True)

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
            "employee_type",
            "branch",
            "block",
            "department",
            "position",
            "status",
            "colored_status",
            "gender",
        ]
        read_only_fields = [
            "id",
            "code_type",
            "colored_code_type",
            "code",
            "avatar",
            "fullname",
            "employee_type",
            "branch",
            "block",
            "department",
            "position",
            "status",
            "colored_status",
            "gender",
        ]
