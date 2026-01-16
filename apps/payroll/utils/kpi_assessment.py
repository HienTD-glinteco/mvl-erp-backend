"""Utilities for KPI assessment snapshot and operations.

This module provides functions for:
- Creating assessment snapshots from KPICriterion
- Resyncing assessments
- Recalculating scores and grades
- Generating assessments for periods
"""

import logging
from decimal import Decimal
from typing import List

from django.db import transaction

from apps.payroll.models import (
    EmployeeKPIAssessment,
    EmployeeKPIItem,
    KPICriterion,
)
from apps.payroll.utils.kpi_calculation import calculate_grade_from_percent

logger = logging.getLogger(__name__)


def create_assessment_items_from_criteria(
    assessment: EmployeeKPIAssessment,
    criteria: List[KPICriterion],
) -> List[EmployeeKPIItem]:
    """Create EmployeeKPIItem instances from KPICriterion snapshots.

    Args:
        assessment: The parent EmployeeKPIAssessment
        criteria: List of KPICriterion to snapshot

    Returns:
        List of created EmployeeKPIItem instances with IDs populated
    """
    items = []
    for criterion in criteria:
        item = EmployeeKPIItem(
            assessment=assessment,
            criterion_id=criterion,
            target=criterion.target,
            criterion=criterion.criterion,
            sub_criterion=criterion.sub_criterion,
            evaluation_type=criterion.evaluation_type,
            description=criterion.description,
            component_total_score=criterion.component_total_score,
            group_number=criterion.group_number,
            order=criterion.order,
        )
        items.append(item)

    EmployeeKPIItem.objects.bulk_create(items)

    # Refetch items to get IDs (bulk_create doesn't return IDs on SQLite)
    return list(EmployeeKPIItem.objects.filter(assessment=assessment).order_by("order"))


def recalculate_assessment_scores(assessment: EmployeeKPIAssessment) -> EmployeeKPIAssessment:
    """Recalculate all scores and grades for an assessment.

    This function:
    1. Sums up employee and manager scores
    2. Calculates totals
    3. Determines grade based on KPIConfig

    Args:
        assessment: The EmployeeKPIAssessment to recalculate

    Returns:
        Updated assessment instance
    """
    items = assessment.items.all()

    # Calculate totals by summing scores
    assessment.total_possible_score = sum(item.component_total_score for item in items)

    total_employee = (
        sum(item.employee_score for item in items if item.employee_score is not None)
        if any(item.employee_score is not None for item in items)
        else None
    )

    total_manager = (
        sum(item.manager_score for item in items if item.manager_score is not None)
        if any(item.manager_score is not None for item in items)
        else None
    )

    assessment.total_employee_score = total_employee
    assessment.total_manager_score = total_manager

    # Calculate grade if we have manager score
    if total_manager is not None:
        config = assessment.period.kpi_config_snapshot

        grade, possible_codes = calculate_grade_from_percent(
            Decimal(str(total_manager)),
            config.get("grade_thresholds", []),
            config.get("ambiguous_assignment", "manual"),
        )

        # If grade_manager_overridden is set, use that instead
        if assessment.grade_manager_overridden:
            assessment.grade_manager = assessment.grade_manager_overridden
        else:
            assessment.grade_manager = grade

    # Use update_fields to skip deadline validation on recalculation
    assessment.save(
        update_fields=[
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
        ]
    )
    return assessment


@transaction.atomic
def resync_assessment_add_missing(assessment: EmployeeKPIAssessment) -> int:
    """Add missing criteria to assessment that were created after assessment generation.

    This only adds NEW criteria that don't exist in the assessment yet.
    Existing items are not modified.

    Args:
        assessment: The EmployeeKPIAssessment to resync

    Returns:
        Number of items added
    """
    if assessment.finalized:
        raise ValueError("Cannot resync finalized assessment")

    # Determine target based on employee's department function
    from apps.hrm.models import Department

    if assessment.employee.department.function == Department.DepartmentFunction.BUSINESS:
        target = "sales"
    else:
        target = "backoffice"

    # Get current criteria for the target
    current_criteria = KPICriterion.objects.filter(
        target=target,
        active=True,
    ).order_by("evaluation_type", "order")

    # Get existing criterion IDs in assessment
    existing_criterion_ids = set(
        assessment.items.filter(criterion_id__isnull=False).values_list("criterion_id", flat=True)
    )

    # Find new criteria
    new_criteria = [c for c in current_criteria if c.id not in existing_criterion_ids]

    if not new_criteria:
        return 0

    # Create items for new criteria
    new_items = create_assessment_items_from_criteria(assessment, new_criteria)

    # Recalculate totals
    recalculate_assessment_scores(assessment)

    return len(new_items)


@transaction.atomic
def resync_assessment_apply_current(assessment: EmployeeKPIAssessment) -> int:
    """Replace all items in assessment with current KPICriterion.

    This DELETES existing items and recreates them from current criteria.
    Use with caution - all scoring data will be lost!

    Args:
        assessment: The EmployeeKPIAssessment to resync

    Returns:
        Number of items created
    """
    if assessment.finalized:
        raise ValueError("Cannot resync finalized assessment")

    # Delete existing items
    assessment.items.all().delete()

    # Determine target based on employee's department function
    from apps.hrm.models import Department

    if assessment.employee.department.function == Department.DepartmentFunction.BUSINESS:
        target = "sales"
    else:
        target = "backoffice"

    # Get current criteria
    current_criteria = KPICriterion.objects.filter(
        target=target,
        active=True,
    ).order_by("evaluation_type", "order")

    # Create new items
    new_items = create_assessment_items_from_criteria(assessment, list(current_criteria))

    # Recalculate totals
    assessment.total_possible_score = sum(item.component_total_score for item in new_items)
    assessment.total_manager_score = None
    assessment.grade_manager = None
    assessment.save(
        update_fields=[
            "total_possible_score",
            "total_manager_score",
            "grade_manager",
        ]
    )

    return len(new_items)


def generate_employee_assessments_for_period(  # noqa: C901
    period,
    targets=None,
    employee_ids=None,
    skip_existing=False,
) -> int:
    """Generate employee KPI assessments for all targets in a period.

    This function creates employee assessments for both sales and backoffice targets,
    creates assessment items from active criteria, and calculates initial scores.

    Args:
        period: KPIAssessmentPeriod instance
        targets: List of targets to generate for (e.g., ["sales", "backoffice"]). If None, generates for all.
        employee_ids: Optional list of employee IDs to filter. If None, generates for all eligible employees.
        skip_existing: If True, skip employees that already have assessments for this period.

    Returns:
        Number of employee assessments created
    """
    from datetime import timedelta

    from apps.hrm.models import Department, Employee
    from apps.payroll.models import KPICriterion

    if targets is None:
        targets = ["sales", "backoffice"]

    created_count = 0

    # Calculate last day of period month
    period_month = period.month
    # Get first day of next month, then subtract one day
    if period_month.month == 12:
        first_day_next_month = period_month.replace(year=period_month.year + 1, month=1)
    else:
        first_day_next_month = period_month.replace(month=period_month.month + 1)
    last_day_of_month = first_day_next_month - timedelta(days=1)

    for target in targets:
        # Get active criteria for target
        criteria = KPICriterion.objects.filter(target=target, active=True).order_by("evaluation_type", "order")

        if not criteria.exists():
            continue

        # Get employees based on target
        # Only include employees with start_date <= last day of period month
        employees_qs = Employee.objects.exclude(status=Employee.Status.RESIGNED).filter(
            start_date__lte=last_day_of_month
        )

        if target == "sales":
            employees_qs = employees_qs.filter(department__function=Department.DepartmentFunction.BUSINESS)
        elif target == "backoffice":
            employees_qs = employees_qs.exclude(department__function=Department.DepartmentFunction.BUSINESS)

        # Filter by employee IDs if provided
        if employee_ids:
            employees_qs = employees_qs.filter(id__in=employee_ids)

        # Process each employee
        for employee in employees_qs:
            try:
                # Check if assessment exists
                if (
                    skip_existing
                    and EmployeeKPIAssessment.objects.filter(
                        employee=employee,
                        period=period,
                    ).exists()
                ):
                    continue

                # Create assessment
                assessment = EmployeeKPIAssessment.objects.create(
                    employee=employee,
                    period=period,
                    manager=employee.department.leader if hasattr(employee.department, "leader") else None,
                    department_snapshot=employee.department,
                )

                # Create items from criteria
                create_assessment_items_from_criteria(assessment, list(criteria))

                # Calculate totals
                recalculate_assessment_scores(assessment)

                created_count += 1

            except Exception as e:
                # Skip errors for individual employees but log them
                logger.warning(
                    "Failed to create assessment for employee %s: %s",
                    employee.id,
                    str(e),
                )

    return created_count


def generate_department_assessments_for_period(
    period,
    department_ids=None,
    skip_existing=False,
) -> int:
    """Generate department KPI assessments for a period.

    Creates department assessments for all active departments with default grade 'C'.
    Also creates or updates leader's EmployeeKPIAssessment with grade_hrm='C' and finalized=True.

    Args:
        period: KPIAssessmentPeriod instance
        department_ids: Optional list of department IDs to filter. If None, generates for all active departments.
        skip_existing: If True, skip departments that already have assessments for this period.

    Returns:
        Number of department assessments created
    """
    from apps.hrm.models import Department
    from apps.payroll.models import DepartmentKPIAssessment

    created_count = 0
    departments_qs = Department.objects.filter(is_active=True).select_related("leader")

    # Filter by department IDs if provided
    if department_ids:
        departments_qs = departments_qs.filter(id__in=department_ids)

    for department in departments_qs:
        try:
            # Check if assessment exists
            if (
                skip_existing
                and DepartmentKPIAssessment.objects.filter(
                    department=department,
                    period=period,
                ).exists()
            ):
                continue

            DepartmentKPIAssessment.objects.create(
                department=department,
                period=period,
                grade="C",
                default_grade="C",
            )
            created_count += 1

            # Update or create leader's employee assessment
            if department.leader:
                EmployeeKPIAssessment.objects.update_or_create(
                    employee=department.leader,
                    period=period,
                    defaults={
                        "grade_hrm": "C",
                        "finalized": True,
                        "manager": department.leader,
                        "department_snapshot": department,
                        "is_for_leader": True,
                    },
                )

        except Exception as e:
            # Skip errors for individual departments but log them
            logger.warning(
                "Failed to create assessment for department %s: %s",
                department.id,
                str(e),
            )

    return created_count
