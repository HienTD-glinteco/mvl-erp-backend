import logging
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import TEMP_CODE_PREFIX
from libs.models import AutoCodeMixin, BaseModel

logger = logging.getLogger(__name__)


@audit_logging_register
class AttendanceDevice(AutoCodeMixin, BaseModel):
    """Attendance device model for managing biometric time attendance devices.

    This model stores information about physical attendance devices deployed
    across the organization. Devices sync attendance logs via polling mechanism.

    Attributes:
        name: Human-readable device name for identification
        location: Physical location where device is installed
        ip_address: IP address or domain name for device network access
        port: Network port for device communication
        password: Authentication password for device access
        serial_number: Manufacturer's serial number
        registration_number: Device registration/license number
        is_connected: Current connection status (online/offline)
        polling_synced_at: Timestamp of last successful polling sync (null if never synced)
    """

    CODE_PREFIX = "TB"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Meta:
        verbose_name = _("Attendance Device")
        verbose_name_plural = _("Attendance Devices")
        db_table = "hrm_attendance_device"
        ordering = ["name"]

    name = models.CharField(
        max_length=200,
        verbose_name=_("Device name"),
        help_text=_("Name for the device"),
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.CASCADE,
        related_name="attendance_devices",
        verbose_name=_("Block"),
        help_text=_("Block where device is installed"),
        null=True,
        blank=True,
    )
    ip_address = models.CharField(
        max_length=255,
        verbose_name=_("IP address or domain"),
        help_text=_("Network address for device communication"),
    )
    port = models.PositiveIntegerField(
        default=4370,
        verbose_name=_("Port"),
        help_text=_("Network port for device communication"),
    )
    password = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Password"),
        help_text=_("Authentication password for device access"),
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Serial number"),
        help_text=_("Manufacturer's device serial number"),
    )
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Registration number"),
        help_text=_("Device registration or license number"),
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Is enabled"),
        help_text=_("Whether the device is enabled for automatic synchronization"),
    )
    is_connected = models.BooleanField(
        default=False,
        verbose_name=_("Connection status"),
        help_text=_("Whether the device is currently online and reachable"),
    )
    realtime_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Realtime enabled"),
        help_text=_("Whether realtime listener is enabled for this device"),
    )
    realtime_disabled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Realtime disabled at"),
        help_text=_("Timestamp when realtime was disabled due to connection failures"),
    )
    polling_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last polling sync"),
        help_text=_("Timestamp of last successful polling sync from device"),
    )

    def __str__(self):
        """Return string representation showing device name."""
        return self.name

    def get_sync_start_time(self, lookback_days: int = 1):
        """Determine start time for log fetching based on device sync history."""
        start_datetime = self.polling_synced_at
        if not start_datetime:
            start_datetime = timezone.now() - timedelta(days=lookback_days)
            logger.info(f"No previous sync time for device {self.name}. Fetching logs from {lookback_days} day(s) ago")
        else:
            logger.info(f"Fetching logs for device {self.name} since last sync at {start_datetime}")
        return start_datetime

    def mark_sync_success(self):
        """Update device status after successful sync."""
        self.is_connected = True
        self.polling_synced_at = timezone.now()
        # Re-enable realtime if it was disabled
        if not self.realtime_enabled:
            self.realtime_enabled = True
            self.realtime_disabled_at = None
            logger.info(f"Re-enabled realtime for device {self.name} after successful polling sync")
        self.save(
            update_fields=[
                "is_connected",
                "polling_synced_at",
                "realtime_enabled",
                "realtime_disabled_at",
                "updated_at",
            ]
        )

    def mark_sync_failed(self):
        """Update device status after failed connection."""
        self.is_connected = False
        self.save(update_fields=["is_connected", "updated_at"])
