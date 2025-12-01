from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import ProposalSession, ProposalStatus, ProposalType, ProposalVerifierStatus
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

    # New fields for leave/overtime proposals
    start_date = models.DateField(null=True, blank=True, verbose_name=_("Start date"))

    end_date = models.DateField(null=True, blank=True, verbose_name=_("End date"))

    effective_date = models.DateField(null=True, blank=True, verbose_name=_("Effective date"))

    total_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Total hours"),
    )

    session = models.CharField(
        max_length=32,
        choices=ProposalSession.choices,
        null=True,
        blank=True,
        verbose_name=_("Session"),
    )

    # JSONField for flexible extra data per proposal type
    extra_data = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name=_("Extra data"),
    )

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

    # FKs for Transfer proposals
    handover_employee = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        related_name="handover_proposals",
        null=True,
        blank=True,
        verbose_name=_("Handover employee"),
    )

    new_department = models.ForeignKey(
        "Department",
        on_delete=models.SET_NULL,
        related_name="transfer_proposals",
        null=True,
        blank=True,
        verbose_name=_("New department"),
    )

    new_job_title = models.ForeignKey(
        "Position",
        on_delete=models.SET_NULL,
        related_name="transfer_proposals",
        null=True,
        blank=True,
        verbose_name=_("New job title"),
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
        errors = {}

        # If proposal type is complaint, complaint_reason cannot be empty
        if self.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            if not self.complaint_reason or not self.complaint_reason.strip():
                errors["complaint_reason"] = _("Complaint reason is required for complaint proposals")

        # If proposal status is rejected, note cannot be empty
        if self.proposal_status == ProposalStatus.REJECTED:
            if not self.note or not self.note.strip():
                errors["note"] = _("Note is required when rejecting a proposal")

        # Validate start_date < end_date when both are provided
        if self.start_date and self.end_date and self.start_date > self.end_date:
            errors["start_date"] = _("Start date cannot be after end date")

        if errors:
            raise ValidationError(errors)

        super().clean()

    def save(self, *args, **kwargs):
        # Call AutoCodeMixin's save first to set the temporary code
        # only if this is a new instance without a code
        if self._state.adding and not self.code:
            temp_prefix = getattr(self.__class__, "TEMP_CODE_PREFIX", "TEMP_")
            from django.utils.crypto import get_random_string

            self.code = f"{temp_prefix}{get_random_string(20)}"
        self.full_clean()
        # Use base model save, not AutoCodeMixin's save (which sets code again)
        models.Model.save(self, *args, **kwargs)


@audit_logging_register
class ProposalTimeSheetEntry(BaseModel):
    """Junction model linking Proposal to TimeSheetEntry.

    For proposals of type TIMESHEET_ENTRY_COMPLAINT, there is a strict bidirectional
    1-1 relationship enforced by clean() validation:
    - Each complaint proposal can link to exactly ONE timesheet entry
    - Each timesheet entry can have exactly ONE complaint proposal

    For proposals of other types, multiple timesheet entries can be linked to
    a single proposal.
    """

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

    def clean(self) -> None:
        """Validate bidirectional 1-1 relationship for TIMESHEET_ENTRY_COMPLAINT proposals.

        This validation enforces two constraints:
        1. A complaint proposal can only be linked to ONE timesheet entry (Proposal → TimeSheetEntry)
        2. A timesheet entry can only have ONE complaint proposal (TimeSheetEntry → Proposal)

        NOTE:
        Since we have a constraint that Proposal (with type TIMESHEET_ENTRY_COMPLAINT)
        has 1-1 relationship with TimeSheetEntry in both directions, and cannot have
        UniqueConstraint at DB level (partial indexes don't support joined field conditions),
        we enforce this validation here in clean().
        DO NOT use queryset methods that may bypass this check (E.g: bulk_create, bulk_update, update...).

        For other proposal types, multiple timesheet entries can be linked.
        """
        super().clean()

        # Only validate for TIMESHEET_ENTRY_COMPLAINT type proposals
        if self.proposal_id and self.proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            # Build base queryset excluding self if this is an update
            base_qs = ProposalTimeSheetEntry.objects.all()
            if self.pk:
                base_qs = base_qs.exclude(pk=self.pk)

            # Check 1: Proposal can only have one timesheet entry
            existing_for_proposal = base_qs.filter(proposal_id=self.proposal_id)
            if existing_for_proposal.exists():
                raise ValidationError(
                    {"proposal": _("A timesheet entry complaint proposal can only be linked to one timesheet entry.")}
                )

            # Check 2: TimeSheetEntry can only have one complaint proposal
            existing_for_timesheet = base_qs.filter(
                timesheet_entry_id=self.timesheet_entry_id,
                proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            )
            if existing_for_timesheet.exists():
                raise ValidationError(
                    {"timesheet_entry": _("This timesheet entry already has a complaint proposal linked to it.")}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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


@audit_logging_register
class ProposalAsset(BaseModel):
    """Model for assets requested in Asset Allocation proposals.

    Each asset represents an item requested in an asset allocation proposal
    with name, unit, and quantity.
    """

    proposal = models.ForeignKey(
        "Proposal",
        on_delete=models.CASCADE,
        related_name="assets",
        verbose_name=_("Proposal"),
        limit_choices_to={"proposal_type": ProposalType.ASSET_ALLOCATION},
    )

    name = models.CharField(
        max_length=200,
        verbose_name=_("Asset name"),
    )

    unit = models.CharField(
        max_length=50,
        verbose_name=_("Unit"),
    )

    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Quantity"),
    )

    class Meta:
        db_table = "hrm_proposal_asset"
        verbose_name = _("Proposal Asset")
        verbose_name_plural = _("Proposal Assets")
        indexes = [
            models.Index(fields=["proposal"], name="pa_proposal_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.quantity} {self.unit})"
