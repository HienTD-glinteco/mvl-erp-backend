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


class RelationType(models.TextChoices):
    """Employee relationship types for next-of-kin management"""

    CHILD = "CHILD", _("Child")
    SPOUSE = "SPOUSE", _("Spouse")
    PARTNER = "PARTNER", _("Partner")
    PARENT = "PARENT", _("Parent")
    SIBLING = "SIBLING", _("Sibling")
    GRANDPARENT = "GRANDPARENT", _("Grandparent")
    OTHER = "OTHER", _("Other")


# API Documentation Constants for Relationship endpoints
API_RELATION_LIST_SUMMARY = "List employee relationships"
API_RELATION_LIST_DESCRIPTION = (
    "Retrieve a paginated list of employee relationships with support for filtering and search"
)
API_RELATION_CREATE_SUMMARY = "Create employee relationship"
API_RELATION_CREATE_DESCRIPTION = "Create a new employee relationship record with optional file attachment"
API_RELATION_RETRIEVE_SUMMARY = "Retrieve employee relationship"
API_RELATION_RETRIEVE_DESCRIPTION = "Get detailed information about a specific employee relationship"
API_RELATION_UPDATE_SUMMARY = "Update employee relationship"
API_RELATION_UPDATE_DESCRIPTION = "Update an existing employee relationship record"
API_RELATION_DELETE_SUMMARY = "Delete employee relationship"
API_RELATION_DELETE_DESCRIPTION = "Soft delete an employee relationship by marking it as inactive"

# Relationship field help text constants
HELP_TEXT_EMPLOYEE = "Employee associated with this relationship"
HELP_TEXT_RELATIVE_NAME = "Full name of the relative"
HELP_TEXT_RELATION_TYPE = "Type of relationship to the employee"
HELP_TEXT_DATE_OF_BIRTH = "Date of birth of the relative"
HELP_TEXT_NATIONAL_ID = "National ID (CMND/CCCD) - 9 or 12 digits"
HELP_TEXT_ADDRESS = "Residential address of the relative"
HELP_TEXT_PHONE = "Contact phone number"
HELP_TEXT_ATTACHMENT = "Supporting document or file attachment"
HELP_TEXT_NOTE = "Additional notes or information"
HELP_TEXT_IS_ACTIVE = "Whether this relationship record is active"

# Validation constants
MAX_ATTACHMENT_SIZE_MB = 10
NATIONAL_ID_LENGTH_9 = 9
NATIONAL_ID_LENGTH_12 = 12
PHONE_INTL_LENGTH = 12  # +84 + 9 digits
PHONE_LOCAL_LENGTH = 10  # 0 + 9 digits
