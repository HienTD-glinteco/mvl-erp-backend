from django.contrib import admin

from .models import SalaryConfig


@admin.register(SalaryConfig)
class SalaryConfigAdmin(admin.ModelAdmin):
    """Admin configuration for SalaryConfig model.

    Configuration editing is done through Django Admin.
    Version field is read-only and auto-incremented.
    """

    list_display = ["version", "updated_at", "created_at"]
    readonly_fields = ["version", "created_at", "updated_at"]
    fieldsets = [
        (
            None,
            {
                "fields": ["version", "config"],
                "description": "Edit the salary configuration JSON. Version is auto-incremented on save.",
            },
        ),
        ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion through admin to maintain history."""
        return False
