from datetime import UTC, datetime, time

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..opensearch_client import get_opensearch_client


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
    action = serializers.CharField(required=False, help_text="Filter by action type")
    object_type = serializers.CharField(required=False, help_text="Filter by object type")
    object_id = serializers.CharField(required=False, help_text="Filter by object ID")
    search_term = serializers.CharField(required=False, help_text="Free text search")
    page_size = serializers.IntegerField(required=False, default=50, min_value=1, max_value=100)
    from_offset = serializers.IntegerField(required=False, default=0, min_value=0)
    sort_order = serializers.ChoiceField(
        choices=[("asc", "Ascending"), ("desc", "Descending")],
        required=False,
        default="desc",
        help_text="Sort order by timestamp (default: desc - newest first)",
    )

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

        # Extract other filters
        for field in [
            "user_id",
            "username",
            "employee_code",
            "action",
            "object_type",
            "object_id",
            "search_term",
        ]:
            value = self.validated_data.get(field)
            if value:
                filters[field] = value

        # Pagination parameters
        page_size = self.validated_data.get("page_size", 50)
        from_offset = self.validated_data.get("from_offset", 0)
        sort_order = self.validated_data.get("sort_order", "desc")

        # Search logs using OpenSearch with summary fields only
        opensearch_client = get_opensearch_client()
        result = opensearch_client.search_logs(
            filters=filters,
            page_size=page_size,
            from_offset=from_offset,
            sort_order=sort_order,
            summary_fields_only=True,  # Return only summary fields
        )

        # Format response
        return {
            "items": result["items"],
            "total": result["total"],
            "page_size": page_size,
            "from_offset": from_offset,
            "next_offset": result.get("next_offset"),
            "has_next": result["has_next"],
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


class AuditLogSearchResponseSerializer(serializers.Serializer):
    """Serializer for audit log search response."""

    items = AuditLogSummarySerializer(many=True)
    total = serializers.IntegerField()
    page_size = serializers.IntegerField()
    from_offset = serializers.IntegerField()
    next_offset = serializers.IntegerField(required=False, allow_null=True)
    has_next = serializers.BooleanField()
