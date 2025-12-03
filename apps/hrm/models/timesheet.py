from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.db import models
from django.utils import timezone

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import (
    TimesheetReason,
    TimesheetStatus,
)
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday
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

    status = models.CharField(
        max_length=32, choices=TimesheetStatus.choices, default=TimesheetStatus.ABSENT, verbose_name="Status"
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
        if start_time is not None:
            self.start_time = start_time
        if end_time is not None:
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
            - Overtime hours: TODO - Complex business logic pending clarification

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

        morning_hours = Decimal("0.00")
        afternoon_hours = Decimal("0.00")

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
                morning_actual_start = max(start, morning_start)
                morning_actual_end = min(end, morning_end)
                if morning_actual_start < morning_actual_end:
                    morning_hours = Decimal((morning_actual_end - morning_actual_start).total_seconds() / 3600)

            # Calculate afternoon session hours (including noon)
            if afternoon_start and afternoon_end:
                afternoon_actual_start = max(start, afternoon_start)
                afternoon_actual_end = min(end, afternoon_end)
                if afternoon_actual_start < afternoon_actual_end:
                    afternoon_hours = Decimal((afternoon_actual_end - afternoon_actual_start).total_seconds() / 3600)

        # Calculate overtime hours
        # Overtime is calculated as: (Actual Work Hours) - (Scheduled Work Hours)
        # NOTE: This calculation considers only actual working time, not including breaks
        overtime_hours = Decimal("0.00")

        if work_schedule:
            # Overtime = time worked OUTSIDE scheduled sessions
            # The morning_hours and afternoon_hours already only count time within the scheduled sessions
            # So we need to check if there's work outside these sessions

            # Check if employee worked before morning_start or after afternoon_end
            overtime_seconds = 0.0

            # Before morning session
            if morning_start and start < morning_start:
                overtime_seconds += (morning_start - start).total_seconds()

            # After afternoon session
            if afternoon_end and end > afternoon_end:
                overtime_seconds += (end - afternoon_end).total_seconds()

            if overtime_seconds > 0:
                overtime_hours = Decimal(overtime_seconds / 3600)

        self.morning_hours = quantize_decimal(morning_hours)
        self.afternoon_hours = quantize_decimal(afternoon_hours)
        self.overtime_hours = quantize_decimal(overtime_hours)

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

        super().clean()

    def calculate_status(self) -> None:
        """Calculate timesheet status based on work schedule and actual times.

        This method determines whether the employee was:
        - ON_TIME: Started work on time (within allowed late minutes)
        - NOT_ON_TIME: Started work late (beyond allowed late minutes)
        - ABSENT: No attendance recorded or no start_time

        The calculation compares the actual start_time with the scheduled morning_start_time
        plus the allowed_late_minutes from the work schedule.
        """
        # If no start_time, consider as absent
        if not self.start_time:
            self.status = TimesheetStatus.ABSENT
            return

        # Get work schedule for this date
        # Convert Python's isoweekday (1=Monday, 7=Sunday) to WorkSchedule.Weekday (2=Monday, 8=Sunday)
        weekday = self.date.isoweekday() + 1
        work_schedule = get_work_schedule_by_weekday(weekday)

        # If no work schedule exists for this day, cannot determine status
        if not work_schedule or not work_schedule.morning_start_time:
            # Keep current status or default to ABSENT
            if not self.status:
                self.status = TimesheetStatus.ABSENT
            return

        # Calculate the allowed start time (morning_start_time + allowed_late_minutes)
        morning_start = timezone.make_aware(datetime.combine(self.date, work_schedule.morning_start_time))

        # Add allowed late minutes if specified
        allowed_late_minutes = work_schedule.allowed_late_minutes or 0
        allowed_start_time = morning_start + timedelta(minutes=allowed_late_minutes)

        # Compare actual start_time with allowed_start_time
        if self.start_time <= allowed_start_time:
            self.status = TimesheetStatus.ON_TIME
        else:
            self.status = TimesheetStatus.NOT_ON_TIME
