from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField

# Cache key for appendix contract type
APPENDIX_CONTRACT_TYPE_CACHE_KEY = "hrm:appendix_contract_type_id"


@audit_logging_register
class ContractType(ColoredValueMixin, AutoCodeMixin, BaseModel):
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

    # ColoredValueMixin configuration
    VARIANT_MAPPING = {
        "duration_type": {
            DurationType.FIXED: ColorVariant.GREEN,
            DurationType.INDEFINITE: ColorVariant.GREY,
        },
        "net_percentage": {
            NetPercentage.FULL: ColorVariant.RED,
            NetPercentage.REDUCED: ColorVariant.GREY,
        },
        "tax_calculation_method": {
            TaxCalculationMethod.PROGRESSIVE: ColorVariant.BLUE,
            TaxCalculationMethod.FLAT_10: ColorVariant.YELLOW,
            TaxCalculationMethod.NONE: ColorVariant.GREY,
        },
        "working_time_type": {
            WorkingTimeType.FULL_TIME: ColorVariant.BLUE,
            WorkingTimeType.PART_TIME: ColorVariant.ORANGE,
            WorkingTimeType.OTHER: ColorVariant.GREY,
        },
        "has_social_insurance": {
            True: ColorVariant.GREEN,
            False: ColorVariant.GREY,
        },
    }

    code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Contract type code",
        help_text="Auto-generated unique contract type code",
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Contract type name",
        help_text="Name of the contract type",
    )

    symbol = models.CharField(
        max_length=20,
        default="",
        verbose_name="Contract type symbol",
        help_text="Symbol or abbreviation for the contract type",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.CONTRACT,
        verbose_name="Category",
        help_text="Whether this is a contract type or appendix type",
    )

    duration_type = models.CharField(
        max_length=20,
        choices=DurationType.choices,
        default=DurationType.INDEFINITE,
        verbose_name="Duration type",
        help_text="Whether the contract has a fixed term or is indefinite",
    )

    duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duration in months",
        help_text="Number of months for fixed-term contracts",
    )

    base_salary = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name="Base salary",
        help_text="Base salary amount",
    )

    lunch_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Lunch allowance",
        help_text="Lunch allowance amount",
    )

    phone_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Phone allowance",
        help_text="Phone allowance amount",
    )

    other_allowance = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Other allowance",
        help_text="Other allowance amount",
    )

    net_percentage = models.CharField(
        max_length=5,
        choices=NetPercentage.choices,
        default=NetPercentage.FULL,
        verbose_name="Net percentage",
        help_text="Net salary percentage (100% or 85%)",
    )

    tax_calculation_method = models.CharField(
        max_length=20,
        choices=TaxCalculationMethod.choices,
        default=TaxCalculationMethod.PROGRESSIVE,
        verbose_name="Tax calculation method",
        help_text="Method for calculating tax",
    )

    working_time_type = models.CharField(
        max_length=20,
        choices=WorkingTimeType.choices,
        default=WorkingTimeType.FULL_TIME,
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

    working_conditions = SafeTextField(
        max_length=1000,
        default="",
        verbose_name="Working conditions",
        help_text="Description of working conditions",
    )

    rights_and_obligations = SafeTextField(
        max_length=5000,
        default="",
        verbose_name="Rights and obligations",
        help_text="Rights and obligations of parties",
    )

    terms = SafeTextField(
        max_length=5000,
        default="",
        verbose_name="Terms",
        help_text="Contract terms and conditions",
    )

    note = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Note",
        help_text="Additional notes",
    )

    template_file = models.ForeignKey(
        FileModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_type_templates",
        verbose_name="Template file",
        help_text="Template file for the contract",
    )

    class Meta:
        verbose_name = "Contract type"
        verbose_name_plural = "Contract types"
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

    @classmethod
    def get_appendix_type_id(cls) -> int:
        """Get the appendix contract type ID with caching.

        Uses Django cache to avoid repeated database queries.
        Cache is set to never expire (None timeout) since this value rarely changes.

        Returns:
            int: The contract type ID with category='appendix'

        Raises:
            ValueError: If no appendix contract type exists in the database
        """
        # Try to get from cache first
        contract_type_id = cache.get(APPENDIX_CONTRACT_TYPE_CACHE_KEY)

        if contract_type_id:
            return contract_type_id

        # Query database for ID only
        contract_type = cls.objects.filter(category=cls.Category.APPENDIX).values("id").first()
        if not contract_type:
            raise ValueError(_("No contract type with category 'appendix' found. Please create one first."))

        contract_type_id = contract_type["id"]

        # Cache the ID (never expires)
        cache.set(APPENDIX_CONTRACT_TYPE_CACHE_KEY, contract_type_id, timeout=None)

        return contract_type_id
