from django.db import models
from django.utils.translation import gettext as _, gettext_lazy

from apps.audit_logging.decorators import audit_logging_register
from libs.base_model_mixin import BaseModel


@audit_logging_register
class Role(BaseModel):
    """Model representing a role that groups permissions"""

    code = models.CharField(max_length=50, unique=True, verbose_name=gettext_lazy("Role code"))
    name = models.CharField(max_length=100, unique=True, verbose_name=gettext_lazy("Role name"))
    description = models.CharField(max_length=255, blank=True, verbose_name=gettext_lazy("Description"))
    is_system_role = models.BooleanField(default=False, verbose_name=gettext_lazy("System role"))
    permissions = models.ManyToManyField(
        "Permission",
        related_name="roles",
        verbose_name=gettext_lazy("Permissions"),
        blank=True,
    )  # type: ignore

    class Meta:
        verbose_name = gettext_lazy("Role")
        verbose_name_plural = gettext_lazy("Roles")
        db_table = "core_role"

        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def created_by_display(self):
        """Display created by source"""
        return _("System") if self.is_system_role else _("User")

    def can_delete(self):
        """Check if role can be deleted"""
        # System roles cannot be deleted
        if self.is_system_role:
            return False, _("Cannot delete system role")

        # Check if role is in use by any users
        if self.users.exists():
            return False, _("Role is currently being used by employees")

        return True, None
