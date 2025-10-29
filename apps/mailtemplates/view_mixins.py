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
from .serializers import TemplatePreviewRequestSerializer
from .services import (
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
    get_template_metadata,
    render_and_prepare_email,
    validate_template_data,
)
from .tasks import send_email_job_task


def generate_email_action_methods(email_actions: dict[str, str]) -> dict[str, Any]:
    """Generate email action methods from email_actions dict.
    
    This function is meant to be called in the ViewSet class body to define methods.
    
    Args:
        email_actions: Dictionary mapping action_name -> template_slug
        
    Returns:
        Dictionary of method_name -> method to be added to class namespace
        
    Example usage:
        class EmployeeViewSet(TemplateActionMixin, BaseModelViewSet):
            email_actions = {
                "send_welcome_email": "welcome",
            }
            
            # Generate the action methods
            locals().update(generate_email_action_methods(email_actions))
    """
    methods = {}
    
    for action_name, template_slug in email_actions.items():
        # Create preview action
        def make_preview_method(action_name=action_name, template_slug=template_slug):
            @action(
                detail=True,
                methods=["post"],
                url_path=f"{action_name}/preview",
                permission_classes=[IsAuthenticated],
            )
            def preview_method(self, request, pk=None):
                return self._handle_preview(request, pk, action_name, template_slug)
            preview_method.__name__ = f"{action_name}_preview"
            return preview_method
        
        # Create send action
        def make_send_method(action_name=action_name, template_slug=template_slug):
            @action(
                detail=True,
                methods=["post"],
                url_path=f"{action_name}/send",
                permission_classes=[CanSendMail],
            )
            def send_method(self, request, pk=None):
                return self._handle_send(request, pk, action_name, template_slug)
            send_method.__name__ = f"{action_name}_send"
            return send_method
        
        methods[f"{action_name}_preview"] = make_preview_method()
        methods[f"{action_name}_send"] = make_send_method()
    
    return methods


class TemplateActionMixin:
    """Mixin to add template-based email actions to ViewSets.

    This mixin provides preview and send actions for domain objects.
    
    To use this mixin, define `email_actions` and call `generate_email_action_methods()`:
    
    Example usage:
        class EmployeeViewSet(TemplateActionMixin, BaseModelViewSet):
            email_actions = {
                "send_welcome_email": "welcome",
                "send_contract": "contract",
            }
            
            # Generate action methods - this must be in the class body
            locals().update(generate_email_action_methods(email_actions))
            
            # This will automatically provide:
            # - POST /api/employees/{pk}/send_welcome_email/preview/
            # - POST /api/employees/{pk}/send_welcome_email/send/
            # - POST /api/employees/{pk}/send_contract/preview/
            # - POST /api/employees/{pk}/send_contract/send/

    The mixin expects the ViewSet to have:
    - get_object() method to retrieve the domain object
    - Domain object should have common attributes or a method to extract template data
    """

    email_actions: dict[str, str] = {}  # Map action_name -> template_slug

    def get_template_action_data(self, instance: Any, action_name: str, template_slug: str) -> dict[str, Any]:
        """Extract template data from domain object.

        Override this method to customize data extraction for specific models.

        Args:
            instance: Domain model instance
            action_name: Action name (e.g., 'send_welcome_email')
            template_slug: Template slug (e.g., 'welcome')

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

    def get_template_action_email(self, instance: Any, action_name: str, template_slug: str) -> str | None:
        """Extract email address from domain object.

        Override this method to customize email extraction.

        Args:
            instance: Domain model instance
            action_name: Action name
            template_slug: Template slug

        Returns:
            Email address or None
        """
        if hasattr(instance, "email"):
            return getattr(instance, "email")
        return None

    def _handle_preview(self, request, pk=None, action_name=None, template_slug=None):
        """Handle preview request for a template action."""
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
            template_meta = get_template_metadata(template_slug)

            # Determine data to use
            if use_real or serializer.validated_data.get("data"):
                # Use provided data or extract from object
                data = serializer.validated_data.get("data")
                if not data:
                    data = self.get_template_action_data(obj, action_name, template_slug)
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

    def _handle_send(self, request, pk=None, action_name=None, template_slug=None):
        """Handle send request for a template action."""
        obj = self.get_object()

        try:
            template_meta = get_template_metadata(template_slug)

            # Get recipients from request or use object's email
            recipients_data = request.data.get("recipients")

            if not recipients_data:
                # Default to object's email if available
                obj_email = self.get_template_action_email(obj, action_name, template_slug)
                if not obj_email:
                    return Response(
                        {"detail": _("No email address found for this object")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Extract data from object
                data = self.get_template_action_data(obj, action_name, template_slug)

                recipients_data = [{"email": obj_email, "data": data}]

            # Get subject and sender from request or use defaults
            subject = request.data.get("subject", template_meta["title"])
            sender = request.data.get("sender", settings.DEFAULT_FROM_EMAIL)

            # Validate all recipient data
            for recipient in recipients_data:
                validate_template_data(recipient["data"], template_meta)

            # Create job
            job = EmailSendJob.objects.create(
                template_slug=template_slug,
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


