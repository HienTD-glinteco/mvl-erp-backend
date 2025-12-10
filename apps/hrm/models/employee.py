from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from apps.audit_logging.decorators import audit_logging_register
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField
from libs.validators import CitizenIdValidator

from ..constants import TEMP_CODE_PREFIX, EmployeeType


def generate_code(employee: "Employee") -> str:
    """Generate a code for an Employee instance based on its code_type.

    The code format is: {code_type}{subcode}
    where code_type is the employee's code_type (MV, CTV, or OS)
    and subcode is the instance ID zero-padded to at least 3 digits.

    Args:
        employee: Employee instance that must have an id and code_type attribute.

    Returns:
        Generated code string (e.g., "MV001", "CTV012", "OS444")
    """
    if not hasattr(employee, "id") or employee.id is None:
        raise ValueError("Employee must have an id to generate code")

    prefix = employee.code_type
    instance_id = employee.id

    # Format with at least 3 digits, but allow more if needed
    if instance_id < 1000:
        subcode = f"{instance_id:03d}"
    else:
        subcode = str(instance_id)

    return f"{prefix}{subcode}"


@audit_logging_register
class Employee(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Employee model representing staff members in the organization.

    This model stores comprehensive employee information including personal details,
    organizational hierarchy, and employment status. Employee codes are automatically
    generated with a prefix based on code_type (MV, CTV, or OS).

    A User account is automatically created when an Employee is created,
    using the employee's username and email fields.

    Attributes:
        code_type: Employee type (MV, CTV, or OS)
        code: Auto-generated unique employee code with prefix based on code_type
        avatar: Employee photo/avatar file
        fullname: Employee's full name
        attendance_code: Code for attendance system (digits only)
        username: Unique username (also used for User account creation)
        email: Unique work email address (also used for User account creation)
        branch: Employee's branch in the organization
        block: Employee's block within the branch
        department: Employee's department within the block
        position: Employee's job position
        employee_type: Employee classification type
        start_date: Employment start date
        status: Current employment status
        resignation_date: Date of resignation (if applicable)
        resignation_reason: Reason for leaving (if applicable)
        note: Additional notes or information about the employee
        date_of_birth: Employee's date of birth
        gender: Employee's gender
        marital_status: Employee's marital status
        nationality: Employee's nationality
        ethnicity: Employee's ethnicity
        religion: Employee's religion
        citizen_id: National ID/CCCD number (digits only)
        citizen_id_issued_date: Date when citizen ID was issued
        citizen_id_issued_place: Place where citizen ID was issued
        citizen_id_file: Citizen ID document file
        phone: Primary contact phone number (digits only)
        personal_email: Personal email address (different from work email)
        tax_code: Tax identification number
        place_of_birth: City/province of birth
        residential_address: Current residential address
        permanent_address: Permanent/registered address
        emergency_contact_name: Name of emergency contact person
        emergency_contact_phone: Phone number of emergency contact
        user: Associated User account (auto-created, nullable)
    """

    class CodeType(models.TextChoices):
        MV = "MV", _("MV")
        CTV = "CTV", _("CTV")
        OS = "OS", _("OS")

    class Status(models.TextChoices):
        ACTIVE = "Active", pgettext_lazy("employee status", "Active")
        ONBOARDING = "Onboarding", _("Onboarding")
        RESIGNED = "Resigned", _("Resigned")
        MATERNITY_LEAVE = "Maternity Leave", _("Maternity Leave")
        UNPAID_LEAVE = "Unpaid Leave", _("Unpaid Leave")

        @classmethod
        def get_working_statuses(cls):
            return [cls.ACTIVE, cls.ONBOARDING]

        @classmethod
        def get_leave_statuses(cls):
            return [cls.RESIGNED, cls.MATERNITY_LEAVE, cls.UNPAID_LEAVE]

    class Gender(models.TextChoices):
        MALE = "MALE", _("Male")
        FEMALE = "FEMALE", _("Female")

    class MaritalStatus(models.TextChoices):
        SINGLE = "SINGLE", _("Single")
        MARRIED = "MARRIED", _("Married")
        DIVORCED = "DIVORCED", _("Divorced")

    class ResignationReason(models.TextChoices):
        AGREEMENT_TERMINATION = "AGREEMENT_TERMINATION", _("Agreement Termination")
        PROBATION_FAIL = "PROBATION_FAIL", _("Probation Fail")
        JOB_ABANDONMENT = "JOB_ABANDONMENT", _("Job Abandonment")
        DISCIPLINARY_TERMINATION = "DISCIPLINARY_TERMINATION", _("Disciplinary Termination")
        WORKFORCE_REDUCTION = "WORKFORCE_REDUCTION", _("Workforce Reduction")
        UNDERPERFORMING = "UNDERPERFORMING", _("Underperforming")
        CONTRACT_EXPIRED = "CONTRACT_EXPIRED", _("Contract Expired")
        VOLUNTARY_HEALTH = "VOLUNTARY_HEALTH", _("Voluntary - Health Reasons")
        VOLUNTARY_PERSONAL = "VOLUNTARY_PERSONAL", _("Voluntary - Personal Reasons")
        VOLUNTARY_CAREER_CHANGE = "VOLUNTARY_CAREER_CHANGE", _("Voluntary - Career Change")
        VOLUNTARY_OTHER = "VOLUNTARY_OTHER", _("Voluntary - Other")
        OTHER = "OTHER", _("Other")

    VARIANT_MAPPING = {
        "code_type": {
            CodeType.MV: ColorVariant.RED,
            CodeType.CTV: ColorVariant.PURPLE,
            CodeType.OS: ColorVariant.BLUE,
        },
        "status": {
            Status.ACTIVE: ColorVariant.GREEN,
            Status.ONBOARDING: ColorVariant.YELLOW,
            Status.RESIGNED: ColorVariant.RED,
            Status.MATERNITY_LEAVE: ColorVariant.BLUE,
            Status.UNPAID_LEAVE: ColorVariant.GREY,
        },
    }

    CODE_PREFIX = "MV"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    # Basic employee info
    code_type = models.CharField(
        max_length=10,
        choices=CodeType.choices,
        default=CodeType.MV,
        verbose_name="Employee type",
    )
    code = models.CharField(max_length=50, unique=True, verbose_name="Employee code")
    avatar = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_avatars",
        verbose_name="Avatar",
    )
    fullname = models.CharField(max_length=200, verbose_name="Full name")
    attendance_code = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r"^\d+$", message=_("Attendance code must contain only digits"))],
        verbose_name="Attendance code",
    )
    username = models.CharField(max_length=150, unique=True, verbose_name="Username")
    email = models.EmailField(unique=True, verbose_name="Email")

    # Organizational structure
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name="Branch",
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name="Block",
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name="Department",
    )
    position = models.ForeignKey(
        "Position",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Position",
    )
    employee_type = models.CharField(
        max_length=30,
        choices=EmployeeType.choices,
        null=True,
        blank=True,
        verbose_name="Employee type (classification)",
    )

    # Employment details
    start_date = models.DateField(verbose_name="Start date")
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.ONBOARDING,
        verbose_name="Status",
    )
    resignation_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Resignation start date",
    )
    resignation_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Resignation end date",
    )
    resignation_reason = models.CharField(
        max_length=50,
        choices=ResignationReason.choices,
        null=True,
        blank=True,
        verbose_name="Resignation reason",
    )
    note = SafeTextField(blank=True, verbose_name="Note")

    # Personal information
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date of birth",
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.MALE,
        verbose_name="Gender",
    )
    marital_status = models.CharField(
        max_length=10,
        choices=MaritalStatus.choices,
        default=MaritalStatus.SINGLE,
        verbose_name="Marital status",
    )
    nationality = models.ForeignKey(
        "core.Nationality",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Nationality",
    )
    ethnicity = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ethnicity",
    )
    religion = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Religion",
    )

    # ID and documentation
    citizen_id = models.CharField(
        max_length=12,
        unique=True,
        validators=[CitizenIdValidator],
        verbose_name="Citizen ID",
    )
    citizen_id_issued_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Citizen ID issued date",
    )
    citizen_id_issued_place = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Citizen ID issued place",
    )
    citizen_id_file = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_citizen_id_files",
        verbose_name="Citizen ID file",
    )
    tax_code = models.CharField(
        max_length=12,
        blank=True,
        verbose_name="Tax code",
    )

    # Contact information
    phone = models.CharField(
        max_length=10,
        unique=True,
        validators=[RegexValidator(regex=r"^\d{10}$", message=_("Phone number must be exactly 10 digits"))],
        verbose_name="Phone number",
    )
    personal_email = models.EmailField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Personal email",
    )

    # Address information
    place_of_birth = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Place of birth",
    )
    residential_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Residential address",
    )
    permanent_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Permanent address",
    )

    # Emergency contact
    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Emergency contact name",
    )
    emergency_contact_phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(regex=r"^\d*$", message=_("Phone number must contain only digits"))],
        verbose_name="Emergency contact phone",
    )

    # User account
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="employee",
        verbose_name="User",
    )
    is_onboarding_email_sent = models.BooleanField(
        default=False,
        verbose_name="Is onboarding email sent",
    )

    # Recruitment
    recruitment_candidate = models.ForeignKey(
        "RecruitmentCandidate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Recruitment Candidate",
    )

    # Available leave days (e.g., remaining annual leave)
    available_leave_days = models.IntegerField(
        default=0,
        verbose_name="Available leave days",
        help_text="Number of available leave days for the employee",
    )

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        db_table = "hrm_employee"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tax_code"],
                condition=models.Q(tax_code__isnull=False) & ~models.Q(tax_code=""),
                name="unique_tax_code_when_not_null",
            )
        ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.old_status = self.status

    def __str__(self):
        return f"{self.code} - {self.fullname}"

    def get_code_prefix(self):
        """Override to return the code prefix based on code_type."""
        return self.code_type if self.code_type else self.CODE_PREFIX

    def save(self, *args, **kwargs):
        """Save employee and auto-set block and branch from department.

        Automatically sets the employee's block and branch based on the
        selected department's organizational structure.
        """
        # Auto-set block and branch from department
        if self.department_id:
            self.block = self.department.block
            self.branch = self.department.branch

        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Additional cleanup when deleting an Employee go here.
        Also deletes the associated User account if it exists.
        """
        user = self.user
        super().delete(*args, **kwargs)
        if user:
            user.delete()

    def _clean_working_statuses(self):
        working_statuses = Employee.Status.get_working_statuses()

        if self.status in working_statuses:
            if self.status == self.Status.ONBOARDING and self.old_status != self.Status.ONBOARDING:
                raise ValidationError(
                    {"status": _("Cannot change status back to On-boarding for an existing employee.")}
                )

            self.resignation_start_date = None
            self.resignation_end_date = None
            self.resignation_reason = None

    def _clean_resigned_statuses(self):
        resigned_statuses = Employee.Status.get_leave_statuses()

        if self.status in resigned_statuses:
            if not self.resignation_start_date:
                raise ValidationError(
                    {
                        "resignation_start_date": _(
                            "Resignation start date is required when changing status to Resigned, Maternity Leave, or Unpaid Leave."
                        )
                    }
                )

            if self.status == self.Status.RESIGNED and not self.resignation_reason:
                raise ValidationError(
                    {"resignation_reason": _("Resignation reason is required when status is Resigned.")}
                )

            if self.status == self.Status.MATERNITY_LEAVE and not self.resignation_end_date:
                raise ValidationError(
                    {"resignation_end_date": _("Resignation end date is required when status is Maternity Leave.")}
                )

    def _clean_status(self):
        """Clean and validate status-related fields before saving."""
        self._clean_working_statuses()
        self._clean_resigned_statuses()

    def clean(self):
        """Validate employee data.

        Ensures that:
        - Block belongs to the selected Branch
        - Department belongs to the selected Block
        - Department belongs to the selected Branch
        - Status cannot be reverted to On-boarding for existing employees
        - `resignation_start_date` is only set for RESIGNED, MATERNITY_LEAVE, UNPAID_LEAVE statuses
        - `resignation_end_date` is only set for MATERNITY_LEAVE status

        Raises:
            ValidationError: If any validation constraint is violated
        """
        super().clean()

        self._clean_status()

    @property
    def colored_code_type(self):
        """Get colored value representation for code_type field."""
        return self.get_colored_value("code_type")

    @property
    def colored_status(self):
        """Get colored value representation for status field."""
        return self.get_colored_value("status")

    @property
    def default_bank_account(self):
        """Get the default bank account for the employee.

        Returns:
            BankAccount | None: The default BankAccount instance or None if not set
        """
        return self.bank_accounts.filter(is_primary=True).first()
