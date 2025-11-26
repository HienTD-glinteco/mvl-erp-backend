from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import TEMP_CODE_PREFIX, AttendanceType
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class AttendanceRecord(AutoCodeMixin, BaseModel):
    """Attendance record model for storing employee clock-in/out logs.

    This model stores individual attendance records captured by various methods:
    - Biometric devices: Records are synced via polling and matched to employees using attendance_code
    - GPS: Records with latitude/longitude validated against AttendanceGeolocation
    - WiFi: Records validated against AttendanceWifiDevice BSSID
    - Other: Manual or other attendance methods

    The raw data from biometric device looks like:
    {
        'uid': 3525,           # user id on device
        'user_id': '531',      # attendance code (matches Employee.attendance_code)
        'timestamp': datetime.datetime(2025, 10, 28, 11, 49, 38),
        'status': 1,           # authentication status
        'punch': 0             # ignored
    }

    Attributes:
        attendance_type: Type of attendance (biometric_device, wifi, gps, other)
        device: Foreign key to AttendanceDevice (for biometric device records)
        employee: Foreign key to Employee (nullable, matched by attendance_code if available)
        attendance_code: User ID from device (matches Employee.attendance_code)
        timestamp: Date and time when attendance was recorded
        latitude: GPS latitude coordinate (for GPS attendance)
        longitude: GPS longitude coordinate (for GPS attendance)
        attendance_geolocation: Reference to AttendanceGeolocation (for GPS attendance)
        image: Reference to FileModel for attendance photo (for GPS attendance)
        attendance_wifi_device: Reference to AttendanceWifiDevice (for WiFi attendance)
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
            models.Index(fields=["employee", "-timestamp"]),
            models.Index(fields=["attendance_type", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Code"))
    
    # Attendance type and method
    attendance_type = models.CharField(
        max_length=20,
        choices=AttendanceType.choices,
        default=AttendanceType.BIOMETRIC_DEVICE,
        verbose_name=_("Attendance type"),
        help_text=_("Type of attendance method used"),
    )
    
    # Device reference (for biometric device attendance)
    device = models.ForeignKey(
        "AttendanceDevice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("Device"),
        help_text=_("Attendance device that captured this record (for biometric device type)"),
    )
    
    # Employee reference (nullable, matched by attendance_code)
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("Employee"),
        help_text=_("Employee associated with this attendance record"),
    )
    
    attendance_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Attendance code"),
        help_text=_("User ID from device, used to match with Employee.attendance_code"),
    )
    
    timestamp = models.DateTimeField(
        verbose_name=_("Timestamp"),
        help_text=_("Date and time when attendance was recorded"),
    )
    
    # GPS fields
    latitude = models.DecimalField(
        max_digits=20,
        decimal_places=17,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        verbose_name=_("Latitude"),
        help_text=_("GPS latitude coordinate (for GPS attendance)"),
    )
    longitude = models.DecimalField(
        max_digits=20,
        decimal_places=17,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        verbose_name=_("Longitude"),
        help_text=_("GPS longitude coordinate (for GPS attendance)"),
    )
    attendance_geolocation = models.ForeignKey(
        "AttendanceGeolocation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("Attendance geolocation"),
        help_text=_("Geolocation reference (for GPS attendance)"),
    )
    image = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("Image"),
        help_text=_("Attendance photo (for GPS attendance)"),
    )
    
    # WiFi fields
    attendance_wifi_device = models.ForeignKey(
        "AttendanceWifiDevice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name=_("WiFi device"),
        help_text=_("WiFi device reference (for WiFi attendance)"),
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
        if self.employee:
            return f"{self.employee.fullname} - {self.timestamp}"
        return f"{self.attendance_code} - {self.timestamp}"
