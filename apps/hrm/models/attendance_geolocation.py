from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


def validate_latitude(value):
    """Validate latitude is between -90 and 90"""
    if value < -90 or value > 90:
        raise ValidationError(_("Latitude must be between -90 and 90 degrees"))


def validate_longitude(value):
    """Validate longitude is between -180 and 180"""
    if value < -180 or value > 180:
        raise ValidationError(_("Longitude must be between -180 and 180 degrees"))


@audit_logging_register
class AttendanceGeolocation(AutoCodeMixin, BaseModel):
    """Attendance geolocation with coordinates and radius for attendance/presence checks"""

    CODE_PREFIX = "DV"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Status(models.TextChoices):
        ACTIVE = "active", pgettext_lazy("geolocation status", "Active")
        INACTIVE = "inactive", pgettext_lazy("geolocation status", "Inactive")

    # Basic fields
    name = models.CharField(max_length=200, verbose_name=_("Geolocation name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Geolocation code"))
    project = models.ForeignKey(
        "realestate.Project",
        on_delete=models.PROTECT,
        related_name="attendance_geolocations",
        verbose_name=_("Project"),
    )

    # Location fields
    address = SafeTextField(blank=True, verbose_name=_("Address"))

    # Decimal fields for latitude/longitude coordinates
    latitude = models.DecimalField(
        max_digits=20,
        decimal_places=17,
        verbose_name=_("Latitude"),
        help_text="Latitude coordinate",
        validators=[validate_latitude],
    )
    longitude = models.DecimalField(
        max_digits=20,
        decimal_places=17,
        verbose_name=_("Longitude"),
        help_text="Longitude coordinate",
        validators=[validate_longitude],
    )

    radius_m = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        verbose_name=_("Radius (meters)"),
        help_text="Radius in meters for geofencing",
    )

    # Status and notes
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Status"),
    )
    notes = SafeTextField(blank=True, verbose_name=_("Notes"))

    # Audit fields
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="created_geolocations",
        verbose_name=_("Created by"),
    )
    updated_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="updated_geolocations",
        verbose_name=_("Updated by"),
    )

    # Soft delete fields
    deleted = models.BooleanField(default=False, verbose_name=_("Deleted"))
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Deleted at"))

    class Meta:
        verbose_name = _("Attendance Geolocation")
        verbose_name_plural = _("Attendance Geolocations")
        db_table = "hrm_attendance_geolocation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["deleted"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def delete(self, using=None, keep_parents=False):
        """Soft delete implementation"""
        self.deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using)
