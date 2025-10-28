from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class AttendanceDevice(BaseModel):
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

    class Meta:
        verbose_name = _("Attendance Device")
        verbose_name_plural = _("Attendance Devices")
        db_table = "hrm_attendance_device"
        ordering = ["name"]

    name = models.CharField(
        max_length=200,
        verbose_name=_("Device name"),
        help_text=_("Human-readable name for the device"),
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Location"),
        help_text=_("Physical location where device is installed"),
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
    polling_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last polling sync"),
        help_text=_("Timestamp of last successful polling sync from device"),
    )

    def __str__(self):
        """Return string representation showing device name and location."""
        if self.location:
            return f"{self.name} ({self.location})"
        return self.name
