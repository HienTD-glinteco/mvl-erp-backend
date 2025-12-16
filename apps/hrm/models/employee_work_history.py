from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel, SafeTextField

from .employee import Employee


@audit_logging_register
class EmployeeWorkHistory(BaseModel):
    """Employee work history model for tracking employee work events.

    This model manages work history records for employees including transfers,
    promotions, role changes, contract changes, and other significant work events.
    Key organizational fields (branch, block, department, position) are automatically
    populated from the associated employee record.

    Attributes:
        date: Date of the work history event
        name: Type of the work history event (Change Position, Change Status, Transfer, Change Contract)
        detail: Detailed description of the event
        employee: Reference to the employee
        branch: Employee's branch (auto-populated from employee)
        block: Employee's block (auto-populated from employee)
        department: Employee's department (auto-populated from employee)
        position: Employee's position (auto-populated from employee)
        note: Additional notes about the work history event (SafeTextField, shared for all event cases)
        status: New employee status after the event (for state-change events)
        from_date: Start date of the event period (e.g., leave start date)
        to_date: End date of the event period (e.g., leave end date)
        retain_seniority: For return to work events, whether seniority is retained or reset
        resignation_reason: Reason for resignation (if applicable)
        contract: New contract type for contract-change events
        previous_data: JSON data storing previous values (status, branch_id, block_id,
                      department_id, contract_type, contract_id)
    """

    class EventType(models.TextChoices):
        CHANGE_POSITION = "Change Position", _("Change Position")
        CHANGE_STATUS = "Change Status", _("Change Status")
        TRANSFER = "Transfer", _("Transfer")
        CHANGE_EMPLOYEE_TYPE = "Change Employee Type", _("Change Employee Type")
        CHANGE_CONTRACT = "Change Contract", _("Change Contract")
        RETURN_TO_WORK = "Return to Work", _("Return to Work")

    date = models.DateField(
        verbose_name="Date",
        help_text="Date of the work history event",
    )
    name = models.CharField(
        max_length=50,
        choices=EventType.choices,
        verbose_name="Event type",
        help_text="Type of the work history event",
    )
    detail = models.TextField(
        blank=True,
        verbose_name="Details",
        help_text="Detailed description of the work history event",
    )
    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        related_name="work_histories",
        verbose_name="Employee",
        help_text="Employee associated with this work history record",
    )
    branch = models.ForeignKey(
        "hrm.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_work_histories",
        verbose_name="Branch",
        help_text="Branch (auto-populated from employee)",
    )
    block = models.ForeignKey(
        "hrm.Block",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_work_histories",
        verbose_name="Block",
        help_text="Block (auto-populated from employee)",
    )
    department = models.ForeignKey(
        "hrm.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_work_histories",
        verbose_name="Department",
        help_text="Department (auto-populated from employee)",
    )
    position = models.ForeignKey(
        "hrm.Position",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_work_histories",
        verbose_name="Position",
        help_text="Position (auto-populated from employee)",
    )
    note = SafeTextField(
        blank=True,
        verbose_name="Note",
        help_text="Additional notes about the work history event",
    )
    status = models.CharField(
        max_length=50,
        choices=Employee.Status.choices,
        null=True,
        blank=True,
        verbose_name="Status",
        help_text="New employee status after the event (for state-change events)",
    )
    from_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="From date",
        help_text="Start date of the event period",
    )
    to_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="To date",
        help_text="End date of the event period",
    )
    retain_seniority = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Retain seniority",
        help_text="For return to work events, whether seniority is retained or reset",
    )
    resignation_reason = models.CharField(
        max_length=50,
        choices=Employee.ResignationReason.choices,
        null=True,
        blank=True,
        verbose_name="Resignation reason",
        help_text="Reason for resignation (if applicable)",
    )
    contract = models.ForeignKey(
        "hrm.Contract",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_work_histories",
        verbose_name="Contract",
        help_text="New contract for contract-change event",
    )
    previous_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Previous data",
        help_text="JSON data storing previous values (status, branch_id, block_id, department_id, contract_type, contract_id)",
    )

    class Meta:
        verbose_name = _("Employee work history")
        verbose_name_plural = _("Employee work histories")
        db_table = "hrm_employee_work_history"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "date"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["block"]),
            models.Index(fields=["department"]),
            models.Index(fields=["position"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.employee} ({self.date})"

    def save(self, *args, **kwargs):
        """Override save to automatically populate organizational fields from employee.

        The branch, block, department, and position fields are automatically
        set from the related employee record whenever the work history is
        created or updated.
        """
        if self.employee:
            self.branch = self.employee.branch
            self.block = self.employee.block
            self.department = self.employee.department
            self.position = self.employee.position

        super().save(*args, **kwargs)
