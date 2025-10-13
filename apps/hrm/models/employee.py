from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class Employee(BaseModel):
    """Employee model"""

    code = models.CharField(max_length=50, unique=True, verbose_name=_("Employee code"))
    name = models.CharField(max_length=200, verbose_name=_("Employee name"))
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee",
        verbose_name=_("User"),
    )

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")
        db_table = "hrm_employee"

    def __str__(self):
        return f"{self.code} - {self.name}"
