from django.contrib import admin

from .models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    EmployeeKPIItem,
    KPIAssessmentPeriod,
    KPIConfig,
    KPICriterion,
    PayrollSlip,
    PenaltyTicket,
    RecoveryVoucher,
    SalaryConfig,
    SalaryPeriod,
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
                "fields": ["period", "employee", "department_snapshot"],
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


class EmployeeKPIAssessmentInline(admin.TabularInline):
    model = EmployeeKPIAssessment
    fk_name = "period"
    extra = 0
    fields = ["employee", "grade_manager", "grade_hrm", "finalized"]
    readonly_fields = ["employee", "grade_manager", "grade_hrm", "finalized"]
    show_change_link = True


class DepartmentKPIAssessmentInline(admin.TabularInline):
    model = DepartmentKPIAssessment
    fk_name = "period"
    extra = 0
    fields = ["department", "grade", "finalized"]
    readonly_fields = ["department", "grade", "finalized"]
    show_change_link = True


@admin.register(KPIAssessmentPeriod)
class KPIAssessmentPeriodAdmin(admin.ModelAdmin):
    """Admin for KPIAssessmentPeriod model."""

    list_display = ["id", "month", "finalized", "created_by", "created_at", "updated_at"]
    list_filter = ["finalized", "created_at"]
    search_fields = ["note"]
    ordering = ["-month"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [EmployeeKPIAssessmentInline, DepartmentKPIAssessmentInline]
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


class InlineAttachmentAdmin(admin.TabularInline):
    """Inline admin for displaying attachments in PenaltyTicket admin."""

    model = PenaltyTicket.attachments.through
    extra = 0
    readonly_fields = ["filemodel"]


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
        "status",
        "created_at",
    ]
    list_filter = ["month", "status"]
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
    inlines = [InlineAttachmentAdmin]

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
                    "status",
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


class PayrollSlipInline(admin.TabularInline):
    model = PayrollSlip
    fk_name = "salary_period"
    extra = 0
    fields = ["code", "employee", "status", "net_salary", "calculated_at"]
    readonly_fields = ["code", "employee", "status", "net_salary", "calculated_at"]
    show_change_link = True


@admin.register(SalaryPeriod)
class SalaryPeriodAdmin(admin.ModelAdmin):
    """Admin configuration for SalaryPeriod model."""

    list_display = [
        "code",
        "month",
        "status",
        "standard_working_days",
        "total_employees",
        "completed_at",
        "created_at",
    ]
    list_filter = ["status", "month", "created_at"]
    search_fields = ["code"]
    readonly_fields = [
        "code",
        "standard_working_days",
        "total_employees",
        "completed_at",
        "completed_by",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]
    ordering = ["-month"]
    inlines = [PayrollSlipInline]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["code", "month", "status"],
            },
        ),
        (
            "Salary Configuration",
            {
                "fields": ["salary_config_snapshot"],
            },
        ),
        (
            "Statistics",
            {
                "fields": ["standard_working_days", "total_employees"],
            },
        ),
        (
            "Completion",
            {
                "fields": ["completed_at", "completed_by"],
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

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of completed periods."""
        if obj and obj.status == SalaryPeriod.Status.COMPLETED:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(PayrollSlip)
class PayrollSlipAdmin(admin.ModelAdmin):
    """Admin configuration for PayrollSlip model."""

    list_display = [
        "code",
        "employee_code",
        "employee_name",
        "get_month_display",
        "status",
        "net_salary",
        "has_unpaid_penalty",
        "calculated_at",
    ]
    list_filter = ["status", "salary_period__month", "has_unpaid_penalty", "need_resend_email"]
    search_fields = ["code", "employee_code", "employee_name", "employee_email", "tax_code"]
    readonly_fields = [
        "code",
        "employee_code",
        "employee_name",
        "employee_email",
        "tax_code",
        "department_name",
        "position_name",
        "employment_status",
        "contract_id",
        "kpi_grade",
        "kpi_percentage",
        "business_grade",
        "sales_revenue",
        "sales_transaction_count",
        "standard_working_days",
        "total_working_days",
        "official_working_days",
        "probation_working_days",
        "hourly_rate",
        "total_overtime_hours",
        "total_position_income",
        "actual_working_days_income",
        "taxable_overtime_salary",
        "overtime_progress_allowance",
        "non_taxable_overtime_salary",
        "gross_income",
        "taxable_income_base",
        "social_insurance_base",
        "personal_deduction",
        "dependent_count",
        "dependent_deduction",
        "taxable_income",
        "net_salary",
        "has_unpaid_penalty",
        "unpaid_penalty_count",
        "calculated_at",
        "email_sent_at",
        "delivered_at",
        "delivered_by",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]
    autocomplete_fields = ["employee", "salary_period"]
    ordering = ["-calculated_at"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": [
                    "code",
                    "salary_period",
                    "employee",
                    "employee_code",
                    "employee_name",
                    "employee_email",
                    "tax_code",
                    "department_name",
                    "position_name",
                    "employment_status",
                ],
            },
        ),
        (
            "Penalty Tickets",
            {
                "fields": ["has_unpaid_penalty", "unpaid_penalty_count"],
            },
        ),
        (
            "Contract Information",
            {
                "fields": [
                    "contract_id",
                    "base_salary",
                    "kpi_salary",
                    "lunch_allowance",
                    "phone_allowance",
                    "other_allowance",
                ],
            },
        ),
        (
            "KPI Component",
            {
                "fields": ["kpi_grade", "kpi_percentage", "kpi_bonus"],
            },
        ),
        (
            "Sales Performance",
            {
                "fields": [
                    "sales_revenue",
                    "sales_transaction_count",
                    "business_grade",
                    "business_progressive_salary",
                ],
            },
        ),
        (
            "Working Days",
            {
                "fields": [
                    "standard_working_days",
                    "total_working_days",
                    "official_working_days",
                    "probation_working_days",
                ],
            },
        ),
        (
            "Overtime",
            {
                "fields": [
                    "tc1_overtime_hours",
                    "tc2_overtime_hours",
                    "tc3_overtime_hours",
                    "total_overtime_hours",
                    "hourly_rate",
                    "overtime_pay",
                    "total_position_income",
                    "actual_working_days_income",
                    "taxable_overtime_salary",
                    "overtime_progress_allowance",
                    "non_taxable_overtime_salary",
                ],
            },
        ),
        (
            "Travel Expenses",
            {
                "fields": ["taxable_travel_expense", "non_taxable_travel_expense", "total_travel_expense"],
            },
        ),
        (
            "Income & Insurance",
            {
                "fields": [
                    "gross_income",
                    "taxable_income_base",
                    "social_insurance_base",
                    "employee_social_insurance",
                    "employee_health_insurance",
                    "employee_unemployment_insurance",
                    "employee_union_fee",
                    "employer_social_insurance",
                    "employer_health_insurance",
                    "employer_unemployment_insurance",
                    "employer_union_fee",
                    "employer_accident_insurance",
                ],
            },
        ),
        (
            "Personal Income Tax",
            {
                "fields": [
                    "personal_deduction",
                    "dependent_count",
                    "dependent_deduction",
                    "taxable_income",
                    "personal_income_tax",
                ],
            },
        ),
        (
            "Recovery Vouchers",
            {
                "fields": ["back_pay_amount", "recovery_amount"],
            },
        ),
        (
            "Final Calculation",
            {
                "fields": ["net_salary"],
            },
        ),
        (
            "Workflow & Status",
            {
                "fields": [
                    "status",
                    "status_note",
                    "need_resend_email",
                    "email_sent_at",
                    "delivered_at",
                    "delivered_by",
                ],
            },
        ),
        (
            "Calculation Log",
            {
                "fields": ["calculation_log", "calculated_at"],
                "classes": ["collapse"],
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
        if obj.salary_period:
            return obj.salary_period.month.strftime("%m/%Y")
        return "-"

    get_month_display.short_description = "Period"  # type: ignore[attr-defined]
    get_month_display.admin_order_field = "salary_period__month"  # type: ignore[attr-defined]

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of delivered slips."""
        if obj and obj.status == PayrollSlip.Status.DELIVERED:
            return False
        return super().has_delete_permission(request, obj)
