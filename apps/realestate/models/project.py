from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from apps.hrm.constants import TEMP_CODE_PREFIX
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class Project(AutoCodeMixin, BaseModel):
    """Real estate project model"""

    CODE_PREFIX = "DA"
    TEMP_CODE_PREFIX = TEMP_CODE_PREFIX

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        COMPLETED = "completed", _("Completed")

    name = models.CharField(max_length=200, verbose_name="Project name")
    code = models.CharField(max_length=50, unique=True, verbose_name="Project code")
    address = SafeTextField(blank=True, verbose_name="Address")
    description = SafeTextField(blank=True, verbose_name="Description")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Status",
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        db_table = "realestate_project"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"
