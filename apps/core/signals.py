"""Signal handlers for Core app."""

from apps.core.models import Role
from libs.code_generation import register_auto_code_signal

TEMP_CODE_PREFIX = "TEMP_"

register_auto_code_signal(
    Role,
    temp_code_prefix=TEMP_CODE_PREFIX,
)
