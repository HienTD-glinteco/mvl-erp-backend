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
    ContractAppendix,
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
from apps.hrm.utils.appendix_code import generate_appendix_codes
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

# Register auto-code generation for Contract with custom code generator
register_auto_code_signal(
    Contract,
    temp_code_prefix=TEMP_CODE_PREFIX,
    custom_generate_code=generate_contract_code,
)


# Custom signal handler for ContractAppendix that saves both code and appendix_code
def contract_appendix_auto_code_handler(sender, instance, created, **kwargs):
    """Auto-generate code and appendix_code for ContractAppendix instances.

    This signal handler generates unique codes for newly created appendices:
    - code: format `xx/yyyy/PLHD-MVL`
    - appendix_code: format `PLHDxxxxx`

    Args:
        sender: The model class
        instance: The ContractAppendix instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal
    """
    if created and hasattr(instance, "code") and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_appendix_codes(instance)
        # Save both code and appendix_code fields
        instance.save(update_fields=["code", "appendix_code"])


# Register the custom handler for ContractAppendix
post_save.connect(contract_appendix_auto_code_handler, sender=ContractAppendix, weak=False)
