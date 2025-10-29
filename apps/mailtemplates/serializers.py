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
