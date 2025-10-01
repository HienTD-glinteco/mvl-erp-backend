import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exceptions import AuditLogException
from .opensearch_client import get_opensearch_client
from .serializers import (
    AuditLogSearchResponseSerializer,
    AuditLogSearchSerializer,
    AuditLogSerializer,
)

logger = logging.getLogger(__name__)


class AuditLogViewSet(viewsets.GenericViewSet):
    """ViewSet for audit log operations."""

    permission_classes = [IsAuthenticated]

    # TODO: Add proper permission check to verify user has access to audit logs

    @extend_schema(
        summary="Tìm kiếm audit logs",
        description="Tìm kiếm audit logs với các bộ lọc. Trả về danh sách các log với các trường tóm tắt.",
        parameters=[
            OpenApiParameter(
                name="start_time",
                type=str,
                description="Lọc log sau thời gian này (ISO 8601 format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_time",
                type=str,
                description="Lọc log trước thời gian này (ISO 8601 format)",
                required=False,
            ),
            OpenApiParameter(
                name="user_id",
                type=str,
                description="Lọc theo ID người dùng",
                required=False,
            ),
            OpenApiParameter(
                name="username",
                type=str,
                description="Lọc theo tên đăng nhập",
                required=False,
            ),
            OpenApiParameter(
                name="action",
                type=str,
                description="Lọc theo loại hành động",
                required=False,
            ),
            OpenApiParameter(
                name="object_type",
                type=str,
                description="Lọc theo loại đối tượng",
                required=False,
            ),
            OpenApiParameter(
                name="object_id",
                type=str,
                description="Lọc theo ID đối tượng",
                required=False,
            ),
            OpenApiParameter(
                name="search_term",
                type=str,
                description="Tìm kiếm văn bản tự do trong object_repr và change_message",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Số lượng kết quả trên mỗi trang (1-100, mặc định: 50)",
                required=False,
            ),
            OpenApiParameter(
                name="from_offset",
                type=int,
                description="Vị trí bắt đầu cho phân trang (mặc định: 0)",
                required=False,
            ),
            OpenApiParameter(
                name="sort_order",
                type=str,
                description="Thứ tự sắp xếp theo thời gian (asc hoặc desc, mặc định: desc)",
                required=False,
            ),
        ],
        responses={
            200: AuditLogSearchResponseSerializer,
            400: OpenApiResponse(description="Tham số không hợp lệ"),
            401: OpenApiResponse(description="Chưa xác thực"),
            500: OpenApiResponse(description="Lỗi tìm kiếm audit logs"),
        },
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """
        Search audit logs using OpenSearch.

        Returns summary fields only (log_id, timestamp, user_id, username, action,
        object_type, object_id, object_repr).

        Query parameters are validated using AuditLogSearchSerializer.
        """
        # Validate input
        serializer = AuditLogSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Execute search using serializer
            response_data = serializer.search()
            return Response(response_data)

        except AuditLogException as e:
            logger.error(f"Audit log search failed: {e}")
            return Response(
                {"error": "Failed to search audit logs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Unexpected error in audit log search: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Lấy chi tiết audit log",
        description="Lấy thông tin chi tiết đầy đủ của một audit log theo log_id",
        parameters=[
            OpenApiParameter(
                name="log_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="ID duy nhất của audit log",
                required=True,
            ),
        ],
        responses={
            200: AuditLogSerializer,
            400: OpenApiResponse(description="log_id không hợp lệ"),
            401: OpenApiResponse(description="Chưa xác thực"),
            404: OpenApiResponse(description="Không tìm thấy log"),
            500: OpenApiResponse(description="Lỗi lấy chi tiết audit log"),
        },
    )
    @action(detail=False, methods=["get"], url_path="detail/(?P<log_id>[^/.]+)")
    def detail(self, request, log_id=None):
        """
        Retrieve a specific audit log by its log_id.

        Returns all fields for the requested log.

        Args:
            log_id: The unique identifier of the audit log

        Returns:
            Full audit log data with all fields
        """
        if not log_id:
            return Response(
                {"error": "log_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            opensearch_client = get_opensearch_client()
            log_data = opensearch_client.get_log_by_id(log_id)
            return Response(log_data)

        except AuditLogException as e:
            if "not found" in str(e).lower():
                return Response(
                    {"error": f"Log with id {log_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            logger.error(f"Failed to retrieve audit log {log_id}: {e}")
            return Response(
                {"error": "Failed to retrieve audit log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error retrieving audit log {log_id}: {e}", exc_info=True
            )
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
