from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel

from .recruitment_request import RecruitmentRequest


@audit_logging_register
class RecruitmentExpense(BaseModel):
    """Recruitment expense for tracking recruitment costs"""

    date = models.DateField(verbose_name="Expense date")
    recruitment_source = models.ForeignKey(
        "RecruitmentSource",
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="Recruitment source",
    )
    recruitment_channel = models.ForeignKey(
        "RecruitmentChannel",
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="Recruitment channel",
    )
    recruitment_request = models.ForeignKey(
        "RecruitmentRequest",
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="Recruitment request",
    )
    num_candidates_participated = models.PositiveIntegerField(
        default=0,
        verbose_name="Number of candidates participated",
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Total cost",
    )
    num_candidates_hired = models.PositiveIntegerField(
        default=0,
        verbose_name="Number of candidates hired",
    )
    referee = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referee_expenses",
        verbose_name="Referee",
    )
    referrer = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrer_expenses",
        verbose_name="Referrer",
    )
    activity = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name="Activity description",
    )
    note = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="Note",
    )

    class Meta:
        verbose_name = "Recruitment Expense"
        verbose_name_plural = "Recruitment Expenses"
        db_table = "hrm_recruitment_expense"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Expense on {self.date}"

    @property
    def avg_cost(self) -> Decimal:
        """Calculate average cost per hired candidate.

        Returns:
            Decimal: Average cost rounded to 2 decimal places, or 0 if no candidates hired
        """
        if self.num_candidates_hired > 0:
            return (self.total_cost / self.num_candidates_hired).quantize(Decimal("0.01"))
        return Decimal("0.00")

    def _clean_recruitment_request(self):
        errors = {}

        # Validate recruitment_request status
        if self.recruitment_request:
            allowed_statuses = [
                RecruitmentRequest.Status.OPEN,
                RecruitmentRequest.Status.CLOSED,
                RecruitmentRequest.Status.PAUSED,
            ]
            if self.recruitment_request.status not in allowed_statuses:
                errors["recruitment_request"] = _("Recruitment request must be in status: Open, Closed, or Paused.")

        return errors

    def _clean_referral_fields(self):
        errors = {}
        # Validate referee and referrer based on recruitment_source.allow_referral
        if self.recruitment_source:
            if self.recruitment_source.allow_referral:
                # If allow_referral is True, both referee and referrer are required
                if not self.referee:
                    errors["referee"] = _("Referee is required when recruitment source allows referral.")
                if not self.referrer:
                    errors["referrer"] = _("Referrer is required when recruitment source allows referral.")
            else:
                # If allow_referral is False, referee and referrer must not be set
                if self.referee:
                    errors["referee"] = _("Referee must not be set when recruitment source does not allow referral.")
                if self.referrer:
                    errors["referrer"] = _("Referrer must not be set when recruitment source does not allow referral.")

        if self.referee and self.referrer and self.referee == self.referrer:
            errors["referrer"] = _("Referrer and referee cannot be the same person.")

        return errors

    def clean(self):
        """Validate recruitment expense business rules"""
        super().clean()
        errors = {}

        errors.update(self._clean_recruitment_request())
        errors.update(self._clean_referral_fields())

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
