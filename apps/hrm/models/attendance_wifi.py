from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, ColoredValueMixin, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class AttendanceWifi(ColoredValueMixin, AutoCodeMixin, BaseModel):
    """Attendance WiFi configuration for WiFi-based attendance tracking"""

    CODE_PREFIX = "WF"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class State(models.TextChoices):
        IN_USE = "in_use", _("In use")
        NOT_IN_USE = "not_in_use", _("Not in use")

    VARIANT_MAPPING = {
        "state": {
            State.IN_USE: "green",
            State.NOT_IN_USE: "red",
        }
    }

    # Basic fields
    name = models.CharField(max_length=100, verbose_name=_("WiFi name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("WiFi code"))
    branch = models.ForeignKey(
        "Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_wifis",
        verbose_name=_("Branch"),
        help_text=_("Branch where this WiFi is located"),
    )
    block = models.ForeignKey(
        "Block",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_wifis",
        verbose_name=_("Block"),
        help_text=_("Block where this WiFi is located (must belong to selected branch)"),
    )
    bssid = models.CharField(
        max_length=17,
        unique=True,
        verbose_name=_("BSSID"),
        help_text=_("WiFi hardware identifier (MAC address format: XX:XX:XX:XX:XX:XX)"),
    )
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.IN_USE,
        verbose_name=_("State"),
    )
    notes = SafeTextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Attendance WiFi")
        verbose_name_plural = _("Attendance WiFis")
        db_table = "hrm_attendance_wifi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        # Auto-set branch from block if block is provided
        if self.block:
            self.branch = self.block.branch
        super().save(*args, **kwargs)

    @property
    def colored_state(self):
        """Get colored value representation for state field."""
        return self.get_colored_value("state")
