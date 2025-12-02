from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class Holiday(BaseModel):
    """Holiday model representing non-working days.

    Attributes:
        name: Name of the holiday
        start_date: Start date of the holiday (inclusive)
        end_date: End date of the holiday (inclusive)
        notes: Additional notes about the holiday
    """

    name = models.CharField(max_length=255, verbose_name="Holiday name")
    start_date = models.DateField(verbose_name="Start date")
    end_date = models.DateField(verbose_name="End date")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        db_table = "hrm_holiday"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    def clean(self):
        """Validate holiday data."""
        super().clean()

        # Validate date range
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": _("End date must be greater than or equal to start date")})


@audit_logging_register
class CompensatoryWorkday(BaseModel):
    """Compensatory Workday model representing working days to compensate for holidays.

    Attributes:
        holiday: Related holiday
        date: Date of the compensatory workday
        session: Work session (morning, afternoon, or full day)
        notes: Additional notes
    """

    class Session(models.TextChoices):
        MORNING = "morning", _("Morning")
        AFTERNOON = "afternoon", _("Afternoon")
        FULL_DAY = "full_day", _("Full Day")

    holiday = models.ForeignKey(
        Holiday,
        on_delete=models.CASCADE,
        related_name="compensatory_days",
        verbose_name="Holiday",
    )
    date = models.DateField(verbose_name="Compensatory workday date")
    session = models.CharField(
        max_length=20,
        choices=Session.choices,
        default=Session.FULL_DAY,
        verbose_name="Session",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Compensatory Workday"
        verbose_name_plural = "Compensatory Workdays"
        db_table = "hrm_compensatory_workday"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["holiday", "date"],
                name="unique_holiday_compensatory_date",
                violation_error_message=_("A compensatory workday with this date already exists for this holiday"),
            ),
        ]
        indexes = [
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.holiday.name} - Compensatory Day: {self.date}"

    def clean(self):
        """Validate compensatory workday data."""
        super().clean()

        # Check if compensatory date falls within the holiday range
        if self.holiday_id and self.date:
            if self.holiday.start_date <= self.date <= self.holiday.end_date:
                raise ValidationError(
                    {"date": _("Compensatory workday date cannot fall within the holiday date range")}
                )

            # Check if the date is Saturday (5) or Sunday (6)
            # Python's weekday(): Monday=0, Sunday=6
            weekday = self.date.weekday()
            if weekday not in [5, 6]:  # 5 = Saturday, 6 = Sunday
                raise ValidationError({"date": _("Compensatory workday must be on Saturday or Sunday")})

            # If Saturday, session can only be afternoon
            if weekday == 5 and self.session != self.Session.AFTERNOON:
                raise ValidationError(
                    {"session": _("For Saturday compensatory workdays, only afternoon session is allowed")}
                )
