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


class DataScope(models.TextChoices):
    """Data scope levels for position-based access control"""

    ALL = "all", _("All data")
    BRANCH = "branch", _("Branch level")
    BLOCK = "block", _("Block level")
    DEPARTMENT = "department", _("Department level")
    SELF = "self", _("Self only")


class CertificateType(models.TextChoices):
    """Certificate types for employee qualifications"""

    FOREIGN_LANGUAGE = "foreign_language", _("Foreign language certificate")
    COMPUTER = "computer", _("Computer certificate")
    DIPLOMA = "diploma", _("Graduation diploma")
    OTHER = "other", _("Other")
    BROKER_TRAINING_COMPLETION = "broker_training_completion", _("Broker training completion")
    REAL_ESTATE_PRACTICE_LICENSE = "real_estate_practice_license", _("Real estate practice license")

    @classmethod
    def dict_choices(cls) -> dict:
        return dict(cls.choices)

    @classmethod
    def get_label(cls, raw_value: str) -> str:
        return cls.dict_choices().get(raw_value, raw_value)
