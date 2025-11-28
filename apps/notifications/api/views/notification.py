from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models import Notification

from ..serializers import (
    BulkMarkAsReadSerializer,
    NotificationResponseSerializer,
    NotificationSerializer,
)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for notification operations.

    Provides endpoints for:
    - Listing notifications for the authenticated user
    - Retrieving a specific notification
    - Marking notifications as read/unread
    - Bulk marking notifications as read
    - Marking all notifications as read
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    queryset = Notification.objects.select_related("actor", "target_content_type")

    def get_queryset(self):
        """Filter notifications to only those for the authenticated user."""
        return self.queryset.filter(recipient=self.request.user)

    @extend_schema(
        summary="List notifications",
        description="Get a paginated list of notifications for the authenticated user.",
        tags=["0.5 Notifications"],
        responses={
            200: NotificationSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "List notifications success",
                description="Example response when listing notifications",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "actor": {"id": "user-uuid-1", "username": "john_doe", "full_name": "John Doe"},
                                "recipient": "user-uuid-2",
                                "verb": "commented on your post",
                                "target_type": "blog.post",
                                "target_id": "post-uuid-123",
                                "message": "Great article! I really enjoyed reading it.",
                                "read": False,
                                "created_at": "2025-10-13T10:30:00Z",
                                "updated_at": "2025-10-13T10:30:00Z",
                            },
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440002",
                                "actor": {"id": "user-uuid-3", "username": "jane_smith", "full_name": "Jane Smith"},
                                "recipient": "user-uuid-2",
                                "verb": "liked your comment",
                                "target_type": "blog.comment",
                                "target_id": "comment-uuid-456",
                                "message": None,
                                "read": True,
                                "created_at": "2025-10-12T15:45:00Z",
                                "updated_at": "2025-10-12T16:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        """List all notifications for the authenticated user."""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve notification",
        description="Get details of a specific notification.",
        tags=["0.5 Notifications"],
        responses={
            200: NotificationSerializer,
            404: OpenApiResponse(description="Notification not found"),
        },
        examples=[
            OpenApiExample(
                "Get notification success",
                description="Example response when retrieving a notification",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "actor": {"id": "user-uuid-1", "username": "john_doe", "full_name": "John Doe"},
                        "recipient": "user-uuid-2",
                        "verb": "commented on your post",
                        "target_type": "blog.post",
                        "target_id": "post-uuid-123",
                        "message": "Great article! I really enjoyed reading it.",
                        "read": False,
                        "created_at": "2025-10-13T10:30:00Z",
                        "updated_at": "2025-10-13T10:30:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get notification not found",
                description="Error response when notification is not found",
                value={"success": False, "error": "Notification not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific notification."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Mark notification as read",
        description="Mark a single notification as read.",
        tags=["0.5 Notifications"],
        request=None,
        responses={
            200: NotificationResponseSerializer,
            404: OpenApiResponse(description="Notification not found"),
        },
        examples=[
            OpenApiExample(
                "Mark as read success",
                description="Success response when marking notification as read",
                value={"success": True, "data": {"message": "Notification marked as read"}},
                response_only=True,
            )
        ],
    )
    @action(detail=True, methods=["patch"], url_path="mark-as-read")
    def mark_as_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(
            {"message": _("Notification marked as read")},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Mark notification as unread",
        description="Mark a single notification as unread.",
        tags=["0.5 Notifications"],
        request=None,
        responses={
            200: NotificationResponseSerializer,
            404: OpenApiResponse(description="Notification not found"),
        },
        examples=[
            OpenApiExample(
                "Mark as unread success",
                description="Success response when marking notification as unread",
                value={"success": True, "data": {"message": "Notification marked as unread"}},
                response_only=True,
            )
        ],
    )
    @action(detail=True, methods=["patch"], url_path="mark-as-unread")
    def mark_as_unread(self, request, pk=None):
        """Mark a single notification as unread."""
        notification = self.get_object()
        notification.mark_as_unread()
        return Response(
            {"message": _("Notification marked as unread")},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Bulk mark notifications as read",
        description="Mark multiple notifications as read at once.",
        tags=["0.5 Notifications"],
        request=BulkMarkAsReadSerializer,
        responses={
            200: NotificationResponseSerializer,
            400: OpenApiResponse(description="Invalid request data"),
        },
        examples=[
            OpenApiExample(
                "Bulk mark as read request",
                description="Example request to mark multiple notifications as read",
                value={
                    "notification_ids": [
                        "550e8400-e29b-41d4-a716-446655440001",
                        "550e8400-e29b-41d4-a716-446655440002",
                        "550e8400-e29b-41d4-a716-446655440003",
                    ]
                },
                request_only=True,
            ),
            OpenApiExample(
                "Bulk mark as read success",
                description="Success response when bulk marking notifications as read",
                value={"success": True, "data": {"message": "Notifications marked as read", "count": 3}},
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="bulk-mark-as-read")
    def bulk_mark_as_read(self, request):
        """Mark multiple notifications as read."""
        serializer = BulkMarkAsReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_ids = serializer.validated_data["notification_ids"]

        # Filter by recipient to ensure user can only mark their own notifications
        updated_count = Notification.objects.filter(
            id__in=notification_ids, recipient=request.user, read=False
        ).update(read=True)

        return Response(
            {
                "message": _("Notifications marked as read"),
                "count": updated_count,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Mark all notifications as read",
        description="Mark all notifications for the authenticated user as read.",
        tags=["0.5 Notifications"],
        request=None,
        responses={
            200: NotificationResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Mark all as read success",
                description="Success response when marking all notifications as read",
                value={"success": True, "data": {"message": "All notifications marked as read", "count": 15}},
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["post"], url_path="mark-all-as-read")
    def mark_all_as_read(self, request):
        """Mark all notifications as read for the authenticated user."""
        updated_count = Notification.objects.filter(recipient=request.user, read=False).update(read=True)

        return Response(
            {
                "message": _("All notifications marked as read"),
                "count": updated_count,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Get unread count",
        description="Get the count of unread notifications for the authenticated user.",
        tags=["0.5 Notifications"],
        responses={
            200: NotificationResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Unread count success",
                description="Success response with unread notification count",
                value={"success": True, "data": {"message": "Unread notification count", "count": 5}},
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Get the count of unread notifications."""
        count = Notification.objects.filter(recipient=request.user, read=False).count()

        return Response(
            {
                "message": _("Unread notification count"),
                "count": count,
            },
            status=status.HTTP_200_OK,
        )
