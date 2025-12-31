from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.hrm.api.views import (
    AttendanceExemptionViewSet,
    AttendanceGeolocationViewSet,
    AttendanceRecordViewSet,
    AttendanceReportViewSet,
    AttendanceWifiDeviceViewSet,
    BlockViewSet,
    BranchContactInfoViewSet,
    BranchViewSet,
    DepartmentViewSet,
    EmployeeTimesheetViewSet,
    EmployeeViewSet,
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
router.register(r"attendance-geolocations", AttendanceGeolocationViewSet, basename="attendance-geolocation")
router.register(r"attendance-exemptions", AttendanceExemptionViewSet, basename="attendance-exemption")
router.register(r"attendance-wifi-devices", AttendanceWifiDeviceViewSet, basename="attendance-wifi-device")

router.register(r"attendance-records", AttendanceRecordViewSet, basename="attendance-record")
router.register(r"attendance-reports", AttendanceReportViewSet, basename="attendance-report")
router.register(r"timesheets", EmployeeTimesheetViewSet, basename="employee-timesheet")
router.register(r"timesheet/entries", TimeSheetEntryViewSet, basename="timesheet-entry")
router.register(r"work-schedules", WorkScheduleViewSet, basename="work-schedule")
# router.register(r"decisions", DecisionViewSet, basename="decision")

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


urlpatterns = [
    path("", include(router.urls)),
    path(
        "employees/dropdown/",
        EmployeeViewSet.as_view({"get": "dropdown"}),
        name="employee-dropdown",
    ),
]
