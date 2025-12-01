"""Contract model for employee employment contracts."""

from datetime import date

from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class Contract(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Contract model representing employee employment contracts and appendices.

    This model stores contract/appendix information including contract details,
    employee snapshot data at the time of contract signing, salary,
    tax, and social insurance information.

    For appendices (contract_type.category='appendix'), the parent_contract field
    references the main contract, and content stores appendix-specific content.

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
        terms: Contract terms and conditions (snapshot)
        content: Content of the appendix (for appendices only)
        note: Additional notes
        attachment: Attached contract file
    """

    class ContractStatus(models.TextChoices):
        """Contract status choices."""

        DRAFT = "draft", _("Draft")
        NOT_EFFECTIVE = "not_effective", _("Not effective")
        ACTIVE = "active", _("Active")
        ABOUT_TO_EXPIRE = "about_to_expire", _("About to expire")
        EXPIRED = "expired", _("Expired")

    # Empty CODE_PREFIX because we use custom code generator (generate_contract_code)
    CODE_PREFIX = ""

    code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Contract code"),
        help_text=_("Auto-generated unique contract code"),
    )

    contract_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Contract number"),
        help_text=_("Business number (e.g., 01/2025/HDLD-MVL or 01/2025/PLHD-MVL)"),
    )

    parent_contract = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appendices",
        verbose_name=_("Parent contract"),
        help_text=_("Reference to parent contract (for appendices only)"),
    )

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name=_("Employee"),
        help_text=_("Employee associated with this contract"),
    )

    contract_type = models.ForeignKey(
        "hrm.ContractType",
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name=_("Contract type"),
        help_text=_("Type of the contract"),
    )

    sign_date = models.DateField(
        verbose_name=_("Sign date"),
        help_text=_("Date when the contract was signed"),
    )

    effective_date = models.DateField(
        verbose_name=_("Effective date"),
        help_text=_("Date when the contract becomes effective"),
    )

    expiration_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Expiration date"),
        help_text=_("Date when the contract expires (null for indefinite contracts)"),
    )

    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        verbose_name=_("Contract status"),
        help_text=_("Current status of the contract"),
    )

    # Salary snapshot fields (copied from ContractType at the time of contract creation)
    base_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name=_("Base salary"),
        help_text=_("Base salary amount at the time of contract"),
    )

    lunch_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name=_("Lunch allowance"),
        help_text=_("Lunch allowance amount at the time of contract"),
    )

    phone_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name=_("Phone allowance"),
        help_text=_("Phone allowance amount at the time of contract"),
    )

    other_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name=_("Other allowance"),
        help_text=_("Other allowance amount at the time of contract"),
    )

    net_percentage = models.CharField(
        max_length=5,
        default="100",
        verbose_name=_("Net percentage"),
        help_text=_("Net salary percentage at the time of contract"),
    )

    tax_calculation_method = models.CharField(
        max_length=20,
        default="progressive",
        verbose_name=_("Tax calculation method"),
        help_text=_("Tax calculation method at the time of contract"),
    )

    has_social_insurance = models.BooleanField(
        default=True,
        verbose_name=_("Has social insurance"),
        help_text=_("Whether social insurance is included"),
    )

    # Text snapshot fields
    working_conditions = SafeTextField(
        max_length=1000,
        default="",
        verbose_name=_("Working conditions"),
        help_text=_("Working conditions at the time of contract"),
    )

    rights_and_obligations = SafeTextField(
        max_length=5000,
        default="",
        verbose_name=_("Rights and obligations"),
        help_text=_("Rights and obligations at the time of contract"),
    )

    terms = SafeTextField(
        max_length=5000,
        default="",
        verbose_name=_("Terms"),
        help_text=_("Contract terms and conditions at the time of contract"),
    )

    content = SafeTextField(
        max_length=5000,
        default="",
        verbose_name=_("Content"),
        help_text=_("Content of the appendix (for appendices only)"),
    )

    note = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Note"),
        help_text=_("Additional notes"),
    )

    attachment = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_attachments",
        verbose_name=_("Attachment"),
        help_text=_("Attached contract file"),
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
        }
    }

    class Meta:
        db_table = "hrm_contract"
        verbose_name = _("Contract")
        verbose_name_plural = _("Contracts")
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
            bool: True if this is an appendix (has parent_contract), False otherwise.
        """
        return self.parent_contract_id is not None

    @property
    def colored_status(self) -> dict:
        """Return colored value for status field.

        Returns a dictionary with value and variant for use with ColoredValueSerializer.

        Returns:
            dict: Contains 'value' (status value) and 'variant' (color variant)
        """
        return self.get_colored_value("status")

    def calculate_status(self) -> str:
        """Calculate contract status based on effective and expiration dates.

        Returns:
            str: The calculated status value
        """
        # Keep DRAFT status if currently in draft
        if self.status == self.ContractStatus.DRAFT:
            return self.ContractStatus.DRAFT

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

        # Expire previous contracts when status is not DRAFT
        if self.status != self.ContractStatus.DRAFT:
            self.expire_previous_contracts()
