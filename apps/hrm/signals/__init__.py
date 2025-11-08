"""Signal handlers for HRM app.

This package contains signal handlers organized by functional area:
- employee: Employee-related signals (user creation, position changes)
- hr_reports: HR reports aggregation signals (EmployeeWorkHistory)
- recruitment_reports: Recruitment reports aggregation signals (RecruitmentCandidate)
"""

# Import all signal handlers to ensure they're registered
from .employee import *  # noqa: F401, F403
from .hr_reports import *  # noqa: F401, F403
from .recruitment_reports import *  # noqa: F401, F403
