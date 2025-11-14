from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField

from ..constants import TEMP_CODE_PREFIX


@audit_logging_register
class Project(AutoCodeMixin, BaseModel):
    """Project model for organizing work and geolocations"""

    CODE_PREFIX = "DA"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        COMPLETED = "completed", _("Completed")

    name = models.CharField(max_length=200, verbose_name=_("Project name"))
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Project code"))
    description = SafeTextField(blank=True, verbose_name=_("Description"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Status"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        db_table = "hrm_project"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"
