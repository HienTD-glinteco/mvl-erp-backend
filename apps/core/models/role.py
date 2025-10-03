from django.db import models

from libs.base_model_mixin import BaseModel


class Role(BaseModel):
    """Model representing a role that groups permissions"""

    name = models.CharField(max_length=100, unique=True, verbose_name="Tên vai trò")
    description = models.CharField(max_length=255, blank=True, verbose_name="Mô tả")
    permissions = models.ManyToManyField(
        "Permission",
        related_name="roles",
        verbose_name="Quyền",
        blank=True,
    )  # type: ignore

    class Meta:
        verbose_name = "Vai trò"
        verbose_name_plural = "Vai trò"
        db_table = "core_role"

    def __str__(self):
        return self.name
