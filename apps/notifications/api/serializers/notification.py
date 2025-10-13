from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.notifications.models import Notification
from libs import FieldFilteringSerializerMixin


class ActorSerializer(serializers.Serializer):
    """Serializer for the actor (user who triggered the notification)."""

    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)


class NotificationSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for notification list and detail views."""

    actor = ActorSerializer(read_only=True)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.CharField(source="target_object_id", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "actor",
            "recipient",
            "verb",
            "target_type",
            "target_id",
            "message",
            "read",
            "extra_data",
            "delivery_method",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "actor",
            "recipient",
            "verb",
            "target_type",
            "target_id",
            "message",
            "extra_data",
            "delivery_method",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_target_type(self, obj):
        """Get the content type of the target object."""
        if obj.target_content_type:
            return f"{obj.target_content_type.app_label}.{obj.target_content_type.model}"
        return None


class BulkMarkAsReadSerializer(serializers.Serializer):
    """Serializer for bulk marking notifications as read."""

    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of notification IDs to mark as read",
        allow_empty=False,
    )


class NotificationResponseSerializer(serializers.Serializer):
    """Response serializer for notification operations."""

    message = serializers.CharField()
    count = serializers.IntegerField(required=False)
