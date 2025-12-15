from django.contrib import admin

from .models import KPIConfig, KPICriterion, SalaryConfig


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


@admin.register(KPIConfig)
class KPIConfigAdmin(admin.ModelAdmin):
    """Admin configuration for KPIConfig model.

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
                "description": "Edit the KPI configuration JSON. Version is auto-incremented on save.",
            },
        ),
        ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion through admin to maintain history."""
        return False


@admin.register(KPICriterion)
class KPICriterionAdmin(admin.ModelAdmin):
    """Admin configuration for KPICriterion model.

    Provides interface to manage KPI evaluation criteria with filtering
    and search capabilities.
    """

    list_display = [
        "target",
        "evaluation_type",
        "criterion",
        "sub_criterion",
        "component_total_score",
        "group_number",
        "order",
        "active",
        "created_at",
        "updated_at",
    ]
    list_filter = ["target", "evaluation_type", "active", "created_at"]
    search_fields = ["criterion", "sub_criterion", "description", "target", "evaluation_type"]
    readonly_fields = ["created_by", "updated_by", "created_at", "updated_at"]
    ordering = ["evaluation_type", "order"]

    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["target", "evaluation_type", "criterion", "sub_criterion", "description"],
            },
        ),
        (
            "Scoring and Display",
            {
                "fields": ["component_total_score", "group_number", "order"],
            },
        ),
        (
            "Status",
            {
                "fields": ["active"],
            },
        ),
        (
            "Audit Information",
            {
                "fields": ["created_by", "updated_by", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def save_model(self, request, obj, form, change):
        """Set created_by or updated_by when saving through admin."""
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
