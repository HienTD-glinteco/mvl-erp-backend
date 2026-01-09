from django.contrib import admin

from apps.payroll.models import PayrollSlip, PenaltyTicket, RecoveryVoucher, SalesRevenue, TravelExpense

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
    ProposalVerifier,
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

    list_display = ["code", "name", "data_scope", "is_leadership", "include_in_employee_report", "is_active"]
    list_filter = ["data_scope", "is_leadership", "include_in_employee_report", "is_active"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["code", "name", "description"]}),
        ("Data Access", {"fields": ["data_scope", "is_leadership"]}),
        ("Reporting", {"fields": ["include_in_employee_report"]}),
        ("Status", {"fields": ["is_active"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]


class PenaltyTicketInline(admin.TabularInline):
    model = PenaltyTicket
    fk_name = "employee"
    extra = 0
    fields = ["code", "month", "amount", "status"]
    readonly_fields = ["code", "month", "amount", "status"]
    show_change_link = True


class TravelExpenseInline(admin.TabularInline):
    model = TravelExpense
    fk_name = "employee"
    extra = 0
    fields = ["code", "name", "expense_type", "amount", "month", "status"]
    readonly_fields = ["code", "name", "expense_type", "amount", "month", "status"]
    show_change_link = True


class PayrollSlipInline(admin.TabularInline):
    model = PayrollSlip
    fk_name = "employee"
    extra = 0
    fields = ["code", "salary_period", "status", "net_salary", "calculated_at"]
    readonly_fields = ["code", "salary_period", "status", "net_salary", "calculated_at"]
    show_change_link = True


class SalesRevenueInline(admin.TabularInline):
    model = SalesRevenue
    fk_name = "employee"
    extra = 0
    fields = ["code", "revenue", "transaction_count", "month", "status"]
    readonly_fields = ["code", "revenue", "transaction_count", "month", "status"]
    show_change_link = True


class RecoveryVoucherInline(admin.TabularInline):
    model = RecoveryVoucher
    fk_name = "employee"
    extra = 0
    fields = ["code", "name", "amount", "month", "status"]
    readonly_fields = ["code", "name", "amount", "month", "status"]
    show_change_link = True


class BankAccountInline(admin.TabularInline):
    model = BankAccount
    fk_name = "employee"
    extra = 0
    fields = ["bank", "account_number", "account_name", "is_primary"]
    readonly_fields = ["bank", "account_number", "account_name", "is_primary"]
    show_change_link = True


class EmployeeDependentInline(admin.TabularInline):
    model = EmployeeDependent
    fk_name = "employee"
    extra = 0
    fields = ["dependent_name", "relationship", "date_of_birth"]
    readonly_fields = ["dependent_name", "relationship", "date_of_birth"]
    show_change_link = True


class EmployeeCertificateInline(admin.TabularInline):
    model = EmployeeCertificate
    fk_name = "employee"
    extra = 0
    fields = ["certificate_type", "certificate_name", "issue_date"]
    readonly_fields = ["certificate_type", "certificate_name", "issue_date"]
    show_change_link = True


class EmployeeRelationshipInline(admin.TabularInline):
    model = EmployeeRelationship
    fk_name = "employee"
    extra = 0
    fields = ["relative_name", "relation_type"]
    readonly_fields = ["relative_name", "relation_type"]
    show_change_link = True


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["code", "fullname", "username", "email", "status", "phone", "start_date"]

    list_filter = [
        "status",
    ]

    search_fields = ["code", "fullname", "email"]
    inlines = [
        PenaltyTicketInline,
        TravelExpenseInline,
        PayrollSlipInline,
        SalesRevenueInline,
        RecoveryVoucherInline,
        BankAccountInline,
        EmployeeDependentInline,
        EmployeeCertificateInline,
        EmployeeRelationshipInline,
    ]


@admin.register(EmployeeWorkHistory)
class EmployeeWorkHistoryAdmin(admin.ModelAdmin):
    list_display = ["date", "name", "employee", "status", "from_date", "to_date"]


@admin.register(AttendanceDevice)
class AttendanceDeviceAdmin(admin.ModelAdmin):
    """Admin configuration for AttendanceDevice model"""

    list_display = ["id", "code", "name", "ip_address", "port", "is_connected", "block"]
    list_filter = ["is_connected", "block"]
    search_fields = ["code", "name", "ip_address", "serial_number"]
    readonly_fields = ["code", "created_at", "updated_at"]


@admin.register(AttendanceExemption)
class AttendanceExemptionAdmin(admin.ModelAdmin):
    """Admin configuration for AttendanceExemption model"""

    list_display = ["id", "employee", "effective_date", "created_at"]
    list_filter = ["effective_date"]
    search_fields = ["employee__code", "employee__fullname"]
    raw_id_fields = ["employee"]


@admin.register(AttendanceGeolocation)
class AttendanceGeolocationAdmin(admin.ModelAdmin):
    """Admin configuration for AttendanceGeolocation model"""

    list_display = ["id", "code", "name", "project", "status", "latitude", "longitude", "radius_m"]
    list_filter = ["status", "project"]
    search_fields = ["code", "name", "address"]
    readonly_fields = ["code", "created_at", "updated_at"]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Admin configuration for AttendanceRecord model"""

    list_display = ["id", "code", "attendance_type", "employee", "attendance_code", "timestamp", "biometric_device"]
    list_filter = ["attendance_type", "biometric_device"]
    search_fields = ["code", "attendance_code", "employee__code", "employee__fullname"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["employee", "biometric_device"]


class DepartmentInlineForBlock(admin.TabularInline):
    model = Department
    fk_name = "block"
    extra = 0
    fields = ["code", "name", "function", "is_active"]
    readonly_fields = ["code", "name", "function", "is_active"]
    show_change_link = True


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    """Admin configuration for Block model"""

    list_display = ["id", "code", "name", "block_type", "branch", "is_active"]
    list_filter = ["block_type", "branch", "is_active"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["director"]
    inlines = [DepartmentInlineForBlock]


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    """Admin configuration for Bank model"""

    list_display = ["id", "code", "name"]
    search_fields = ["code", "name"]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """Admin configuration for BankAccount model"""

    list_display = ["id", "employee", "bank", "account_number", "account_name", "is_primary"]
    list_filter = ["is_primary", "bank"]
    search_fields = ["account_number", "account_name", "employee__code", "employee__fullname"]
    raw_id_fields = ["employee", "bank"]


class BlockInline(admin.TabularInline):
    model = Block
    fk_name = "branch"
    extra = 0
    fields = ["code", "name", "block_type", "is_active"]
    readonly_fields = ["code", "name", "block_type", "is_active"]
    show_change_link = True


class DepartmentInline(admin.TabularInline):
    model = Department
    fk_name = "branch"
    extra = 0
    fields = ["code", "name", "function", "is_active"]
    readonly_fields = ["code", "name", "function", "is_active"]
    show_change_link = True


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    """Admin configuration for Branch model"""

    list_display = ["id", "code", "name", "province", "is_active"]
    list_filter = ["province", "is_active"]
    search_fields = ["code", "name", "address"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["director"]
    inlines = [BlockInline, DepartmentInline]


@admin.register(BranchContactInfo)
class BranchContactInfoAdmin(admin.ModelAdmin):
    """Admin configuration for BranchContactInfo model"""

    list_display = ["id", "branch", "business_line", "name", "phone_number", "email"]
    list_filter = ["business_line", "branch"]
    search_fields = ["name", "phone_number", "email"]
    raw_id_fields = ["branch"]


class EmployeeInline(admin.TabularInline):
    model = Employee
    fk_name = "department"
    extra = 0
    fields = ["code", "fullname", "status", "start_date"]
    readonly_fields = ["code", "fullname", "status", "start_date"]
    show_change_link = True


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model"""

    list_display = ["id", "code", "name", "branch", "block", "function", "is_active"]
    list_filter = ["function", "is_main_department", "is_active", "branch", "block"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["leader", "parent_department", "management_department"]
    inlines = [EmployeeInline]


@admin.register(RecruitmentChannel)
class RecruitmentChannelAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentChannel model"""

    list_display = ["id", "code", "name", "belong_to", "is_active"]
    list_filter = ["belong_to", "is_active"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]


@admin.register(RecruitmentSource)
class RecruitmentSourceAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentSource model"""

    list_display = ["id", "code", "name", "allow_referral"]
    list_filter = ["allow_referral"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]


@admin.register(EmployeeCertificate)
class EmployeeCertificateAdmin(admin.ModelAdmin):
    """Admin configuration for EmployeeCertificate model"""

    list_display = ["id", "code", "employee", "certificate_type", "certificate_name", "issue_date"]
    list_filter = ["certificate_type"]
    search_fields = ["code", "certificate_code", "certificate_name", "employee__code", "employee__fullname"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["employee"]


@admin.register(EmployeeDependent)
class EmployeeDependentAdmin(admin.ModelAdmin):
    """Admin configuration for EmployeeDependent model"""

    list_display = ["id", "code", "employee", "dependent_name", "relationship", "date_of_birth"]
    list_filter = ["relationship"]
    search_fields = ["code", "dependent_name", "citizen_id", "employee__code", "employee__fullname"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["employee"]


@admin.register(EmployeeRelationship)
class EmployeeRelationshipAdmin(admin.ModelAdmin):
    """Admin configuration for EmployeeRelationship model"""

    list_display = ["id", "code", "employee", "relative_name", "relation_type"]
    list_filter = ["relation_type"]
    search_fields = ["code", "relative_name", "employee__code", "employee__fullname"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["employee"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """Admin configuration for Contract model"""

    list_display = [
        "id",
        "code",
        "contract_number",
        "employee",
        "contract_type",
        "status",
        "sign_date",
        "effective_date",
    ]
    list_filter = ["status", "contract_type"]
    search_fields = ["code", "contract_number", "employee__code", "employee__fullname"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["employee", "contract_type", "parent_contract"]


@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    """Admin configuration for ContractType model"""

    list_display = ["id", "code", "name", "symbol", "category", "duration_type", "duration_months"]
    list_filter = ["category", "duration_type"]
    search_fields = ["code", "name", "symbol"]
    readonly_fields = ["code", "created_at", "updated_at"]


@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    """Admin configuration for JobDescription model"""

    list_display = ["id", "code", "title", "position_title", "proposed_salary"]
    search_fields = ["code", "title", "position_title"]
    readonly_fields = ["code", "created_at", "updated_at"]


@admin.register(InterviewCandidate)
class InterviewCandidateAdmin(admin.ModelAdmin):
    """Admin configuration for InterviewCandidate model"""

    list_display = ["id", "recruitment_candidate", "interview_schedule", "interview_time", "email_sent_at"]
    list_filter = ["interview_time"]
    search_fields = ["recruitment_candidate__name", "recruitment_candidate__code"]
    raw_id_fields = ["recruitment_candidate", "interview_schedule"]


@admin.register(InterviewSchedule)
class InterviewScheduleAdmin(admin.ModelAdmin):
    """Admin configuration for InterviewSchedule model"""

    list_display = ["id", "title", "recruitment_request", "interview_type", "location", "time"]
    list_filter = ["interview_type"]
    search_fields = ["title", "location"]
    raw_id_fields = ["recruitment_request"]


@admin.register(RecruitmentRequest)
class RecruitmentRequestAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentRequest model"""

    list_display = ["id", "code", "name", "recruitment_type", "status", "number_of_positions", "proposed_salary"]
    list_filter = ["recruitment_type", "status"]
    search_fields = ["code", "name"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = ["job_description", "branch", "block", "department", "proposer"]


@admin.register(RecruitmentCandidate)
class RecruitmentCandidateAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentCandidate model"""

    list_display = ["id", "code", "name", "email", "phone", "status", "recruitment_request"]
    list_filter = ["status", "recruitment_source", "recruitment_channel"]
    search_fields = ["code", "name", "email", "phone", "citizen_id"]
    readonly_fields = ["code", "created_at", "updated_at"]
    raw_id_fields = [
        "recruitment_request",
        "recruitment_source",
        "recruitment_channel",
        "branch",
        "block",
        "department",
    ]


@admin.register(RecruitmentCandidateContactLog)
class RecruitmentCandidateContactLogAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentCandidateContactLog model"""

    list_display = ["id", "recruitment_candidate", "employee", "date", "method"]
    list_filter = ["method", "date"]
    search_fields = ["recruitment_candidate__name", "recruitment_candidate__code"]
    raw_id_fields = ["recruitment_candidate", "employee"]


@admin.register(RecruitmentExpense)
class RecruitmentExpenseAdmin(admin.ModelAdmin):
    """Admin configuration for RecruitmentExpense model"""

    list_display = ["id", "date", "recruitment_request", "recruitment_source", "recruitment_channel", "total_cost"]
    list_filter = ["date", "recruitment_source", "recruitment_channel"]
    search_fields = ["recruitment_request__code", "recruitment_request__name"]
    raw_id_fields = ["recruitment_request", "recruitment_source", "recruitment_channel", "referee", "referrer"]


@admin.register(ProposalVerifier)
class ProposalVerifierAdmin(admin.ModelAdmin):
    """Admin configuration for ProposalVerifier model"""

    list_display = ["id", "proposal", "employee", "status", "verified_time"]
    list_filter = ["status"]
    search_fields = ["proposal__code", "employee__code", "employee__fullname"]
    raw_id_fields = ["proposal", "employee"]


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    """Admin configuration for WorkSchedule model"""

    list_display = [
        "id",
        "weekday",
        "morning_start_time",
        "morning_end_time",
        "afternoon_start_time",
        "afternoon_end_time",
    ]
    list_filter = ["weekday"]


@admin.register(CompensatoryWorkday)
class CompensatoryWorkdayAdmin(admin.ModelAdmin):
    """Admin configuration for CompensatoryWorkday model"""

    list_display = ["id", "holiday", "date", "session"]
    list_filter = ["session", "date"]
    search_fields = ["holiday__name"]
    raw_id_fields = ["holiday"]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    """Admin configuration for Holiday model"""

    list_display = ["id", "name", "start_date", "end_date"]
    list_filter = ["start_date", "end_date"]
    search_fields = ["name"]


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
