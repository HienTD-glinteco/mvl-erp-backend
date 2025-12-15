"""Contract model for employee employment contracts."""

from datetime import date

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from apps.hrm.constants import EmployeeType
from apps.hrm.models.contract_type import ContractType
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class Contract(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Contract model representing employee employment contracts and appendices.

    This model stores contract/appendix information including contract details,
    employee snapshot data at the time of contract signing, salary,
    tax, and social insurance information.

    For appendices (contract_type.category='appendix'), the parent_contract field
    references the main contract, and terms stores appendix-specific content.

    Attributes:
        code: Auto-generated unique contract code (e.g., HD00001 for contracts, PLHD00001 for appendices)
        contract_number: Business number (e.g., 01/2025/HDLD-MVL or 01/2025/PLHD-MVL)
        parent_contract: Reference to parent contract (for appendices only)
        employee: Foreign key to Employee
        contract_type: Foreign key to ContractType
        sign_date: Date when the contract was signed
        effective_date: Date when the contract becomes effective
        expiration_date: Date when the contract expires (null for indefinite)
        status: Current contract status
        base_salary: Base salary amount (snapshot from contract type)
        lunch_allowance: Lunch allowance amount (snapshot)
        phone_allowance: Phone allowance amount (snapshot)
        other_allowance: Other allowance amount (snapshot)
        net_percentage: Net salary percentage (snapshot)
        tax_calculation_method: Tax calculation method (snapshot)
        has_social_insurance: Whether social insurance is included (snapshot)
        working_conditions: Working conditions (snapshot)
        rights_and_obligations: Rights and obligations (snapshot)
        terms: Contract terms and conditions (snapshot) or appendix content
        note: Additional notes
        attachment: Attached contract file
    """

    class ContractStatus(models.TextChoices):
        """Contract status choices."""

        DRAFT = "draft", _("Draft")
        NOT_EFFECTIVE = "not_effective", _("Not effective")
        ACTIVE = "active", pgettext_lazy("contract status", "Active")
        ABOUT_TO_EXPIRE = "about_to_expire", _("About to expire")
        EXPIRED = "expired", _("Expired")

    # Empty CODE_PREFIX because we use custom code generator (generate_contract_code)
    CODE_PREFIX = ""

    code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Contract code",
        help_text="Auto-generated unique contract code",
    )

    contract_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Contract number",
        help_text="Business number (e.g., 01/2025/HDLD-MVL or 01/2025/PLHD-MVL)",
    )

    parent_contract = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appendices",
        verbose_name="Parent contract",
        help_text="Reference to parent contract (for appendices only)",
    )

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="Employee",
        help_text="Employee associated with this contract",
    )

    contract_type = models.ForeignKey(
        "hrm.ContractType",
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="Contract type",
        help_text="Type of the contract",
    )

    duration_type = models.CharField(
        max_length=20,
        choices=ContractType.DurationType.choices,
        default=ContractType.DurationType.INDEFINITE,
        verbose_name="Duration type",
        help_text="Whether the contract has a fixed term or is indefinite",
    )

    duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duration in months",
        help_text="Number of months for fixed-term contracts",
    )

    sign_date = models.DateField(
        verbose_name="Sign date",
        help_text="Date when the contract was signed",
    )

    effective_date = models.DateField(
        verbose_name="Effective date",
        help_text="Date when the contract becomes effective",
    )

    expiration_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Expiration date",
        help_text="Date when the contract expires (null for indefinite contracts)",
    )

    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        verbose_name="Contract status",
        help_text="Current status of the contract",
    )

    # Salary snapshot fields (copied from ContractType at the time of contract creation)
    base_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name="Base salary",
        help_text="Base salary amount at the time of contract",
    )

    base_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name="Base salary",
        help_text="Base salary amount at the time of contract",
    )

    kpi_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name="KPI salary",
        help_text="KPI salary amount at the time of contract",
    )

    lunch_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Lunch allowance",
        help_text="Lunch allowance amount at the time of contract",
    )

    phone_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Phone allowance",
        help_text="Phone allowance amount at the time of contract",
    )

    other_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Other allowance",
        help_text="Other allowance amount at the time of contract",
    )

    net_percentage = models.CharField(
        max_length=5,
        choices=ContractType.NetPercentage.choices,
        default=ContractType.NetPercentage.FULL,
        verbose_name="Net percentage",
        help_text="Net salary percentage at the time of contract",
    )

    tax_calculation_method = models.CharField(
        max_length=20,
        choices=ContractType.TaxCalculationMethod.choices,
        default=ContractType.TaxCalculationMethod.PROGRESSIVE,
        verbose_name="Tax calculation method",
        help_text="Tax calculation method at the time of contract",
    )

    working_time_type = models.CharField(
        max_length=20,
        choices=ContractType.WorkingTimeType.choices,
        default=ContractType.WorkingTimeType.FULL_TIME,
        verbose_name="Working time type",
        help_text="Type of working time arrangement",
    )

    annual_leave_days = models.PositiveIntegerField(
        default=12,
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        verbose_name="Annual leave days",
        help_text="Number of annual leave days (maximum 12)",
    )

    has_social_insurance = models.BooleanField(
        default=True,
        verbose_name="Has social insurance",
        help_text="Whether social insurance is included",
    )

    # Text snapshot fields
    working_conditions = SafeTextField(
        max_length=1000,
        default="",
        verbose_name="Working conditions",
        help_text="Working conditions at the time of contract",
    )

    rights_and_obligations = SafeTextField(
        max_length=5000,
        default="",
        verbose_name="Rights and obligations",
        help_text="Rights and obligations at the time of contract",
    )

    terms = SafeTextField(
        max_length=5000,
        default="",
        verbose_name="Terms",
        help_text="Contract terms and conditions at the time of contract",
    )

    content = SafeTextField(
        max_length=5000,
        default="",
        verbose_name="Content",
        help_text="Content of the appendix (for appendices only)",
    )

    note = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Note",
        help_text="Additional notes",
    )

    attachment = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_attachments",
        verbose_name="Attachment",
        help_text="Attached contract file",
    )

    # ColoredValueMixin configuration
    # Colors: DRAFT=yellow, NOT_EFFECTIVE=blue, ACTIVE=green, ABOUT_TO_EXPIRE=red, EXPIRED=grey
    VARIANT_MAPPING = {
        "status": {
            ContractStatus.DRAFT: ColorVariant.YELLOW,
            ContractStatus.NOT_EFFECTIVE: ColorVariant.BLUE,
            ContractStatus.ACTIVE: ColorVariant.GREEN,
            ContractStatus.ABOUT_TO_EXPIRE: ColorVariant.RED,
            ContractStatus.EXPIRED: ColorVariant.GREY,
        },
        "duration_type": {
            ContractType.DurationType.FIXED: ColorVariant.GREEN,
            ContractType.DurationType.INDEFINITE: ColorVariant.GREY,
        },
        "net_percentage": {
            ContractType.NetPercentage.FULL: ColorVariant.RED,
            ContractType.NetPercentage.REDUCED: ColorVariant.GREY,
        },
        "tax_calculation_method": {
            ContractType.TaxCalculationMethod.PROGRESSIVE: ColorVariant.YELLOW,
        },
        "working_time_type": {
            ContractType.WorkingTimeType.FULL_TIME: ColorVariant.BLUE,
            ContractType.WorkingTimeType.PART_TIME: ColorVariant.ORANGE,
            ContractType.WorkingTimeType.OTHER: ColorVariant.GREY,
        },
        "has_social_insurance": {
            True: ColorVariant.GREEN,
            False: ColorVariant.GREY,
        },
    }

    class Meta:
        db_table = "hrm_contract"
        verbose_name = "Contract"
        verbose_name_plural = "Contracts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"], name="contract_code_idx"),
            models.Index(fields=["contract_number"], name="contract_number_idx"),
            models.Index(fields=["status"], name="contract_status_idx"),
            models.Index(fields=["effective_date"], name="contract_effective_date_idx"),
            models.Index(fields=["expiration_date"], name="contract_expiration_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.employee.fullname}"

    @property
    def is_appendix(self) -> bool:
        """Check if this contract is an appendix.

        Returns:
            bool: True if this is an appendix (contract_type.category='appendix'), False otherwise.
        """
        return self.contract_type_id is not None and self.contract_type.category == ContractType.Category.APPENDIX

    @property
    def duration_display(self) -> str:
        """Return human-readable duration display.

        Returns:
            str: 'Indefinite term' for indefinite contracts,
                 or '{n} months' for fixed-term contracts.
        """
        if self.duration_type == ContractType.DurationType.INDEFINITE:
            return str(_("Indefinite term"))
        return str(_("{months} months").format(months=self.duration_months))

    @property
    def colored_status(self) -> dict:
        """Return colored value for status field.

        Returns a dictionary with value and variant for use with ColoredValueSerializer.

        Returns:
            dict: Contains 'value' (status value) and 'variant' (color variant)
        """
        return self.get_colored_value("status")

    @property
    def colored_duration_type(self) -> dict:
        """Return colored value for duration_type field.

        Returns:
            dict: Contains 'value' (duration type) and 'variant' (color variant)
        """
        return self.get_colored_value("duration_type")

    @property
    def colored_net_percentage(self) -> dict:
        """Return colored value for net_percentage field.

        Returns:
            dict: Contains 'value' (net percentage) and 'variant' (color variant)
        """
        return self.get_colored_value("net_percentage")

    @property
    def colored_tax_calculation_method(self) -> dict:
        """Return colored value for tax_calculation_method field.

        Returns:
            dict: Contains 'value' (tax method) and 'variant' (color variant)
        """
        return self.get_colored_value("tax_calculation_method")

    @property
    def colored_working_time_type(self) -> dict:
        """Return colored value for working_time_type field.

        Returns:
            dict: Contains 'value' (working time type) and 'variant' (color variant)
        """
        return self.get_colored_value("working_time_type")

    @property
    def colored_has_social_insurance(self) -> dict:
        """Return colored value for has_social_insurance field.

        Returns:
            dict: Contains 'value' (boolean) and 'variant' (color variant)
        """
        return self.get_colored_value("has_social_insurance")

    def get_status_from_dates(self) -> str:
        """Calculate status based on dates, ignoring current DRAFT status.

        Returns:
            str: The calculated status value
        """
        # Special case: Employee type is Unpaid Official or status is Resigned
        # -> Contract defaults to EXPIRED
        if self.employee:
            if (
                self.employee.employee_type == EmployeeType.UNPAID_OFFICIAL
                or self.employee.status == self.employee.Status.RESIGNED
            ):
                return self.ContractStatus.EXPIRED

        today = date.today()

        if self.effective_date > today:
            return self.ContractStatus.NOT_EFFECTIVE

        if self.expiration_date is None:
            # Indefinite contract - always active after effective date
            return self.ContractStatus.ACTIVE

        if self.expiration_date < today:
            return self.ContractStatus.EXPIRED

        # Calculate days until expiration
        days_until_expiration = (self.expiration_date - today).days

        if days_until_expiration <= 30:
            return self.ContractStatus.ABOUT_TO_EXPIRE

        return self.ContractStatus.ACTIVE

    def calculate_status(self) -> str:
        """Calculate contract status based on effective and expiration dates.

        Returns:
            str: The calculated status value
        """
        # Keep DRAFT status if currently in draft
        if self.status == self.ContractStatus.DRAFT:
            return self.ContractStatus.DRAFT

        return self.get_status_from_dates()

    def expire_previous_contracts(self):
        """Mark previous active contracts for the same employee as expired.

        This should be called after successfully saving a contract when status is not DRAFT.
        """
        if self.pk is None:
            return

        Contract.objects.filter(
            employee=self.employee,
            status__in=[
                self.ContractStatus.ACTIVE,
                self.ContractStatus.ABOUT_TO_EXPIRE,
            ],
        ).exclude(pk=self.pk).update(status=self.ContractStatus.EXPIRED)

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Override save to calculate status and handle business logic.

        - Calculates status based on dates (except for DRAFT contracts)
        - Uses transaction.atomic() decorator for data integrity
        - Expires previous contracts when status is not DRAFT
        """
        # Calculate status before save (only for non-DRAFT contracts)
        # DRAFT status is preserved - status will be recalculated when user explicitly
        # changes it from DRAFT to another status
        if self.status != self.ContractStatus.DRAFT:
            self.status = self.calculate_status()

        super().save(*args, **kwargs)

        # Expire previous contracts only when the contract is active or nearing expiration
        if self.status in [self.ContractStatus.ACTIVE, self.ContractStatus.ABOUT_TO_EXPIRE]:
            self.expire_previous_contracts()
