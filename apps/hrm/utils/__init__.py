"""HRM utilities package."""

# Import existing utility functions from functions module
# Import new data scope utilities
from .contract_code import generate_contract_code
from .data_scope import (
    AllowedUnits,
    collect_allowed_units,
    filter_by_leadership,
    filter_queryset_by_data_scope,
)
from .filters import DataScopeFilterBackend, LeadershipFilterBackend, RoleDataScopeFilterBackend
from .functions import (
    get_current_month_range,
    get_current_quarter_range,
    get_current_week_range,
    get_current_year_range,
    get_experience_category,
    get_last_6_months_range,
    get_week_key_from_date,
    get_week_label_from_date_range,
)
from .role_data_scope import (
    ROLE_UNITS_CACHE_TIMEOUT,
    RoleAllowedUnits,
    collect_role_allowed_units,
    filter_queryset_by_role_data_scope,
    get_role_units_cache_key,
    invalidate_role_units_cache,
    invalidate_role_units_cache_for_role,
)
from .validators import validate_national_id, validate_phone
from .work_schedule_cache import (
    get_all_work_schedules,
    get_work_schedule_by_weekday,
    invalidate_work_schedule_cache,
)

__all__ = [
    # Existing utilities
    "get_experience_category",
    "get_current_month_range",
    "get_current_week_range",
    "get_current_quarter_range",
    "get_current_year_range",
    "get_last_6_months_range",
    "get_week_key_from_date",
    "get_week_label_from_date_range",
    # Data scope utilities (legacy user-based)
    "AllowedUnits",
    "collect_allowed_units",
    "filter_by_leadership",
    "filter_queryset_by_data_scope",
    "DataScopeFilterBackend",
    "LeadershipFilterBackend",
    # Role data scope utilities (new role-based)
    "RoleAllowedUnits",
    "collect_role_allowed_units",
    "filter_queryset_by_role_data_scope",
    "invalidate_role_units_cache",
    "invalidate_role_units_cache_for_role",
    "get_role_units_cache_key",
    "ROLE_UNITS_CACHE_TIMEOUT",
    "RoleDataScopeFilterBackend",
    # Validators
    "validate_national_id",
    "validate_phone",
    # Work schedule cache
    "get_all_work_schedules",
    "get_work_schedule_by_weekday",
    "invalidate_work_schedule_cache",
    # Contract code generation
    "generate_contract_code",
]
