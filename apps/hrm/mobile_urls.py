from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.hrm.api.views import (
    AttendanceGeolocationViewSet,
    AttendanceWifiDeviceViewSet,
    BlockViewSet,
    BranchViewSet,
    DepartmentViewSet,
    EmployeeViewSet,
    MyAttendanceRecordViewSet,
    MyProposalAssetAllocationViewSet,
    MyProposalDeviceChangeViewSet,
    MyProposalJobTransferViewSet,
    MyProposalLateExemptionViewSet,
    MyProposalMaternityLeaveViewSet,
    MyProposalOvertimeWorkViewSet,
    MyProposalPaidLeaveViewSet,
    MyProposalPostMaternityBenefitsViewSet,
    MyProposalsVerificationViewSet,
    MyProposalTimesheetEntryComplaintViewSet,
    MyProposalUnpaidLeaveViewSet,
    MyProposalViewSet,
    MyTimesheetEntryViewSet,
    MyTimesheetViewSet,
    PositionViewSet,
)

app_name = "hrm-mobile"

router = DefaultRouter()

# router.register(r"attendance-geolocations", AttendanceGeolocationViewSet, basename="attendance-geolocation")

# My timesheets
router.register(r"me/timesheets", MyTimesheetViewSet, basename="my-timesheet")

# My timesheet entries
router.register(r"me/timesheet/entries", MyTimesheetEntryViewSet, basename="my-timesheet-entry")

# My attendance records
router.register(r"me/attendance-records", MyAttendanceRecordViewSet, basename="my-attendance-record")

# Type-specific proposal endpoints (must be registered before general proposals)
router.register(
    r"me/proposals/maternity-leave",
    MyProposalMaternityLeaveViewSet,
    basename="my-proposal-maternity-leave",
)
router.register(
    r"me/proposals/unpaid-leave",
    MyProposalUnpaidLeaveViewSet,
    basename="my-proposal-unpaid-leave",
)
router.register(
    r"me/proposals/paid-leave",
    MyProposalPaidLeaveViewSet,
    basename="my-proposal-paid-leave",
)
router.register(
    r"me/proposals/post-maternity-benefits",
    MyProposalPostMaternityBenefitsViewSet,
    basename="my-proposal-post-maternity-benefits",
)
router.register(
    r"me/proposals/overtime-work",
    MyProposalOvertimeWorkViewSet,
    basename="my-proposal-overtime-work",
)
router.register(
    r"me/proposals/late-exemption",
    MyProposalLateExemptionViewSet,
    basename="my-proposal-late-exemption",
)
router.register(
    r"me/proposals/job-transfer",
    MyProposalJobTransferViewSet,
    basename="my-proposal-job-transfer",
)
router.register(
    r"me/proposals/device-change",
    MyProposalDeviceChangeViewSet,
    basename="my-proposal-device-change",
)
router.register(
    r"me/proposals/asset-allocation",
    MyProposalAssetAllocationViewSet,
    basename="my-proposal-asset-allocation",
)
router.register(
    r"me/proposals/timesheet-entry-complaint",
    MyProposalTimesheetEntryComplaintViewSet,
    basename="my-proposal-timesheet-entry-complaint",
)

# My proposals (all types) - must be registered AFTER specific types
router.register(r"me/proposals", MyProposalViewSet, basename="my-proposal")

# Pending verifications
router.register(
    r"me/proposals-verifications",
    MyProposalsVerificationViewSet,
    basename="my-proposals-verification",
)

urlpatterns = router.urls

urlpatterns += [
    path(
        "attendance-geolocations/",
        AttendanceGeolocationViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="list-attendance-geolocaitons",
    ),
    path(
        "attendance-wifi-devices/",
        AttendanceWifiDeviceViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="list-attendance-wifidevices",
    ),
    path(
        "blocks/",
        BlockViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="list-blocks",
    ),
    path(
        "branches/",
        BranchViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="list-branches",
    ),
    path(
        "departments/",
        DepartmentViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="list-departments",
    ),
    path(
        "positions/",
        PositionViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="list-positions",
    ),
    path(
        "employees/dropdown/",
        EmployeeViewSet.as_view({"get": "dropdown"}),
        name="employee-dropdown",
    ),
]
