from django.conf import settings
from django.db import models

from apps.audit_logging.decorators import audit_logging_register
from libs.models import BaseModel


@audit_logging_register
class DepartmentKPIAssessment(BaseModel):
    """Department KPI assessment model for department-level grade assignment.

    This model stores grade assignments for departments. When a department
    grade is set, it can auto-assign grades to employees in that department based
    on quota and ranking.

    Attributes:
        period: Foreign key to KPIAssessmentPeriod
        department: Foreign key to Department
        grade: Department's grade (A/B/C/D)
        default_grade: Default grade when auto-created (default 'C')
        assigned_by: User who assigned the grade
        assigned_at: Timestamp when grade was assigned
        finalized: Whether assessment is locked
        created_by: User who created this assessment
        updated_by: User who last updated this assessment
        note: Additional notes
    """

    period = models.ForeignKey(
        "KPIAssessmentPeriod",
        on_delete=models.PROTECT,
        related_name="department_assessments",
        verbose_name="Assessment period",
        help_text="KPI assessment period this assessment belongs to",
    )

    department = models.ForeignKey(
        "hrm.Department",
        on_delete=models.PROTECT,
        related_name="kpi_assessments",
        verbose_name="Department",
        help_text="Department being assessed",
    )

    grade = models.CharField(
        max_length=10,
        verbose_name="Grade",
        help_text="Department's grade (A/B/C/D)",
    )

    default_grade = models.CharField(
        max_length=10,
        default="C",
        verbose_name="Default grade",
        help_text="Default grade when auto-created",
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_kpi_assessments_assigned",
        verbose_name="Assigned by",
        help_text="User who assigned the grade",
    )

    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Assigned at",
        help_text="Timestamp when grade was assigned",
    )

    finalized = models.BooleanField(
        default=False,
        verbose_name="Finalized",
        help_text="Whether assessment is locked",
    )

    is_valid_unit_control = models.BooleanField(
        default=True, verbose_name="Is valid unit control", help_text="This department valid unit control or not"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_kpi_assessments_created",
        verbose_name="Created by",
        help_text="User who created this assessment",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_kpi_assessments_updated",
        verbose_name="Updated by",
        help_text="User who last updated this assessment",
    )

    note = models.TextField(
        blank=True,
        verbose_name="Note",
        help_text="Additional notes",
    )

    class Meta:
        verbose_name = "Department KPI Assessment"
        verbose_name_plural = "Department KPI Assessments"
        db_table = "payroll_department_kpi_assessment"
        ordering = ["-period__month", "-created_at"]
        unique_together = [["department", "period"]]
        indexes = [
            models.Index(fields=["department", "period"]),
            models.Index(fields=["period"]),
            models.Index(fields=["finalized"]),
        ]

    def __str__(self):
        return f"{self.department.name} - {self.period.month.strftime('%Y-%m')} - Grade: {self.grade}"
