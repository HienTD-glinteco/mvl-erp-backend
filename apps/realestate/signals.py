"""Signal handlers for Real Estate app."""

from apps.hrm.constants import TEMP_CODE_PREFIX
from apps.realestate.models import Project
from libs.code_generation import register_auto_code_signal

# Register auto-code generation for models
register_auto_code_signal(
    Project,
    temp_code_prefix=TEMP_CODE_PREFIX,
)
