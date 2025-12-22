from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.hrm.api.views import (
    AttendanceDeviceViewSet,
    AttendanceExemptionViewSet,
    AttendanceGeolocationViewSet,
    AttendanceRecordViewSet,
    AttendanceReportViewSet,
    AttendanceWifiDeviceViewSet,
    BankAccountViewSet,
    BankViewSet,
    BlockViewSet,
    BranchContactInfoViewSet,
    BranchViewSet,
    CompensatoryWorkdayViewSet,
    ContractAppendixViewSet,
    ContractTypeViewSet,
    ContractViewSet,
    DecisionViewSet,
    DepartmentViewSet,
    EmployeeCertificateViewSet,
    EmployeeDependentViewSet,
    EmployeeRelationshipViewSet,
    EmployeeReportsViewSet,
    EmployeeRoleViewSet,
    EmployeeSeniorityReportViewSet,
    EmployeeTimesheetViewSet,
    EmployeeTypeConversionReportViewSet,
    EmployeeViewSet,
    EmployeeWorkHistoryViewSet,
    HolidayViewSet,
    InterviewCandidateViewSet,
    InterviewScheduleViewSet,
    JobDescriptionViewSet,
    PositionViewSet,
    ProposalAssetAllocationViewSet,
    ProposalDeviceChangeViewSet,
    ProposalJobTransferViewSet,
    ProposalLateExemptionViewSet,
    ProposalMaternityLeaveViewSet,
    ProposalOvertimeWorkViewSet,
    ProposalPaidLeaveViewSet,
    ProposalPostMaternityBenefitsViewSet,
    ProposalTimesheetEntryComplaintViewSet,
    ProposalUnpaidLeaveViewSet,
    ProposalVerifierViewSet,
    ProposalViewSet,
    RecruitmentCandidateContactLogViewSet,
    RecruitmentCandidateViewSet,
    RecruitmentChannelViewSet,
    RecruitmentDashboardViewSet,
    RecruitmentExpenseViewSet,
    RecruitmentReportsViewSet,
    RecruitmentRequestViewSet,
    RecruitmentSourceViewSet,
    TimeSheetEntryViewSet,
    WorkScheduleViewSet,
)

app_name = "hrm"

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"branch-contact-infos", BranchContactInfoViewSet, basename="branch-contact-info")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"positions", PositionViewSet, basename="position")
router.register(r"employee-roles", EmployeeRoleViewSet, basename="employee-role")
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"employee-certificates", EmployeeCertificateViewSet, basename="employee-certificate")
router.register(r"employee-dependents", EmployeeDependentViewSet, basename="employee-dependent")
router.register(r"employee-work-histories", EmployeeWorkHistoryViewSet, basename="employee-work-history")
router.register(r"contract-types", ContractTypeViewSet, basename="contract-type")
router.register(r"contracts", ContractViewSet, basename="contract")
router.register(r"contract-appendices", ContractAppendixViewSet, basename="contract-appendix")
router.register(r"banks", BankViewSet, basename="bank")
router.register(r"bank-accounts", BankAccountViewSet, basename="bank-account")
router.register(r"attendance-geolocations", AttendanceGeolocationViewSet, basename="attendance-geolocation")
router.register(r"attendance-exemptions", AttendanceExemptionViewSet, basename="attendance-exemption")
router.register(r"attendance-wifi-devices", AttendanceWifiDeviceViewSet, basename="attendance-wifi-device")
router.register(r"holidays", HolidayViewSet, basename="holiday")
router.register(r"recruitment-channels", RecruitmentChannelViewSet, basename="recruitment-channel")
router.register(r"recruitment-sources", RecruitmentSourceViewSet, basename="recruitment-source")
router.register(r"job-descriptions", JobDescriptionViewSet, basename="job-description")
router.register(r"recruitment-requests", RecruitmentRequestViewSet, basename="recruitment-request")
router.register(r"recruitment-candidates", RecruitmentCandidateViewSet, basename="recruitment-candidate")
router.register(
    r"recruitment-candidate-contact-logs",
    RecruitmentCandidateContactLogViewSet,
    basename="recruitment-candidate-contact-log",
)
router.register(r"recruitment-expenses", RecruitmentExpenseViewSet, basename="recruitment-expense")
router.register(r"interview-schedules", InterviewScheduleViewSet, basename="interview-schedule")
router.register(r"interview-candidates", InterviewCandidateViewSet, basename="interview-candidate")
router.register(r"employee-relationships", EmployeeRelationshipViewSet, basename="employee-relationship")
router.register(r"attendance-devices", AttendanceDeviceViewSet, basename="attendance-device")
router.register(r"attendance-records", AttendanceRecordViewSet, basename="attendance-record")
router.register(r"attendance-reports", AttendanceReportViewSet, basename="attendance-report")
router.register(r"timesheets", EmployeeTimesheetViewSet, basename="employee-timesheet")
router.register(r"timesheet/entries", TimeSheetEntryViewSet, basename="timesheet-entry")
router.register(r"work-schedules", WorkScheduleViewSet, basename="work-schedule")
router.register(r"decisions", DecisionViewSet, basename="decision")

# Proposal endpoints - nested under proposals/
router.register(
    r"proposals/timesheet-entry-complaint",
    ProposalTimesheetEntryComplaintViewSet,
    basename="proposal-timesheet-entry-complaint",
)
router.register(
    r"proposals/post-maternity-benefits",
    ProposalPostMaternityBenefitsViewSet,
    basename="proposal-post-maternity-benefits",
)
router.register(
    r"proposals/late-exemption",
    ProposalLateExemptionViewSet,
    basename="proposal-late-exemption",
)
router.register(
    r"proposals/overtime-work",
    ProposalOvertimeWorkViewSet,
    basename="proposal-overtime-work",
)
router.register(
    r"proposals/paid-leave",
    ProposalPaidLeaveViewSet,
    basename="proposal-paid-leave",
)
router.register(
    r"proposals/unpaid-leave",
    ProposalUnpaidLeaveViewSet,
    basename="proposal-unpaid-leave",
)
router.register(
    r"proposals/maternity-leave",
    ProposalMaternityLeaveViewSet,
    basename="proposal-maternity-leave",
)
router.register(
    r"proposals/job-transfer",
    ProposalJobTransferViewSet,
    basename="proposal-job-transfer",
)
router.register(
    r"proposals/asset-allocation",
    ProposalAssetAllocationViewSet,
    basename="proposal-asset-allocation",
)
router.register(
    r"proposals/device-change",
    ProposalDeviceChangeViewSet,
    basename="proposal-device-change",
)

# Proposal verifiers
router.register(r"proposal-verifiers", ProposalVerifierViewSet, basename="proposal-verifier")

# Proposal endpoints
router.register(r"proposals", ProposalViewSet, basename="proposal")

# Report endpoints (single ViewSet with custom actions)
router.register(r"reports", EmployeeReportsViewSet, basename="employee-reports")
router.register(
    r"reports/employee-seniority-report", EmployeeSeniorityReportViewSet, basename="employee-seniority-reports"
)
router.register(
    r"reports/employee-type-conversion-report",
    EmployeeTypeConversionReportViewSet,
    basename="employee-type-conversion-reports",
)
router.register(r"reports", RecruitmentReportsViewSet, basename="recruitment-reports")

# Dashboard endpoints (single ViewSet with custom actions)
router.register(r"dashboard", RecruitmentDashboardViewSet, basename="recruitment-dashboard")

# Nested routes for compensatory workdays under holidays
compensatory_router = DefaultRouter()
compensatory_router.register(r"compensatory-days", CompensatoryWorkdayViewSet, basename="compensatory-day")

urlpatterns = [
    path("", include(router.urls)),
    path("holidays/<int:holiday_pk>/", include(compensatory_router.urls)),
]
