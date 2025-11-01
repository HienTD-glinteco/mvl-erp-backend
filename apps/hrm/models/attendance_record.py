from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import TEMP_CODE_PREFIX
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class AttendanceRecord(AutoCodeMixin, BaseModel):
    """Attendance record model for storing employee clock-in/out logs from devices.

    This model stores individual attendance records captured by biometric devices.
    Records are synced via polling and matched to employees using attendance_code.

    The raw data from device looks like:
    {
        'uid': 3525,           # user id on device
        'user_id': '531',      # attendance code (matches Employee.attendance_code)
        'timestamp': datetime.datetime(2025, 10, 28, 11, 49, 38),
        'status': 1,           # authentication status
        'punch': 0             # ignored
    }

    Attributes:
        device: Foreign key to AttendanceDevice that captured this record
        attendance_code: User ID from device (matches Employee.attendance_code)
        timestamp: Date and time when attendance was recorded
        raw_data: JSON field storing complete raw data from device for debugging
    """

    CODE_PREFIX = "DD"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Meta:
        verbose_name = _("Attendance Record")
        verbose_name_plural = _("Attendance Records")
        db_table = "hrm_attendance_record"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["attendance_code", "-timestamp"]),
            models.Index(fields=["device", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    device = models.ForeignKey(
        "AttendanceDevice",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name=_("Device"),
        help_text=_("Attendance device that captured this record"),
    )
    attendance_code = models.CharField(
        max_length=20,
        verbose_name=_("Attendance code"),
        help_text=_("User ID from device, used to match with Employee.attendance_code"),
    )
    timestamp = models.DateTimeField(
        verbose_name=_("Timestamp"),
        help_text=_("Date and time when attendance was recorded"),
    )
    is_valid = models.BooleanField(
        default=True,
        verbose_name=_("Is valid"),
        help_text=_("Whether this attendance record is valid"),
    )
    notes = SafeTextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional notes or comments about this attendance record"),
    )
    raw_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Raw data"),
        help_text=_("Complete raw data from device for debugging purposes"),
    )

    def __str__(self):
        """Return string representation showing attendance code and timestamp."""
        return f"{self.attendance_code} - {self.timestamp}"
