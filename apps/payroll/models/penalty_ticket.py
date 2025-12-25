"""PenaltyTicket model for uniform violation records."""

from django.conf import settings
from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from apps.payroll.constants import (
    PENALTY_TICKET_CODE_PREFIX,
    PaymentStatus,
    PayrollStatus,
    ViolationType,
)
from libs.models import AutoCodeMixin, BaseModel, SafeTextField


def generate_penalty_ticket_code(ticket: "PenaltyTicket", force_save: bool = True) -> None:
    """Generate and assign a code for a PenaltyTicket instance.

    Format: RVF-{YYYYMM}-{seq}
    Example: RVF-202511-0001

    Args:
        ticket: PenaltyTicket instance which MUST have a non-None id and month
        force_save: If True (default), save only the code field after assignment

    Raises:
        ValueError: If the ticket has no id set
    """
    if not hasattr(ticket, "id") or ticket.id is None:
        raise ValueError("PenaltyTicket must have an id to generate code")

    if not ticket.month:
        raise ValueError("PenaltyTicket must have a month to generate code")

    # Extract year and month from month field (stored as first day of month)
    month_str = ticket.month.strftime("%Y%m")

    # Get sequence number from ID
    seq = str(ticket.id).zfill(4)

    ticket.code = f"{PENALTY_TICKET_CODE_PREFIX}-{month_str}-{seq}"

    if force_save:
        ticket.save(update_fields=["code"])


@audit_logging_register
class PenaltyTicket(AutoCodeMixin, BaseModel):
    """Penalty ticket for uniform violations."""

    TEMP_CODE_PREFIX = "TEMP_RVF_"

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
    payment_status = models.CharField(
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        verbose_name="Payment Status",
        db_index=True,
    )
    payroll_status = models.CharField(
        max_length=20,
        choices=PayrollStatus.choices,
        default=PayrollStatus.NOT_CALCULATED,
        verbose_name="Payroll Status",
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
            models.Index(fields=["payment_status"], name="pen_ticket_pay_status_idx"),
            models.Index(fields=["payroll_status"], name="pen_ticket_payroll_idx"),
            models.Index(fields=["month"], name="payroll_pen_month_b4f6e7_idx"),
            models.Index(fields=["-created_at"], name="payroll_pen_created_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.employee_code}"
