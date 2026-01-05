from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel


@audit_logging_register
class Role(AutoCodeMixin, BaseModel):
    """Model representing a role that groups permissions"""

    CODE_PREFIX = "VT"
    TEMP_CODE_PREFIX = "TEMP_"

    code = models.CharField(max_length=50, unique=True, verbose_name="Role code")
    name = models.CharField(max_length=100, unique=True, verbose_name="Role name")
    description = models.CharField(max_length=255, blank=True, verbose_name="Description")
    is_system_role = models.BooleanField(default=False, verbose_name="System role")
    is_default_role = models.BooleanField(default=False, verbose_name="Default role")
    permissions = models.ManyToManyField(
        "Permission",
        related_name="roles",
        verbose_name="Permissions",
        blank=True,
    )  # type: ignore

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        db_table = "core_role"

        ordering = ["code"]

    def clean(self):
        super().clean()
        if self.is_default_role:
            if Role.objects.filter(is_default_role=True).exclude(id=self.id).exists():
                raise ValidationError(_("Only one role can be set as default."))

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["code"])
        super().save(*args, **kwargs)

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
