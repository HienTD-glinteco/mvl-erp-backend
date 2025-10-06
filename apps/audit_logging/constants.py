from django.db import models
from django.utils.translation import gettext_lazy as _


class LogAction(models.TextChoices):
    """Audit log action types."""

    ADD = "ADD", _("Add")
    CHANGE = "CHANGE", _("Change")
    DELETE = "DELETE", _("Delete")
    IMPORT = "IMPORT", _("Import")
    EXPORT = "EXPORT", _("Export")


class ObjectType(models.TextChoices):
    pass
