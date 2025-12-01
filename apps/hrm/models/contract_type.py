from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class ContractType(AutoCodeMixin, BaseModel):
    """Contract type model representing employment contract types.

    This model stores contract type information including terms, salary,
    allowances, tax calculation, working conditions, and other employment terms.

    Attributes:
        code: Auto-generated unique contract type code
        name: Contract type name
        symbol: Contract type symbol/abbreviation
        category: Whether this is a contract type or appendix type
        duration_type: Whether contract has fixed term or indefinite
        duration_months: Number of months for fixed-term contracts
        base_salary: Base salary amount
        lunch_allowance: Lunch allowance amount
        phone_allowance: Phone allowance amount
        other_allowance: Other allowance amount
        net_percentage: Net salary percentage (100% or 85%)
        tax_calculation_method: Method for calculating tax
        working_time_type: Type of working time arrangement
        annual_leave_days: Number of annual leave days (max 12)
        has_social_insurance: Whether social insurance is included
        working_conditions: Working conditions description
        rights_and_obligations: Rights and obligations of parties
        terms: Contract terms and conditions
        note: Additional notes
        template_file: Template file for the contract
    """

    class DurationType(models.TextChoices):
        """Duration type choices for contract."""

        INDEFINITE = "indefinite", _("Indefinite term")
        FIXED = "fixed", _("Fixed term")

    class NetPercentage(models.TextChoices):
        """Net salary percentage choices."""

        FULL = "100", _("100%")
        REDUCED = "85", _("85%")

    class TaxCalculationMethod(models.TextChoices):
        """Tax calculation method choices."""

        PROGRESSIVE = "progressive", _("Progressive tax")
        FLAT_10 = "flat_10", _("10% flat tax")
        NONE = "none", _("No tax")

    class WorkingTimeType(models.TextChoices):
        """Working time type choices."""

        FULL_TIME = "full_time", _("Full-time - Office hours")
        PART_TIME = "part_time", _("Part-time")
        OTHER = "other", _("Other")

    class Category(models.TextChoices):
        """Category type choices for contract type."""

        CONTRACT = "contract", _("Contract")
        APPENDIX = "appendix", _("Appendix")

    CODE_PREFIX = "LHD"

    code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Contract type code"),
        help_text=_("Auto-generated unique contract type code"),
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Contract type name"),
        help_text=_("Name of the contract type"),
    )

    symbol = models.CharField(
        max_length=20,
        default="",
        verbose_name=_("Contract type symbol"),
        help_text=_("Symbol or abbreviation for the contract type"),
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.CONTRACT,
        verbose_name=_("Category"),
        help_text=_("Whether this is a contract type or appendix type"),
    )

    duration_type = models.CharField(
        max_length=20,
        choices=DurationType.choices,
        default=DurationType.INDEFINITE,
        verbose_name=_("Duration type"),
        help_text=_("Whether the contract has a fixed term or is indefinite"),
    )

    duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration in months"),
        help_text=_("Number of months for fixed-term contracts"),
    )

    base_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name=_("Base salary"),
        help_text=_("Base salary amount"),
    )

    lunch_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name=_("Lunch allowance"),
        help_text=_("Lunch allowance amount"),
    )

    phone_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name=_("Phone allowance"),
        help_text=_("Phone allowance amount"),
    )

    other_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name=_("Other allowance"),
        help_text=_("Other allowance amount"),
    )

    net_percentage = models.CharField(
        max_length=5,
        choices=NetPercentage.choices,
        default=NetPercentage.FULL,
        verbose_name=_("Net percentage"),
        help_text=_("Net salary percentage (100% or 85%)"),
    )

    tax_calculation_method = models.CharField(
        max_length=20,
        choices=TaxCalculationMethod.choices,
        default=TaxCalculationMethod.PROGRESSIVE,
        verbose_name=_("Tax calculation method"),
        help_text=_("Method for calculating tax"),
    )

    working_time_type = models.CharField(
        max_length=20,
        choices=WorkingTimeType.choices,
        default=WorkingTimeType.FULL_TIME,
        verbose_name=_("Working time type"),
        help_text=_("Type of working time arrangement"),
    )

    annual_leave_days = models.PositiveIntegerField(
        default=12,
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        verbose_name=_("Annual leave days"),
        help_text=_("Number of annual leave days (maximum 12)"),
    )

    has_social_insurance = models.BooleanField(
        default=True,
        verbose_name=_("Has social insurance"),
        help_text=_("Whether social insurance is included"),
    )

    working_conditions = SafeTextField(
        max_length=1000,
        default="",
        verbose_name=_("Working conditions"),
        help_text=_("Description of working conditions"),
    )

    rights_and_obligations = SafeTextField(
        max_length=5000,
        default="",
        verbose_name=_("Rights and obligations"),
        help_text=_("Rights and obligations of parties"),
    )

    terms = SafeTextField(
        max_length=5000,
        default="",
        verbose_name=_("Terms"),
        help_text=_("Contract terms and conditions"),
    )

    note = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Note"),
        help_text=_("Additional notes"),
    )

    template_file = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_type_templates",
        verbose_name=_("Template file"),
        help_text=_("Template file for the contract"),
    )

    class Meta:
        verbose_name = _("Contract type")
        verbose_name_plural = _("Contract types")
        db_table = "hrm_contract_type"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def duration_display(self) -> str:
        """Return human-readable duration display.

        Returns:
            str: 'Indefinite term' for indefinite contracts,
                 or '{n} months' for fixed-term contracts.
        """
        if self.duration_type == self.DurationType.INDEFINITE:
            return str(_("Indefinite term"))
        return str(_("{months} months").format(months=self.duration_months))
