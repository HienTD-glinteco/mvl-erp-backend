"""HRM utilities package."""

# Import existing utility functions from functions module
# Import new data scope utilities
from .data_scope import (
    AllowedUnits,
    collect_allowed_units,
    filter_by_leadership,
    filter_queryset_by_data_scope,
)
from .filters import DataScopeFilterBackend, LeadershipFilterBackend
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
    # Data scope utilities
    "AllowedUnits",
    "collect_allowed_units",
    "filter_by_leadership",
    "filter_queryset_by_data_scope",
    "DataScopeFilterBackend",
    "LeadershipFilterBackend",
    # Validators
    "validate_national_id",
    "validate_phone",
    # Work schedule cache
    "get_all_work_schedules",
    "get_work_schedule_by_weekday",
    "invalidate_work_schedule_cache",
]
