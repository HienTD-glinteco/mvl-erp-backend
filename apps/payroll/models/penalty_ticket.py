"""PenaltyTicket model for uniform violation records."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


@audit_logging_register
class PenaltyTicket(AutoCodeMixin, BaseModel):
    """Penalty ticket for uniform violations."""

    # Penalty Ticket Code Prefix
    CODE_PREFIX = "RVF"

    class Status(models.TextChoices):
        """Payment status for penalty board rows."""

        PAID = "PAID", _("Paid")
        UNPAID = "UNPAID", _("Unpaid")

    class ViolationType(models.TextChoices):
        """Violation types for penalty tickets."""

        UNDER_10_MINUTES = "UNDER_10_MINUTES", _("Violation under 10 minutes")
        OVER_10_MINUTES = "OVER_10_MINUTES", _("Violation over 10 minutes")
        ABSENT_WITHOUT_REASON = "ABSENT_WITHOUT_REASON", _("Absent without reason")
        UNIFORM_ERROR = "UNIFORM_ERROR", _("Uniform error")
        OTHER = "OTHER", _("Other violation")

    code = models.CharField(max_length=50, unique=True, verbose_name="Code")

    # Employee information (snapshot at time of ticket creation)
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="penalty_tickets",
        verbose_name="Employee",
    )
    employee_code = models.CharField(max_length=50, verbose_name="Employee Code")
    employee_name = models.CharField(max_length=200, verbose_name="Employee Name")

    # Violation details
    violation_count = models.PositiveIntegerField(default=1, verbose_name="Violation Count")
    violation_type = models.CharField(
        max_length=30,
        choices=ViolationType.choices,
        default=ViolationType.OTHER,
        verbose_name="Violation Type",
        db_index=True,
    )
    amount = models.PositiveIntegerField(verbose_name="Amount")
    month = models.DateField(verbose_name="Month", db_index=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.UNPAID,
        verbose_name="Status",
        db_index=True,
    )
    note = SafeTextField(max_length=500, blank=True, verbose_name="Note")

    # Optional attachments
    attachments = models.ManyToManyField(
        "files.FileModel",
        blank=True,
        related_name="penalty_tickets",
        verbose_name="Attachments",
    )

    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="penalty_tickets_created",
        verbose_name="Created By",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="penalty_tickets_updated",
        verbose_name="Updated By",
    )

    class Meta:
        verbose_name = "Penalty Ticket"
        verbose_name_plural = "Penalty Tickets"
        db_table = "payroll_penalty_ticket"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["month", "employee"], name="pen_ticket_month_emp_idx"),
            models.Index(fields=["status"], name="pen_ticket_status_idx"),
            models.Index(fields=["month"], name="payroll_pen_month_b4f6e7_idx"),
            models.Index(fields=["-created_at"], name="payroll_pen_created_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.employee_code}"
