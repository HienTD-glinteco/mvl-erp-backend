"""
DRF ViewSet mixin for document export functionality.
"""

import os
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .constants import (
    DEFAULT_DELIVERY,
    DEFAULT_FILE_TYPE,
    DELIVERY_DIRECT,
    DELIVERY_LINK,
    ERROR_INVALID_DELIVERY,
    ERROR_INVALID_FILE_TYPE,
    ERROR_S3_UPLOAD_FAILED,
    ERROR_TEMPLATE_MISSING,
    FILE_TYPE_DOCX,
    FILE_TYPE_PDF,
    STORAGE_S3,
)
from .serializers import ExportDocumentS3ResponseSerializer
from .utils import convert_html_to_docx, convert_html_to_pdf


class ExportDocumentMixin:
    """
    Mixin for DRF ViewSets to add document export functionality.

    Adds an export_detail_document action that exports detail views as PDF or DOCX.

    Subclasses must implement:
        - document_template_name: Path to the HTML template
        - get_export_context(instance): Return context dict for template rendering
        - get_export_filename(instance): Return filename without extension

    Usage:
        class MyViewSet(ExportDocumentMixin, ModelViewSet):
            document_template_name = 'documents/my_template.html'

            def get_export_context(self, instance):
                return {'my_model': instance}

            def get_export_filename(self, instance):
                return f'{instance.code}_document'
    """

    document_template_name: str | None = None

    def get_document_template_name(self, request, instance):
        """
        Get the template name for the document export.

        Args:
            request: The request object
            instance: The model instance to export

        Returns:
            str: Path to the HTML template
        """
        return self.document_template_name

    def get_export_context(self, instance):
        """
        Prepare context dictionary for template rendering.

        Args:
            instance: The model instance to export

        Returns:
            dict: Context dictionary for template rendering

        Raises:
            NotImplementedError: If not overridden in subclass
        """
        raise NotImplementedError("Subclasses must implement get_export_context()")

    def get_export_filename(self, instance):
        """
        Generate filename for the exported document.

        Args:
            instance: The model instance to export

        Returns:
            str: Filename without extension

        Raises:
            NotImplementedError: If not overridden in subclass
        """
        raise NotImplementedError("Subclasses must implement get_export_filename()")

    @extend_schema(
        summary="Export detail document",
        description="Export the detail view as a PDF or DOCX document. "
        "By default, returns the file directly. Use delivery=link to get a presigned S3 URL instead.",
        parameters=[
            OpenApiParameter(
                name="type",
                description="File export format. 'pdf' (default) or 'docx'",
                required=False,
                type=str,
                enum=["pdf", "docx"],
            ),
            OpenApiParameter(
                name="delivery",
                description="File delivery method. "
                "'direct' (default) returns the file as an HTTP attachment; "
                "'link' returns a presigned S3 link.",
                required=False,
                type=str,
                enum=["link", "direct"],
            ),
        ],
        responses={
            200: ExportDocumentS3ResponseSerializer,
            206: OpenApiResponse(description="File returned as HTTP attachment (direct delivery)"),
            400: OpenApiResponse(description="Bad request (invalid parameters)"),
            404: OpenApiResponse(description="Object not found"),
            500: OpenApiResponse(description="Internal server error (conversion or upload failure)"),
        },
        tags=["0.2: Export"],
    )
    @action(detail=True, methods=["get"], url_path="export-document")
    def export_detail_document(self, request, pk=None):
        """
        Export detail document as PDF or DOCX.

        Query parameters:
            type: File format ('pdf' or 'docx'), defaults to 'pdf'
            delivery: Delivery mode ('link' or 'direct'), defaults to 'direct'

        Returns:
            - Direct (206): File download response
            - Link (200): JSON with presigned URL and metadata
        """
        # Get parameters
        file_type = request.query_params.get("type", DEFAULT_FILE_TYPE).lower()
        delivery = request.query_params.get("delivery", DEFAULT_DELIVERY).lower()

        # Validate file type
        if file_type not in (FILE_TYPE_PDF, FILE_TYPE_DOCX):
            return Response(
                {"error": _(ERROR_INVALID_FILE_TYPE)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate delivery parameter
        if delivery not in (DELIVERY_LINK, DELIVERY_DIRECT):
            return Response(
                {"error": _(ERROR_INVALID_DELIVERY)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get object
        instance = self.get_object()

        # Get template name
        template_name = self.get_document_template_name(request, instance)

        # Validate template name
        if not template_name:
            return Response(
                {"error": _(ERROR_TEMPLATE_MISSING)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Get context and filename from subclass
        try:
            context = self.get_export_context(instance)
            filename = self.get_export_filename(instance)
        except NotImplementedError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Convert HTML to document
        try:
            if file_type == FILE_TYPE_PDF:
                file_info = convert_html_to_pdf(template_name, context, filename)
            else:  # DOCX
                file_info = convert_html_to_docx(template_name, context, filename)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Handle delivery mode
        try:
            if delivery == DELIVERY_DIRECT:
                return self._document_direct_file_response(file_info)
            else:  # DELIVERY_LINK
                return self._document_s3_delivery_response(file_info, instance)
        finally:
            # Clean up temporary file
            self._cleanup_temp_file(file_info.get("file_path"))

    def _document_direct_file_response(self, file_info):
        """
        Create HTTP response for direct file download.

        Args:
            file_info: File information dict with file_path, file_name, size

        Returns:
            HttpResponse: File download response
        """
        # Read file content
        file_path = Path(file_info["file_path"])
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Determine content type
        if file_info["file_name"].endswith(".pdf"):
            content_type = "application/pdf"
        else:
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        response = HttpResponse(
            file_content,
            content_type=content_type,
            status=status.HTTP_206_PARTIAL_CONTENT,
        )
        response["Content-Disposition"] = f'attachment; filename="{file_info["file_name"]}"'
        return response

    def _document_s3_delivery_response(self, file_info, instance):
        """
        Upload to S3 and return presigned URL response.

        Args:
            file_info: File information dict with file_path, file_name, size
            instance: Model instance being exported

        Returns:
            Response: JSON response with presigned URL and metadata
        """
        try:
            # Reuse storage backend from export_xlsx for consistency
            # This ensures S3 upload logic is centralized and follows the same patterns
            from libs.export_xlsx.storage import get_storage_backend

            # Get S3 storage backend
            storage = get_storage_backend(STORAGE_S3)

            # Read file content and upload to S3
            file_path = Path(file_info["file_path"])
            with open(file_path, "rb") as f:
                file_content = f.read()

            # Save file to S3
            from io import BytesIO

            s3_path = storage.save(BytesIO(file_content), file_info["file_name"])

            # Generate presigned URL
            presigned_url = storage.get_url(s3_path)

            # Get file size
            file_size = file_info.get("size") or storage.get_file_size(s3_path)

            # Get expiration time from settings
            expires_in = getattr(
                settings,
                "EXPORTER_PRESIGNED_URL_EXPIRES",
                getattr(settings, "EXPORTER_S3_SIGNED_URL_EXPIRE", 3600),
            )

            # Return JSON response
            response_data = {
                "url": presigned_url,
                "filename": file_info["file_name"],
                "expires_in": expires_in,
                "storage_backend": "s3",
            }

            if file_size is not None:
                response_data["size_bytes"] = file_size

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle S3 upload errors
            return Response(
                {"error": _(ERROR_S3_UPLOAD_FAILED) + f": {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _cleanup_temp_file(self, file_path):
        """
        Clean up temporary file.

        Args:
            file_path: Path to temporary file
        """
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception:  # nosec B110
                # Silently ignore cleanup errors - file deletion failures are non-critical
                # and should not interrupt the response flow
                pass
