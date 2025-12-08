from django.contrib import admin

from .models import (
    AttendanceDevice,
    AttendanceExemption,
    AttendanceGeolocation,
    AttendanceRecord,
    Bank,
    BankAccount,
    Block,
    Branch,
    BranchContactInfo,
    CompensatoryWorkday,
    Contract,
    ContractType,
    Decision,
    Department,
    Employee,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    EmployeeWorkHistory,
    Holiday,
    InterviewCandidate,
    InterviewSchedule,
    JobDescription,
    Position,
    Proposal,
    ProposalAsset,
    ProposalOvertimeEntry,
    RecruitmentCandidate,
    RecruitmentCandidateContactLog,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
    WorkSchedule,
)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin configuration for Position model"""

    list_display = ["code", "name", "data_scope", "is_leadership", "include_in_hr_report", "is_active"]
    list_filter = ["data_scope", "is_leadership", "include_in_hr_report", "is_active"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["code", "name", "description"]}),
        ("Data Access", {"fields": ["data_scope", "is_leadership"]}),
        ("Reporting", {"fields": ["include_in_hr_report"]}),
        ("Status", {"fields": ["is_active"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["code", "fullname", "username", "email", "status", "phone", "start_date"]

    list_filter = [
        "status",
    ]

    search_fields = ["code", "fullname", "email"]


@admin.register(EmployeeWorkHistory)
class EmployeeWorkHistoryAdmin(admin.ModelAdmin):
    list_display = ["date", "name", "employee", "status", "from_date", "to_date"]


admin.site.register(AttendanceDevice)
admin.site.register(AttendanceExemption)
admin.site.register(AttendanceGeolocation)
admin.site.register(AttendanceRecord)

admin.site.register(Block)
admin.site.register(Bank)
admin.site.register(BankAccount)
admin.site.register(Branch)
admin.site.register(BranchContactInfo)
admin.site.register(Department)
admin.site.register(RecruitmentChannel)
admin.site.register(RecruitmentSource)

admin.site.register(EmployeeCertificate)
admin.site.register(EmployeeDependent)
admin.site.register(EmployeeRelationship)
admin.site.register(Contract)
admin.site.register(ContractType)
admin.site.register(JobDescription)
admin.site.register(InterviewCandidate)
admin.site.register(InterviewSchedule)
admin.site.register(RecruitmentRequest)
admin.site.register(RecruitmentCandidate)
admin.site.register(RecruitmentCandidateContactLog)
admin.site.register(RecruitmentExpense)
admin.site.register(WorkSchedule)

admin.site.register(CompensatoryWorkday)
admin.site.register(Holiday)


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    """Admin configuration for Decision model"""

    list_display = ["decision_number", "name", "signing_date", "signer", "effective_date", "signing_status"]
    list_filter = ["signing_status", "signing_date", "effective_date"]
    search_fields = ["decision_number", "name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["signer"]
    fieldsets = [
        (None, {"fields": ["decision_number", "name"]}),
        ("Signing Information", {"fields": ["signing_date", "signer", "effective_date", "signing_status"]}),
        ("Content", {"fields": ["reason", "content", "note"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    """Admin configuration for Proposal model"""

    list_display = ["code", "proposal_type", "proposal_status", "proposal_date", "created_by"]
    list_filter = ["proposal_type", "proposal_status", "proposal_date"]
    search_fields = ["code"]
    readonly_fields = ["code", "proposal_date", "created_at", "updated_at"]
    raw_id_fields = ["created_by", "approved_by", "maternity_leave_replacement_employee"]


@admin.register(ProposalAsset)
class ProposalAssetAdmin(admin.ModelAdmin):
    """Admin configuration for ProposalAsset model"""

    list_display = ["name", "unit_type", "quantity", "proposal"]
    list_filter = ["unit_type"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["proposal"]


@admin.register(ProposalOvertimeEntry)
class ProposalOvertimeEntryAdmin(admin.ModelAdmin):
    """Admin configuration for ProposalOvertimeEntry model"""

    list_display = ["proposal", "date", "start_time", "end_time", "duration_hours"]
    list_filter = ["date"]
    search_fields = ["proposal__code"]
    readonly_fields = ["created_at", "updated_at", "duration_hours"]
    raw_id_fields = ["proposal"]
