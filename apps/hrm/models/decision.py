from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.files.models import FileModel
from libs.constants import ColorVariant
from libs.models import BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class Decision(ColoredValueMixin, BaseModel):
    """Decision model for managing organizational decisions.

    This model stores decision records including decision number, name,
    signing information, effective dates, and attachments.

    Attributes:
        decision_number: Unique decision number/code
        name: Decision name/title
        signing_date: Date when the decision was signed
        signer: Employee who signed the decision
        effective_date: Date when the decision becomes effective
        reason: Reason for the decision
        content: Full content of the decision
        note: Additional notes
        signing_status: Current signing status (draft or issued)
        attachments: Related file attachments via GenericRelation
    """

    class SigningStatus(models.TextChoices):
        """Signing status choices for Decision model."""

        DRAFT = "draft", _("Draft")
        ISSUED = "issued", _("Issued")

    decision_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Decision number",
        help_text="Unique decision number/code",
    )

    name = models.CharField(
        max_length=500,
        verbose_name="Decision name",
        help_text="Name or title of the decision",
    )

    signing_date = models.DateField(
        verbose_name="Signing date",
        help_text="Date when the decision was signed",
    )

    signer = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="signed_decisions",
        verbose_name="Signer",
        help_text="Employee who signed the decision",
    )

    effective_date = models.DateField(
        verbose_name="Effective date",
        help_text="Date when the decision becomes effective",
    )

    reason = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Reason",
        help_text="Reason for the decision",
    )

    content = SafeTextField(
        max_length=2000,
        null=True,
        blank=True,
        verbose_name="Decision content",
        help_text="Full content of the decision",
    )

    note = SafeTextField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name="Note",
        help_text="Additional notes",
    )

    signing_status = models.CharField(
        max_length=20,
        choices=SigningStatus.choices,
        default=SigningStatus.DRAFT,
        verbose_name="Signing status",
        help_text="Current signing status of the decision",
    )

    # GenericRelation for file attachments
    attachments = GenericRelation(
        FileModel,
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="decision",
    )

    # ColoredValueMixin configuration
    VARIANT_MAPPING = {
        "signing_status": {
            SigningStatus.DRAFT: ColorVariant.GREY,
            SigningStatus.ISSUED: ColorVariant.GREEN,
        }
    }

    class Meta:
        db_table = "hrm_decision"
        verbose_name = _("Decision")
        verbose_name_plural = _("Decisions")
        ordering = ["-signing_date", "-created_at"]
        indexes = [
            models.Index(fields=["decision_number"], name="decision_number_idx"),
            models.Index(fields=["signing_date"], name="decision_signing_date_idx"),
            models.Index(fields=["effective_date"], name="decision_effective_date_idx"),
            models.Index(fields=["signing_status"], name="decision_signing_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.decision_number} - {self.name}"

    @property
    def colored_signing_status(self) -> dict:
        """Return colored value for signing_status field.

        Returns a dictionary with value and variant for use with ColoredValueSerializer.

        Returns:
            dict: Contains 'value' (status value) and 'variant' (color variant)
        """
        return self.get_colored_value("signing_status")
