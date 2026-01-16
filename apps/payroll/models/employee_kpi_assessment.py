from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext as _

from apps.audit_logging.decorators import audit_logging_register
from apps.payroll.models.kpi_criterion import KPICriterion
from libs import ColorVariant
from libs.models import BaseModel, ColoredValueMixin, SafeTextField


@audit_logging_register
class EmployeeKPIAssessment(ColoredValueMixin, BaseModel):
    """Employee KPI assessment model for monthly KPI evaluations.

    This model stores KPI assessment for employees with snapshot of criteria
    to preserve history. The assessment captures self-scoring and manager scoring,
    calculates grades based on KPI config, and supports finalization with unit control.

    Attributes:
        period: Foreign key to KPIAssessmentPeriod
        employee: Foreign key to hrm.Employee (employee being assessed)
        manager: Foreign key to hrm.Employee (manager from department leader)
        status: Assessment status (new, waiting_manager, completed)
        total_possible_score: Sum of all component_total_score from items
        total_manager_score: Sum of all manager scores from items
        grade_manager: Final grade used for payroll (A/B/C/D)
        grade_manager_overridden: Manager's explicit grade override
        plan_tasks: Planned tasks for the assessment period
        extra_tasks: Extra tasks handled during the period
        proposal: Employee's proposals or suggestions
        manager_assessment: Manager's assessment comments and feedback
        manager_assessment_date: Date when manager completed assessment
        grade_hrm: HRM department's final grade assessment
        hrm_assessed: Whether HRM has assessed this
        hrm_assessment_date: Date when HRM completed assessment
        finalized: Whether assessment is locked (no further edits)
        department: Employee's department when KPI period was generated (snapshot)
        created_by: User who created this assessment
        updated_by: User who last updated this assessment
        note: Additional notes or comments
    """

    class StatusChoices(models.TextChoices):
        NEW = "new", _("New")
        WAITING_MANAGER = "waiting_manager", _("Waiting for manager assessment")
        COMPLETED = "completed", _("Completed")

    VARIANT_MAPPING = {
        "status": {
            StatusChoices.NEW: ColorVariant.GREY,
            StatusChoices.WAITING_MANAGER: ColorVariant.YELLOW,
            StatusChoices.COMPLETED: ColorVariant.GREEN,
        },
    }

    period = models.ForeignKey(
        "KPIAssessmentPeriod",
        on_delete=models.PROTECT,
        related_name="employee_assessments",
        verbose_name="Assessment period",
        help_text="KPI assessment period this assessment belongs to",
    )

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        related_name="kpi_assessments",
        verbose_name="Employee",
        help_text="Employee being assessed",
    )

    manager = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="managed_kpi_assessments",
        verbose_name="Manager",
        help_text="Manager responsible for assessing this employee (from department leader)",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.NEW,
        verbose_name="Status",
        help_text="Assessment status (system-managed)",
    )

    total_possible_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Total possible score",
        help_text="Sum of all component_total_score from items",
    )

    total_employee_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Total employee score",
        help_text="Sum of all employee scores from items",
    )

    total_manager_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Total manager score",
        help_text="Sum of all manager scores from items",
    )

    grade_manager = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="Manager grade",
        help_text="Final grade used for payroll (A/B/C/D)",
    )

    grade_manager_overridden = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="Manager grade override",
        help_text="Manager's explicit grade override",
    )

    plan_tasks = SafeTextField(
        blank=True,
        verbose_name="Plan tasks",
        help_text="Planned tasks for the assessment period",
    )

    extra_tasks = SafeTextField(
        blank=True,
        verbose_name="Extra tasks",
        help_text="Extra tasks handled during the period",
    )

    proposal = SafeTextField(
        blank=True,
        verbose_name="Proposal",
        help_text="Employee's proposals or suggestions",
    )

    manager_assessment = SafeTextField(
        blank=True,
        verbose_name="Manager assessment",
        help_text="Manager's assessment comments and feedback",
    )

    manager_assessment_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Manager assessment date",
        help_text="Date when manager completed assessment",
    )

    grade_hrm = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="HRM grade",
        help_text="HRM department's final grade assessment",
    )

    hrm_assessed = models.BooleanField(
        default=False,
        verbose_name="HRM assessed",
        help_text="Whether HRM has assessed this",
    )

    hrm_assessment_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="HRM assessment date",
        help_text="Date when HRM completed assessment",
    )

    finalized = models.BooleanField(
        default=False,
        verbose_name="Finalized",
        help_text="Whether assessment is locked (no further edits)",
    )

    department_snapshot = models.ForeignKey(
        "hrm.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_kpi_assessments",
        verbose_name="Department Snapshot",
        help_text="Employee's department when KPI period was generated (snapshot)",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kpi_assessments_created",
        verbose_name="Created by",
        help_text="User who created this assessment",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kpi_assessments_updated",
        verbose_name="Updated by",
        help_text="User who last updated this assessment",
    )

    note = models.TextField(
        blank=True,
        verbose_name="Note",
        help_text="Additional notes or comments",
    )

    is_for_leader = models.BooleanField(
        default=False,
        verbose_name="Is for leader",
        help_text="Whether this assessment is for a department leader (admin-only evaluation)",
    )

    class Meta:
        verbose_name = "Employee KPI Assessment"
        verbose_name_plural = "Employee KPI Assessments"
        db_table = "payroll_employee_kpi_assessment"
        ordering = ["-period__month", "-created_at"]
        unique_together = [["employee", "period"]]
        indexes = [
            models.Index(fields=["employee", "period"]),
            models.Index(fields=["period"]),
            models.Index(fields=["finalized"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_for_leader"]),
        ]

    @property
    def colored_status(self):
        """Get status with color variant"""
        return self.get_colored_value("status")

    def __str__(self):
        return f"{self.employee.code} - {self.period.month.strftime('%Y-%m')} - Grade: {self.grade_manager or 'N/A'}"


@audit_logging_register
class EmployeeKPIItem(BaseModel):
    """Employee KPI item model for storing criterion snapshots.

    This model stores snapshot of KPICriterion for each assessment item.
    Even if the original criterion is modified or deleted, this snapshot
    preserves the assessment history.

    Attributes:
        assessment: Foreign key to EmployeeKPIAssessment
        criterion_id: Original criterion (can be NULL if deleted)
        target: Snapshot of target group or role
        criterion: Snapshot of criterion name
        sub_criterion: Snapshot of sub-criterion
        evaluation_type: Snapshot of evaluation type
        description: Snapshot of criterion description
        component_total_score: Snapshot of maximum score
        group_number: Snapshot of group number for UI display
        order: Display order
        employee_score: Employee self-evaluation score
        manager_score: Manager evaluation score
        note: Additional notes
    """

    assessment = models.ForeignKey(
        EmployeeKPIAssessment,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Assessment",
        help_text="Parent assessment",
    )

    criterion_id = models.ForeignKey(
        "KPICriterion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criterion",
        help_text="Original criterion (can be NULL if deleted)",
    )

    target = models.CharField(
        max_length=200,
        choices=KPICriterion.TargetChoices.choices,
        verbose_name="Target",
        help_text="Snapshot of target group or role",
    )

    criterion = models.CharField(
        max_length=255,
        verbose_name="Criterion",
        help_text="Snapshot of criterion name",
    )

    sub_criterion = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Sub-criterion",
        help_text="Snapshot of sub-criterion",
    )

    evaluation_type = models.CharField(
        max_length=50,
        choices=KPICriterion.EvaluationTypeChoices.choices,
        verbose_name="Evaluation type",
        help_text="Snapshot of evaluation type",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Snapshot of criterion description",
    )

    component_total_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
        verbose_name="Component total score",
        help_text="Snapshot of maximum score",
    )

    group_number = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Group number",
        help_text="Snapshot of group number for UI display",
    )

    order = models.IntegerField(
        verbose_name="Order",
        help_text="Display order",
    )

    employee_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Employee score",
        help_text="Employee self-evaluation score",
    )

    manager_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Manager score",
        help_text="Manager evaluation score",
    )

    note = models.TextField(
        blank=True,
        verbose_name="Note",
        help_text="Additional notes",
    )

    class Meta:
        verbose_name = "Employee KPI Item"
        verbose_name_plural = "Employee KPI Items"
        db_table = "payroll_employee_kpi_item"
        ordering = ["-evaluation_type", "order"]
        indexes = [
            models.Index(fields=["assessment", "order"]),
        ]

    def clean(self):
        """Validate that scores don't exceed component_total_score."""
        from django.core.exceptions import ValidationError

        errors = {}

        if self.employee_score is not None and self.employee_score > self.component_total_score:
            errors["employee_score"] = "Employee score cannot exceed component total score"

        if self.manager_score is not None and self.manager_score > self.component_total_score:
            errors["manager_score"] = "Manager score cannot exceed component total score"

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.assessment.employee.username} - {self.criterion}"
