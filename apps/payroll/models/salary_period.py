"""SalaryPeriod model for monthly salary periods."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel

from ..utils.salary_period import calculate_standard_working_days, generate_salary_period_code


@audit_logging_register
class SalaryPeriod(BaseModel):
    """Salary period model representing a monthly salary calculation period.
    
    This model stores information about a salary period including the month,
    configuration snapshot, and employee count. Only one period per month is allowed.
    
    Attributes:
        code: Unique code in format SP-YYYYMM
        month: First day of the salary month
        salary_config_snapshot: Snapshot of SalaryConfig used for this period
        status: Period status (ONGOING or COMPLETED)
        standard_working_days: Total working days in the month
        total_employees: Count of employees in this period
        completed_at: Completion timestamp
        completed_by: User who completed the period
    """
    
    class Status(models.TextChoices):
        """Status choices for salary period."""
        
        ONGOING = "ONGOING", _("Ongoing")
        COMPLETED = "COMPLETED", _("Completed")
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Unique code in format SP-YYYYMM"
    )
    
    month = models.DateField(
        unique=True,
        db_index=True,
        verbose_name="Month",
        help_text="First day of the salary month"
    )
    
    salary_config_snapshot = models.JSONField(
        verbose_name="Salary Config Snapshot",
        help_text="Snapshot of salary configuration for this period"
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONGOING,
        db_index=True,
        verbose_name="Status",
        help_text="Current status of the period"
    )
    
    standard_working_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Standard Working Days",
        help_text="Total working days in the month"
    )
    
    total_employees = models.PositiveIntegerField(
        default=0,
        verbose_name="Total Employees",
        help_text="Count of employees with payroll slips in this period"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completed At",
        help_text="Timestamp when period was completed"
    )
    
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_salary_periods",
        verbose_name="Completed By",
        help_text="User who completed the period"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_salary_periods",
        verbose_name="Created By"
    )
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_salary_periods",
        verbose_name="Updated By"
    )
    
    class Meta:
        verbose_name = "Salary Period"
        verbose_name_plural = "Salary Periods"
        db_table = "payroll_salary_period"
        ordering = ["-month"]
        indexes = [
            models.Index(fields=["month"], name="salary_period_month_idx"),
            models.Index(fields=["status"], name="salary_period_status_idx"),
            models.Index(fields=["-created_at"], name="salary_period_created_idx"),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.month.strftime('%Y-%m')}"
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate code and calculate working days."""
        # Generate code if not set
        if not self.code:
            self.code = generate_salary_period_code(self.month.year, self.month.month)
        
        # Calculate standard working days if not set
        if not self.pk and not self.standard_working_days:
            self.standard_working_days = calculate_standard_working_days(
                self.month.year, 
                self.month.month
            )
        
        super().save(*args, **kwargs)
    
    def can_complete(self) -> bool:
        """Check if period can be completed.
        
        A period can be completed if all payroll slips are in READY or DELIVERED status.
        
        Returns:
            bool: True if period can be completed
        """
        from .payroll_slip import PayrollSlip
        
        # Check if there are any slips not in READY or DELIVERED status
        blocking_slips = self.payroll_slips.exclude(
            status__in=[PayrollSlip.Status.READY, PayrollSlip.Status.DELIVERED]
        ).exists()
        
        return not blocking_slips
    
    def complete(self, user=None):
        """Mark period as completed and set all READY slips to DELIVERED.
        
        Args:
            user: User who is completing the period
            
        Raises:
            ValueError: If period cannot be completed
        """
        from django.utils import timezone
        from .payroll_slip import PayrollSlip
        
        if not self.can_complete():
            raise ValueError("Cannot complete period with pending or hold payroll slips")
        
        # Update all READY slips to DELIVERED
        self.payroll_slips.filter(status=PayrollSlip.Status.READY).update(
            status=PayrollSlip.Status.DELIVERED,
            delivered_at=timezone.now(),
            delivered_by=user
        )
        
        # Mark period as completed
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
