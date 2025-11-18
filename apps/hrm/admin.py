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
    CompensatoryWorkday,
    ContractType,
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
admin.site.register(Department)
admin.site.register(RecruitmentChannel)
admin.site.register(RecruitmentSource)

admin.site.register(EmployeeCertificate)
admin.site.register(EmployeeDependent)
admin.site.register(EmployeeRelationship)
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
