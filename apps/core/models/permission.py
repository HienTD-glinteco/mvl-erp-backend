from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class Permission(BaseModel):
    """Model representing a permission in the system"""

    code = models.CharField(max_length=100, unique=True, verbose_name=_("Permission code"))
    name = models.CharField(max_length=255, blank=True, verbose_name=_("Permission name"))
    description = models.CharField(max_length=255, blank=True, verbose_name=_("Description"))
    module = models.CharField(max_length=100, blank=True, verbose_name=_("Module"))
    submodule = models.CharField(max_length=100, blank=True, verbose_name=_("Submodule"))

    class Meta:
        verbose_name = _("Permission")
        verbose_name_plural = _("Permissions")
        db_table = "core_permission"

    def __str__(self):
        if self.name:
            return f"{self.code} - {self.name}"
        return f"{self.code} - {self.description}"
