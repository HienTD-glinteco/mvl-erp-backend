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

            for model_class, info in model_info_map.items():
                # Prefer the actual class name for attribute naming
                raw_name = getattr(model_class, "__name__", str(info.get("model_name", "")).title())
                # Sanitize to a safe Python identifier
                safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch == "_") or raw_name
                if safe_name and safe_name[0].isdigit():
                    safe_name = f"_{safe_name}"

                verbose = info.get("verbose_name") or raw_name
                # Ensure user-facing string goes through translation
                setattr(cls, safe_name, verbose)
        except Exception as exc:  # pragma: no cover - defensive guard
            logging.getLogger(__name__).warning("Failed to populate ObjectType: %s", exc)
