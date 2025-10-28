from django.contrib import admin

from .models import (
    Block,
    Branch,
    ContractType,
    Department,
    Employee,
    JobDescription,
    OrganizationChart,
    Position,
    RecruitmentCandidate,
    RecruitmentCandidateContactLog,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin configuration for Position model"""

    list_display = ["code", "name", "data_scope", "is_leadership", "is_active"]
    list_filter = ["data_scope", "is_leadership", "is_active"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["code", "name", "description"]}),
        ("Data Access", {"fields": ["data_scope", "is_leadership"]}),
        ("Status", {"fields": ["is_active"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]


@admin.register(OrganizationChart)
class OrganizationChartAdmin(admin.ModelAdmin):
    """Admin configuration for OrganizationChart model"""

    list_display = ["employee", "position", "department", "block", "branch", "start_date", "is_primary", "is_active"]
    list_filter = ["is_primary", "is_active", "position__is_leadership"]
    search_fields = ["employee__username", "employee__email", "position__name"]
    autocomplete_fields = ["employee", "position", "department", "block", "branch"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "start_date"
    fieldsets = [
        (
            "Assignment",
            {
                "fields": ["employee", "position"],
            },
        ),
        (
            "Organizational Unit",
            {
                "fields": ["department", "block", "branch"],
                "description": "Specify at least one: department, block, or branch. Block and branch will be auto-filled from department if not specified.",
            },
        ),
        (
            "Period",
            {
                "fields": ["start_date", "end_date"],
            },
        ),
        (
            "Status",
            {
                "fields": ["is_primary", "is_active"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at"],
            },
        ),
    ]


admin.site.register(Block)
admin.site.register(Branch)
admin.site.register(Department)
admin.site.register(RecruitmentChannel)
admin.site.register(RecruitmentSource)
admin.site.register(Employee)
admin.site.register(ContractType)
admin.site.register(JobDescription)
admin.site.register(RecruitmentRequest)
admin.site.register(RecruitmentCandidate)
admin.site.register(RecruitmentCandidateContactLog)
admin.site.register(RecruitmentExpense)
