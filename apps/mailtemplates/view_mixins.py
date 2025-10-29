"""Mixins for domain-level template action endpoints."""

from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from .models import EmailSendJob, EmailSendRecipient
from .permissions import CanPreviewRealData
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


class EmailTemplateActionMixin:
    """Mixin to add template-based email functionality to ViewSets.

    This mixin provides reusable helper methods that you can call from
    your ViewSet's action methods.
    
    Usage - define actions manually in your ViewSet:
    
        from rest_framework.decorators import action
        from apps.mailtemplates.view_mixins import EmailTemplateActionMixin
        
        # Define callback function (optional)
        def mark_welcome_email_sent(employee_instance, recipient, **kwargs):
            # kwargs contains any additional params passed via callback_params
            notification_type = kwargs.get("notification_type", "welcome")
            employee_instance.is_sent_welcome_email = True
            employee_instance.last_notification = notification_type
            employee_instance.save(update_fields=["is_sent_welcome_email", "last_notification"])
        
        class EmployeeViewSet(EmailTemplateActionMixin, BaseModelViewSet):
            
            @action(detail=True, methods=["post"], url_path="welcome_email/preview")
            def welcome_email_preview(self, request, pk=None):
                return self.preview_template_email("welcome", request, pk)
            
            @action(detail=True, methods=["post"], url_path="welcome_email/send")
            def welcome_email_send(self, request, pk=None):
                return self.send_template_email(
                    "welcome", 
                    request, 
                    pk,
                    on_success_callback=mark_welcome_email_sent,
                    callback_params={"notification_type": "welcome", "source": "api"}
                )
            
            @action(detail=True, methods=["post"], url_path="contract/preview")
            def contract_preview(self, request, pk=None):
                return self.preview_template_email("contract", request, pk)
            
            @action(detail=True, methods=["post"], url_path="contract/send")
            def contract_send(self, request, pk=None):
                return self.send_template_email("contract", request, pk)
            
            # Optionally override data extraction
            def get_template_action_data(self, instance, template_slug):
                data = super().get_template_action_data(instance, template_slug)
                # Add custom fields
                if template_slug == "welcome":
                    data["custom_field"] = instance.custom_value
                return data

    The mixin expects the ViewSet to have:
    - get_object() method to retrieve the domain object
    - Domain object should have common attributes (email, first_name, etc.)
    
    Callbacks:
    - You can provide an optional callback function via on_success_callback parameter
    - The callback is executed after each successful email send
    - Callback signature: callback(instance, recipient, **callback_params)
    - Can be a callable or a string path like "apps.hrm.callbacks.my_callback"
    - Additional parameters can be passed via callback_params dict
    
    Permissions:
    - Email send actions use the ViewSet's role-based permission system
    - No need to specify custom permission classes on action methods
    """

    def preview_template_email(self, template_slug: str, request, pk=None):
        """Preview template email for an object.
        
        Call this from your action methods to preview an email.
        
        Args:
            template_slug: Template slug (e.g., "welcome")
            request: DRF request object
            pk: Primary key (optional, uses self.get_object() if not provided)
            
        Returns:
            Response with rendered HTML and text
        """
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
                    data = self.get_template_action_data(obj, template_slug)
                # Merge with sample data to ensure all required fields are present
                data = {**template_meta["sample_data"], **data}
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

    def send_template_email(self, template_slug: str, request, pk=None, on_success_callback=None, callback_params=None):
        """Send template email for an object.
        
        Call this from your action methods to send an email.
        
        Args:
            template_slug: Template slug (e.g., "welcome")
            request: DRF request object
            pk: Primary key (optional, uses self.get_object() if not provided)
            on_success_callback: Optional callback path to call after successful send
                                Format: "app.module.function_name" or callable
            callback_params: Optional dict of additional parameters to pass to callback
                           These params will be available to callback in addition to (instance, recipient)
            
        Returns:
            Response with job_id
        """
        obj = self.get_object()

        try:
            template_meta = get_template_metadata(template_slug)

            # Get recipients from request or use object's email
            recipients_data = request.data.get("recipients")

            if not recipients_data:
                # Default to object's email if available
                obj_email = self.get_template_action_email(obj, template_slug)
                if not obj_email:
                    return Response(
                        {"detail": _("No email address found for this object")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Extract data from object
                data = self.get_template_action_data(obj, template_slug)

                recipients_data = [{"email": obj_email, "data": data}]

            # Get subject and sender from request or use defaults
            subject = request.data.get("subject", template_meta["title"])
            sender = request.data.get("sender", settings.DEFAULT_FROM_EMAIL)

            # Validate all recipient data
            for recipient in recipients_data:
                validate_template_data(recipient["data"], template_meta)

            # Prepare callback data if callback provided
            callback_data = None
            if on_success_callback:
                # Store callback information with object reference
                if callable(on_success_callback):
                    # Store the callable's module and name
                    callback_data = {
                        "module": on_success_callback.__module__,
                        "function": on_success_callback.__name__,
                        "object_id": obj.pk,
                        "model_name": obj.__class__.__name__,
                        "app_label": obj._meta.app_label,
                    }
                elif isinstance(on_success_callback, str):
                    # Store the string path
                    callback_data = {
                        "path": on_success_callback,
                        "object_id": obj.pk,
                        "model_name": obj.__class__.__name__,
                        "app_label": obj._meta.app_label,
                    }
                
                # Add callback params if provided
                if callback_params:
                    callback_data["params"] = callback_params

            # Create job
            job = EmailSendJob.objects.create(
                template_slug=template_slug,
                subject=subject,
                sender=sender,
                total=len(recipients_data),
                created_by=request.user if request.user.is_authenticated else None,
                callback_data=callback_data,
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

    def get_template_action_data(self, instance: Any, template_slug: str) -> dict[str, Any]:
        """Extract template data from domain object.

        Override this method to customize data extraction for specific models.

        Args:
            instance: Domain model instance
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

    def get_template_action_email(self, instance: Any, template_slug: str) -> str | None:
        """Extract email address from domain object.

        Override this method to customize email extraction.

        Args:
            instance: Domain model instance
            template_slug: Template slug

        Returns:
            Email address or None
        """
        if hasattr(instance, "email"):
            return getattr(instance, "email")
        return None
