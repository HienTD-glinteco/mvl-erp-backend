from django.contrib import admin

from .models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    EmployeeKPIItem,
    KPIAssessmentPeriod,
    KPIConfig,
    KPICriterion,
    PenaltyTicket,
    RecoveryVoucher,
    SalaryConfig,
    SalesRevenue,
    TravelExpense,
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
    readonly_fields = ["criterion_id", "target", "criterion", "evaluation_type", "component_total_score", "order"]
    fields = [
        "criterion",
        "target",
        "evaluation_type",
        "component_total_score",
        "employee_score",
        "manager_score",
        "order",
    ]


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
        "order",
    ]
    list_filter = ["evaluation_type"]
    search_fields = ["criterion", "assessment__employee__username"]
    ordering = ["assessment", "order"]
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


@admin.register(KPIAssessmentPeriod)
class KPIAssessmentPeriodAdmin(admin.ModelAdmin):
    """Admin for KPIAssessmentPeriod model."""

    list_display = ["id", "month", "finalized", "created_by", "created_at", "updated_at"]
    list_filter = ["finalized", "created_at"]
    search_fields = ["note"]
    ordering = ["-month"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["month", "kpi_config_snapshot"],
            },
        ),
        (
            "Status",
            {
                "fields": ["finalized", "note"],
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


@admin.register(RecoveryVoucher)
class RecoveryVoucherAdmin(admin.ModelAdmin):
    """Admin configuration for RecoveryVoucher model.

    Provides interface to manage recovery and back pay vouchers with filtering
    and search capabilities.
    """

    list_display = [
        "code",
        "name",
        "voucher_type",
        "employee_code",
        "employee_name",
        "amount",
        "get_month_display",
        "status",
        "created_at",
        "updated_at",
    ]
    list_filter = ["voucher_type", "status", "month", "created_at"]
    search_fields = ["code", "name", "employee_code", "employee_name", "note"]
    readonly_fields = [
        "code",
        "employee_code",
        "employee_name",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    fieldsets = [
        (
            "Voucher Information",
            {
                "fields": ["code", "name", "voucher_type", "employee"],
            },
        ),
        (
            "Cached Employee Information",
            {
                "fields": ["employee_code", "employee_name"],
                "description": "These fields are automatically cached from the employee record.",
                "classes": ["collapse"],
            },
        ),
        (
            "Financial Details",
            {
                "fields": ["amount", "month"],
            },
        ),
        (
            "Status and Notes",
            {
                "fields": ["status", "note"],
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

    def get_month_display(self, obj):
        """Display month in MM/YYYY format."""
        if obj.month:
            return obj.month.strftime("%m/%Y")
        return "-"

    get_month_display.short_description = "Period"  # type: ignore[attr-defined]
    get_month_display.admin_order_field = "month"  # type: ignore[attr-defined]

    def save_model(self, request, obj, form, change):
        """Set created_by or updated_by when saving through admin."""
        if not change:
            obj.created_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TravelExpense)
class TravelExpenseAdmin(admin.ModelAdmin):
    """Admin for TravelExpense model."""

    list_display = [
        "code",
        "name",
        "employee",
        "expense_type",
        "amount",
        "month",
        "status",
        "created_at",
    ]
    list_filter = ["expense_type", "status", "month", "created_at"]
    search_fields = ["code", "name", "employee__code", "employee__fullname"]
    ordering = ["-created_at"]
    readonly_fields = ["code", "status", "created_at", "updated_at"]
    autocomplete_fields = ["employee"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["code", "name", "expense_type", "employee"],
            },
        ),
        (
            "Amount and Period",
            {
                "fields": ["amount", "month"],
            },
        ),
        (
            "Status and Notes",
            {
                "fields": ["status", "note"],
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


@admin.register(SalesRevenue)
class SalesRevenueAdmin(admin.ModelAdmin):
    """Admin for SalesRevenue model."""

    list_display = [
        "code",
        "employee",
        "revenue",
        "transaction_count",
        "month",
        "status",
        "created_at",
    ]
    list_filter = ["status", "month", "created_at"]
    search_fields = ["code", "employee__code", "employee__fullname"]
    ordering = ["-created_at"]
    readonly_fields = ["code", "status", "created_at", "updated_at"]
    autocomplete_fields = ["employee"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["code", "employee"],
            },
        ),
        (
            "Revenue Details",
            {
                "fields": ["revenue", "transaction_count", "month"],
            },
        ),
        (
            "Status",
            {
                "fields": ["status"],
            },
        ),
    ]


@admin.register(PenaltyTicket)
class PenaltyTicketAdmin(admin.ModelAdmin):
    """Admin configuration for PenaltyTicket model.

    Provides interface to view and manage penalty tickets (uniform violations).
    """

    list_display = [
        "code",
        "employee_code",
        "employee_name",
        "amount",
        "month",
        "payment_status",
        "payroll_status",
        "created_at",
    ]
    list_filter = ["month", "payment_status", "payroll_status"]
    search_fields = ["code", "employee_code", "employee_name", "note"]
    readonly_fields = [
        "code",
        "employee_code",
        "employee_name",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    fieldsets = [
        (
            "Ticket Information",
            {
                "fields": ["code", "month"],
            },
        ),
        (
            "Employee Information",
            {
                "fields": [
                    "employee",
                    "employee_code",
                    "employee_name",
                ],
            },
        ),
        (
            "Violation Details",
            {
                "fields": [
                    "violation_count",
                    "violation_type",
                    "amount",
                    "payment_status",
                    "payroll_status",
                    "note",
                    "attachments",
                ],
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
