from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class WorkSchedule(BaseModel):
    """Work schedule model representing working hours for each day of the week."""

    class Weekday(models.IntegerChoices):
        """Weekday choices for WorkSchedule model."""

        MONDAY = 2, _("Monday")
        TUESDAY = 3, _("Tuesday")
        WEDNESDAY = 4, _("Wednesday")
        THURSDAY = 5, _("Thursday")
        FRIDAY = 6, _("Friday")
        SATURDAY = 7, _("Saturday")
        SUNDAY = 8, _("Sunday")

    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        unique=True,
        verbose_name="Weekday",
        help_text="Day of the week",
    )

    morning_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Morning start time",
        help_text="Start time of morning session",
    )

    morning_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Morning end time",
        help_text="End time of morning session",
    )

    noon_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Noon start time",
        help_text="Start time of noon session",
    )

    noon_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Noon end time",
        help_text="End time of noon session",
    )

    afternoon_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Afternoon start time",
        help_text="Start time of afternoon session",
    )

    afternoon_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Afternoon end time",
        help_text="End time of afternoon session",
    )

    allowed_late_minutes = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Allowed late minutes",
        help_text="Number of minutes late allowed",
    )

    note = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Note",
        help_text="Additional notes",
    )

    class Meta:
        verbose_name = "Work schedule"
        verbose_name_plural = "Work schedules"
        db_table = "hrm_work_schedule"
        ordering = ["weekday"]

    def __str__(self):
        return f"{self.get_weekday_display()}"

    @property
    def morning_time(self):
        """Return morning time range as formatted string."""
        if self.morning_start_time and self.morning_end_time:
            return f"{self.morning_start_time.strftime('%H:%M')} - {self.morning_end_time.strftime('%H:%M')}"
        return None

    @property
    def noon_time(self):
        """Return noon time range as formatted string."""
        if self.noon_start_time and self.noon_end_time:
            return f"{self.noon_start_time.strftime('%H:%M')} - {self.noon_end_time.strftime('%H:%M')}"
        return None

    @property
    def afternoon_time(self):
        """Return afternoon time range as formatted string."""
        if self.afternoon_start_time and self.afternoon_end_time:
            return f"{self.afternoon_start_time.strftime('%H:%M')} - {self.afternoon_end_time.strftime('%H:%M')}"
        return None

    def clean(self):
        """Validate WorkSchedule model fields."""
        super().clean()

        # Validate that weekday is one of the predefined choices
        if self.weekday not in [choice[0] for choice in self.Weekday.choices]:
            raise ValidationError({"weekday": _("Invalid weekday value. Must be one of the predefined weekdays.")})

        # For weekdays Monday-Friday, all working time fields must be present
        self._validate_weekday_required_times()

        # Validate time sequence: each session's start time >= previous session's end time
        self._validate_time_sequence()

    def _validate_weekday_required_times(self):
        """Validate that Monday-Friday have all required time fields."""
        weekdays_requiring_times = [
            self.Weekday.MONDAY,
            self.Weekday.TUESDAY,
            self.Weekday.WEDNESDAY,
            self.Weekday.THURSDAY,
            self.Weekday.FRIDAY,
        ]

        if self.weekday not in weekdays_requiring_times:
            return

        required_fields = [
            ("morning_start_time", _("Morning start time")),
            ("morning_end_time", _("Morning end time")),
            ("noon_start_time", _("Noon start time")),
            ("noon_end_time", _("Noon end time")),
            ("afternoon_start_time", _("Afternoon start time")),
            ("afternoon_end_time", _("Afternoon end time")),
        ]

        missing_fields = []
        for field_name, field_label in required_fields:
            if getattr(self, field_name) is None:
                missing_fields.append(field_label)

        if missing_fields:
            raise ValidationError(
                {
                    "weekday": _(
                        "For weekdays Monday-Friday, all working time fields must be provided. Missing: %(fields)s"
                    )
                    % {"fields": ", ".join(str(f) for f in missing_fields)}
                }
            )

    def _validate_time_sequence(self):
        """Validate that times are in non-decreasing order."""
        time_sequence = []

        if self.morning_start_time is not None:
            time_sequence.append(("morning_start_time", self.morning_start_time))
        if self.morning_end_time is not None:
            time_sequence.append(("morning_end_time", self.morning_end_time))
        if self.noon_start_time is not None:
            time_sequence.append(("noon_start_time", self.noon_start_time))
        if self.noon_end_time is not None:
            time_sequence.append(("noon_end_time", self.noon_end_time))
        if self.afternoon_start_time is not None:
            time_sequence.append(("afternoon_start_time", self.afternoon_start_time))
        if self.afternoon_end_time is not None:
            time_sequence.append(("afternoon_end_time", self.afternoon_end_time))

        # Check that times are in non-decreasing order
        for i in range(len(time_sequence) - 1):
            current_field, current_time = time_sequence[i]
            next_field, next_time = time_sequence[i + 1]

            if current_time > next_time:
                raise ValidationError(
                    {
                        next_field: _(
                            "%(next_field)s (%(next_time)s) must be greater than or equal to "
                            "%(current_field)s (%(current_time)s)"
                        )
                        % {
                            "next_field": next_field.replace("_", " ").title(),
                            "next_time": next_time.strftime("%H:%M"),
                            "current_field": current_field.replace("_", " ").title(),
                            "current_time": current_time.strftime("%H:%M"),
                        }
                    }
                )
