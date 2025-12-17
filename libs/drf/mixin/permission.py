from typing import Any

from django.utils.translation import gettext_lazy as _


class PermissionRegistrationMixin:
    """
    Mixin for ViewSets with automatic permission registration.

    This mixin provides automatic permission generation for ViewSets.
    Permissions are generated for standard DRF actions and custom actions.

    Class Attributes:
        module (str): Module/system the permissions belong to (e.g., "HRM", "CRM")
        submodule (str): Sub-module within the main module (e.g., "Employee Management")
        permission_prefix (str): Prefix for permission codes (e.g., "document")
    """

    # Allow module/submodule to be plain strings or lazy translation objects
    module: Any = ""
    submodule: Any = ""
    permission_prefix = ""

    # Standard DRF actions with their metadata (full CRUD)
    STANDARD_ACTIONS = {
        "list": {
            "name_template": _("List {model_name}"),
            "description_template": _("View list of {model_name}"),
        },
        "retrieve": {
            "name_template": _("View {model_name}"),
            "description_template": _("View detail of {model_name}"),
        },
        "create": {
            "name_template": _("Create {model_name}"),
            "description_template": _("Create a new {model_name}"),
        },
        "update": {
            "name_template": _("Update {model_name}"),
            "description_template": _("Update {model_name}"),
        },
        "partial_update": {
            "name_template": _("Partially update {model_name}"),
            "description_template": _("Partially update {model_name}"),
        },
        "destroy": {
            "name_template": _("Delete {model_name}"),
            "description_template": _("Delete {model_name}"),
        },
        "export": {
            "name_template": _("Export {model_name}"),
            "description_template": _("Export {model_name} data"),
        },
        "histories": {
            "name_template": _("History {model_name}"),
            "description_template": _("View history of {model_name}"),
        },
        "history_detail": {
            "name_template": _("History detail of {model_name}"),
            "description_template": _("View history detail of {model_name}"),
        },
    }

    @classmethod
    def get_model_name(cls):
        """
        Get the model name in a human-readable format.

        Returns:
            str: Model name (e.g., "Role", "Permission")
        """
        if hasattr(cls, "queryset") and cls.queryset is not None:
            return cls.queryset.model._meta.verbose_name
        return cls.__name__.replace("ViewSet", "")

    @classmethod
    def get_model_name_plural(cls):
        """
        Get the plural model name in a human-readable format.

        Returns:
            str: Plural model name (e.g., "Roles", "Permissions")
        """
        if hasattr(cls, "queryset") and cls.queryset is not None:
            return cls.queryset.model._meta.verbose_name_plural.title()
        return cls.__name__.replace("ViewSet", "") + "s"

    @classmethod
    def get_custom_actions(cls):
        """
        Get all custom actions defined in the viewset.

        Returns:
            list: List of custom action names (decorated with @action)
        """
        custom_actions = []
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name)
            if callable(attr) and hasattr(attr, "mapping"):
                # This is a DRF action
                if attr_name not in cls.STANDARD_ACTIONS:
                    if (
                        hasattr(cls, "PERMISSION_REGISTERED_ACTIONS")
                        and attr_name in cls.PERMISSION_REGISTERED_ACTIONS
                    ):
                        continue
                    custom_actions.append(attr_name)
        return custom_actions

    @classmethod
    def get_permission_registered_actions(cls):
        """
        Get all custom actions defined in the viewset.

        Returns:
            list: List of custom action names (decorated with @action)
        """
        custom_actions = []
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name)
            if callable(attr) and hasattr(attr, "mapping") and hasattr(cls, "PERMISSION_REGISTERED_ACTIONS"):
                # This is a DRF action
                if attr_name in cls.PERMISSION_REGISTERED_ACTIONS:
                    custom_actions.append(attr_name)
        return custom_actions

    @classmethod
    def get_registered_permissions(cls):
        """
        Get all permission metadata for this viewset.

        This method generates permission metadata for all standard DRF actions
        that the viewset supports, plus any custom actions decorated with @action.

        Returns:
            list: List of permission dictionaries with keys:
                - code: Permission code (e.g., "document.list")
                - name: Human-readable name (e.g., "List Documents")
                - description: Permission description (e.g., "View list of documents")
                - module: Module name (e.g., "HRM")
                - submodule: Submodule name (e.g., "Document Management")
        """
        if not cls.permission_prefix:
            # Skip viewsets without permission_prefix
            return []

        permissions = []
        model_name = cls.get_model_name()
        model_name_plural = cls.get_model_name_plural()
        # Generate permissions for standard actions
        for action_name, action_meta in cls.STANDARD_ACTIONS.items():
            # Check if the viewset supports this action
            if hasattr(cls, action_name):
                # Use plural for list action, singular for others
                display_name = model_name_plural if action_name == "list" else model_name

                permissions.append(
                    {
                        "code": f"{cls.permission_prefix}.{action_name}",
                        "name": str(action_meta["name_template"]).format(model_name=display_name),
                        "description": str(action_meta["description_template"]).format(model_name=display_name),
                        "module": cls.module,
                        "submodule": cls.submodule,
                    }
                )
        # Genetrate permissions for registered actions
        for action_name in cls.get_permission_registered_actions():
            action_meta = cls.PERMISSION_REGISTERED_ACTIONS[action_name]
            permissions.append(
                {
                    "code": f"{cls.permission_prefix}.{action_name}",
                    "name": str(action_meta["name_template"]).format(model_name=model_name),
                    "description": str(action_meta["description_template"]).format(model_name=model_name),
                    "module": cls.module,
                    "submodule": cls.submodule,
                }
            )

        # Generate permissions for custom actions
        for action_name in cls.get_custom_actions():
            # attr = getattr(cls, action_name)
            # Convert action name to readable format (e.g., "approve" -> "Approve")
            action_title = action_name.replace("_", " ").title()

            permissions.append(
                {
                    "code": f"{cls.permission_prefix}.{action_name}",
                    "name": f"UNREGISTERED {action_title} {model_name}",
                    "description": f"You need to add this action to PERMISSION_REGISTERED_ACTIONS to it's View {action_title} a {model_name}",
                    "module": cls.module,
                    "submodule": cls.submodule,
                }
            )

        return permissions
