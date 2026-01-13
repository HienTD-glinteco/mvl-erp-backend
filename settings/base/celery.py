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

# Use database-backed scheduler for managing periodic tasks via Django Admin
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE: dict[str, dict] = {
    # Reactivate employees from maternity leave when leave period ends
    "reactive_maternity_leave_employees": {
        "task": "apps.hrm.tasks.employee.reactive_maternity_leave_employees_task",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
    # Sync attendance logs from all devices once a day at midnight
    "backup_database": {
        "task": "apps.core.tasks.dbbackup.run_dbbackup",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
    # Sync attendance logs from all devices once a day at midnight
    "sync_all_attendance_devices": {
        "task": "apps.hrm.tasks.attendances.sync_all_attendance_devices",
        "schedule": crontab(hour=0, minute=2),  # Daily at midnight
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
    },
    # Recalculate Daily Attendance Reports
    "recalculate_daily_attendance_reports": {
        "task": "hrm.tasks.attendance_report.recalculate_daily_attendance_reports",
        "schedule": crontab(hour=1, minute=10),
    },
    # Prepare timesheet entries and monthly model at the beginning of month
    "prepare_monthly_timesheets": {
        "task": "apps.hrm.tasks.timesheets.prepare_monthly_timesheets",
        "schedule": crontab(day_of_month="1", hour=0, minute=1),
    },
    # Generate salary period for the current month on first day of month
    "auto_generate_salary_period": {
        "task": "apps.payroll.tasks.auto_generate_salary_period",
        "schedule": crontab(day_of_month="1", hour=0, minute=0),  # First day at 00:00
    },
    # Generate KPI assessment period for the current month on first day of month
    "generate_kpi_assessment_period": {
        "task": "apps.payroll.tasks.generate_kpi_assessment_period_task",
        "schedule": crontab(day_of_month="1", hour=0, minute=1),  # First day at 00:01 (after salary period)
    },
    # Check KPI assessment deadlines and finalize periods daily
    "check_kpi_assessment_deadline_and_finalize": {
        "task": "apps.payroll.tasks.check_kpi_assessment_deadline_and_finalize_task",
        "schedule": crontab(hour=0, minute=30),  # Daily at 00:30
    },
    # Update EmployeeMonthlyTimesheet rows marked with need_refresh every short period
    "update_monthly_timesheet_async": {
        "task": "apps.hrm.tasks.timesheets.update_monthly_timesheet_async",
        "schedule": 30.0,
    },
    # Finalize daily timesheets at 17:30
    "finalize_daily_timesheets": {
        "task": "apps.hrm.tasks.timesheets.finalize_daily_timesheets",
        "schedule": crontab(hour=17, minute=30),
    },
    # Check contract status daily
    "check_contract_status": {
        "task": "apps.hrm.tasks.contracts.check_contract_status",
        "schedule": crontab(hour=0, minute=0),  # Daily at 00:00
    },
    # Update employee status from approved leave proposals daily
    "update_employee_status_from_leave_proposals": {
        "task": "apps.hrm.tasks.proposal.update_employee_status_from_approved_leave_proposals",
        "schedule": crontab(hour=0, minute=0),  # Daily at 00:00
    },
}
