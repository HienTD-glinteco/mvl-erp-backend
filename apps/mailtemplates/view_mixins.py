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

    Note: This mixin expects to be used with a ViewSet that has get_object() method.

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
        obj = self.get_object()  # type: ignore[attr-defined]
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

            # Add subject to response with priority logic
            subject = None
            if serializer.validated_data.get("data") and "subject" in serializer.validated_data["data"]:
                subject = serializer.validated_data["data"]["subject"]
            elif "default_subject" in template_meta:
                subject = template_meta["default_subject"]
            
            result["subject"] = subject

            return Response(result)

        except TemplateNotFoundError as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except TemplateValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except TemplateRenderError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def send_template_email(  # noqa: C901
        self, template_slug: str, request, pk=None, on_success_callback=None, callback_params=None
    ):
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
        from django.db import transaction

        obj = self.get_object()  # type: ignore[attr-defined]

        try:
            template_meta = get_template_metadata(template_slug)

            # Get recipients using the new hook
            try:
                recipients_data = self.get_recipients(request, obj)
            except Exception:
                # Don't expose internal exception details
                return Response(
                    {"detail": _("Failed to get recipients. Override get_recipients() or provide recipients in request.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate recipients list
            if not recipients_data:
                return Response(
                    {"detail": _("No recipients found")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate all recipient data
            for recipient in recipients_data:
                if "email" not in recipient or "data" not in recipient:
                    return Response(
                        {"detail": _("Each recipient must have 'email' and 'data' fields")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                validate_template_data(recipient["data"], template_meta)

            # Get subject and sender from request or use defaults
            subject = request.data.get("subject")
            if not subject:
                subject = template_meta.get("default_subject", template_meta["title"])
            sender = request.data.get("sender", settings.DEFAULT_FROM_EMAIL)

            # Get client_request_id if provided
            client_request_id = request.data.get("client_request_id")

            # Prepare callback data for job-level if callback provided
            job_callback_data = None
            if on_success_callback:
                # Store callback information with object reference
                if callable(on_success_callback):
                    # Store the callable's module and name
                    job_callback_data = {
                        "module": on_success_callback.__module__,
                        "function": on_success_callback.__name__,
                        "object_id": obj.pk,
                        "model_name": obj.__class__.__name__,
                        "app_label": obj._meta.app_label,
                    }
                elif isinstance(on_success_callback, str):
                    # Store the string path
                    job_callback_data = {
                        "path": on_success_callback,
                        "object_id": obj.pk,
                        "model_name": obj.__class__.__name__,
                        "app_label": obj._meta.app_label,
                    }

                # Add callback params if provided
                if callback_params and job_callback_data is not None:
                    job_callback_data["params"] = callback_params

            # Create job and recipients atomically
            with transaction.atomic():
                job = EmailSendJob.objects.create(
                    template_slug=template_slug,
                    subject=subject,
                    sender=sender,
                    total=len(recipients_data),
                    created_by=request.user if request.user.is_authenticated else None,
                    callback_data=job_callback_data,
                    client_request_id=client_request_id,
                )

                # Create recipients with per-recipient callback_data
                for recipient in recipients_data:
                    # Prepare per-recipient callback data if provided
                    recipient_callback_data = recipient.get("callback_data")
                    
                    # If job-level callback exists and recipient doesn't have callback_data,
                    # we'll let the task use job-level callback
                    EmailSendRecipient.objects.create(
                        job=job,
                        email=recipient["email"],
                        data=recipient["data"],
                        callback_data=recipient_callback_data,
                    )

            # Enqueue task
            send_email_job_task.delay(str(job.id))

            return Response(
                {
                    "job_id": str(job.id),
                    "total_recipients": len(recipients_data),
                    "detail": _("Email send job enqueued"),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except TemplateNotFoundError:
            return Response({"detail": _("Template not found")}, status=status.HTTP_404_NOT_FOUND)
        except TemplateValidationError:
            return Response({"detail": _("Template validation failed. Please check your data.")}, status=status.HTTP_400_BAD_REQUEST)

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
            For Employee: fullname, start_date, position, department
        """
        # Default simple attribute mapping
        data: dict[str, Any] = {}

        # Common employee attributes
        if hasattr(instance, "fullname"):
            data["fullname"] = getattr(instance, "fullname", "")
        if hasattr(instance, "fullname"):
            data["candidate_name"] = getattr(instance, "fullname", "")

        if hasattr(instance, "start_date"):
            start_date = instance.start_date
            data["start_date"] = start_date.isoformat() if start_date else ""

        if hasattr(instance, "position"):
            position = instance.position
            data["position"] = position.name if position and hasattr(position, "name") else ""

        if hasattr(instance, "department"):
            department = instance.department
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
            return instance.email
        return None

    def get_recipients(self, request, instance: Any) -> list[dict[str, Any]]:
        """Get recipients for an instance.

        Override this method to support multiple recipients per instance.

        Args:
            request: DRF request object
            instance: Domain model instance

        Returns:
            List of recipient dicts, each containing:
            - email: recipient email address (required)
            - data: template context data (required)
            - callback_data: per-recipient callback data (optional)

        Default behavior:
            Returns a single recipient using instance.email and extracted data.
            If instance has no email, raises ValidationError.
        """
        # Check if recipients provided in request
        recipients_data = request.data.get("recipients")
        if recipients_data:
            return recipients_data

        # Default: single recipient from instance
        # Note: template_slug may not be available in this context, pass empty string
        email = self.get_template_action_email(instance, template_slug="")
        if not email:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                _("No email address found. Override get_recipients() to provide recipients.")
            )

        # Extract data from instance - get template_slug from request if available
        template_slug_param = request.data.get("template_slug", "")
        data = self.get_template_action_data(instance, template_slug_param)

        return [{"email": email, "data": data}]

    def bulk_send_template_mail(self, request):  # noqa: C901
        """Send template email for multiple objects.

        This method creates a single job for multiple objects, collecting recipients from each.

        Args:
            request: DRF request object containing:
                - template_slug (required)
                - object_ids or filters (one required)
                - subject (optional)
                - sender (optional)
                - client_request_id (optional)
                - meta (optional)

        Returns:
            Response with job_id and total_recipients
        """
        from django.db import transaction
        from .serializers import BulkSendTemplateMailRequestSerializer

        serializer = BulkSendTemplateMailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        template_slug = serializer.validated_data["template_slug"]
        object_ids = serializer.validated_data.get("object_ids")
        filters = serializer.validated_data.get("filters")
        subject = serializer.validated_data.get("subject")
        sender = serializer.validated_data.get("sender", settings.DEFAULT_FROM_EMAIL)
        client_request_id = serializer.validated_data.get("client_request_id")

        try:
            template_meta = get_template_metadata(template_slug)

            # Use default subject if not provided
            if not subject:
                subject = template_meta.get("default_subject", template_meta["title"])

            # Get queryset and apply filters
            queryset = self.get_queryset()  # type: ignore[attr-defined]

            if object_ids:
                instances = queryset.filter(pk__in=object_ids)
            elif filters:
                # Apply filters to queryset
                # ViewSet should implement filter logic or use filterset_class
                instances = queryset.filter(**filters)
            else:
                return Response(
                    {"detail": _("Either object_ids or filters must be provided")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Collect all recipients from all instances
            all_recipients = []
            for instance in instances:
                try:
                    recipients = self.get_recipients(request, instance)
                    all_recipients.extend(recipients)
                except Exception:
                    # Don't expose internal exception details to users
                    error_message = _("Failed to get recipients for instance") + f" {instance.pk}"
                    return Response(
                        {"detail": error_message},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Validate all recipients
            if not all_recipients:
                return Response(
                    {"detail": _("No recipients found for the selected objects")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for recipient in all_recipients:
                if "email" not in recipient or "data" not in recipient:
                    return Response(
                        {"detail": _("Each recipient must have 'email' and 'data' fields")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                validate_template_data(recipient["data"], template_meta)

            # Create job and recipients atomically
            with transaction.atomic():
                job = EmailSendJob.objects.create(
                    template_slug=template_slug,
                    subject=subject,
                    sender=sender,
                    total=len(all_recipients),
                    created_by=request.user if request.user.is_authenticated else None,
                    client_request_id=client_request_id,
                )

                # Create all recipient records
                for recipient in all_recipients:
                    EmailSendRecipient.objects.create(
                        job=job,
                        email=recipient["email"],
                        data=recipient["data"],
                        callback_data=recipient.get("callback_data"),
                    )

            # Enqueue task
            send_email_job_task.delay(str(job.id))

            return Response(
                {
                    "job_id": str(job.id),
                    "total_recipients": len(all_recipients),
                    "detail": _("Bulk email send job enqueued"),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except TemplateNotFoundError:
            return Response({"detail": _("Template not found")}, status=status.HTTP_404_NOT_FOUND)
        except TemplateValidationError:
            return Response({"detail": _("Template validation failed. Please check your data.")}, status=status.HTTP_400_BAD_REQUEST)
