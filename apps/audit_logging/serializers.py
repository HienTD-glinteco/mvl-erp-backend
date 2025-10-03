from rest_framework import serializers

from .opensearch_client import get_opensearch_client


class AuditLogSearchSerializer(serializers.Serializer):
    """Serializer for audit log search query parameters."""

    start_time = serializers.DateTimeField(required=False, help_text="Filter logs after this time")
    end_time = serializers.DateTimeField(required=False, help_text="Filter logs before this time")
    user_id = serializers.CharField(required=False, help_text="Filter by user ID")
    username = serializers.CharField(required=False, help_text="Filter by username")
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
    )

    def search(self):
        """
        Execute search using validated data.

        Returns:
            dict: Search results with summary logs, total, pagination info
        """
        # Extract filters
        filters = {}
        for field in [
            "start_time",
            "end_time",
            "user_id",
            "username",
            "action",
            "object_type",
            "object_id",
            "search_term",
        ]:
            value = self.validated_data.get(field)
            if value:
                # Convert datetime objects to ISO format strings for OpenSearch
                if field in ["start_time", "end_time"]:
                    filters[field] = value.isoformat()
                else:
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
    action = serializers.CharField(required=False, allow_null=True)
    object_type = serializers.CharField(required=False, allow_null=True)
    object_id = serializers.CharField(required=False, allow_null=True)
    object_repr = serializers.CharField(required=False, allow_null=True)
    change_message = serializers.CharField(required=False, allow_null=True)
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
