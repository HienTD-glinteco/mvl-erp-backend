"""Import handlers for HRM module.

This package contains import handlers for various HRM entities.
Each handler is in its own module for better organization.
"""

from .contract import import_handler as contract_import_handler
from .contract_appendix import (
    import_handler as contract_appendix_import_handler,
    pre_import_initialize as contract_appendix_pre_import_initialize,
)
from .employee import (
    import_handler as employee_import_handler,
    pre_import_initialize as employee_pre_import_initialize,
)
from .recruitment_candidate import import_handler as recruitment_candidate_import_handler

__all__ = [
    "contract_import_handler",
    "contract_appendix_import_handler",
    "contract_appendix_pre_import_initialize",
    "employee_import_handler",
    "employee_pre_import_initialize",
    "recruitment_candidate_import_handler",
]
