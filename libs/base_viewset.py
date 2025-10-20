"""
Base ViewSet with automatic permission registration.

This module provides base ViewSet classes that automatically generate
permission metadata for all standard DRF actions and custom actions.
"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


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

    module = ""
    submodule = ""
    permission_prefix = ""

    # Standard DRF actions with their metadata (full CRUD)
    STANDARD_ACTIONS = {
        "list": {
            "name_template": _("List {model_name}"),
            "description_template": _("View list of {model_name}"),
        },
        "retrieve": {
            "name_template": _("View {model_name}"),
            "description_template": _("View details of a {model_name}"),
        },
        "create": {
            "name_template": _("Create {model_name}"),
            "description_template": _("Create a new {model_name}"),
        },
        "update": {
            "name_template": _("Update {model_name}"),
            "description_template": _("Update a {model_name}"),
        },
        "partial_update": {
            "name_template": _("Partially update {model_name}"),
            "description_template": _("Partially update a {model_name}"),
        },
        "destroy": {
            "name_template": _("Delete {model_name}"),
            "description_template": _("Delete a {model_name}"),
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
            # Get the model class name and convert to readable format
            # e.g., "OrganizationChart" -> "Organization Chart"
            model_name = cls.queryset.model.__name__
            # Add space before capital letters (except the first one)
            import re

            spaced_name = re.sub(r"(?<!^)(?=[A-Z])", " ", model_name)
            return spaced_name
        return cls.__name__.replace("ViewSet", "")

    @classmethod
    def get_model_name_plural(cls):
        """
        Get the plural model name in a human-readable format.

        Returns:
            str: Plural model name (e.g., "Roles", "Permissions")
        """
        model_name = cls.get_model_name()
        # Simple pluralization: add 's' or 'es'
        if model_name.endswith(("s", "x", "z", "ch", "sh")):
            return model_name + "es"
        elif model_name.endswith("y") and len(model_name) > 1 and model_name[-2] not in "aeiou":
            return model_name[:-1] + "ies"
        else:
            return model_name + "s"

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

        # Generate permissions for custom actions
        for action_name in cls.get_custom_actions():
            attr = getattr(cls, action_name)
            # Convert action name to readable format (e.g., "approve" -> "Approve")
            action_title = action_name.replace("_", " ").title()

            permissions.append(
                {
                    "code": f"{cls.permission_prefix}.{action_name}",
                    "name": f"{action_title} {model_name}",
                    "description": f"{action_title} a {model_name}",
                    "module": cls.module,
                    "submodule": cls.submodule,
                }
            )

        return permissions


class HistoryMixin:
    """
    Mixin that adds a history action to ViewSets.

    This mixin provides an endpoint to retrieve the audit log history
    of a specific object instance. It queries the audit logging system
    based on the object's type and ID.

    Requirements:
        - The ViewSet must have a queryset with a model
        - The model should be registered with @audit_logging_register
        - The ViewSet should inherit from this mixin before ModelViewSet

    Usage:
        class CustomerViewSet(HistoryMixin, BaseModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            module = "CRM"
            submodule = "Customer Management"
            permission_prefix = "customer"

        This will automatically add:
            - GET /customers/{id}/history/ endpoint
            - customer.history permission
    """

    @extend_schema(
        summary="Get object history",
        description="Retrieve the audit log history for this object, showing all changes made over time",
        tags=["History"],
        parameters=[
            OpenApiParameter(
                name="id",
                type=str,
                location=OpenApiParameter.PATH,
                description="ID of the object",
                required=True,
            ),
            OpenApiParameter(
                name="from_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter logs from this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="to_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter logs to this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="action",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by action type (CREATE, CHANGE, DELETE)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of results per page (1-100, default: 50)",
                required=False,
            ),
            OpenApiParameter(
                name="from_offset",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Offset for pagination (default: 0)",
                required=False,
            ),
        ],
        examples=[
            OpenApiExample(
                "Success - History with changes",
                description="Example response showing object history with field-level changes",
                value={
                    "success": True,
                    "data": {
                        "results": [
                            {
                                "log_id": "abc123def456",
                                "timestamp": "2025-10-13T14:30:00Z",
                                "user_id": "user-uuid-1",
                                "username": "admin@example.com",
                                "full_name": "Admin User",
                                "employee_code": "EMP001",
                                "action": "CHANGE",
                                "object_type": "customer",
                                "object_id": "123",
                                "object_repr": "John Doe",
                                "change_message": {
                                    "headers": ["field", "old_value", "new_value"],
                                    "rows": [
                                        {
                                            "field": "Email",
                                            "old_value": "old@example.com",
                                            "new_value": "new@example.com",
                                        },
                                        {"field": "Phone", "old_value": "0123456789", "new_value": "0987654321"},
                                    ],
                                },
                            },
                            {
                                "log_id": "xyz789uvw012",
                                "timestamp": "2025-10-12T10:15:00Z",
                                "user_id": "user-uuid-2",
                                "username": "john.doe@example.com",
                                "full_name": "John Doe",
                                "action": "CREATE",
                                "object_type": "customer",
                                "object_id": "123",
                                "object_repr": "John Doe",
                                "change_message": "Created new object",
                            },
                        ],
                        "total": 2,
                        "page_size": 50,
                        "from_offset": 0,
                        "has_next": False,
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Object not found",
                description="Error response when object doesn't exist",
                value={"success": False, "error": "Object not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        Get the audit log history for a specific object.

        Returns a list of all audit log entries for this object,
        including create, update, and delete actions.
        """
        # Import here to avoid circular dependency
        from apps.audit_logging.api.serializers import AuditLogSearchSerializer
        from apps.audit_logging.exceptions import AuditLogException

        # Get the object to ensure it exists and get its model info
        try:
            obj = self.get_object()
        except Exception:
            return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get model metadata
        model_class = obj.__class__
        object_type = model_class._meta.model_name
        object_id = str(obj.pk)

        # Build search parameters
        search_params = {
            "object_type": object_type,
            "object_id": object_id,
        }

        # Add optional filters from query params
        if request.query_params.get("from_date"):
            search_params["from_date"] = request.query_params["from_date"]
        if request.query_params.get("to_date"):
            search_params["to_date"] = request.query_params["to_date"]
        if request.query_params.get("action"):
            search_params["action"] = request.query_params["action"]
        if request.query_params.get("page_size"):
            search_params["page_size"] = request.query_params["page_size"]
        if request.query_params.get("from_offset"):
            search_params["from_offset"] = request.query_params["from_offset"]

        # Use the audit log search serializer
        serializer = AuditLogSearchSerializer(data=search_params)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Execute search
            result = serializer.search()
            return Response(result)
        except AuditLogException as e:
            return Response(
                {"error": f"Failed to retrieve history: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BaseModelViewSet(HistoryMixin, PermissionRegistrationMixin, viewsets.ModelViewSet):
    """
    Base ModelViewSet with automatic permission registration.

    All project viewsets that need full CRUD should inherit from this class.

    Example:
        class DocumentViewSet(BaseModelViewSet):
            queryset = Document.objects.all()
            serializer_class = DocumentSerializer
            module = "HRM"
            submodule = "Document Management"
            permission_prefix = "document"

        This will automatically generate permissions:
            - document.list
            - document.retrieve
            - document.create
            - document.update
            - document.destroy
    """

    pass


class BaseReadOnlyModelViewSet(HistoryMixin, PermissionRegistrationMixin, viewsets.ReadOnlyModelViewSet):
    """
    Base ReadOnlyModelViewSet with automatic permission registration.

    All project viewsets that only need read operations should inherit from this class.

    Example:
        class PermissionViewSet(BaseReadOnlyModelViewSet):
            queryset = Permission.objects.all()
            serializer_class = PermissionSerializer
            module = "Core"
            submodule = "Permission Management"
            permission_prefix = "permission"

        This will automatically generate permissions:
            - permission.list
            - permission.retrieve
    """

    # Override STANDARD_ACTIONS to only include read operations
    STANDARD_ACTIONS = {
        "list": {
            "name_template": _("List {model_name}"),
            "description_template": _("View list of {model_name}"),
        },
        "retrieve": {
            "name_template": _("View {model_name}"),
            "description_template": _("View details of a {model_name}"),
        },
    }
