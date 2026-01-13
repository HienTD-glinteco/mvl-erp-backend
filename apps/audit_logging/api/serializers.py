from datetime import UTC, datetime, time

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..opensearch_client import get_opensearch_client
from ..translations import (
    get_action_display,
    get_object_type_display,
    translate_change_message,
)


@extend_schema_field(
    field={
        "oneOf": [
            {"type": "string", "nullable": True, "example": "Created new object"},
            {"type": "null"},
            {
                "type": "object",
                "properties": {
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["field", "old_value", "new_value"],
                        "description": "Fixed array of column headers",
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "description": "Name of the changed field",
                                    "example": "Phone number",
                                },
                                "old_value": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {"type": "array", "items": {"type": "string"}},
                                    ],
                                    "description": "Previous value (can be string or array)",
                                    "example": "0987654321",
                                },
                                "new_value": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {"type": "array", "items": {"type": "string"}},
                                    ],
                                    "description": "New value (can be string or array)",
                                    "example": "1234567890",
                                },
                            },
                            "required": ["field", "old_value", "new_value"],
                        },
                        "description": "Array of field changes",
                    },
                },
                "required": ["headers", "rows"],
                "example": {
                    "headers": ["field", "old_value", "new_value"],
                    "rows": [
                        {"field": "Phone number", "old_value": "0987654321", "new_value": "1234567890"},
                        {
                            "field": "Certificates",
                            "old_value": ["old_cert.jpg"],
                            "new_value": ["cert1.jpg", "cert2.jpg"],
                        },
                    ],
                },
            },
        ],
        "description": (
            "Change message can be a string, object, or null. "
            "When it's an object, it contains 'headers' (fixed array: ['field', 'old_value', 'new_value']) "
            "and 'rows' (array of change records with field name, old value, and new value)."
        ),
    }
)
class ChangeMessageField(serializers.JSONField):
    """
    Custom field for change_message that can be a string, object, or None.

    When the value is an object, it has the following structure:
    {
        "headers": ["field", "old_value", "new_value"],
        "rows": [
            {
                "field": "Field name",
                "old_value": "old value or array of values",
                "new_value": "new value or array of values"
            },
            ...
        ]
    }
    """

    pass


class AuditLogSearchSerializer(serializers.Serializer):
    """Serializer for audit log search query parameters."""

    from_date = serializers.DateField(required=False, help_text="Filter logs from this date")
    to_date = serializers.DateField(required=False, help_text="Filter logs to this date")
    user_id = serializers.CharField(required=False, help_text="Filter by user ID")
    username = serializers.CharField(required=False, help_text="Filter by username")
    employee_code = serializers.CharField(required=False, help_text="Filter by employee code")
    actions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter by action types (use multiple values: ?actions=CREATE&actions=UPDATE)",
    )
    object_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter by object types (use multiple values: ?object_types=User&object_types=Role)",
    )
    object_id = serializers.CharField(required=False, help_text="Filter by object ID")
    search_term = serializers.CharField(required=False, help_text="Free text search")
    page_size = serializers.IntegerField(required=False, default=25, min_value=1, max_value=100)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    sort_order = serializers.ChoiceField(
        choices=[("asc", "Ascending"), ("desc", "Descending")],
        required=False,
        default="desc",
        help_text="Sort order by timestamp (default: desc - newest first)",
    )
    summary_fields_only = serializers.BooleanField(required=False, default=True)

    def search(self):
        """
        Execute search using validated data.

        Returns:
            dict: Search results with summary logs, total, pagination info
        """
        # Extract filters
        filters = {}

        # Handle date filtering with from_date/to_date
        from_date = self.validated_data.get("from_date")
        to_date = self.validated_data.get("to_date")

        if from_date:
            # Convert date to start of day in app timezone, then to UTC
            dt_start = timezone.make_aware(datetime.combine(from_date, time.min))
            filters["from_date"] = dt_start.astimezone(UTC).isoformat()
        if to_date:
            # Convert date to end of day in app timezone, then to UTC
            dt_end = timezone.make_aware(datetime.combine(to_date, time.max))
            filters["to_date"] = dt_end.astimezone(UTC).isoformat()

        # Extract single-value filters
        for field in [
            "user_id",
            "username",
            "employee_code",
            "object_id",
            "search_term",
        ]:
            value = self.validated_data.get(field)
            if value:
                filters[field] = value

        # Extract multiple-value filters
        actions = self.validated_data.get("actions")
        if actions:
            filters["action"] = actions

        object_types = self.validated_data.get("object_types")
        if object_types:
            filters["object_type"] = object_types

        # Pagination parameters
        page_size = self.validated_data.get("page_size", 50)
        page = self.validated_data.get("page", 1)
        sort_order = self.validated_data.get("sort_order", "desc")

        summary_fields_only = self.validated_data.get("summary_fields_only")

        # Search logs using OpenSearch with summary fields only
        opensearch_client = get_opensearch_client()
        result = opensearch_client.search_logs(
            filters=filters,
            page_size=page_size,
            page=page,
            sort_order=sort_order,
            summary_fields_only=summary_fields_only,
        )

        # Format response
        return {
            "results": result["results"],
            "count": result["count"],
            "next": result.get("next"),
            "previous": result.get("previous"),
            "object_name": self.context.get("object_name") or "",
        }


class AuditLogSummarySerializer(serializers.Serializer):
    """Serializer for audit log summary (search results)."""

    log_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    user_id = serializers.CharField(required=False, allow_null=True)
    username = serializers.CharField(required=False, allow_null=True)
    employee_code = serializers.CharField(required=False, allow_null=True)
    full_name = serializers.CharField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_null=True)
    object_type = serializers.CharField(required=False, allow_null=True)
    object_id = serializers.CharField(required=False, allow_null=True)
    object_repr = serializers.CharField(required=False, allow_null=True)


class AuditLogSerializer(serializers.Serializer):
    """Serializer for full audit log detail."""

    log_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    user_id = serializers.CharField(required=False, allow_null=True)
    username = serializers.CharField(required=False, allow_null=True)
    employee_code = serializers.CharField(required=False, allow_null=True)
    full_name = serializers.CharField(required=False, allow_null=True)
    action = serializers.CharField(required=False, allow_null=True)
    object_type = serializers.CharField(required=False, allow_null=True)
    object_id = serializers.CharField(required=False, allow_null=True)
    object_repr = serializers.CharField(required=False, allow_null=True)
    change_message = ChangeMessageField(required=False, allow_null=True)
    ip_address = serializers.CharField(required=False, allow_null=True)
    user_agent = serializers.CharField(required=False, allow_null=True)
    session_key = serializers.CharField(required=False, allow_null=True)
    object_name = serializers.CharField(required=False, allow_null=True)

    # Added translated fields
    object_type_display = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    change_message_display = serializers.SerializerMethodField()
    is_system_action = serializers.SerializerMethodField()

    def get_change_message(self, obj) -> str | dict | None:
        change_message = obj.get("change_message")
        if not change_message:
            return None
        if "message" in change_message:
            return change_message["message"]
        return change_message

    def get_object_type_display(self, obj):
        """Return translated object type using model verbose_name."""
        return get_object_type_display(obj.get("object_type", ""))

    def get_action_display(self, obj):
        """Return translated action."""
        return get_action_display(obj.get("action", ""))

    def get_change_message_display(self, obj):
        """Return change message with translated field names."""
        return translate_change_message(obj.get("change_message"), obj.get("object_type"))

    def get_is_system_action(self, obj):
        """Check if action was performed by system (no user or system user)."""
        user_id = obj.get("user_id")
        username = obj.get("username", "")

        # System actions typically have no user or special system usernames
        if not user_id:
            return True
        if username in ["system", "celery", "scheduler"]:
            return True
        return False


class AuditLogSearchResponseSerializer(serializers.Serializer):
    """Serializer for audit log search response."""

    count = serializers.IntegerField()
    next = serializers.IntegerField(required=False, allow_null=True)
    previous = serializers.IntegerField(required=False, allow_null=True)
    results = AuditLogSummarySerializer(many=True)
    object_name = serializers.CharField(required=False, allow_null=True)
