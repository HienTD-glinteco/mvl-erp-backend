from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import ProposalStatus, ProposalType, ProposalVerifierStatus
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class Proposal(AutoCodeMixin, BaseModel):
    """Employee proposal model for various requests like leave, overtime, complaints, etc."""

    CODE_PREFIX = "DX"

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Proposal code"))

    proposal_date = models.DateField(auto_now_add=True, verbose_name=_("Proposal date"))

    proposal_type = models.CharField(
        max_length=64,
        choices=ProposalType.choices,
        null=True,
        blank=True,
        verbose_name=_("Proposal type"),
    )

    proposal_status = models.CharField(
        max_length=32,
        choices=ProposalStatus.choices,
        default=ProposalStatus.PENDING,
        verbose_name=_("Proposal status"),
    )

    complaint_reason = SafeTextField(null=True, blank=True, verbose_name=_("Complaint reason"))

    proposed_check_in_time = models.TimeField(null=True, blank=True, verbose_name=_("Proposed check-in time"))

    proposed_check_out_time = models.TimeField(null=True, blank=True, verbose_name=_("Proposed check-out time"))

    approved_check_in_time = models.TimeField(null=True, blank=True, verbose_name=_("Approved check-in time"))

    approved_check_out_time = models.TimeField(null=True, blank=True, verbose_name=_("Approved check-out time"))

    note = SafeTextField(null=True, blank=True, verbose_name=_("Note"))

    created_by = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="created_proposals",
        verbose_name=_("Created by"),
    )

    approved_by = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="approved_proposals",
        null=True,
        blank=True,
        verbose_name=_("Approved by"),
    )

    class Meta:
        db_table = "hrm_proposal"
        verbose_name = _("Proposal")
        verbose_name_plural = _("Proposals")
        indexes = [
            models.Index(fields=["proposal_status"], name="proposal_status_idx"),
            models.Index(fields=["proposal_date"], name="proposal_date_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        code = getattr(self, "code", None) or f"#{self.pk}" if self.pk else "New"
        return f"Proposal {code} - {self.proposal_type}"

    def clean(self) -> None:
        """Validate proposal fields based on business rules."""
        # If proposal type is complaint, complaint_reason cannot be empty
        if self.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            if not self.complaint_reason or not self.complaint_reason.strip():
                raise ValidationError({"complaint_reason": _("Complaint reason is required for complaint proposals")})

        # If proposal status is rejected, note cannot be empty
        if self.proposal_status == ProposalStatus.REJECTED:
            if not self.note or not self.note.strip():
                raise ValidationError({"note": _("Note is required when rejecting a proposal")})

        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


@audit_logging_register
class ProposalTimeSheetEntry(BaseModel):
    """Junction model linking Proposal to TimeSheetEntry."""

    proposal = models.ForeignKey(
        "Proposal",
        on_delete=models.CASCADE,
        related_name="timesheet_entries",
        verbose_name=_("Proposal"),
        limit_choices_to={"proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT},
    )

    timesheet_entry = models.ForeignKey(
        "TimeSheetEntry",
        on_delete=models.CASCADE,
        related_name="proposals",
        verbose_name=_("Timesheet entry"),
    )

    class Meta:
        db_table = "hrm_proposal_timesheet_entry"
        verbose_name = _("Proposal Timesheet Entry")
        verbose_name_plural = _("Proposal Timesheet Entries")
        unique_together = [["proposal", "timesheet_entry"]]
        indexes = [
            models.Index(fields=["proposal"], name="pt_proposal_idx"),
            models.Index(fields=["timesheet_entry"], name="pt_entry_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Proposal {self.proposal_id} - TimeSheetEntry {self.timesheet_entry_id}"


@audit_logging_register
class ProposalVerifier(BaseModel):
    """Model linking proposals to employees who can verify them."""

    proposal = models.ForeignKey(
        "Proposal",
        on_delete=models.CASCADE,
        related_name="verifiers",
        verbose_name=_("Proposal"),
    )

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="verifiable_proposals",
        verbose_name=_("Employee"),
    )

    status = models.CharField(
        max_length=32,
        choices=ProposalVerifierStatus.choices,
        default=ProposalVerifierStatus.NOT_VERIFIED,
        verbose_name=_("Status"),
    )

    verified_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Verified time"),
    )

    note = SafeTextField(
        null=True,
        blank=True,
        verbose_name=_("Note"),
    )

    class Meta:
        db_table = "hrm_proposal_verifier"
        verbose_name = _("Proposal Verifier")
        verbose_name_plural = _("Proposal Verifiers")
        unique_together = [["proposal", "employee"]]
        indexes = [
            models.Index(fields=["proposal"], name="pv_proposal_idx"),
            models.Index(fields=["employee"], name="pv_employee_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Proposal {self.proposal_id} - Verifier {self.employee_id}"
