# HRM Module Constants
from django.db import models
from django.utils.translation import gettext_lazy as _

# Employee Status
EMPLOYEE_STATUS_ACTIVE = "active"
EMPLOYEE_STATUS_INACTIVE = "inactive"
EMPLOYEE_STATUS_ON_LEAVE = "on_leave"

# Working Hours
STANDARD_WORKING_HOURS_PER_DAY = 8
STANDARD_WORKING_DAYS_PER_WEEK = 5

# Leave Types
ANNUAL_LEAVE_DAYS_PER_YEAR = 12
SICK_LEAVE_DAYS_PER_YEAR = 30

# Code Prefixes
TEMP_CODE_PREFIX = "TEMP_"


class RecruitmentSourceType(models.TextChoices):
    REFERRAL_SOURCE = "referral_source", _("Referral Source")
    MARKETING_CHANNEL = "marketing_channel", _("Marketing Channel")
    JOB_WEBSITE_CHANNEL = "job_website_channel", _("Job Website Channel")
    RECRUITMENT_DEPARTMENT_SOURCE = "recruitment_department_source", _("Recruitment Department Source")
    RETURNING_EMPLOYEE = "returning_employee", _("Returning Employee")

    @classmethod
    def dict_choices(cls) -> dict:
        return dict(cls.choices)

    @classmethod
    def get_label(cls, raw_value: str) -> str:
        return cls.dict_choices().get(raw_value, raw_value)


class ReportPeriodType(models.TextChoices):
    WEEK = "week", _("Week")
    MONTH = "month", _("Month")
