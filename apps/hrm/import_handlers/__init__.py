"""Import handlers for HRM module.

This package contains import handlers for various HRM entities.
Each handler is in its own module for better organization.
"""

from .contract_appendix import import_handler as contract_appendix_import_handler
from .contract_creation import import_handler as contract_creation_import_handler
from .contract_update import import_handler as contract_update_import_handler
from .employee import (
    import_handler as employee_import_handler,
    pre_import_initialize as employee_pre_import_initialize,
)
from .recruitment_candidate import import_handler as recruitment_candidate_import_handler

__all__ = [
    "contract_appendix_import_handler",
    "contract_creation_import_handler",
    "contract_update_import_handler",
    "employee_import_handler",
    "employee_pre_import_initialize",
    "recruitment_candidate_import_handler",
]
