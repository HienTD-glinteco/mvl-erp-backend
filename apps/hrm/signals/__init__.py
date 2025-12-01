"""Signal handlers for HRM app.

This package contains signal handlers organized by functional area:
- employee: Employee-related signals (user creation, position changes)
- hr_reports: HR reports aggregation signals (EmployeeWorkHistory)
- recruitment_reports: Recruitment reports aggregation signals (RecruitmentCandidate)
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

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
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)
from apps.hrm.utils.contract_code import generate_contract_code

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

# Register auto-code generation for models
register_auto_code_signal(
    AttendanceGeolocation,
    AttendanceDevice,
    AttendanceRecord,
    AttendanceWifiDevice,
    Branch,
    Block,
    ContractType,
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


# Custom signal handler for Contract that saves both code and contract_number
def contract_auto_code_handler(sender, instance, created, **kwargs):
    """Auto-generate code and contract_number for Contract instances.

    This signal handler generates unique codes for newly created contracts/appendices:
    - For contracts: code=HDxxxxx, contract_number=xx/yyyy/SYMBOL - MVL
    - For appendices: code=PLHDxxxxx, contract_number=xx/yyyy/PLHD-MVL

    Args:
        sender: The model class
        instance: The Contract instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal
    """
    if created and hasattr(instance, "code") and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_contract_code(instance)
        # Save both code and contract_number fields
        instance.save(update_fields=["code", "contract_number"])


# Register the custom handler for Contract
post_save.connect(contract_auto_code_handler, sender=Contract, weak=False)
