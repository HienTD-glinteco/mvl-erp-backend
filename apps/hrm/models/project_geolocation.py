from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class ProjectGeolocation(AutoCodeMixin, BaseModel):
    """Project geolocation with coordinates and radius for attendance/presence checks"""

    CODE_PREFIX = "DV"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")

    # Basic fields
    name = models.CharField(max_length=200, verbose_name=_("Geolocation name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Geolocation code"))
    project = models.ForeignKey(
        "hrm.Project",
        on_delete=models.PROTECT,
        related_name="geolocations",
        verbose_name=_("Project"),
    )

    # Location fields
    address = SafeTextField(blank=True, verbose_name=_("Address"))
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        verbose_name=_("Latitude"),
        help_text=_("Latitude coordinate"),
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        verbose_name=_("Longitude"),
        help_text=_("Longitude coordinate"),
    )
    radius_m = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        verbose_name=_("Radius (meters)"),
        help_text=_("Radius in meters for geofencing"),
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
        verbose_name = _("Project Geolocation")
        verbose_name_plural = _("Project Geolocations")
        db_table = "hrm_project_geolocation"
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
