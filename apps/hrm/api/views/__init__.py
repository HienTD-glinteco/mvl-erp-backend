from .attendance_device import AttendanceDeviceViewSet
from .attendance_exemption import AttendanceExemptionViewSet
from .attendance_geolocation import AttendanceGeolocationViewSet
from .attendance_record import AttendanceRecordViewSet
from .attendance_report import AttendanceReportViewSet
from .attendance_wifi_device import AttendanceWifiDeviceViewSet
from .bank import BankViewSet
from .bank_account import BankAccountViewSet
from .contract import ContractViewSet
from .contract_appendix import ContractAppendixViewSet
from .contract_type import ContractTypeViewSet
from .decision import DecisionViewSet
from .employee import EmployeeViewSet
from .employee_certificate import EmployeeCertificateViewSet
from .employee_dependent import EmployeeDependentViewSet
from .employee_relationship import EmployeeRelationshipViewSet
from .employee_reports import EmployeeReportsViewSet
from .employee_role import EmployeeRoleViewSet
from .employee_work_history import EmployeeWorkHistoryViewSet
from .holiday import CompensatoryWorkdayViewSet, HolidayViewSet
from .interview_candidate import InterviewCandidateViewSet
from .interview_schedule import InterviewScheduleViewSet
from .job_description import JobDescriptionViewSet
from .organization import (
    BlockViewSet,
    BranchContactInfoViewSet,
    BranchViewSet,
    DepartmentViewSet,
    PositionViewSet,
)
from .proposal import (
    ProposalAssetAllocationViewSet,
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
)
from .recruitment_candidate import RecruitmentCandidateViewSet
from .recruitment_candidate_contact_log import RecruitmentCandidateContactLogViewSet
from .recruitment_channel import RecruitmentChannelViewSet
from .recruitment_dashboard import RecruitmentDashboardViewSet
from .recruitment_expense import RecruitmentExpenseViewSet
from .recruitment_reports import RecruitmentReportsViewSet
from .recruitment_request import RecruitmentRequestViewSet
from .recruitment_source import RecruitmentSourceViewSet
from .timesheet import EmployeeTimesheetViewSet, TimeSheetEntryViewSet
from .work_schedule import WorkScheduleViewSet

__all__ = [
    "AttendanceDeviceViewSet",
    "AttendanceExemptionViewSet",
    "AttendanceGeolocationViewSet",
    "AttendanceRecordViewSet",
    "AttendanceReportViewSet",
    "AttendanceWifiDeviceViewSet",
    "BankViewSet",
    "BankAccountViewSet",
    "BranchViewSet",
    "BranchContactInfoViewSet",
    "BlockViewSet",
    "DepartmentViewSet",
    "PositionViewSet",
    "EmployeeReportsViewSet",
    "EmployeeRoleViewSet",
    "EmployeeViewSet",
    "EmployeeCertificateViewSet",
    "EmployeeDependentViewSet",
    "EmployeeWorkHistoryViewSet",
    "ContractViewSet",
    "ContractAppendixViewSet",
    "ContractTypeViewSet",
    "HolidayViewSet",
    "CompensatoryWorkdayViewSet",
    "RecruitmentChannelViewSet",
    "RecruitmentSourceViewSet",
    "JobDescriptionViewSet",
    "RecruitmentRequestViewSet",
    "RecruitmentCandidateViewSet",
    "RecruitmentCandidateContactLogViewSet",
    "RecruitmentExpenseViewSet",
    "InterviewScheduleViewSet",
    "InterviewCandidateViewSet",
    "RecruitmentReportsViewSet",
    "RecruitmentDashboardViewSet",
    "EmployeeRelationshipViewSet",
    "EmployeeTimesheetViewSet",
    "TimeSheetEntryViewSet",
    "WorkScheduleViewSet",
    "ProposalTimesheetEntryComplaintViewSet",
    "ProposalPostMaternityBenefitsViewSet",
    "ProposalLateExemptionViewSet",
    "ProposalOvertimeWorkViewSet",
    "ProposalPaidLeaveViewSet",
    "ProposalUnpaidLeaveViewSet",
    "ProposalMaternityLeaveViewSet",
    "ProposalJobTransferViewSet",
    "ProposalAssetAllocationViewSet",
    "ProposalVerifierViewSet",
    "ProposalViewSet",
    "DecisionViewSet",
]
