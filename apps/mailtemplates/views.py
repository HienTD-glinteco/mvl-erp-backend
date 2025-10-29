"""API views for mail templates."""

from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import TEMPLATE_REGISTRY
from .models import EmailSendJob
from .permissions import CanPreviewRealData, CanSendMail, IsTemplateEditor
from .serializers import (
    BulkSendRequestSerializer,
    EmailSendJobStatusSerializer,
    TemplatePreviewRequestSerializer,
    TemplateSaveRequestSerializer,
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


@extend_schema(
    summary="List all mail templates",
    description="Retrieve a list of all available mail templates with their metadata",
    tags=["Mail Templates"],
    parameters=[
        {
            "name": "include_preview",
            "in": "query",
            "description": "Include sample preview HTML and text",
            "required": False,
            "schema": {"type": "boolean"},
        }
    ],
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
                            {"name": "first_name", "type": "string", "required": True, "description": "Employee's first name"}
                        ],
                        "sample_data": {"first_name": "John", "start_date": "2025-11-01"},
                    }
                ],
            },
            response_only=True,
        )
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_templates(request):
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
    tags=["Mail Templates"],
    parameters=[
        {
            "name": "include_content",
            "in": "query",
            "description": "Include template HTML content",
            "required": False,
            "schema": {"type": "boolean"},
        }
    ],
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
            },
            response_only=True,
        ),
        OpenApiExample(
            "Template not found",
            value={"success": False, "error": "Template with slug 'invalid' not found"},
            response_only=True,
            status_codes=["404"],
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_template(request, slug):
    """Get template metadata and optionally content."""
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
    description="Save edited template HTML content with backup",
    tags=["Mail Templates"],
    request=TemplateSaveRequestSerializer,
    examples=[
        OpenApiExample(
            "Save template request",
            value={"content": "<html>...</html>", "sample_data": {"first_name": "John"}},
            request_only=True,
        ),
        OpenApiExample(
            "Save template success",
            value={"success": True, "data": {"ok": True, "slug": "welcome"}},
            response_only=True,
        ),
    ],
)
@api_view(["PUT"])
@permission_classes([IsTemplateEditor])
def save_template(request, slug):
    """Save template content."""
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
    tags=["Mail Templates"],
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
    examples=[
        OpenApiExample(
            "Preview request with data",
            value={"data": {"first_name": "Jane", "start_date": "2025-12-01"}},
            request_only=True,
        ),
        OpenApiExample(
            "Preview success",
            value={
                "success": True,
                "data": {
                    "html": "<html><body>Welcome Jane!</body></html>",
                    "text": "Welcome Jane!",
                },
            },
            response_only=True,
        ),
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_template(request, slug):
    """Preview template with data."""
    mode = request.query_params.get("mode", "sample")

    # Check permissions for real mode
    if mode == "real":
        permission = CanPreviewRealData()
        if not permission.has_permission(request, None):
            return Response(
                {"detail": _("Real data preview permission required")},
                status=status.HTTP_403_FORBIDDEN,
            )

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
    tags=["Mail Templates"],
    request=BulkSendRequestSerializer,
    examples=[
        OpenApiExample(
            "Bulk send request",
            value={
                "subject": "Welcome!",
                "sender": "hr@example.com",
                "recipients": [
                    {"email": "user1@example.com", "data": {"first_name": "John", "start_date": "2025-11-01"}},
                    {"email": "user2@example.com", "data": {"first_name": "Jane", "start_date": "2025-11-02"}},
                ],
            },
            request_only=True,
        ),
        OpenApiExample(
            "Bulk send success",
            value={
                "success": True,
                "data": {"job_id": "123e4567-e89b-12d3-a456-426614174000", "detail": "Job enqueued"},
            },
            response_only=True,
            status_codes=["202"],
        ),
    ],
)
@api_view(["POST"])
@permission_classes([CanSendMail])
def send_bulk_email(request, slug):
    """Create bulk email send job."""
    serializer = BulkSendRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        template_meta = get_template_metadata(slug)

        # Get or set subject and sender
        subject = serializer.validated_data.get("subject", f"{template_meta['title']}")
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
            )

        # Enqueue task
        send_email_job_task.delay(str(job.id))

        return Response(
            {
                "job_id": str(job.id),
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
    tags=["Mail Templates"],
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
                        {"email": "user1@example.com", "status": "sent", "attempts": 1, "sent_at": "2025-10-29T10:30:00Z"}
                    ],
                },
            },
            response_only=True,
        )
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_send_job_status(request, job_id):
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
