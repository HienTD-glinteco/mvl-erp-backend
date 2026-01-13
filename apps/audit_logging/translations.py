"""Translation utilities for audit log content.

Uses model verbose_name from AuditLogRegistry instead of hardcoded mappings.
"""

from django.utils.translation import gettext_lazy as _

from .registry import AuditLogRegistry

# Only need to define action translations (not model-specific)
ACTION_TRANSLATIONS = {
    "CREATE": _("Create"),
    "UPDATE": _("Update"),
    "DELETE": _("Delete"),
}


def get_object_type_display(object_type: str) -> str:
    """Get translated display name for an object type using model verbose_name.

    Looks up the model in AuditLogRegistry and returns its verbose_name.
    Falls back to humanized object_type if not found.

    Args:
        object_type: The model name (e.g., "Employee", "Proposal")

    Returns:
        Translated display name from model Meta.verbose_name
    """
    # Find model in registry by model_name
    for model_class, info in AuditLogRegistry.get_all_model_info().items():
        if info.get("model_name", "").lower() == object_type.lower():
            verbose_name = info.get("verbose_name")
            if verbose_name:
                return str(verbose_name)
            break

    # Fallback: humanize the object_type
    return object_type.replace("_", " ").title()


def get_field_display(field_name: str, object_type: str | None = None) -> str:
    """Get translated display name for a field using model field's verbose_name.

    Looks up the field in the model and returns its verbose_name.
    Falls back to humanized field_name if not found.

    Args:
        field_name: The field name (e.g., "phone_number", "status")
        object_type: Optional model name to look up field verbose_name

    Returns:
        Translated display name from field.verbose_name
    """
    if object_type:
        for model_class, info in AuditLogRegistry.get_all_model_info().items():
            if info.get("model_name", "").lower() == object_type.lower():
                try:
                    field = model_class._meta.get_field(field_name)
                    if hasattr(field, "verbose_name") and field.verbose_name:
                        return str(field.verbose_name)
                except Exception:
                    pass
                break

    # Fallback: humanize field name
    return field_name.replace("_", " ").title()


def get_action_display(action: str) -> str:
    """Get translated display name for an action."""
    if action in ACTION_TRANSLATIONS:
        return str(ACTION_TRANSLATIONS[action])
    return action.title()


def translate_change_message(
    change_message: dict | str | None, object_type: str | None = None
) -> dict | str | None:
    """Translate field names in change_message using model field verbose_names."""
    if not change_message or not isinstance(change_message, dict):
        return change_message

    rows = change_message.get("rows", [])
    if not rows:
        return change_message

    translated_rows = []
    for row in rows:
        field_name = row.get("field", "")
        translated_rows.append({
            "field": get_field_display(field_name, object_type),
            "old_value": row.get("old_value"),
            "new_value": row.get("new_value"),
        })

    return {
        "headers": [str(_("Field")), str(_("Old value")), str(_("New value"))],
        "rows": translated_rows,
    }
