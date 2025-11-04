from .attendance_device import AttendanceDeviceViewSet
from .attendance_record import AttendanceRecordViewSet
from .bank import BankViewSet
from .bank_account import BankAccountViewSet
from .contract_type import ContractTypeViewSet
from .employee import EmployeeViewSet
from .employee_certificate import EmployeeCertificateViewSet
from .employee_dependent import EmployeeDependentViewSet
from .employee_relationship import EmployeeRelationshipViewSet
from .employee_role import EmployeeRoleViewSet
from .interview_candidate import InterviewCandidateViewSet
from .interview_schedule import InterviewScheduleViewSet
from .job_description import JobDescriptionViewSet
from .organization import (
    BlockViewSet,
    BranchViewSet,
    DepartmentViewSet,
    OrganizationChartViewSet,
    PositionViewSet,
)
from .recruitment_candidate import RecruitmentCandidateViewSet
from .recruitment_candidate_contact_log import RecruitmentCandidateContactLogViewSet
from .recruitment_channel import RecruitmentChannelViewSet
from .recruitment_dashboard import RecruitmentDashboardViewSet
from .recruitment_expense import RecruitmentExpenseViewSet
from .recruitment_reports import RecruitmentReportsViewSet
from .recruitment_request import RecruitmentRequestViewSet
from .recruitment_source import RecruitmentSourceViewSet

__all__ = [
    "AttendanceDeviceViewSet",
    "AttendanceRecordViewSet",
    "BankViewSet",
    "BankAccountViewSet",
    "BranchViewSet",
    "BlockViewSet",
    "DepartmentViewSet",
    "PositionViewSet",
    "OrganizationChartViewSet",
    "EmployeeRoleViewSet",
    "EmployeeViewSet",
    "EmployeeCertificateViewSet",
    "EmployeeDependentViewSet",
    "ContractTypeViewSet",
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
]
