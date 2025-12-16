"""
Base ViewSet with automatic permission registration.

This module provides base ViewSet classes that automatically generate
permission metadata for all standard DRF actions and custom actions.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets

from libs.drf.mixin.permission import PermissionRegistrationMixin
from libs.drf.mixin.protected_delete import ProtectedDeleteMixin


class BaseModelViewSet(ProtectedDeleteMixin, PermissionRegistrationMixin, viewsets.ModelViewSet):
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


class BaseReadOnlyModelViewSet(PermissionRegistrationMixin, viewsets.ReadOnlyModelViewSet):
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
        "histories": {
            "name_template": _("History {model_name}"),
            "description_template": _("View history of {model_name}"),
        },
        "history_detail": {
            "name_template": _("History detail of {model_name}"),
            "description_template": _("View history detail of {model_name}"),
        },
    }


class BaseGenericViewSet(PermissionRegistrationMixin, viewsets.GenericViewSet):
    pass
