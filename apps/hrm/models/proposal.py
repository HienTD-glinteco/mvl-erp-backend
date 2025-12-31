import datetime
import logging

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import (
    ProposalAssetUnitType,
    ProposalStatus,
    ProposalType,
    ProposalVerifierStatus,
    ProposalWorkShift,
)
from libs.constants import ColorVariant
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField

logger = logging.getLogger(__name__)


@audit_logging_register
class Proposal(ColoredValueMixin, AutoCodeMixin, BaseModel):
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

    note = SafeTextField(null=True, blank=True, verbose_name=_("Note for employee who create the proposal"))
    approval_note = SafeTextField(
        null=True, blank=True, verbose_name=_("Note for employee who approve/reject the proposal")
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
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Approved at"),
    )

    # TIMESHEET_ENTRY_COMPLAINT fields
    timesheet_entry_complaint_complaint_date = models.DateField(
        null=True, blank=True, verbose_name=_("Timesheet Entry Complaint date")
    )
    timesheet_entry_complaint_complaint_reason = SafeTextField(
        null=True, blank=True, verbose_name=_("Timesheet Entry Complaint Complaint reason")
    )

    timesheet_entry_complaint_proposed_check_in_time = models.TimeField(
        null=True, blank=True, verbose_name=_("Timesheet Entry Complaint Proposed check-in time")
    )

    timesheet_entry_complaint_proposed_check_out_time = models.TimeField(
        null=True, blank=True, verbose_name=_("Timesheet Entry Complaint Proposed check-out time")
    )

    timesheet_entry_complaint_approved_check_in_time = models.TimeField(
        null=True, blank=True, verbose_name=_("Timesheet Entry Complaint Approved check-in time")
    )

    timesheet_entry_complaint_approved_check_out_time = models.TimeField(
        null=True, blank=True, verbose_name=_("Timesheet Entry Complaint Approved check-out time")
    )
    timesheet_entry_complaint_latitude = models.DecimalField(
        max_digits=20,
        decimal_places=17,
        verbose_name=_("Latitude"),
        help_text="Timesheet Entry Complaint Latitude coordinate",
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        blank=True,
        null=True,
    )
    timesheet_entry_complaint_longitude = models.DecimalField(
        max_digits=20,
        decimal_places=17,
        verbose_name=_("Longitude"),
        help_text="Timesheet Entry Complaint Longitude coordinate",
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        blank=True,
        null=True,
    )
    timesheet_entry_complaint_address = models.CharField(
        max_length=255, blank=True, verbose_name=_("Timesheet Entry Complaint Address"), null=True
    )
    timesheet_entry_complaint_complaint_image = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timesheet_entry_complaint_proposals",
        verbose_name=_("Timesheet Entry Complaint Image"),
    )

    # LATE_EXEMPTION fields
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

    # POST_MATERNITY_BENEFITS fields
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

    # MATERNITY_LEAVE fields
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

    # PAID_LEAVE fields
    paid_leave_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Paid leave start date"),
    )
    paid_leave_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Paid leave end date"),
    )
    paid_leave_shift = models.CharField(
        max_length=20,
        choices=ProposalWorkShift.choices,
        null=True,
        blank=True,
        verbose_name=_("Paid leave shift"),
    )
    paid_leave_reason = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Paid leave reason"),
    )

    # UNPAID_LEAVE fields
    unpaid_leave_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Unpaid leave start date"),
    )
    unpaid_leave_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Unpaid leave end date"),
    )
    unpaid_leave_shift = models.CharField(
        max_length=20,
        choices=ProposalWorkShift.choices,
        null=True,
        blank=True,
        verbose_name=_("Unpaid leave shift"),
    )
    unpaid_leave_reason = SafeTextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Unpaid leave reason"),
    )

    # JOB_TRANSFER fields
    job_transfer_new_branch = models.ForeignKey(
        "Branch",
        on_delete=models.PROTECT,
        related_name="job_transfer_proposals",
        null=True,
        blank=True,
        verbose_name=_("New branch"),
    )
    job_transfer_new_block = models.ForeignKey(
        "Block",
        on_delete=models.PROTECT,
        related_name="job_transfer_proposals",
        null=True,
        blank=True,
        verbose_name=_("New block"),
    )
    job_transfer_new_department = models.ForeignKey(
        "Department",
        on_delete=models.PROTECT,
        related_name="job_transfer_proposals",
        null=True,
        blank=True,
        verbose_name=_("New department"),
    )
    job_transfer_new_position = models.ForeignKey(
        "Position",
        on_delete=models.PROTECT,
        related_name="job_transfer_proposals",
        null=True,
        blank=True,
        verbose_name=_("New position"),
    )
    job_transfer_effective_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Job transfer effective date"),
    )
    job_transfer_reason = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name=_("Job transfer reason"),
    )

    # DEVICE_CHANGE fields
    device_change_new_device_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("New device ID"),
        help_text="New device ID being requested",
    )
    device_change_new_platform = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("New platform"),
        help_text="Platform of the new device (ios, android, web)",
    )
    device_change_old_device_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Old device ID"),
        help_text="Previous device ID (if any)",
    )

    class Meta:
        db_table = "hrm_proposal"
        verbose_name = _("Proposal")
        verbose_name_plural = _("Proposals")
        indexes = [
            models.Index(fields=["proposal_status"], name="proposal_status_idx"),
            models.Index(fields=["proposal_date"], name="proposal_date_idx"),
        ]

    VARIANT_MAPPING = {
        "proposal_status": {
            ProposalStatus.PENDING: ColorVariant.YELLOW,
            ProposalStatus.APPROVED: ColorVariant.GREEN,
            ProposalStatus.REJECTED: ColorVariant.RED,
        }
    }

    VERIFIER_QUANTITY_LIMIT_MAPPING = {
        ProposalType.LATE_EXEMPTION: 1,
        ProposalType.POST_MATERNITY_BENEFITS: 1,
        ProposalType.TIMESHEET_ENTRY_COMPLAINT: 1,
        ProposalType.MATERNITY_LEAVE: 1,
        ProposalType.PAID_LEAVE: 1,
        ProposalType.UNPAID_LEAVE: 1,
        ProposalType.JOB_TRANSFER: 2,
        ProposalType.ASSET_ALLOCATION: 1,
        ProposalType.OVERTIME_WORK: 1,
        ProposalType.DEVICE_CHANGE: 1,
    }

    @classmethod
    def get_active_leave_proposals(cls, employee_id: int, date: "datetime.date") -> QuerySet["Proposal"]:
        """Get active leave proposals (Paid, Unpaid, Maternity) for a specific date."""
        return cls.objects.filter(
            created_by=employee_id,
            proposal_status=ProposalStatus.APPROVED,
        ).filter(
            Q(paid_leave_start_date__lte=date, paid_leave_end_date__gte=date)
            | Q(unpaid_leave_start_date__lte=date, unpaid_leave_end_date__gte=date)
            | Q(maternity_leave_start_date__lte=date, maternity_leave_end_date__gte=date)
        )

    @classmethod
    def get_active_complaint_proposals(cls, employee_id: int, date: "datetime.date") -> QuerySet["Proposal"]:
        return cls.objects.filter(
            created_by=employee_id,
            proposal_status=ProposalStatus.APPROVED,
        ).filter(
            Q(late_exemption_start_date__lte=date, late_exemption_end_date__gte=date)
            | Q(
                post_maternity_benefits_start_date__lte=date,
                post_maternity_benefits_end_date__gte=date,
            )
        )

    def __str__(self) -> str:  # pragma: no cover - trivial
        code = getattr(self, "code", None) or f"#{self.pk}" if self.pk else "New"
        return f"Proposal {code} - {self.proposal_type}"

    @property
    def colored_proposal_status(self) -> dict:
        """Get colored value representation for proposal_status field."""
        return self.get_colored_value("proposal_status")

    @property
    def is_morning_leave(self) -> bool:
        if self.proposal_type == ProposalType.PAID_LEAVE:
            return self.paid_leave_shift == ProposalWorkShift.MORNING
        if self.proposal_type == ProposalType.UNPAID_LEAVE:
            return self.unpaid_leave_shift == ProposalWorkShift.MORNING
        return False

    @property
    def is_afternoon_leave(self) -> bool:
        if self.proposal_type == ProposalType.PAID_LEAVE:
            return self.paid_leave_shift == ProposalWorkShift.AFTERNOON
        if self.proposal_type == ProposalType.UNPAID_LEAVE:
            return self.unpaid_leave_shift == ProposalWorkShift.AFTERNOON
        return False

    @property
    def short_description(self) -> str | None:
        """Get short description based on proposal type.

        Returns:
            Short description string or None if no method exists for the proposal type.
        """
        if not self.proposal_type:
            return None
        method = getattr(self, f"_get_{self.proposal_type}_short_description", None)
        if method and callable(method):
            return method()
        return None

    def _get_post_maternity_benefits_short_description(self) -> str | None:
        """Get short description for post-maternity benefits proposal."""
        if self.post_maternity_benefits_start_date and self.post_maternity_benefits_end_date:
            return f"{self.post_maternity_benefits_start_date} - {self.post_maternity_benefits_end_date}"
        return None

    def _get_late_exemption_short_description(self) -> str | None:
        """Get short description for late exemption proposal."""
        day_string = _("day")
        if self.late_exemption_start_date and self.late_exemption_end_date and self.late_exemption_minutes:
            return f"{self.late_exemption_minutes} {day_string} - {self.late_exemption_start_date} - {self.late_exemption_end_date} "
        return None

    def _get_overtime_work_short_description(self) -> str | None:
        """Get short description for overtime work proposal."""
        # Overtime entries are stored in related ProposalOvertimeEntry model
        entries = getattr(self, "overtime_entries", None)
        if not entries:
            return None
        descriptions = []
        for entry in entries.all():
            descriptions.append(f"{entry.overtime_date} ({entry.start_time} - {entry.end_time})")
        return ", ".join(descriptions)

    def _get_paid_leave_short_description(self) -> str | None:
        """Get short description for paid leave proposal."""
        if self.paid_leave_start_date and self.paid_leave_end_date:
            shift = f"{self.paid_leave_shift} - " if self.paid_leave_shift else ""
            return f"{shift}{self.paid_leave_start_date} - {self.paid_leave_end_date}"
        return None

    def _get_unpaid_leave_short_description(self) -> str | None:
        """Get short description for unpaid leave proposal."""
        if self.unpaid_leave_start_date and self.unpaid_leave_end_date:
            shift = f"{self.unpaid_leave_shift} - " if self.unpaid_leave_shift else ""
            return f"{shift}{self.unpaid_leave_start_date} - {self.unpaid_leave_end_date}"
        return None

    def _get_maternity_leave_short_description(self) -> str | None:
        """Get short description for maternity leave proposal."""
        if self.maternity_leave_start_date and self.maternity_leave_end_date:
            return f"{self.maternity_leave_start_date} - {self.maternity_leave_end_date}"
        return None

    def _get_timesheet_entry_complaint_short_description(self) -> str | None:
        """
        Get short description for timesheet entry complaint proposal.
        Return None since we don't need a description for this proposal type.
        """
        return None

    def _get_job_transfer_short_description(self) -> str | None:
        """Get short description for job transfer proposal."""
        parts = []
        if self.job_transfer_new_department:
            parts.extend(
                [
                    self.job_transfer_new_department.branch.name,
                    self.job_transfer_new_department.block.name,
                    self.job_transfer_new_department.name,
                ]
            )
        if self.job_transfer_new_position:
            parts.append(self.job_transfer_new_position.name)
        if parts:
            return ", ".join(parts)
        return None

    def _get_asset_allocation_short_description(self) -> str | None:
        """Get short description for asset allocation proposal."""
        # Assets are stored in related ProposalAsset model
        assets = getattr(self, "assets", None)
        if not assets:
            return None
        descriptions = []
        for asset in assets.all():
            descriptions.append(f"{asset.quantity} {asset.unit_type} {asset.name}")
        return ", ".join(descriptions)

    def _get_device_change_short_description(self) -> str | None:
        """Get short description for device change proposal."""
        if self.device_change_new_device_id:
            platform = f" ({self.device_change_new_platform})" if self.device_change_new_platform else ""
            return f"New device: {self.device_change_new_device_id}{platform}"
        return None

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
        # If proposal type is complaint, timesheet_entry_complaint_complaint_reason cannot be empty
        # if (
        #     not self.timesheet_entry_complaint_complaint_reason
        #     or not self.timesheet_entry_complaint_complaint_reason.strip()
        # ):
        #     raise ValidationError(
        #         {
        #             "timesheet_entry_complaint_complaint_reason": _(
        #                 "TimeSheet Entry Complaint reason is required for complaint proposals"
        #             )
        #         }
        #     )
        # NOTE: skip this check for now, leave it in comments.
        pass

    def _clean_maternity_leave_fields(self) -> None:
        """Validate maternity leave proposal fields."""
        errors = {}

        # Validate date range if both dates are provided
        if self.maternity_leave_start_date and self.maternity_leave_end_date:
            if self.maternity_leave_start_date > self.maternity_leave_end_date:
                errors["maternity_leave_end_date"] = _("Maternity leave end date must be on or after start date")

        if errors:
            raise ValidationError(errors)

    def _clean_paid_leave_fields(self) -> None:
        """Validate paid leave proposal fields."""
        errors = {}

        # Validate date range if both dates are provided
        if self.paid_leave_start_date and self.paid_leave_end_date:
            if self.paid_leave_start_date > self.paid_leave_end_date:
                errors["paid_leave_end_date"] = _("Paid leave end date must be on or after start date")

        if errors:
            raise ValidationError(errors)

    def _clean_unpaid_leave_fields(self) -> None:
        """Validate unpaid leave proposal fields."""
        errors = {}

        # Validate date range if both dates are provided
        if self.unpaid_leave_start_date and self.unpaid_leave_end_date:
            if self.unpaid_leave_start_date > self.unpaid_leave_end_date:
                errors["unpaid_leave_end_date"] = _("Unpaid leave end date must be on or after start date")

        if errors:
            raise ValidationError(errors)

    def _clean_job_transfer_fields(self) -> None:
        """Validate job transfer proposal fields."""
        errors = {}

        # Job transfer effective date is required
        if not self.job_transfer_effective_date:
            errors["job_transfer_effective_date"] = _("Job transfer effective date is required")

        # New department is required
        if not self.job_transfer_new_department:
            errors["job_transfer_new_department"] = _("New department is required for job transfer")

        # New position is required
        if not self.job_transfer_new_position:
            errors["job_transfer_new_position"] = _("New position is required for job transfer")

        if errors:
            raise ValidationError(errors)

        # Set new block and branch based on the new department, so we don't need to write additional code on save() method
        self.job_transfer_new_block = self.job_transfer_new_department.block  # type: ignore
        self.job_transfer_new_branch = self.job_transfer_new_department.branch  # type: ignore

    def clean(self) -> None:
        """Validate proposal fields based on business rules."""
        super().clean()

        # If proposal status is rejected, note cannot be empty
        if self.proposal_status == ProposalStatus.REJECTED:
            if not self.approval_note or not self.approval_note.strip():
                raise ValidationError({"approval_note": _("Resolution note is required when rejecting a proposal")})

        # Call type-specific validation methods
        # NOTE: add more here when needed
        clean_method_mapping = {
            ProposalType.LATE_EXEMPTION: self._clean_late_exemption_fields,
            ProposalType.POST_MATERNITY_BENEFITS: self._clean_post_maternity_benefits_fields,
            ProposalType.TIMESHEET_ENTRY_COMPLAINT: self._clean_timesheet_entry_complaint_fields,
            ProposalType.MATERNITY_LEAVE: self._clean_maternity_leave_fields,
            ProposalType.PAID_LEAVE: self._clean_paid_leave_fields,
            ProposalType.UNPAID_LEAVE: self._clean_unpaid_leave_fields,
            ProposalType.JOB_TRANSFER: self._clean_job_transfer_fields,
        }
        clean_method = clean_method_mapping.get(self.proposal_type)  # type: ignore
        if clean_method:
            clean_method()

    def save(self, *args, **kwargs):
        self.clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Auto-assign department leader as verifier for new proposals
        if is_new:
            self._assign_department_leader_as_verifier()
            self._assign_to_timesheet_entry()

    def _assign_department_leader_as_verifier(self) -> None:
        """Auto-assign the department leader of the proposal creator as a verifier.

        This method creates a ProposalVerifier record linking the proposal to the
        department leader of the employee who created the proposal.
        """
        # Get the department leader of the proposal creator
        if self.created_by_id and self.created_by.department_id:
            department_leader = self.created_by.department.leader
            if department_leader:
                # Create verifier only if leader exists
                ProposalVerifier.objects.get_or_create(
                    proposal=self,
                    employee=department_leader,
                    defaults={"status": ProposalVerifierStatus.PENDING},
                )

    def _assign_to_timesheet_entry(self) -> None:
        """Ensure exactly one ProposalTimeSheetEntry is created for this complaint proposal if possible."""
        from apps.hrm.models import TimeSheetEntry

        # Only run for TIMESHEET_ENTRY_COMPLAINT proposals
        if self.proposal_type != ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            logger.info("Proposal type is not TIMESHEET_ENTRY_COMPLAINT")
            return

        # Must have a complaint date and created_by
        if not self.timesheet_entry_complaint_complaint_date or not self.created_by_id:
            logger.error("Missing complaint date or created_by for TIMESHEET_ENTRY_COMPLAINT proposal")
            return

        # Find the timesheet entry for the complaint date and created_by
        # It should not happened, but we need to handle for the case one day has multiple timesheet entries
        # then we will use the latest one.
        timesheet_entry = (
            TimeSheetEntry.objects.filter(
                employee_id=self.created_by_id,
                date=self.timesheet_entry_complaint_complaint_date,
            )
            .order_by("-id")
            .first()
        )
        if not timesheet_entry:
            logger.warning(
                f"No TimeSheetEntry found for employee {self.created_by_id} on date {self.timesheet_entry_complaint_complaint_date}"
            )
            return

        # Create the junction record - validation will be enforced in ProposalTimeSheetEntry.clean()
        try:
            # NOTE: use try-except to catch validation errors and log them, and not break saving flow.
            ProposalTimeSheetEntry.objects.get_or_create(
                proposal=self,
                timesheet_entry=timesheet_entry,
            )
        except ValidationError as ve:
            logger.error(
                f"Validation error when creating ProposalTimeSheetEntry for proposal {self.pk} and timesheet entry {timesheet_entry.pk}: {ve}"
            )


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
        2. A timesheet entry can only have ONE ACTIVE complaint proposal (TimeSheetEntry → Proposal)

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
            # Terminal statuses that allow a new complaint to supersede the old one
            TERMINAL_STATUSES = [ProposalStatus.REJECTED]

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

            # Check 2: TimeSheetEntry can only have one ACTIVE (Non-Terminal) complaint proposal
            existing_for_timesheet = base_qs.filter(
                timesheet_entry_id=self.timesheet_entry_id,
                proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            ).exclude(proposal__proposal_status__in=TERMINAL_STATUSES)

            if existing_for_timesheet.exists():
                raise ValidationError(
                    {
                        "timesheet_entry": _(
                            "This timesheet entry already has a pending or approved complaint proposal."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


@audit_logging_register
class ProposalVerifier(ColoredValueMixin, BaseModel):
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
        default=ProposalVerifierStatus.PENDING,
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

    VARIANT_MAPPING = {
        "status": {
            ProposalVerifierStatus.PENDING: ColorVariant.YELLOW,
            ProposalVerifierStatus.NOT_VERIFIED: ColorVariant.RED,
            ProposalVerifierStatus.VERIFIED: ColorVariant.GREEN,
        }
    }

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

    @property
    def colored_status(self) -> dict:
        """Get colored value representation for status field."""
        return self.get_colored_value("status")

    def clean(self):
        super().clean()
        # Build queryset for existing verifiers, excluding self if this is an update
        existing_verifiers = self.proposal.verifiers.all()
        if self.pk:
            existing_verifiers = existing_verifiers.exclude(pk=self.pk)

        limit = Proposal.VERIFIER_QUANTITY_LIMIT_MAPPING.get(self.proposal.proposal_type, 1)
        if existing_verifiers.count() >= limit:
            raise ValidationError(
                {"proposal": _("Only one verifier is allowed per proposal in the current system design.")}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


@audit_logging_register
class ProposalAsset(BaseModel):
    """Model for assets requested in asset allocation proposals."""

    name = models.CharField(
        max_length=255,
        verbose_name=_("Asset name"),
    )

    unit_type = models.CharField(
        max_length=32,
        choices=ProposalAssetUnitType.choices,
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


@audit_logging_register
class ProposalOvertimeEntry(BaseModel):
    """Model for overtime work entries in overtime work proposals."""

    date = models.DateField(
        verbose_name=_("Overtime date"),
    )

    start_time = models.TimeField(
        verbose_name=_("Start time"),
    )

    end_time = models.TimeField(
        verbose_name=_("End time"),
    )

    description = SafeTextField(
        max_length=250,
        null=True,
        blank=True,
        verbose_name=_("Description"),
    )

    proposal = models.ForeignKey(
        "Proposal",
        on_delete=models.CASCADE,
        related_name="overtime_entries",
        verbose_name=_("Proposal"),
        limit_choices_to={"proposal_type": ProposalType.OVERTIME_WORK},
    )

    class Meta:
        db_table = "hrm_proposal_overtime_entry"
        verbose_name = _("Proposal Overtime Entry")
        verbose_name_plural = _("Proposal Overtime Entries")
        indexes = [
            models.Index(fields=["proposal"], name="poe_proposal_idx"),
            models.Index(fields=["date"], name="poe_date_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        proposal_code = self.proposal.code if self.proposal_id else "New"
        return f"{proposal_code} - {self.date} ({self.start_time} - {self.end_time})"

    @property
    def duration_hours(self) -> float:
        """Calculate the duration in hours."""
        from datetime import datetime

        start_dt = datetime.combine(self.date, self.start_time)
        end_dt = datetime.combine(self.date, self.end_time)
        duration = end_dt - start_dt
        return duration.total_seconds() / 3600

    def clean(self) -> None:
        """Validate overtime entry fields."""
        super().clean()

        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError({"end_time": _("End time must be after start time")})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
