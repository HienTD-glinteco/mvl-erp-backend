from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
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
        status: Current status of the holiday (active, inactive, archived)
        created_by: User who created this holiday
        updated_by: User who last updated this holiday
        deleted: Soft delete flag
        deleted_at: Timestamp when the holiday was soft deleted
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        ARCHIVED = "archived", _("Archived")

    name = models.CharField(max_length=255, verbose_name=_("Holiday name"))
    start_date = models.DateField(verbose_name=_("Start date"))
    end_date = models.DateField(verbose_name=_("End date"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Status"),
    )

    # Audit fields
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="created_holidays",
        verbose_name=_("Created by"),
    )
    updated_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="updated_holidays",
        verbose_name=_("Updated by"),
    )

    # Soft delete fields
    deleted = models.BooleanField(default=False, verbose_name=_("Deleted"))
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Deleted at"))

    class Meta:
        verbose_name = _("Holiday")
        verbose_name_plural = _("Holidays")
        db_table = "hrm_holiday"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["deleted"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    def clean(self):
        """Validate holiday data."""
        super().clean()

        # Validate date range
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": _("End date must be greater than or equal to start date")})

    def save(self, *args, **kwargs):
        """Override save method."""
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Soft delete the holiday."""
        self.deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted", "deleted_at"])


@audit_logging_register
class CompensatoryWorkday(BaseModel):
    """Compensatory Workday model representing working days to compensate for holidays.

    Attributes:
        holiday: Related holiday
        date: Date of the compensatory workday
        notes: Additional notes
        status: Current status (active, inactive, archived)
        created_by: User who created this compensatory workday
        updated_by: User who last updated this compensatory workday
        deleted: Soft delete flag
        deleted_at: Timestamp when the compensatory workday was soft deleted
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        ARCHIVED = "archived", _("Archived")

    holiday = models.ForeignKey(
        Holiday,
        on_delete=models.CASCADE,
        related_name="compensatory_days",
        verbose_name=_("Holiday"),
    )
    date = models.DateField(verbose_name=_("Compensatory workday date"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Status"),
    )

    # Audit fields
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="created_compensatory_days",
        verbose_name=_("Created by"),
    )
    updated_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="updated_compensatory_days",
        verbose_name=_("Updated by"),
    )

    # Soft delete fields
    deleted = models.BooleanField(default=False, verbose_name=_("Deleted"))
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Deleted at"))

    class Meta:
        verbose_name = _("Compensatory Workday")
        verbose_name_plural = _("Compensatory Workdays")
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
            models.Index(fields=["status"]),
            models.Index(fields=["deleted"]),
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

    def save(self, *args, **kwargs):
        """Override save method."""
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Soft delete the compensatory workday."""
        self.deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted", "deleted_at"])
