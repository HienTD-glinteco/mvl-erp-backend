"""Signal handlers for HRM app.

This module re-exports all signal handlers from the signals package
and maintains backward compatibility with existing imports.
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
from libs.code_generation import register_auto_code_signal

from .constants import TEMP_CODE_PREFIX

# Import all signal handlers from organized modules
from .signals import *  # noqa: F401, F403

User = get_user_model()

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
