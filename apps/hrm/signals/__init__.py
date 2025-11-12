"""Signal handlers for HRM app.

This package contains signal handlers organized by functional area:
- employee: Employee-related signals (user creation, position changes)
- hr_reports: HR reports aggregation signals (EmployeeWorkHistory)
- recruitment_reports: Recruitment reports aggregation signals (RecruitmentCandidate)
"""

from django.contrib.auth import get_user_model

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeCertificate,
    EmployeeDependent,
    EmployeeRelationship,
    JobDescription,
    Position,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)

from ..constants import TEMP_CODE_PREFIX

User = get_user_model()

# Import signal handlers to register them (must be after User is defined)
# Import libs after models to avoid circular imports
from libs.code_generation import register_auto_code_signal  # noqa: E402

from .employee import *  # noqa: E402, F401, F403
from .hr_reports import *  # noqa: E402, F401, F403
from .recruitment_reports import *  # noqa: E402, F401, F403

# Register auto-code generation for models
register_auto_code_signal(
    Branch,
    Block,
    Department,
    Employee,
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
    temp_code_prefix=TEMP_CODE_PREFIX,
)
