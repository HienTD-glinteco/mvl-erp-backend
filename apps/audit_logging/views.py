import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exceptions import AuditLogException
from .serializers import AuditLogSearchSerializer

logger = logging.getLogger(__name__)


class AuditLogViewSet(viewsets.GenericViewSet):
    """ViewSet for audit log operations."""

    permission_classes = [IsAuthenticated]

    # TODO: Add proper permission check to verify user has access to audit logs

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """
        Search audit logs using OpenSearch.

        Query parameters are validated using AuditLogSearchSerializer.

        TODO: Add comprehensive API documentation here (request/response examples, filters, etc.)
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
