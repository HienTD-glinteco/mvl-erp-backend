from decimal import ROUND_HALF_UP, Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import (
    TimesheetReason,
    TimesheetStatus,
)
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
        verbose_name=_("Employee"),
    )
    date = models.DateField(verbose_name=_("Date"))

    start_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Start time"))
    end_time = models.DateTimeField(null=True, blank=True, verbose_name=_("End time"))

    morning_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Morning hours")
    )
    afternoon_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Afternoon hours")
    )
    official_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Official hours")
    )
    overtime_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Overtime hours")
    )
    total_worked_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Total worked hours")
    )
    # Deprecated: kept for backward compatibility, use total_worked_hours instead
    total_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Total hours")
    )

    status = models.CharField(
        max_length=32, choices=TimesheetStatus.choices, default=TimesheetStatus.ON_TIME, verbose_name=_("Status")
    )

    absent_reason = models.CharField(
        max_length=64, choices=TimesheetReason.choices, null=True, blank=True, verbose_name=_("Absent reason")
    )

    # Whether this entry should be counted as full salary (affects payroll calculations)
    is_full_salary = models.BooleanField(default=True, verbose_name=_("Is full salary"))

    count_for_payroll = models.BooleanField(default=True, verbose_name=_("Count for payroll"))

    note = SafeTextField(blank=True, verbose_name=_("Note"))

    def update_times(self, start_time, end_time):
        """Update start_time and end_time for this timesheet entry.

        Args:
            start_time: DateTime for when work started
            end_time: DateTime for when work ended
        """
        self.start_time = start_time
        self.end_time = end_time

    def calculate_hours_from_schedule(self, work_schedule=None):
        """Calculate morning_hours, afternoon_hours, and total_hours based on WorkSchedule.

        This method integrates with the WorkSchedule model to determine official working hours
        and splits them into morning and afternoon sessions.

        Args:
            work_schedule: Optional WorkSchedule instance for this date's weekday.
                          If not provided, will be fetched from cache/database.

        Note:
            TODO: Implement logic after WorkSchedule integration and caching is complete.
                  - Determine morning/afternoon split based on schedule
                  - Calculate overtime based on hours outside official schedule
                  - Handle edge cases (holidays, weekends, partial days)
        """
        # TODO: Implement full WorkSchedule integration
        # For now, maintain existing behavior
        pass

    class Meta:
        db_table = "hrm_timesheet"
        verbose_name = _("Timesheet")
        verbose_name_plural = _("Timesheets")
        indexes = [models.Index(fields=["employee", "date"], name="timesheet_employee_date_idx")]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"TimesheetEntry {self.employee_id} - {self.date}"

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
            self.morning_hours = Decimal(str(self.morning_hours))
        if not isinstance(self.afternoon_hours, Decimal):
            self.afternoon_hours = Decimal(str(self.afternoon_hours))
        if not isinstance(self.overtime_hours, Decimal):
            self.overtime_hours = Decimal(str(self.overtime_hours))

        self.morning_hours = self._quantize(self.morning_hours)
        self.afternoon_hours = self._quantize(self.afternoon_hours)
        self.overtime_hours = self._quantize(self.overtime_hours)

        # Calculate official_hours as sum of morning and afternoon
        self.official_hours = self._quantize(self.morning_hours + self.afternoon_hours)

        # Calculate total_worked_hours as official_hours + overtime_hours
        self.total_worked_hours = self._quantize(self.official_hours + self.overtime_hours)

        # Keep total_hours in sync for backward compatibility
        self.total_hours = self.total_worked_hours

        super().clean()

    def save(self, *args, **kwargs):
        # Validate and ensure quantization before saving
        self.full_clean()
        super().save(*args, **kwargs)
