"""ContractAppendix model for contract amendments/appendices."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class ContractAppendix(AutoCodeMixin, BaseModel):
    """ContractAppendix model representing amendments or appendices to contracts.

    This model stores appendix information including the appendix number and code.
    The code (appendix number) is auto-generated using format `x/yyyy/PLHD-MVL`.
    The appendix_code is auto-generated using format `PLHDxxxxx`.

    Attributes:
        code: Auto-generated unique appendix number (e.g., 01/2025/PLHD-MVL)
        appendix_code: Auto-generated appendix code (e.g., PLHD00001)
        contract: Foreign key to Contract
        sign_date: Date when the appendix was signed
        effective_date: Date when the appendix becomes effective
        content: Content of the appendix
        note: Additional notes
    """

    # Empty CODE_PREFIX because we use custom code generator (generate_appendix_codes)
    CODE_PREFIX = ""

    code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Appendix number"),
        help_text=_("Auto-generated unique appendix number (format: x/yyyy/PLHD-MVL)"),
    )

    appendix_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Appendix code"),
        help_text=_("Auto-generated appendix code (format: PLHDxxxxx)"),
    )

    contract = models.ForeignKey(
        "hrm.Contract",
        on_delete=models.PROTECT,
        related_name="appendices",
        verbose_name=_("Contract"),
        help_text=_("Contract associated with this appendix"),
    )

    sign_date = models.DateField(
        verbose_name=_("Sign date"),
        help_text=_("Date when the appendix was signed"),
    )

    effective_date = models.DateField(
        verbose_name=_("Effective date"),
        help_text=_("Date when the appendix becomes effective"),
    )

    content = SafeTextField(
        max_length=5000,
        default="",
        verbose_name=_("Content"),
        help_text=_("Content of the appendix"),
    )

    note = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Note"),
        help_text=_("Additional notes"),
    )

    class Meta:
        db_table = "hrm_contract_appendix"
        verbose_name = _("Contract appendix")
        verbose_name_plural = _("Contract appendices")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"], name="contract_appendix_code_idx"),
            models.Index(fields=["appendix_code"], name="contract_appendix_acode_idx"),
            models.Index(fields=["effective_date"], name="contract_appendix_eff_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.contract.employee.fullname}"

    @property
    def appendix_number(self) -> str | None:
        """Return appendix number (alias for code).

        Returns:
            str | None: The code value
        """
        return self.code
