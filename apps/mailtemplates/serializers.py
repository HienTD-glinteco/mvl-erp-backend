"""Serializers for mail template API."""

from rest_framework import serializers

from .models import EmailSendJob, EmailSendRecipient


class RecipientInputSerializer(serializers.Serializer):
    """Input serializer for a single recipient."""

    email = serializers.EmailField(required=True)
    data = serializers.JSONField(required=True)


class BulkSendRequestSerializer(serializers.Serializer):
    """Request serializer for bulk send endpoint."""

    subject = serializers.CharField(max_length=500, required=False, allow_blank=True)
    sender = serializers.EmailField(required=False, allow_blank=True)
    client_request_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    recipients = RecipientInputSerializer(many=True, required=True)

    def validate_recipients(self, value):
        """Validate recipients list is not empty."""
        if not value:
            raise serializers.ValidationError("At least one recipient is required")
        return value


class TemplateSaveRequestSerializer(serializers.Serializer):
    """Request serializer for template save endpoint."""

    content = serializers.CharField(required=True, allow_blank=False)
    sample_data = serializers.JSONField(required=False)


class TemplatePreviewRequestSerializer(serializers.Serializer):
    """Request serializer for template preview endpoint."""

    data = serializers.JSONField(required=False)
    ref = serializers.JSONField(required=False)


class EmailSendRecipientSerializer(serializers.ModelSerializer):
    """Serializer for email send recipient status."""

    class Meta:
        model = EmailSendRecipient
        fields = [
            "id",
            "email",
            "status",
            "attempts",
            "last_error",
            "message_id",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields


class EmailSendJobSerializer(serializers.ModelSerializer):
    """Serializer for email send job."""

    created_by_email = serializers.SerializerMethodField()
    recipients = EmailSendRecipientSerializer(many=True, read_only=True)

    class Meta:
        model = EmailSendJob
        fields = [
            "id",
            "template_slug",
            "subject",
            "sender",
            "total",
            "sent_count",
            "failed_count",
            "status",
            "created_by",
            "created_by_email",
            "client_request_id",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "recipients",
        ]
        read_only_fields = fields

    def get_created_by_email(self, obj):
        """Get email of user who created the job."""
        if obj.created_by:
            return obj.created_by.email
        return None


class EmailSendJobStatusSerializer(serializers.ModelSerializer):
    """Simplified serializer for job status check."""

    created_by_email = serializers.SerializerMethodField()
    recipients_status = EmailSendRecipientSerializer(many=True, read_only=True, source="recipients")

    class Meta:
        model = EmailSendJob
        fields = [
            "id",
            "template_slug",
            "subject",
            "total",
            "sent_count",
            "failed_count",
            "status",
            "created_by_email",
            "started_at",
            "finished_at",
            "created_at",
            "recipients_status",
        ]
        read_only_fields = fields

    def get_created_by_email(self, obj):
        """Get email of user who created the job."""
        if obj.created_by:
            return obj.created_by.email
        return None


class TemplateMetadataResponseSerializer(serializers.Serializer):
    """Response serializer for template metadata."""

    slug = serializers.CharField()
    filename = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    purpose = serializers.CharField(required=False, allow_null=True)
    variables = serializers.ListField()
    sample_data = serializers.JSONField()
    content = serializers.CharField(required=False, help_text="Template HTML content (only when include_content=true)")
    sample_preview_html = serializers.CharField(
        required=False, help_text="Sample preview HTML (only when include_preview=true)"
    )
    sample_preview_text = serializers.CharField(
        required=False, help_text="Sample preview plain text (only when include_preview=true)"
    )


class TemplatePreviewResponseSerializer(serializers.Serializer):
    """Response serializer for template preview endpoint."""

    html = serializers.CharField(help_text="Rendered HTML content with inlined CSS")
    text = serializers.CharField(help_text="Plain text version of the email")


class TemplateSaveResponseSerializer(serializers.Serializer):
    """Response serializer for template save endpoint."""

    ok = serializers.BooleanField()
    slug = serializers.CharField()
    message = serializers.CharField(required=False)


class BulkSendResponseSerializer(serializers.Serializer):
    """Response serializer for bulk send endpoint."""

    job_id = serializers.UUIDField(help_text="UUID of the created email send job")
    detail = serializers.CharField(help_text="Human-readable message about the operation")
    total_recipients = serializers.IntegerField(help_text="Total number of recipients in this job")
