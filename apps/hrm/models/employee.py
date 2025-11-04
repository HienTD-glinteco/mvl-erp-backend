from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField
from libs.validators import CitizenIdValidator

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class Employee(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Employee model representing staff members in the organization.

    This model stores comprehensive employee information including personal details,
    organizational hierarchy, and employment status. Employee codes are automatically
    generated with a prefix based on code_type (MV or CTV).

    A User account is automatically created when an Employee is created,
    using the employee's username and email fields.

    Attributes:
        code_type: Employee type (MV or CTV)
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
        contract_type: Type of employment contract
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

    class Status(models.TextChoices):
        ACTIVE = "Active", _("Active")
        ONBOARDING = "Onboarding", _("Onboarding")
        RESIGNED = "Resigned", _("Resigned")
        MATERNITY_LEAVE = "Maternity Leave", _("Maternity Leave")
        UNPAID_LEAVE = "Unpaid Leave", _("Unpaid Leave")

    class Gender(models.TextChoices):
        MALE = "MALE", _("Male")
        FEMALE = "FEMALE", _("Female")

    class MaritalStatus(models.TextChoices):
        SINGLE = "SINGLE", _("Single")
        MARRIED = "MARRIED", _("Married")
        DIVORCED = "DIVORCED", _("Divorced")

    class ResignationReason(models.TextChoices):
        CAREER_CHANGE = "Career Change", _("Career Change")
        UNDERPERFORMING = "Underperforming", _("Underperforming")
        TERMINATED = "Terminated", _("Terminated")
        PERSONAL_ISSUES = "Personal Issues", _("Personal Issues")
        JOB_ABANDONMENT = "Job Abandonment", _("Job Abandonment")
        NOT_A_GOOD_FIT = "Not a Good Fit", _("Not a Good Fit")
        HEALTH_ISSUES = "Health Issues", _("Health Issues")

    VARIANT_MAPPING = {
        "code_type": {
            CodeType.MV: ColorVariant.RED,
            CodeType.CTV: ColorVariant.PURPLE,
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
        verbose_name=_("Employee type"),
    )
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Employee code"))
    avatar = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_avatars",
        verbose_name=_("Avatar"),
    )
    fullname = models.CharField(max_length=200, verbose_name=_("Full name"))
    attendance_code = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r"^\d+$", message=_("Attendance code must contain only digits"))],
        verbose_name=_("Attendance code"),
    )
    username = models.CharField(max_length=150, unique=True, verbose_name=_("Username"))
    email = models.EmailField(unique=True, verbose_name=_("Email"))

    # Organizational structure
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Branch"),
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Block"),
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Department"),
    )
    position = models.ForeignKey(
        "Position",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Position"),
    )
    contract_type = models.ForeignKey(
        "ContractType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Contract type"),
    )

    # Employment details
    start_date = models.DateField(verbose_name=_("Start date"))
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Status"),
    )
    resignation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Resignation date"),
    )
    resignation_reason = models.CharField(
        max_length=50,
        choices=ResignationReason.choices,
        null=True,
        blank=True,
        verbose_name=_("Resignation reason"),
    )
    note = SafeTextField(blank=True, verbose_name=_("Note"))

    # Personal information
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date of birth"),
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.MALE,
        verbose_name=_("Gender"),
    )
    marital_status = models.CharField(
        max_length=10,
        choices=MaritalStatus.choices,
        default=MaritalStatus.SINGLE,
        verbose_name=_("Marital status"),
    )
    nationality = models.ForeignKey(
        "core.Nationality",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Nationality"),
    )
    ethnicity = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Ethnicity"),
    )
    religion = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Religion"),
    )

    # ID and documentation
    citizen_id = models.CharField(
        max_length=12,
        unique=True,
        validators=[CitizenIdValidator],
        verbose_name=_("Citizen ID"),
    )
    citizen_id_issued_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Citizen ID issued date"),
    )
    citizen_id_issued_place = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Citizen ID issued place"),
    )
    tax_code = models.CharField(
        max_length=12,
        blank=True,
        verbose_name=_("Tax code"),
    )

    # Contact information
    phone = models.CharField(
        max_length=10,
        validators=[RegexValidator(regex=r"^\d{10}$", message=_("Phone number must be exactly 10 digits"))],
        verbose_name=_("Phone number"),
    )
    personal_email = models.EmailField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Personal email"),
    )

    # Address information
    place_of_birth = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Place of birth"),
    )
    residential_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Residential address"),
    )
    permanent_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Permanent address"),
    )

    # Emergency contact
    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Emergency contact name"),
    )
    emergency_contact_phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(regex=r"^\d*$", message=_("Phone number must contain only digits"))],
        verbose_name=_("Emergency contact phone"),
    )

    # User account
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="employee",
        verbose_name=_("User"),
    )
    is_onboarding_email_sent = models.BooleanField(
        default=False,
        verbose_name=_("Is onboarding email sent"),
    )

    # Recruitment
    recruitment_candidate = models.ForeignKey(
        "RecruitmentCandidate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Recruitment Candidate"),
    )

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")
        db_table = "hrm_employee"
        constraints = [
            models.UniqueConstraint(
                fields=["tax_code"],
                condition=models.Q(tax_code__isnull=False) & ~models.Q(tax_code=""),
                name="unique_tax_code_when_not_null",
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.fullname}"

    def get_code_prefix(self):
        """Override to return the code prefix based on code_type."""
        return self.code_type if self.code_type else self.CODE_PREFIX

    def save(self, *args, **kwargs):
        """Save employee and auto-set block and branch from department.

        Automatically sets the employee's block and branch based on the
        selected department's organizational structure.
        
        Also manages OrganizationChart entries when position changes:
        - Deactivates all existing organization chart entries
        - Creates a new active and primary entry if position is set
        """
        # Auto-set block and branch from department
        if self.department:
            self.block = self.department.block
            self.branch = self.department.branch

        self.clean()
        
        # Track if this is a new employee or if position changed
        is_new = self.pk is None
        position_changed = False
        
        if not is_new:
            try:
                old_instance = Employee.objects.get(pk=self.pk)
                position_changed = old_instance.position != self.position
            except Employee.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Handle OrganizationChart when position is set and has changed or is new
        if (is_new or position_changed) and self.position and self.department and self.user:
            from apps.hrm.models import OrganizationChart
            from datetime import date as date_module
            
            # Deactivate all existing organization chart entries for this employee
            OrganizationChart.objects.filter(
                employee=self.user,
                is_active=True
            ).update(is_active=False, is_primary=False)
            
            # Create new organization chart entry
            OrganizationChart.objects.create(
                employee=self.user,
                position=self.position,
                department=self.department,
                block=self.block,
                branch=self.branch,
                start_date=self.start_date or date_module.today(),
                is_primary=True,
                is_active=True,
            )

    def clean(self):
        """Validate employee data.

        Ensures that:
        - Block belongs to the selected Branch
        - Department belongs to the selected Block
        - Department belongs to the selected Branch
        - Resignation date and reason are provided when status is Resigned

        Raises:
            ValidationError: If any validation constraint is violated
        """
        super().clean()

        # Validate resignation fields
        if self.status == self.Status.RESIGNED:
            if not self.resignation_date:
                raise ValidationError({"resignation_date": _("Resignation date is required when status is Resigned.")})
            if not self.resignation_reason:
                raise ValidationError(
                    {"resignation_reason": _("Resignation reason is required when status is Resigned.")}
                )

    @property
    def colored_code_type(self):
        """Get colored value representation for code_type field."""
        return self.get_colored_value("code_type")

    @property
    def colored_status(self):
        """Get colored value representation for status field."""
        return self.get_colored_value("status")
