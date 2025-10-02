from django.db import models

from libs.base_model_mixin import BaseModel


class Permission(BaseModel):
    """Model representing a permission in the system"""

    code = models.CharField(max_length=100, unique=True, verbose_name="Mã quyền")
    description = models.CharField(max_length=255, blank=True, verbose_name="Mô tả")

    class Meta:
        verbose_name = "Quyền"
        verbose_name_plural = "Quyền"
        db_table = "core_permission"

    def __str__(self):
        return f"{self.code} - {self.description}"
