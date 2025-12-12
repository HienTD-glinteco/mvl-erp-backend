"""Signal handlers for HRM app.

This package contains signal handlers organized by functional area:
- employee: Employee-related signals (user creation, position changes)
- hr_reports: HR reports aggregation signals (EmployeeWorkHistory)
- recruitment_reports: Recruitment reports aggregation signals (RecruitmentCandidate)
"""

from django.contrib.auth import get_user_model

from apps.hrm.models import (
    AttendanceDevice,
    AttendanceGeolocation,
    AttendanceRecord,
    AttendanceWifiDevice,
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    JobDescription,
    Position,
    Proposal,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)
from apps.hrm.models.employee import generate_code as employee_generate_code
from apps.hrm.utils import generate_contract_code

from ..constants import TEMP_CODE_PREFIX

User = get_user_model()

# Import signal handlers to register them (must be after User is defined)
# Import libs after models to avoid circular imports
from libs.code_generation import register_auto_code_signal  # noqa: E402

from .attendance import *  # noqa: E402, F401, F403
from .attendance_report import *  # noqa: E402, F401, F403
from .employee import *  # noqa: E402, F401, F403
from .hr_reports import *  # noqa: E402, F401, F403
from .recruitment_reports import *  # noqa: E402, F401, F403
from .work_schedule import *  # noqa: E402, F401, F403

# Register auto-code generation for models (excluding Employee)
register_auto_code_signal(
    AttendanceGeolocation,
    AttendanceDevice,
    AttendanceRecord,
    AttendanceWifiDevice,
    Branch,
    Block,
    ContractType,
    Department,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    Position,
    RecruitmentChannel,
    RecruitmentSource,
    JobDescription,
    RecruitmentRequest,
    RecruitmentCandidate,
    RecruitmentExpense,
    Proposal,
    temp_code_prefix=TEMP_CODE_PREFIX,
)

# Register auto-code generation for Employee with custom generate_code
register_auto_code_signal(
    Employee,
    temp_code_prefix=TEMP_CODE_PREFIX,
    custom_generate_code=employee_generate_code,
)

# Register auto-code generation for Contract with custom generate_code
register_auto_code_signal(
    Contract,
    temp_code_prefix=TEMP_CODE_PREFIX,
    custom_generate_code=generate_contract_code,
)
