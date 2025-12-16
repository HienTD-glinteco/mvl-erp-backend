from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class Permission(BaseModel):
    """Model representing a permission in the system"""

    code = models.CharField(max_length=100, unique=True, verbose_name="Permission code")
    name = models.CharField(max_length=255, blank=True, verbose_name="Permission name")
    description = models.CharField(max_length=255, blank=True, verbose_name="Description")
    module = models.CharField(max_length=100, blank=True, verbose_name="Module")
    submodule = models.CharField(max_length=100, blank=True, verbose_name="Submodule")

    class Meta:
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        db_table = "core_permission"

    def __str__(self):
        if self.name:
            return f"{self.code} - {self.name}"
        return f"{self.code} - {self.description}"
