import logging

from django.db import models
from django.utils.translation import gettext_lazy as _


class LogAction(models.TextChoices):
    """Audit log action types."""

    ADD = "ADD", _("Add")
    CHANGE = "CHANGE", _("Change")
    DELETE = "DELETE", _("Delete")
    IMPORT = "IMPORT", _("Import")
    EXPORT = "EXPORT", _("Export")
    LOGIN = "LOGIN", _("Login")
    PASSWORD_CHANGE = "PASSWORD_CHANGE", _("Password Change")
    PASSWORD_RESET = "PASSWORD_RESET", _("Password Reset")


class _ObjectTypeMeta(type):
    """Metaclass to enable lazy population on first attribute access."""

    def __getattr__(cls, name):
        # Populate once on first attribute access
        if not getattr(cls, "_is_populated", False):
            cls.refresh()
        # Retry attribute lookup after refresh
        try:
            return super().__getattribute__(name)
        except AttributeError:
            # Maintain normal AttributeError semantics
            raise


class ObjectType(metaclass=_ObjectTypeMeta):
    """Dynamic container of translated object type labels for registered models.

    Attributes are populated from the AuditLogRegistry so code can reference
    ObjectType.<ModelClassName> and get a lazily-translated verbose name, e.g.:

        ObjectType.Branch -> _("Branch")
        ObjectType.Block -> _("Block")

    If new models are registered at runtime (e.g., during tests), call
    ObjectType.refresh() to repopulate attributes.
    """

    # One-time population guard
    _is_populated: bool = False

    @classmethod
    def refresh(cls) -> None:
        """Populate class attributes from the AuditLogRegistry.

        For each registered model, define an attribute on this class named after
        the model's class name (sanitized to a valid identifier) whose value is
        the lazily-translated verbose_name of the model.
        """
        if cls._is_populated:
            return

        # Mark as populated after first successful pass
        cls._is_populated = True

        try:
            # Local import to avoid circular imports at module load
            from .registry import AuditLogRegistry  # noqa: WPS433

            model_info_map = AuditLogRegistry.get_all_model_info()
            if not model_info_map:
                return

            for _, info in model_info_map.items():
                model_name = info["model_name"]
                # Prefer the actual class name for attribute naming
                verbose = info.get("verbose_name") or model_name
                # Ensure user-facing string goes through translation
                setattr(cls, model_name, verbose)
        except Exception as exc:  # pragma: no cover - defensive guard
            logging.getLogger(__name__).warning("Failed to populate ObjectType: %s", exc)
