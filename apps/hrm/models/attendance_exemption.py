from django.db import models
from django.utils.translation import gettext as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class AttendanceExemption(BaseModel):
    """Model for employees exempt from attendance tracking.

    This model stores information about employees who are exempt from
    the standard attendance tracking requirements. Each employee can
    have at most one active exemption record.

    Attributes:
        employee: Reference to the exempt employee (one-to-one relationship)
        effective_date: Date when the exemption becomes active (optional)
        notes: Additional notes or remarks about the exemption
    """

    class Status(models.TextChoices):
        ENABLED = "ENABLED", _("Enabled")
        DISABLED = "DISABLED", _("Disabled")

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_exemptions",
        verbose_name=_("Employee"),
        help_text="Employee to be exempt from attendance tracking",
    )
    effective_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Effective Date"),
        help_text="Date when exemption becomes active",
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("End Date"),
        help_text="Date when exemption ends",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ENABLED,
        db_index=True,
        verbose_name=_("Status"),
        help_text="Status of the exemption",
    )
    notes = models.TextField(
        blank=True,
        max_length=1000,
        verbose_name=_("Notes"),
        help_text="Additional notes or remarks",
    )

    class Meta:
        db_table = "hrm_attendance_exemption"
        verbose_name = _("Attendance Exemption")
        verbose_name_plural = _("Attendance Exemptions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["effective_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["end_date"]),
        ]

    def __str__(self):
        return f"{self.employee.code} - {self.employee.fullname} ({self.status})"
