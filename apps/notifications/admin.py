from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = [
        "id",
        "actor",
        "recipient",
        "verb",
        "read",
        "delivery_method",
        "created_at",
    ]
    list_filter = [
        "read",
        "delivery_method",
        "created_at",
        "target_content_type",
    ]
    search_fields = [
        "actor__username",
        "actor__email",
        "recipient__username",
        "recipient__email",
        "verb",
        "message",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "actor",
                    "recipient",
                    "verb",
                    "message",
                )
            },
        ),
        (
            _("Target"),
            {
                "fields": (
                    "target_content_type",
                    "target_object_id",
                )
            },
        ),
        (
            _("Additional Data"),
            {
                "fields": (
                    "extra_data",
                    "delivery_method",
                )
            },
        ),
        (
            _("Status"),
            {"fields": ("read",)},
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queries by selecting related objects."""
        queryset = super().get_queryset(request)
        return queryset.select_related("actor", "recipient", "target_content_type")
