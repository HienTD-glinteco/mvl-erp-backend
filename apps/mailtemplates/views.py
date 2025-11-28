"""API views for mail templates."""

from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api.permissions import RoleBasedPermission
from libs.drf.base_viewset import BaseGenericViewSet

from .constants import TEMPLATE_REGISTRY
from .models import EmailSendJob
from .serializers import (
    BulkSendRequestSerializer,
    BulkSendResponseSerializer,
    EmailSendJobStatusSerializer,
    TemplateMetadataResponseSerializer,
    TemplatePreviewRequestSerializer,
    TemplatePreviewResponseSerializer,
    TemplateSaveRequestSerializer,
    TemplateSaveResponseSerializer,
)
from .services import (
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
    get_template_metadata,
    load_template_content,
    render_and_prepare_email,
    sanitize_html_for_storage,
    save_template_content,
)
from .tasks import send_email_job_task


class MailTemplateViewSet(BaseGenericViewSet):
    """ViewSet for mail template operations."""

    permission_classes = [RoleBasedPermission]
    lookup_field = "pk"  # Will map to slug in URL

    # Permission registration attributes
    module = "Mail Templates"
    submodule = "Template Management"
    permission_prefix = "mailtemplate"

    @extend_schema(
        summary="List all mail templates",
        description="Retrieve a list of all available mail templates with their metadata",
        tags=["0.6 Mail Templates"],
        parameters=[
            {
                "name": "include_preview",
                "in": "query",
                "description": "Include sample preview HTML and text",
                "required": False,
                "schema": {"type": "boolean"},
            }
        ],
        responses={
            200: TemplateMetadataResponseSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "List templates success",
                value={
                    "success": True,
                    "data": [
                        {
                            "slug": "welcome",
                            "title": "Welcome Email",
                            "description": "Welcome new employees to the organization",
                            "purpose": "Send to new employees on their first day",
                            "filename": "welcome.html",
                            "variables": [
                                {
                                    "name": "fullname",
                                    "type": "string",
                                    "required": True,
                                    "description": "Employee's full name",
                                }
                            ],
                            "sample_data": {"fullname": "John Doe", "start_date": "2025-11-01"},
                        }
                    ],
                    "error": None,
                },
                response_only=True,
            )
        ],
    )
    def list(self, request):
        """List all available mail templates."""
        include_preview = request.query_params.get("include_preview", "false").lower() == "true"

        templates = []
        for template_meta in TEMPLATE_REGISTRY:
            template_data = dict(template_meta)

            if include_preview:
                try:
                    # Render sample preview
                    result = render_and_prepare_email(
                        template_meta,
                        template_meta["sample_data"],
                        validate=False,
                    )
                    template_data["sample_preview_html"] = result["html"]
                    template_data["sample_preview_text"] = result["text"]
                except Exception as e:
                    template_data["sample_preview_error"] = str(e)

            templates.append(template_data)

        return Response(templates)

    @extend_schema(
        summary="Get template details",
        description="Retrieve detailed information about a specific template",
        tags=["0.6 Mail Templates"],
        parameters=[
            {
                "name": "include_content",
                "in": "query",
                "description": "Include template HTML content",
                "required": False,
                "schema": {"type": "boolean"},
            }
        ],
        responses={
            200: TemplateMetadataResponseSerializer,
            404: OpenApiExample(
                "Template not found",
                value={"success": False, "data": None, "error": "Template with slug 'invalid' not found"},
            ),
        },
        examples=[
            OpenApiExample(
                "Get template success",
                value={
                    "success": True,
                    "data": {
                        "slug": "welcome",
                        "title": "Welcome Email",
                        "description": "Welcome new employees",
                        "content": "<html>...</html>",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    )
    def retrieve(self, request, pk=None):
        """Get template metadata and optionally content."""
        slug = pk
        try:
            template_meta = get_template_metadata(slug)
            include_content = request.query_params.get("include_content", "false").lower() == "true"

            response_data = dict(template_meta)

            if include_content:
                try:
                    content = load_template_content(template_meta["filename"])
                    response_data["content"] = content
                except FileNotFoundError as e:
                    return Response(
                        {"detail": str(e)},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            return Response(response_data)

        except TemplateNotFoundError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        summary="Save template content",
        description="Save edited template HTML content with automatic backup",
        tags=["0.6 Mail Templates"],
        request=TemplateSaveRequestSerializer,
        responses={
            200: TemplateSaveResponseSerializer,
            400: OpenApiExample(
                "Invalid request",
                value={"success": False, "data": None, "error": {"content": ["This field is required."]}},
            ),
            403: OpenApiExample(
                "Permission denied",
                value={"success": False, "data": None, "error": "You do not have permission to perform this action."},
            ),
            404: OpenApiExample(
                "Template not found",
                value={"success": False, "data": None, "error": "Template with slug 'invalid' not found"},
            ),
        },
        examples=[
            OpenApiExample(
                "Save template request",
                value={
                    "content": "<html><body>Welcome {{ fullname }}!</body></html>",
                    "sample_data": {"fullname": "John Doe"},
                },
                request_only=True,
            ),
            OpenApiExample(
                "Save template success",
                value={"success": True, "data": {"ok": True, "slug": "welcome"}, "error": None},
                response_only=True,
            ),
        ],
    )
    def update(self, request, pk=None):
        """Save template content."""
        slug = pk
        serializer = TemplateSaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            template_meta = get_template_metadata(slug)

            # Sanitize content
            content = serializer.validated_data["content"]
            sanitized_content = sanitize_html_for_storage(content)

            # Save with backup
            save_template_content(
                template_meta["filename"],
                sanitized_content,
                create_backup=True,
            )

            return Response({"ok": True, "slug": slug})

        except TemplateNotFoundError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"detail": _("Failed to save template"), "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Preview template",
        description="Render and preview a template with sample or real data",
        tags=["0.6 Mail Templates"],
        parameters=[
            {
                "name": "mode",
                "in": "query",
                "description": "Preview mode: 'sample' or 'real'",
                "required": False,
                "schema": {"type": "string", "enum": ["sample", "real"], "default": "sample"},
            }
        ],
        request=TemplatePreviewRequestSerializer,
        responses={
            200: TemplatePreviewResponseSerializer,
            400: OpenApiExample(
                "Validation error",
                value={
                    "success": False,
                    "data": None,
                    "error": "Template validation failed: missing required variable 'fullname'",
                },
            ),
            403: OpenApiExample(
                "Permission denied for real mode",
                value={"success": False, "data": None, "error": "Real data preview permission required"},
            ),
            404: OpenApiExample(
                "Template not found",
                value={"success": False, "data": None, "error": "Template with slug 'invalid' not found"},
            ),
        },
        examples=[
            OpenApiExample(
                "Preview request with data",
                value={"data": {"fullname": "Jane Doe", "start_date": "2025-12-01"}},
                request_only=True,
            ),
            OpenApiExample(
                "Preview success",
                value={
                    "success": True,
                    "data": {
                        "html": "<html><body>Welcome Jane Doe!</body></html>",
                        "text": "Welcome Jane Doe!",
                        "subject": "Welcome to MaiVietLand!",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="preview")
    def preview(self, request, pk=None):
        """Preview template with data."""
        slug = pk
        mode = request.query_params.get("mode", "sample")

        # Real mode preview is handled by the same permission
        # If specific real data preview permission is needed, it can be checked here

        serializer = TemplatePreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            template_meta = get_template_metadata(slug)

            # Determine data to use
            if mode == "sample":
                # Merge request data with sample_data, prioritizing request data
                data = {**template_meta["sample_data"], **serializer.validated_data.get("data", {})}
            else:
                # Real mode - use provided data or fetch from ref
                data = serializer.validated_data.get("data")
                if not data:
                    # TODO: Implement ref-based data fetching via hooks
                    return Response(
                        {"detail": _("Data or ref required for real mode")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Render template
            result = render_and_prepare_email(template_meta, data, validate=True)

            # Add subject to response with priority logic
            subject = None
            if "subject" in data:
                subject = data["subject"]
            elif "default_subject" in template_meta:
                subject = template_meta["default_subject"]

            result["subject"] = subject

            return Response(result)

        except TemplateNotFoundError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except TemplateValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TemplateRenderError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except FileNotFoundError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        summary="Send bulk emails",
        description="Create a bulk email send job with multiple recipients",
        tags=["0.6 Mail Templates"],
        request=BulkSendRequestSerializer,
        responses={
            202: BulkSendResponseSerializer,
            400: OpenApiExample(
                "Validation error",
                value={
                    "success": False,
                    "data": None,
                    "error": "Validation error for user@example.com: missing required variable 'fullname'",
                },
            ),
            403: OpenApiExample(
                "Permission denied",
                value={"success": False, "data": None, "error": "You do not have permission to perform this action."},
            ),
            404: OpenApiExample(
                "Template not found",
                value={"success": False, "data": None, "error": "Template with slug 'invalid' not found"},
            ),
            409: OpenApiExample(
                "Duplicate client_request_id",
                value={"success": False, "data": None, "error": "Job with this client_request_id already exists"},
            ),
        },
        examples=[
            OpenApiExample(
                "Bulk send request",
                value={
                    "subject": "Welcome to the team!",
                    "sender": "hr@example.com",
                    "recipients": [
                        {"email": "user1@example.com", "data": {"fullname": "John Doe", "start_date": "2025-11-01"}},
                        {"email": "user2@example.com", "data": {"fullname": "Jane Smith", "start_date": "2025-11-02"}},
                    ],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Bulk send success",
                value={
                    "success": True,
                    "data": {
                        "job_id": "123e4567-e89b-12d3-a456-426614174000",
                        "total_recipients": 2,
                        "detail": "Job enqueued",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        """Create bulk email send job."""
        slug = pk
        serializer = BulkSendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            template_meta = get_template_metadata(slug)

            # Get or set subject and sender - use default_subject if not provided
            subject = serializer.validated_data.get("subject")
            if not subject:
                subject = template_meta.get("default_subject", template_meta["title"])
            sender = serializer.validated_data.get("sender", settings.DEFAULT_FROM_EMAIL)
            client_request_id = serializer.validated_data.get("client_request_id")

            # Check for duplicate client_request_id
            if client_request_id:
                existing_job = EmailSendJob.objects.filter(client_request_id=client_request_id).first()
                if existing_job:
                    return Response(
                        {
                            "detail": _("Job with this client_request_id already exists"),
                            "job_id": str(existing_job.id),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            # Validate all recipient data
            recipients_data = serializer.validated_data["recipients"]
            for recipient in recipients_data:
                try:
                    from .services import validate_template_data

                    validate_template_data(recipient["data"], template_meta)
                except TemplateValidationError as e:
                    return Response(
                        {"detail": f"Validation error for {recipient['email']}: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Create job
            job = EmailSendJob.objects.create(
                template_slug=slug,
                subject=subject,
                sender=sender,
                total=len(recipients_data),
                created_by=request.user if request.user.is_authenticated else None,
                client_request_id=client_request_id,
            )

            # Create recipients
            from .models import EmailSendRecipient

            for recipient in recipients_data:
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
                    "total_recipients": len(recipients_data),
                    "detail": _("Job enqueued"),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except TemplateNotFoundError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        summary="Get send job status",
        description="Retrieve the status of a bulk email send job",
        tags=["0.6 Mail Templates"],
        examples=[
            OpenApiExample(
                "Job status success",
                value={
                    "success": True,
                    "data": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "completed",
                        "total": 2,
                        "sent_count": 2,
                        "failed_count": 0,
                        "recipients_status": [
                            {
                                "email": "user1@example.com",
                                "status": "sent",
                                "attempts": 1,
                                "sent_at": "2025-10-29T10:30:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="job/(?P<job_id>[^/.]+)/status")
    def job_status(self, request, job_id=None):
        """Get status of a send job."""
        try:
            job = EmailSendJob.objects.prefetch_related("recipients").get(id=job_id)

            # Check permissions - user must own the job or be staff
            if not request.user.is_staff and job.created_by != request.user:
                return Response(
                    {"detail": _("Not authorized to view this job")},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = EmailSendJobStatusSerializer(job)
            return Response(serializer.data)

        except EmailSendJob.DoesNotExist:
            return Response(
                {"detail": _("Job not found")},
                status=status.HTTP_404_NOT_FOUND,
            )
