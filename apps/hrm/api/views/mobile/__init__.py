from apps.hrm.api.views.mobile.attendance import MyAttendanceRecordViewSet
from apps.hrm.api.views.mobile.proposal import (
    MyProposalAssetAllocationViewSet,
    MyProposalDeviceChangeViewSet,
    MyProposalJobTransferViewSet,
    MyProposalLateExemptionViewSet,
    MyProposalMaternityLeaveViewSet,
    MyProposalOvertimeWorkViewSet,
    MyProposalPaidLeaveViewSet,
    MyProposalPostMaternityBenefitsViewSet,
    MyProposalTimesheetEntryComplaintViewSet,
    MyProposalUnpaidLeaveViewSet,
    MyProposalVerifierViewSet,
    MyProposalViewSet,
)
from apps.hrm.api.views.mobile.timesheet import MyTimesheetEntryViewSet, MyTimesheetViewSet

__all__ = [
    "MyProposalViewSet",
    "MyProposalMaternityLeaveViewSet",
    "MyProposalUnpaidLeaveViewSet",
    "MyProposalPaidLeaveViewSet",
    "MyProposalPostMaternityBenefitsViewSet",
    "MyProposalOvertimeWorkViewSet",
    "MyProposalLateExemptionViewSet",
    "MyProposalJobTransferViewSet",
    "MyProposalDeviceChangeViewSet",
    "MyProposalAssetAllocationViewSet",
    "MyProposalTimesheetEntryComplaintViewSet",
    "MyProposalVerifierViewSet",
    "MyTimesheetViewSet",
    "MyTimesheetEntryViewSet",
    "MyAttendanceRecordViewSet",
]
