from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from typing import Optional

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import (
    ProposalStatus,
    TimesheetReason,
    TimesheetStatus,
)
from apps.hrm.models.contract import Contract
from apps.hrm.models.contract_type import ContractType
from apps.hrm.models.holiday import Holiday
from apps.hrm.models.proposal import ProposalOvertimeEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday
from libs.datetimes import compute_intersection_hours
from libs.decimals import quantize_decimal
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class TimeSheetEntry(AutoCodeMixin, BaseModel):
    """Employee timesheet entry.

    - Hours are stored as Decimal with 2 decimal places.
    - Rounding is applied using ROUND_HALF_UP to two decimal places.
    """

    CODE_PREFIX = "NC"

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="timesheets",
        verbose_name="Employee",
    )
    date = models.DateField(verbose_name="Date")

    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Start time")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="End time")

    morning_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Morning hours"
    )
    afternoon_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Afternoon hours"
    )
    official_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Official hours"
    )
    overtime_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Overtime hours"
    )
    total_worked_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"), verbose_name="Total worked hours"
    )

    # TODO: add a new field to store working_days. Also add logic to autopopulate it using working hours, and other business rules.

    status = models.CharField(
        max_length=32, choices=TimesheetStatus.choices, null=True, blank=True, verbose_name="Status"
    )

    absent_reason = models.CharField(
        max_length=64, choices=TimesheetReason.choices, null=True, blank=True, verbose_name="Absent reason"
    )

    # Whether this entry should be counted as full salary (affects payroll calculations)
    is_full_salary = models.BooleanField(default=True, verbose_name="Is full salary")

    count_for_payroll = models.BooleanField(default=True, verbose_name="Count for payroll")

    # Flag to prevent automatic updates from overwriting manual corrections (e.g., from approved proposals)
    is_manually_corrected = models.BooleanField(default=False, verbose_name="Is manually corrected")

    note = SafeTextField(blank=True, verbose_name="Note")

    class Meta:
        db_table = "hrm_timesheet"
        verbose_name = "Timesheet"
        verbose_name_plural = "Timesheets"
        indexes = [models.Index(fields=["employee", "date"], name="timesheet_employee_date_idx")]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"TimesheetEntry {self.employee_id} - {self.date}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track the initial value of is_full_salary to detect explicit overrides
        self._initial_is_full_salary = self.is_full_salary

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

    def calculate_hours_from_schedule(self, work_schedule: Optional["WorkSchedule"] = None) -> None:
        """Calculate morning_hours, afternoon_hours, and overtime_hours based on WorkSchedule.

        This method integrates with the WorkSchedule model to determine official working hours
        and splits them into morning and afternoon sessions based on the work schedule.

        Args:
            work_schedule: Optional WorkSchedule instance for this date's weekday.
                          If not provided, will be fetched from cache/database.

        Note:
            This implementation uses the cached WorkSchedule to calculate hours.
            - Morning hours: time worked during morning session
            - Afternoon hours: time worked during afternoon session (including noon)
            - Overtime hours: intersection of actual worked time and approved overtime entries.

        Raises:
            ValueError: If start_time or end_time is not set, or if no work schedule is found.
        """
        # Get work schedule if not provided
        if work_schedule is None:
            # Convert Python's isoweekday (1=Monday, 7=Sunday) to WorkSchedule.Weekday (2=Monday, 8=Sunday)
            weekday = self.date.isoweekday() + 1
            work_schedule = get_work_schedule_by_weekday(weekday)

        if not self.start_time:
            # If start time is missing, no reliable work hours can be computed; set to 0 and exit early.
            self.morning_hours = Decimal(0)
            self.afternoon_hours = Decimal(0)
            self.overtime_hours = Decimal(0)
            return

        # TODO: implement case missing end time, that means employee doesn't make enough attendance, at least 2 must be considered as valid.
        # If end time is missing, no reliable work hours can be computed; set to 0 and exit early.
        if not self.end_time:
            self.morning_hours = Decimal(0)
            self.afternoon_hours = Decimal(0)
            self.overtime_hours = Decimal(0)
            return

        # Calculate hours based on schedule
        work_date = self.date
        start = self.start_time
        end = self.end_time

        morning_hours = Fraction(0)
        afternoon_hours = Fraction(0)

        morning_start = None
        morning_end = None
        afternoon_start = None
        afternoon_end = None

        # Only calculate morning and afternoon hours if work schedule exists
        if work_schedule:
            # Convert schedule times to datetime for comparison
            morning_start = (
                timezone.make_aware(datetime.combine(work_date, work_schedule.morning_start_time))
                if work_schedule.morning_start_time
                else None
            )
            morning_end = (
                timezone.make_aware(datetime.combine(work_date, work_schedule.morning_end_time))
                if work_schedule.morning_end_time
                else None
            )
            afternoon_start = (
                timezone.make_aware(datetime.combine(work_date, work_schedule.afternoon_start_time))
                if work_schedule.afternoon_start_time
                else None
            )
            afternoon_end = (
                timezone.make_aware(datetime.combine(work_date, work_schedule.afternoon_end_time))
                if work_schedule.afternoon_end_time
                else None
            )

            # Calculate morning session hours
            if morning_start and morning_end:
                morning_hours = compute_intersection_hours(start, end, morning_start, morning_end)

            # Calculate afternoon session hours (including noon)
            if afternoon_start and afternoon_end:
                afternoon_hours = compute_intersection_hours(start, end, afternoon_start, afternoon_end)

        # Calculate overtime hours
        overtime_hours = Fraction(0)

        # Check if there's an approved overtime proposal for this date
        # Fetch all approved entries for this date
        approved_overtime_entries = ProposalOvertimeEntry.objects.filter(
            proposal__created_by=self.employee,
            proposal__proposal_status=ProposalStatus.APPROVED,
            date=self.date,
        )

        for entry in approved_overtime_entries:
            ot_start = timezone.make_aware(datetime.combine(self.date, entry.start_time))
            ot_end = timezone.make_aware(datetime.combine(self.date, entry.end_time))

            # Calculate intersection with actual work
            raw_ot_hours = compute_intersection_hours(start, end, ot_start, ot_end)

            # Deduct any overlap with standard working hours to avoid double counting
            overlap_morning = Fraction(0)
            overlap_afternoon = Fraction(0)

            # Use intersection of (Actual work AND OT entry) to check against standard hours
            effective_ot_start = max(start, ot_start)
            effective_ot_end = min(end, ot_end)

            if effective_ot_start < effective_ot_end:
                if morning_start and morning_end:
                    overlap_morning = compute_intersection_hours(
                        effective_ot_start, effective_ot_end, morning_start, morning_end
                    )
                if afternoon_start and afternoon_end:
                    overlap_afternoon = compute_intersection_hours(
                        effective_ot_start, effective_ot_end, afternoon_start, afternoon_end
                    )

            overtime_hours += raw_ot_hours - overlap_morning - overlap_afternoon

        self.morning_hours = quantize_decimal(Decimal(morning_hours.numerator) / Decimal(morning_hours.denominator))
        self.afternoon_hours = quantize_decimal(
            Decimal(afternoon_hours.numerator) / Decimal(afternoon_hours.denominator)
        )
        self.overtime_hours = quantize_decimal(Decimal(overtime_hours.numerator) / Decimal(overtime_hours.denominator))

    def clean(self) -> None:
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

        # Calculate status based on actual working hours
        self.calculate_status()

        # Set is_full_salary based on active contract's net_percentage
        self._set_is_full_salary_from_contract()

        super().clean()

    def calculate_status(self) -> None:
        """Calculate timesheet `status` using schedule, holidays, compensatory days and attendance.

        Behavior summary:
        - Non-working day / holiday:
                - If there is no defined working session for the date (and it is not a
                    compensatory workday) or the recorded attendance falls entirely
                    outside defined sessions, the day is considered non-working.
                - For non-working/holiday days: if the employee did NOT attend
                    (`start_time` is None) => `status = None`; if they DID attend =>
                    `status = ON_TIME` by default.
        - Working day:
                - If a working session is defined for the date and there is no
                    `start_time` => `status = ABSENT`.
                - If `start_time` exists and schedule morning start time is available
                    then punctuality is determined by comparing `start_time` to
                    (`morning_start_time` + `allowed_late_minutes`):
                        - `<= allowed_start_time` => `ON_TIME`
                        - `> allowed_start_time` => `NOT_ON_TIME`

        Compensatory workday rules:
        - A `CompensatoryWorkday` defined for `self.date` overrides holiday/non-working
            defaults and specifies which session(s) (morning / afternoon / full) are
            treated as working for that date.
        - When a compensatory workday is present but the normal `WorkSchedule`
            lacks time definitions (common for weekend schedules), any attendance
            in the compensatory session(s) is treated as `ON_TIME` (no lateness
            computation is possible without schedule times).
        - Compensatory days are considered working days for absence/attendance
            purposes (i.e., lack of `start_time` => `ABSENT`).

        Notes:
        - Weekday lookup converts Python `isoweekday()` (1=Mon, 7=Sun) to
            `WorkSchedule.Weekday` (2=Mon, ..., 8=Sun).
        - Holidays are checked via `_is_holiday()`; compensatory workdays take
            precedence over holidays for that date.
        """

        # Delegate to service implementation to keep model thin and avoid circular imports
        from apps.hrm.services.timesheets import compute_timesheet_status

        compute_timesheet_status(self)

    def _set_is_full_salary_from_contract(self) -> None:
        """Set is_full_salary based on the active contract's net_percentage.

        This method fetches the active contract for the employee on the timesheet entry's date
        and sets is_full_salary to False if the contract has a probation net_percentage (85%),
        or True if the contract has full net_percentage (100%) or no active contract exists.

        This logic only runs when creating a new timesheet entry (self.pk is None) and
        only if is_full_salary wasn't explicitly set to a non-default value.

        Business Rules:
        - If active contract exists and net_percentage == "85" (probation): is_full_salary = False
        - If active contract exists and net_percentage == "100" (full): is_full_salary = True
        - If no active contract exists: is_full_salary = True (default)
        """
        # Only set is_full_salary from contract when creating a new entry
        # For updates, preserve the existing value (allows manual corrections)
        if self.pk is not None:
            return

        # Check if is_full_salary was explicitly set to a non-default value (False)
        # If the initial value is False (non-default), respect that explicit override
        if hasattr(self, "_initial_is_full_salary") and self._initial_is_full_salary is False:
            return

        if not self.employee_id or not self.date:
            # If employee or date is not set, keep default value (True)
            return

        # Fetch active contract for the employee on this date
        # Contract is active if:
        # - status is ACTIVE or ABOUT_TO_EXPIRE
        # - effective_date <= self.date
        # - expiration_date >= self.date OR expiration_date is None (indefinite)
        active_contract = (
            Contract.objects.filter(
                employee_id=self.employee_id,
                status__in=[Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE],
                effective_date__lte=self.date,
            )
            .filter(Q(expiration_date__gte=self.date) | Q(expiration_date__isnull=True))
            .order_by("-effective_date")
            .first()
        )

        if active_contract:
            # Set is_full_salary based on contract's net_percentage
            if active_contract.net_percentage == ContractType.NetPercentage.REDUCED:  # "85"
                self.is_full_salary = False
            else:
                # For full percentage or any other value, set to True
                self.is_full_salary = True
        else:
            # No active contract found, default to True
            self.is_full_salary = True

    def _is_holiday(self) -> bool:
        """Check if the date is a holiday.

        Returns:
            bool: True if it's a holiday, False if it's a working day
        """
        # Check if date falls within any holiday period
        return Holiday.objects.filter(
            start_date__lte=self.date,
            end_date__gte=self.date,
        ).exists()
