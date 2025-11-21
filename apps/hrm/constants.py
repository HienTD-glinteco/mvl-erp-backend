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


class ExtendedReportPeriodType(models.TextChoices):
    WEEK = "week", _("Week")
    MONTH = "month", _("Month")
    QUARTER = "quarter", _("Quarter")
    YEAR = "year", _("Year")


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
    WIFE = "WIFE", _("Wife")
    HUSBAND = "HUSBAND", _("Husband")
    FATHER = "FATHER", _("Father")
    MOTHER = "MOTHER", _("Mother")
    BROTHER = "BROTHER", _("Brother")
    SISTER = "SISTER", _("Sister")
    SIBLING = "SIBLING", _("Sibling")
    GRANDFATHER = "GRANDFATHER", _("Grandfather")
    GRANDMOTHER = "GRANDMOTHER", _("Grandmother")
    OTHER = "OTHER", _("Other")


# Validation constants
MAX_ATTACHMENT_SIZE_MB = 10
NATIONAL_ID_LENGTH_9 = 9
NATIONAL_ID_LENGTH_12 = 12
PHONE_INTL_LENGTH = 12  # +84 + 9 digits
PHONE_LOCAL_LENGTH = 10  # 0 + 9 digits


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


class EmployeeSalaryType(models.TextChoices):
    """Salary-type choices used for filtering and display."""

    SALARIED = "salaried", _("Salaried employee")
    UNSALARIED = "unsalaried", _("Unpaid / not contracted")

    @classmethod
    def dict_choices(cls) -> dict:
        return dict(cls.choices)

    @classmethod
    def get_label(cls, raw_value: str) -> str:
        return cls.dict_choices().get(raw_value, raw_value)


class ActionType:
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"


class TimesheetStatus(models.TextChoices):
    ON_TIME = "on_time", _("On time")
    NOT_ON_TIME = "not_on_time", _("Not on time")
    ABSENT = "absent", _("Absent")


class TimesheetReason(models.TextChoices):
    PAID_LEAVE = "paid_leave", _("Paid leave")
    UNPAID_LEAVE = "unpaid_leave", _("Unpaid leave")
    MATERNITY_LEAVE = "maternity_leave", _("Maternity leave")
    PUBLIC_HOLIDAY = "public_holiday", _("Public holiday")
    UNEXCUSED_ABSENCE = "unexcused_absence", _("Unexcused Absence")

    @classmethod
    def dict_choices(cls) -> dict:
        return dict(cls.choices)

    @classmethod
    def get_label(cls, raw_value: str) -> str:
        return cls.dict_choices().get(raw_value, raw_value)


class ProposalType(models.TextChoices):
    """Proposal type choices for employee proposals."""

    POST_MATERNITY_BENEFITS = "post_maternity_benefits", _("Post-maternity benefits")
    LATE_EXEMPTION = "late_exemption", _("Late exemption")
    OVERTIME_WORK = "overtime_work", _("Overtime work")
    PAID_LEAVE = "paid_leave", _("Paid leave")
    UNPAID_LEAVE = "unpaid_leave", _("Unpaid leave")
    MATERNITY_LEAVE = "maternity_leave", _("Maternity leave")
    ATTENDANCE_EXEMPTION = "attendance_exemption", _("Attendance exemption")
    TIMESHEET_ENTRY_COMPLAINT = "timesheet_entry_complaint", _("Timesheet entry complaint")


class ProposalStatus(models.TextChoices):
    """Proposal status choices."""

    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")
