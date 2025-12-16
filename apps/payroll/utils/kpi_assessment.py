"""Utilities for KPI assessment snapshot and operations.

This module provides functions for:
- Creating assessment snapshots from KPICriterion
- Resyncing assessments
- Recalculating scores and grades
"""

from typing import List

from django.db import transaction

from apps.payroll.models import (
    EmployeeKPIAssessment,
    EmployeeKPIItem,
    KPICriterion,
)
from apps.payroll.utils.kpi_calculation import calculate_grade_from_percent


def create_assessment_items_from_criteria(
    assessment: EmployeeKPIAssessment,
    criteria: List[KPICriterion],
) -> List[EmployeeKPIItem]:
    """Create EmployeeKPIItem instances from KPICriterion snapshots.

    Args:
        assessment: The parent EmployeeKPIAssessment
        criteria: List of KPICriterion to snapshot

    Returns:
        List of created EmployeeKPIItem instances
    """
    items = []
    for criterion in criteria:
        item = EmployeeKPIItem(
            assessment=assessment,
            criterion_id=criterion,
            criterion=criterion.criterion,
            sub_criterion=criterion.sub_criterion,
            evaluation_type=criterion.evaluation_type,
            description=criterion.description,
            component_total_score=criterion.component_total_score,
            group_number=criterion.group_number,
            ordering=criterion.order,
        )
        items.append(item)

    EmployeeKPIItem.objects.bulk_create(items)
    return items


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

    assessment.total_manager_score = total_manager

    # Calculate grade if we have manager score
    if total_manager is not None:
        config = assessment.period.kpi_config_snapshot

        grade, possible_codes = calculate_grade_from_percent(
            total_manager,
            config.get("grade_thresholds", []),
            config.get("ambiguous_assignment", "manual"),
        )

        # If grade_manager_overridden is set, use that instead
        if assessment.grade_manager_overridden:
            assessment.grade_manager = assessment.grade_manager_overridden
        else:
            assessment.grade_manager = grade

    assessment.save()
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
    assessment.save()

    return len(new_items)
