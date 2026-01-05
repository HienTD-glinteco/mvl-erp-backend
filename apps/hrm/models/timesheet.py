from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.db import models
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import (
    STANDARD_WORKING_HOURS_PER_DAY,
    AllowedLateMinutesReason,
    EmployeeType,
    TimesheetDayType,
    TimesheetReason,
    TimesheetStatus,
)
from apps.hrm.models.work_schedule import WorkSchedule
from libs.constants import ColorVariant
from libs.decimals import quantize_decimal
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class TimeSheetEntry(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Employee timesheet entry.

    - Hours are stored as Decimal with 2 decimal places.
    - Rounding is applied using ROUND_HALF_UP to two decimal places.
    """

    CODE_PREFIX = "NC"

    # 1. Basic Info & Foreign Keys
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="timesheets",
        verbose_name=_("Employee"),
    )
    date = models.DateField(verbose_name=_("Date"))

    # 2. Snapshot Fields
    contract = models.ForeignKey(
        "Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Contract"),
        help_text=_("Snapshot of the active contract at the time of creation."),
    )
    net_percentage = models.IntegerField(
        default=100,
        verbose_name=_("Net percentage"),
        help_text=_("Snapshot of the contract net percentage."),
    )
    is_exempt = models.BooleanField(
        default=False,
        verbose_name=_("Is exempt"),
        help_text=_("Whether the employee is exempt from attendance tracking (e.g., Board of Directors)."),
    )

    # 3. Time Logs
    # Effective times (used for calculations)
    start_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Start time"))
    end_time = models.DateTimeField(null=True, blank=True, verbose_name=_("End time"))
    # Original logs
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Original Check-in"))
    check_out_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Original Check-out"))

    # 4. Calculated Metrics - Standard Hours
    morning_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Morning hours")
    )
    afternoon_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Afternoon hours")
    )
    official_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Official hours")
    )
    total_worked_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Total worked hours")
    )

    # 5. Calculated Metrics - Overtime Breakdown
    overtime_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Overtime hours")
    )
    ot_tc1_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("OT TC1 (Weekday) hours")
    )
    ot_tc2_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("OT TC2 (Weekend) hours")
    )
    ot_tc3_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("OT TC3 (Holiday) hours")
    )
    ot_start_time = models.DateTimeField(null=True, blank=True, verbose_name=_("OT Start Time"))
    ot_end_time = models.DateTimeField(null=True, blank=True, verbose_name=_("OT End Time"))

    # Snapshot of Approved Overtime (from Proposals)
    approved_ot_start_time = models.TimeField(null=True, blank=True, verbose_name=_("Approved OT Start Time"))
    approved_ot_end_time = models.TimeField(null=True, blank=True, verbose_name=_("Approved OT End Time"))
    approved_ot_minutes = models.IntegerField(default=0, verbose_name=_("Approved OT Minutes"))

    # 6. Compensation & Penalties
    compensation_value = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Compensation value")
    )
    paid_leave_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Paid leave hours")
    )
    late_minutes = models.IntegerField(default=0, verbose_name=_("Late minutes"))
    early_minutes = models.IntegerField(default=0, verbose_name=_("Early minutes"))
    is_punished = models.BooleanField(default=False, verbose_name=_("Is punished"))
    allowed_late_minutes = models.IntegerField(default=0, verbose_name=_("Allowed late minutes"))
    allowed_late_minutes_reason = models.CharField(
        max_length=32,
        choices=AllowedLateMinutesReason.choices,
        null=True,
        blank=True,
        verbose_name=_("Allowed late minutes reason"),
    )

    # 7. Status & Classification
    working_days = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Working days"), null=True, blank=True
    )
    day_type = models.CharField(
        max_length=32,
        choices=TimesheetDayType.choices,
        null=True,
        blank=True,
        verbose_name=_("Day type"),
    )
    status = models.CharField(
        max_length=32, choices=TimesheetStatus.choices, null=True, blank=True, verbose_name=_("Status")
    )
    absent_reason = models.CharField(
        max_length=64, choices=TimesheetReason.choices, null=True, blank=True, verbose_name=_("Absent reason")
    )

    # 8. Flags & Meta
    is_full_salary = models.BooleanField(default=True, verbose_name=_("Is full salary"))
    count_for_payroll = models.BooleanField(default=True, verbose_name=_("Count for payroll"))

    is_manually_corrected = models.BooleanField(default=False, verbose_name=_("Is manually corrected"))
    manually_corrected_by = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corrected_timesheets",
        verbose_name=_("Manually corrected by"),
    )
    manually_corrected_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Manually corrected at"))

    note = SafeTextField(blank=True, verbose_name=_("Note"))

    VARIANT_MAPPING = {
        "status": {
            TimesheetStatus.ABSENT: ColorVariant.RED,
            TimesheetStatus.ON_TIME: ColorVariant.GREEN,
            TimesheetStatus.NOT_ON_TIME: ColorVariant.YELLOW,
            TimesheetStatus.SINGLE_PUNCH: ColorVariant.YELLOW,
        }
    }

    class Meta:
        db_table = "hrm_timesheet"
        verbose_name = _("Timesheet")
        verbose_name_plural = _("Timesheets")
        indexes = [models.Index(fields=["employee", "date"], name="timesheet_employee_date_idx")]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"TimesheetEntry {self.employee_id} - {self.date}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Validate and ensure quantization before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def update_times(self, start_time: datetime | None, end_time: datetime | None) -> None:
        """Update start_time and end_time for this timesheet entry.

        Args:
            start_time: DateTime for when work started. If None, do not update.
            end_time: DateTime for when work ended. If None, do not update.
        """
        # Only update if argument is not None
        self.start_time = start_time
        self.end_time = end_time
        # Basic validation: if both are set, ensure start_time <= end_time
        if self.start_time is not None and self.end_time is not None:
            if self.start_time > self.end_time:
                raise ValueError("start_time cannot be after end_time")

    def calculate_hours_from_schedule(self, work_schedule: Optional["WorkSchedule"] = None) -> None:  # NOQA: C901
        """Calculate morning_hours, afternoon_hours, and overtime_hours based on WorkSchedule.

        Delegates to TimesheetCalculator.
        """
        from apps.hrm.services.timesheet_calculator import TimesheetCalculator
        from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService

        # Legacy compatibility: snapshot data that the calculator now expects to be on the entry
        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_overtime_data(self)
        snapshot_service.snapshot_allowed_late_minutes(self)

        calc = TimesheetCalculator(self)
        calc.calculate_hours(work_schedule)
        calc.calculate_overtime()

    def clean(self) -> None:
        # Import local to avoid circular import (model <-> calculator)
        from apps.hrm.services.timesheet_calculator import TimesheetCalculator
        from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService

        # Auto-Sync Logic
        if not self.is_manually_corrected:
            self.start_time = self.check_in_time
            self.end_time = self.check_out_time

        # Ensure we have the latest snapshotted data (schedule, proposals, contract)
        # before running calculations.
        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_data(self)

        # Ensure hours are quantized to 2 decimals and calculate derived fields
        if self.morning_hours is None:
            self.morning_hours = Decimal("0.00")
        if self.afternoon_hours is None:
            self.afternoon_hours = Decimal("0.00")
        if self.overtime_hours is None:
            self.overtime_hours = Decimal("0.00")

        # Convert to Decimal if necessary and quantize
        if not isinstance(self.morning_hours, Decimal):
            self.morning_hours = Decimal(self.morning_hours)
        if not isinstance(self.afternoon_hours, Decimal):
            self.afternoon_hours = Decimal(self.afternoon_hours)
        if not isinstance(self.overtime_hours, Decimal):
            self.overtime_hours = Decimal(self.overtime_hours)

        self.morning_hours = quantize_decimal(self.morning_hours)
        self.afternoon_hours = quantize_decimal(self.afternoon_hours)
        self.overtime_hours = quantize_decimal(self.overtime_hours)

        # Calculate official_hours as sum of morning and afternoon
        self.official_hours = quantize_decimal(self.morning_hours + self.afternoon_hours)

        # Calculate total_worked_hours as official_hours + overtime_hours
        self.total_worked_hours = quantize_decimal(self.official_hours + self.overtime_hours)

        # Calculate working_days from official hours (exclude overtime)
        try:
            self.working_days = quantize_decimal(
                Decimal(self.official_hours) / Decimal(STANDARD_WORKING_HOURS_PER_DAY)
            )
        except Exception:
            self.working_days = Decimal("0.00")

        # Run all calculations via calculator
        calculator = TimesheetCalculator(self)

        # Calculate penalties (late/early)
        calculator.calculate_penalties()

        # Calculate status
        calculator.compute_status(is_finalizing=False)

        # Compute working_days according to business rules
        calculator.compute_working_days(is_finalizing=False)

        super().clean()

    @property
    def is_holiday(self) -> bool:
        return self.day_type == TimesheetDayType.HOLIDAY

    @property
    def is_compensatory(self) -> bool:
        return self.day_type == TimesheetDayType.COMPENSATORY

    @property
    def payroll_status(self) -> Promise:
        status = _("Paid")
        if self.employee.employee_type in [EmployeeType.UNPAID_OFFICIAL, EmployeeType.UNPAID_PROBATION]:
            status = _("Unpaid")

        return status

    @property
    def colored_status(self) -> dict:
        return self.get_colored_value("status")
