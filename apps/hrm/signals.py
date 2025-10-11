"""Signal handlers for HRM app."""

from apps.hrm.models import Block, Branch, Department, RecruitmentChannel
from libs.code_generation import register_auto_code_signal

from .constants import TEMP_CODE_PREFIX

register_auto_code_signal(
    Branch,
    Block,
    Department,
    RecruitmentChannel,
    temp_code_prefix=TEMP_CODE_PREFIX,
)
