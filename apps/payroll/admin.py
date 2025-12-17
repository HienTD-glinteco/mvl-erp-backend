from django.contrib import admin

from .models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    EmployeeKPIItem,
    KPIConfig,
    KPICriterion,
    SalaryConfig,
)


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


class EmployeeKPIItemInline(admin.TabularInline):
    """Inline for EmployeeKPIItem in EmployeeKPIAssessment admin."""

    model = EmployeeKPIItem
    extra = 0
    readonly_fields = ["criterion_id", "criterion", "evaluation_type", "component_total_score", "ordering"]
    fields = ["criterion", "evaluation_type", "component_total_score", "employee_score", "manager_score", "ordering"]


@admin.register(EmployeeKPIAssessment)
class EmployeeKPIAssessmentAdmin(admin.ModelAdmin):
    """Admin for EmployeeKPIAssessment model."""

    list_display = [
        "id",
        "employee",
        "get_month",
        "grade_manager",
        "grade_hrm",
        "total_manager_score",
        "finalized",
    ]
    list_filter = ["period__month", "grade_manager", "grade_hrm", "finalized"]
    search_fields = ["employee__username", "employee__first_name", "employee__last_name"]
    ordering = ["-period__month", "employee__username"]
    readonly_fields = [
        "total_possible_score",
        "total_employee_score",
        "total_manager_score",
        "grade_manager",
        "created_at",
        "updated_at",
    ]
    inlines = [EmployeeKPIItemInline]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["period", "employee", "department_assignment_source"],
            },
        ),
        (
            "Scores and Grades",
            {
                "fields": [
                    "total_possible_score",
                    "total_employee_score",
                    "total_manager_score",
                    "grade_manager",
                    "grade_manager_overridden",
                    "grade_hrm",
                ],
            },
        ),
        (
            "Tasks and Proposals",
            {
                "fields": ["plan_tasks", "extra_tasks", "proposal"],
            },
        ),
        (
            "Status",
            {
                "fields": ["finalized", "note"],
            },
        ),
        (
            "Audit",
            {
                "fields": ["created_by", "updated_by", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def get_month(self, obj):
        """Display month from period."""
        return obj.period.month.strftime("%Y-%m")

    get_month.short_description = "Month"  # type: ignore[attr-defined]
    get_month.admin_order_field = "period__month"  # type: ignore[attr-defined]


@admin.register(EmployeeKPIItem)
class EmployeeKPIItemAdmin(admin.ModelAdmin):
    """Admin for EmployeeKPIItem model."""

    list_display = [
        "id",
        "assessment",
        "criterion",
        "evaluation_type",
        "component_total_score",
        "employee_score",
        "manager_score",
        "ordering",
    ]
    list_filter = ["evaluation_type"]
    search_fields = ["criterion", "assessment__employee__username"]
    ordering = ["assessment", "ordering"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DepartmentKPIAssessment)
class DepartmentKPIAssessmentAdmin(admin.ModelAdmin):
    """Admin for DepartmentKPIAssessment model."""

    list_display = ["id", "department", "get_month", "grade", "finalized"]
    list_filter = ["period__month", "grade", "finalized"]
    search_fields = ["department__name", "department__code"]
    ordering = ["-period__month", "department__name"]
    readonly_fields = ["assigned_by", "assigned_at", "created_at", "updated_at"]

    def get_month(self, obj):
        """Display month from period."""
        return obj.period.month.strftime("%Y-%m")

    get_month.short_description = "Month"  # type: ignore[attr-defined]
    get_month.admin_order_field = "period__month"  # type: ignore[attr-defined]

    list_display = ["id", "period", "department", "grade"]
    search_fields = ["department__name", "employee__username"]
    ordering = ["-id"]
    readonly_fields = ["id"]
