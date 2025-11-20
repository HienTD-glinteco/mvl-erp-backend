from celery.schedules import crontab

from .base import config
from .internationalization import TIME_ZONE

# Celery Configuration Options
# Celery
# -------------------------------------------------------------------------------
# https://docs.celeryproject.org/en/stable/userguide/configuration.html
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "pickle"
CELERY_RESULT_SERIALIZER = "pickle"
CELERY_RESULT_EXTENDED = True
CELERY_ACCEPT_CONTENT = ["pickle"]
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 60 * 6  # default to 6 hours.
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = config("CELERY_TASK_EAGER_PROPAGATES", default=False, cast=bool)

CELERY_BEAT_SCHEDULE: dict[str, dict] = {
    # Sync attendance logs from all devices once a day at midnight
    "sync_all_attendance_devices": {
        "task": "apps.hrm.tasks.attendances.sync_all_attendance_devices",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
    # Aggregate HR reports batch at midnight
    "aggregate_hr_reports_batch": {
        "task": "apps.hrm.tasks.reports_hr.aggregate_hr_reports_batch",
        "schedule": crontab(hour=0, minute=5),  # Daily at 00:05 (after attendance sync)
    },
    # Aggregate recruitment reports batch at midnight
    "aggregate_recruitment_reports_batch": {
        "task": "apps.hrm.tasks.reports_recruitment.aggregate_recruitment_reports_batch",
        "schedule": crontab(hour=0, minute=10),  # Daily at 00:10 (after HR reports)
    },
    # Update certificate statuses based on expiry dates
    "update_certificate_statuses": {
        "task": "apps.hrm.tasks.certificates.update_certificate_statuses",
        "schedule": crontab(hour=1, minute=0),  # Daily at 01:00
        # Prepare timesheet entries and monthly model at the beginning of month
    },
    "prepare_monthly_timesheets": {
        "task": "apps.hrm.tasks.timesheets.prepare_monthly_timesheets",
        "schedule": crontab(day_of_month="1", hour=0, minute=1),
    },
    # Update EmployeeMonthlyTimesheet rows marked with need_refresh every 60 seconds
    "update_monthly_timesheet_async": {
        "task": "apps.hrm.tasks.timesheets.update_monthly_timesheet_async",
        "schedule": 60.0,
    },
}
