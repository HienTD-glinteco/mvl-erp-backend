from django.db import models
from django.utils.translation import gettext_lazy as _

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

    employee = models.OneToOneField(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_exemption",
        verbose_name=_("Employee"),
        help_text=_("Employee to be exempt from attendance tracking"),
    )
    effective_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Effective Date"),
        help_text=_("Date when exemption becomes active"),
    )
    notes = models.TextField(
        blank=True,
        max_length=1000,
        verbose_name=_("Notes"),
        help_text=_("Additional notes or remarks"),
    )

    class Meta:
        db_table = "hrm_attendance_exemption"
        verbose_name = _("Attendance Exemption")
        verbose_name_plural = _("Attendance Exemptions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["effective_date"]),
        ]

    def __str__(self):
        return f"{self.employee.code} - {self.employee.fullname}"
