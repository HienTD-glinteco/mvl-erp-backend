"""Contract model for employee employment contracts."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class Contract(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Contract model representing employee employment contracts.

    This model stores contract information including contract details,
    employee snapshot data at the time of contract signing, salary,
    tax, and social insurance information.

    Attributes:
        code: Auto-generated unique contract code (e.g., HD00001)
        contract_number: Unique contract number in format xx/yyyy/abc - MVL
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
        max_length=100,
        unique=True,
        verbose_name=_("Contract number"),
        help_text=_("Unique contract number in format xx/yyyy/abc - MVL"),
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
    VARIANT_MAPPING = {
        "status": {
            ContractStatus.DRAFT: ColorVariant.GREY,
            ContractStatus.NOT_EFFECTIVE: ColorVariant.BLUE,
            ContractStatus.ACTIVE: ColorVariant.GREEN,
            ContractStatus.ABOUT_TO_EXPIRE: ColorVariant.YELLOW,
            ContractStatus.EXPIRED: ColorVariant.RED,
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
    def colored_status(self) -> dict:
        """Return colored value for status field.

        Returns a dictionary with value and variant for use with ColoredValueSerializer.

        Returns:
            dict: Contains 'value' (status value) and 'variant' (color variant)
        """
        return self.get_colored_value("status")
