"""Payroll module constants and enums."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentStatus(models.TextChoices):
    """Payment status for penalty board rows."""

    PAID = "PAID", _("Paid")
    UNPAID = "UNPAID", _("Unpaid")


class PayrollStatus(models.TextChoices):
    """Payroll calculation status for penalty board rows."""

    CALCULATED = "CALCULATED", _("Calculated")
    NOT_CALCULATED = "NOT_CALCULATED", _("Not Calculated")


# Penalty Ticket Code Prefix
PENALTY_TICKET_CODE_PREFIX = "RVF"


class ViolationType(models.TextChoices):
    """Violation types for penalty tickets."""

    UNDER_10_MINUTES = "UNDER_10_MINUTES", _("Violation under 10 minutes")
    OVER_10_MINUTES = "OVER_10_MINUTES", _("Violation over 10 minutes")
    ABSENT_WITHOUT_REASON = "ABSENT_WITHOUT_REASON", _("Absent without reason")
    UNIFORM_ERROR = "UNIFORM_ERROR", _("Uniform error")
    OTHER = "OTHER", _("Other violation")
