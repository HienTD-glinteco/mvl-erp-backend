"""Mixins for domain-level template action endpoints."""

from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import EmailSendJob, EmailSendRecipient
from .permissions import CanPreviewRealData, CanSendMail
from .serializers import BulkSendRequestSerializer, TemplatePreviewRequestSerializer
from .services import (
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
    get_template_by_action,
    render_and_prepare_email,
    validate_template_data,
)
from .tasks import send_email_job_task


class TemplateActionMixin:
    """Mixin to add template-based email actions to ViewSets.

    This mixin provides preview and send actions for domain objects.
    Actions are defined by ACTION_TEMPLATE_MAP in constants.py.

    Example usage:
        class EmployeeViewSet(TemplateActionMixin, BaseModelViewSet):
            # This will automatically provide:
            # - POST /api/employees/{pk}/send_welcome_email/preview/
            # - POST /api/employees/{pk}/send_welcome_email/send/
            pass

    The mixin expects the ViewSet to have:
    - get_object() method to retrieve the domain object
    - Domain object should have common attributes or a method to extract template data
    """

    def get_template_action_data(self, instance: Any, action_key: str) -> dict[str, Any]:
        """Extract template data from domain object.

        Override this method to customize data extraction for specific models.

        Args:
            instance: Domain model instance
            action_key: Action identifier

        Returns:
            Dictionary with template variables

        Default behavior:
            Maps common attribute names to template variables.
            For Employee: first_name, start_date, position, department
        """
        # Default simple attribute mapping
        data: dict[str, Any] = {}

        # Common employee attributes
        if hasattr(instance, "first_name"):
            data["first_name"] = getattr(instance, "first_name", "")
        if hasattr(instance, "fullname"):
            data["candidate_name"] = getattr(instance, "fullname", "")

        if hasattr(instance, "start_date"):
            start_date = getattr(instance, "start_date")
            data["start_date"] = start_date.isoformat() if start_date else ""

        if hasattr(instance, "position"):
            position = getattr(instance, "position")
            data["position"] = position.name if position and hasattr(position, "name") else ""

        if hasattr(instance, "department"):
            department = getattr(instance, "department")
            data["department"] = department.name if department and hasattr(department, "name") else ""

        return data

    def get_template_action_email(self, instance: Any, action_key: str) -> str | None:
        """Extract email address from domain object.

        Override this method to customize email extraction.

        Args:
            instance: Domain model instance
            action_key: Action identifier

        Returns:
            Email address or None
        """
        if hasattr(instance, "email"):
            return getattr(instance, "email")
        return None

    def _create_template_action(self, action_key: str):
        """Create preview and send actions for a specific action key."""

        @action(
            detail=True,
            methods=["post"],
            url_path=f"{action_key}/preview",
            permission_classes=[IsAuthenticated],
        )
        def preview_action(self, request, pk=None):
            """Preview template for this object."""
            obj = self.get_object()
            use_real = request.query_params.get("use_real", "0") == "1"

            # Check permissions for real data
            if use_real:
                permission = CanPreviewRealData()
                if not permission.has_permission(request, self):
                    return Response(
                        {"detail": _("Real data preview permission required")},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            serializer = TemplatePreviewRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                template_meta, action_config = get_template_by_action(action_key)

                # Determine data to use
                if use_real or serializer.validated_data.get("data"):
                    # Use provided data or extract from object
                    data = serializer.validated_data.get("data")
                    if not data:
                        data = self.get_template_action_data(obj, action_key)
                else:
                    # Use sample data
                    data = template_meta["sample_data"]

                # Render template
                result = render_and_prepare_email(template_meta, data, validate=True)

                return Response(result)

            except TemplateNotFoundError as e:
                return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
            except TemplateValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except TemplateRenderError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        @action(
            detail=True,
            methods=["post"],
            url_path=f"{action_key}/send",
            permission_classes=[CanSendMail],
        )
        def send_action(self, request, pk=None):
            """Send email for this object."""
            obj = self.get_object()

            try:
                template_meta, action_config = get_template_by_action(action_key)

                # Get recipients from request or use object's email
                recipients_data = request.data.get("recipients")

                if not recipients_data:
                    # Default to object's email if available
                    obj_email = self.get_template_action_email(obj, action_key)
                    if not obj_email:
                        return Response(
                            {"detail": _("No email address found for this object")},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Extract data from object
                    data = self.get_template_action_data(obj, action_key)

                    recipients_data = [{"email": obj_email, "data": data}]

                # Get subject and sender from request or use defaults
                subject = request.data.get("subject", action_config.get("default_subject", template_meta["title"]))
                sender = request.data.get("sender", action_config.get("default_sender") or settings.DEFAULT_FROM_EMAIL)

                # Validate all recipient data
                for recipient in recipients_data:
                    validate_template_data(recipient["data"], template_meta)

                # Create job
                job = EmailSendJob.objects.create(
                    template_slug=template_meta["slug"],
                    subject=subject,
                    sender=sender,
                    total=len(recipients_data),
                    created_by=request.user if request.user.is_authenticated else None,
                )

                # Create recipients
                for recipient in recipients_data:
                    EmailSendRecipient.objects.create(
                        job=job,
                        email=recipient["email"],
                        data=recipient["data"],
                    )

                # Enqueue task
                send_email_job_task.delay(str(job.id))

                return Response(
                    {
                        "job_id": str(job.id),
                        "detail": _("Email send job enqueued"),
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            except TemplateNotFoundError as e:
                return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
            except TemplateValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Dynamically set method names to avoid conflicts
        preview_action.__name__ = f"{action_key}_preview"
        send_action.__name__ = f"{action_key}_send"

        return preview_action, send_action

    def __init__(self, *args, **kwargs):
        """Initialize mixin and register template actions."""
        super().__init__(*args, **kwargs)

        # Import here to avoid circular imports
        from .constants import ACTION_TEMPLATE_MAP

        # Register all actions from ACTION_TEMPLATE_MAP
        for action_key in ACTION_TEMPLATE_MAP.keys():
            preview_func, send_func = self._create_template_action(action_key)

            # Attach methods to the class instance
            setattr(self, f"{action_key}_preview", preview_func.__get__(self, self.__class__))
            setattr(self, f"{action_key}_send", send_func.__get__(self, self.__class__))
