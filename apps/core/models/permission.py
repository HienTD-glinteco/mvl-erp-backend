from django.db import models

from libs.models import BaseModel


class Permission(BaseModel):
    """Model representing a permission in the system"""

    code = models.CharField(max_length=100, unique=True, verbose_name="Permission code")
    name = models.CharField(max_length=255, blank=True, verbose_name="Permission name")
    description = models.CharField(max_length=255, blank=True, verbose_name="Description")
    module = models.CharField(max_length=100, blank=True, verbose_name="Module")
    submodule = models.CharField(max_length=100, blank=True, verbose_name="Submodule")

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        db_table = "core_permission"

    def __str__(self):
        if self.name:
            return f"{self.code} - {self.name}"
        return f"{self.code} - {self.description}"
