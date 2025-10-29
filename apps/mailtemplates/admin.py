"""Admin configuration for mail templates."""

from django.contrib import admin

from .models import EmailSendJob, EmailSendRecipient


class EmailSendRecipientInline(admin.TabularInline):
    """Inline admin for email recipients."""

    model = EmailSendRecipient
    extra = 0
    fields = ["email", "status", "attempts", "last_error", "sent_at"]
    readonly_fields = ["email", "status", "attempts", "last_error", "sent_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EmailSendJob)
class EmailSendJobAdmin(admin.ModelAdmin):
    """Admin for email send jobs."""

    list_display = [
        "id",
        "template_slug",
        "subject",
        "status",
        "total",
        "sent_count",
        "failed_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["status", "template_slug", "created_at"]
    search_fields = ["id", "subject", "sender", "template_slug"]
    readonly_fields = [
        "id",
        "template_slug",
        "subject",
        "sender",
        "total",
        "sent_count",
        "failed_count",
        "created_by",
        "client_request_id",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ]
    inlines = [EmailSendRecipientInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(EmailSendRecipient)
class EmailSendRecipientAdmin(admin.ModelAdmin):
    """Admin for email recipients."""

    list_display = ["id", "job", "email", "status", "attempts", "sent_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["email", "job__id"]
    readonly_fields = [
        "id",
        "job",
        "email",
        "data",
        "status",
        "attempts",
        "last_error",
        "message_id",
        "sent_at",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
