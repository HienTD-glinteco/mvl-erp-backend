from django.db import models

from libs.base_model_mixin import BaseModel


class Role(BaseModel):
    """Model representing a role that groups permissions"""

    code = models.CharField(max_length=50, unique=True, verbose_name="Mã vai trò")
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên vai trò")
    description = models.CharField(max_length=255, blank=True, verbose_name="Mô tả")
    is_system_role = models.BooleanField(default=False, verbose_name="Vai trò hệ thống")
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
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def created_by_display(self):
        """Display created by source"""
        return "Hệ thống" if self.is_system_role else "Người dùng"

    def can_delete(self):
        """Check if role can be deleted"""
        # System roles cannot be deleted
        if self.is_system_role:
            return False, "Không thể xóa vai trò hệ thống."

        # Check if role is in use by any users
        if self.users.exists():
            return False, "Vai trò đang được sử dụng bởi nhân viên."

        return True, None
