from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import AssetUnitType, ProposalStatus, ProposalType, ProposalVerifierStatus
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

    # Late exemption fields
    late_exemption_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Late exemption start date"),
    )
    late_exemption_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Late exemption end date"),
    )
    late_exemption_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Late exemption minutes"),
    )

    # Overtime work fields
    overtime_work_start_at = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Overtime work start time"),
    )
    overtime_work_end_at = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Overtime work end time"),
    )

    # Post-maternity benefits fields
    post_maternity_benefits_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Post-maternity benefits start date"),
    )
    post_maternity_benefits_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Post-maternity benefits end date"),
    )

    # Maternity leave fields
    maternity_leave_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Maternity leave start date"),
    )
    maternity_leave_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Maternity leave end date"),
    )
    maternity_leave_estimated_due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Maternity leave estimated due date"),
    )
    maternity_leave_replacement_employee = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="replacement_for_maternity_proposals",
        null=True,
        blank=True,
        verbose_name=_("Replacement employee for maternity leave"),
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

    def _clean_late_exemption_fields(self) -> None:
        """Validate late exemption proposal fields."""
        errors = {}

        if not self.late_exemption_start_date:
            errors["late_exemption_start_date"] = _("Late exemption start date is required")
        if not self.late_exemption_end_date:
            errors["late_exemption_end_date"] = _("Late exemption end date is required")
        if not self.late_exemption_minutes:
            errors["late_exemption_minutes"] = _("Late exemption minutes is required")

        # Validate date range
        if self.late_exemption_start_date and self.late_exemption_end_date:
            if self.late_exemption_start_date > self.late_exemption_end_date:
                errors["late_exemption_end_date"] = _("Late exemption end date must be on or after start date")

        if errors:
            raise ValidationError(errors)

    def _clean_overtime_work_fields(self) -> None:
        """Validate overtime work proposal fields."""
        errors = {}

        if not self.overtime_work_start_at:
            errors["overtime_work_start_at"] = _("Overtime work start time is required")
        if not self.overtime_work_end_at:
            errors["overtime_work_end_at"] = _("Overtime work end time is required")

        # Validate time range
        if self.overtime_work_start_at and self.overtime_work_end_at:
            if self.overtime_work_start_at >= self.overtime_work_end_at:
                errors["overtime_work_end_at"] = _("Overtime work end time must be after start time")

        if errors:
            raise ValidationError(errors)

    def _clean_post_maternity_benefits_fields(self) -> None:
        """Validate post-maternity benefits proposal fields."""
        errors = {}

        if not self.post_maternity_benefits_start_date:
            errors["post_maternity_benefits_start_date"] = _("Post-maternity benefits start date is required")
        if not self.post_maternity_benefits_end_date:
            errors["post_maternity_benefits_end_date"] = _("Post-maternity benefits end date is required")

        # Validate date range
        if self.post_maternity_benefits_start_date and self.post_maternity_benefits_end_date:
            if self.post_maternity_benefits_start_date > self.post_maternity_benefits_end_date:
                errors["post_maternity_benefits_end_date"] = _(
                    "Post-maternity benefits end date must be on or after start date"
                )

        if errors:
            raise ValidationError(errors)

    def _clean_timesheet_entry_complaint_fields(self) -> None:
        """Validate timesheet entry complaint proposal fields."""
        # If proposal type is complaint, complaint_reason cannot be empty
        if not self.complaint_reason or not self.complaint_reason.strip():
            raise ValidationError({"complaint_reason": _("Complaint reason is required for complaint proposals")})

    def _clean_maternity_leave_fields(self) -> None:
        """Validate maternity leave proposal fields."""
        errors = {}

        # Validate date range if both dates are provided
        if self.maternity_leave_start_date and self.maternity_leave_end_date:
            if self.maternity_leave_start_date > self.maternity_leave_end_date:
                errors["maternity_leave_end_date"] = _("Maternity leave end date must be on or after start date")

        if errors:
            raise ValidationError(errors)

    def clean(self) -> None:
        """Validate proposal fields based on business rules."""
        super().clean()

        # If proposal status is rejected, note cannot be empty
        if self.proposal_status == ProposalStatus.REJECTED:
            if not self.note or not self.note.strip():
                raise ValidationError({"note": _("Note is required when rejecting a proposal")})

        # Call type-specific validation methods
        # NOTE: add more here when needed
        clean_method_mapping = {
            ProposalType.LATE_EXEMPTION: self._clean_late_exemption_fields,
            ProposalType.OVERTIME_WORK: self._clean_overtime_work_fields,
            ProposalType.POST_MATERNITY_BENEFITS: self._clean_post_maternity_benefits_fields,
            ProposalType.TIMESHEET_ENTRY_COMPLAINT: self._clean_timesheet_entry_complaint_fields,
            ProposalType.MATERNITY_LEAVE: self._clean_maternity_leave_fields,
        }
        clean_method = clean_method_mapping.get(self.proposal_type)  # type: ignore
        if clean_method:
            clean_method()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


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
    """Model for assets requested in asset allocation proposals."""

    name = models.CharField(
        max_length=255,
        verbose_name=_("Asset name"),
    )

    unit_type = models.CharField(
        max_length=32,
        choices=AssetUnitType.choices,
        null=True,
        blank=True,
        verbose_name=_("Unit type"),
    )

    quantity = models.PositiveIntegerField(
        verbose_name=_("Quantity"),
    )

    note = SafeTextField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name=_("Note"),
    )

    proposal = models.ForeignKey(
        "Proposal",
        on_delete=models.CASCADE,
        related_name="assets",
        verbose_name=_("Proposal"),
        limit_choices_to={"proposal_type": ProposalType.ASSET_ALLOCATION},
    )

    class Meta:
        db_table = "hrm_proposal_asset"
        verbose_name = _("Proposal Asset")
        verbose_name_plural = _("Proposal Assets")
        indexes = [
            models.Index(fields=["proposal"], name="pa_proposal_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.unit_type:
            return f"{self.name} - {self.quantity} {self.get_unit_type_display()}"
        return f"{self.name} - {self.quantity}"
