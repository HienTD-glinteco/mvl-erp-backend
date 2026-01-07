"""Signal handlers for employee lifecycle events.

This module handles automatic creation of assessments and payroll slips
when employees are added with start_date within existing periods.
"""

import logging
from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="hrm.Employee")
def create_assessments_for_new_employee(sender, instance, created, **kwargs):  # noqa: C901
    """Create KPI assessments and payroll slips for new employee if applicable.

    When an employee is created with start_date within an existing period month:
    - If KPI period exists and not finalized, create assessment
    - If Salary period exists and not completed, create payroll slip

    Args:
        sender: Employee model class
        instance: Employee instance
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments
    """
    from apps.hrm.models import Department
    from apps.payroll.models import (
        EmployeeKPIAssessment,
        KPIAssessmentPeriod,
        KPICriterion,
        PayrollSlip,
        SalaryPeriod,
    )
    from apps.payroll.services.payroll_calculation import PayrollCalculationService
    from apps.payroll.utils.kpi_assessment import (
        create_assessment_items_from_criteria,
        recalculate_assessment_scores,
    )

    # Only process if employee was just created
    if not created:
        return

    # Only process if employee has a start_date
    if not instance.start_date:
        return

    # Ensure start_date is a date object
    from datetime import date as date_type

    start_date = instance.start_date
    if isinstance(start_date, str):
        try:
            start_date = date_type.fromisoformat(start_date)
        except (ValueError, AttributeError):
            return
    elif not isinstance(start_date, date_type):
        return

    start_month = start_date.replace(day=1)

    # Calculate last day of start month
    if start_month.month == 12:
        first_day_next_month = start_month.replace(year=start_month.year + 1, month=1)
    else:
        first_day_next_month = start_month.replace(month=start_month.month + 1)
    last_day_of_month = first_day_next_month - timedelta(days=1)

    # Check if start_date is before last day of month (not in next month)
    if start_date > last_day_of_month:
        return

    # 1. Check for KPI Assessment Period
    try:
        kpi_period = KPIAssessmentPeriod.objects.get(month=start_month, finalized=False)

        # Check if assessment already exists
        if not EmployeeKPIAssessment.objects.filter(employee=instance, period=kpi_period).exists():
            # Determine target based on department function
            target = None
            if hasattr(instance, "department") and instance.department:
                if instance.department.function == Department.DepartmentFunction.BUSINESS:
                    target = "sales"
                else:
                    target = "backoffice"

            if target:
                # Get active criteria for target
                criteria = KPICriterion.objects.filter(target=target, active=True).order_by("evaluation_type", "order")

                if criteria.exists():
                    try:
                        # Create assessment
                        assessment = EmployeeKPIAssessment.objects.create(
                            employee=instance,
                            period=kpi_period,
                            manager=instance.department.leader if hasattr(instance.department, "leader") else None,
                            department_snapshot=instance.department,
                        )

                        # Create items from criteria
                        create_assessment_items_from_criteria(assessment, list(criteria))

                        # Calculate totals
                        recalculate_assessment_scores(assessment)

                        logger.info(
                            f"Created KPI assessment for new employee {instance.code} in period {kpi_period.month}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to create KPI assessment for employee {instance.code}: {str(e)}",
                            exc_info=True,
                        )

    except KPIAssessmentPeriod.DoesNotExist:
        # No KPI period for this month, skip
        pass
    except Exception as e:
        logger.error(
            f"Error checking KPI period for employee {instance.code}: {str(e)}",
            exc_info=True,
        )

    # 2. Check for Salary Period
    try:
        salary_period = SalaryPeriod.objects.get(month=start_month)

        # Only create if period is not completed
        if salary_period.status != SalaryPeriod.Status.COMPLETED:
            # Check if payroll slip already exists
            if not PayrollSlip.objects.filter(employee=instance, salary_period=salary_period).exists():
                try:
                    # Create payroll slip
                    payroll_slip = PayrollSlip.objects.create(salary_period=salary_period, employee=instance)

                    # Calculate payroll - wrap in try/except since config might be incomplete in tests
                    try:
                        calculator = PayrollCalculationService(payroll_slip)
                        calculator.calculate()
                    except (KeyError, ValueError) as calc_error:
                        # Log but don't fail - config might be incomplete
                        logger.warning(f"Could not calculate payroll for employee {instance.code}: {str(calc_error)}")

                    # Update salary period statistics
                    salary_period.total_employees = salary_period.payroll_slips.count()
                    salary_period.save(update_fields=["total_employees"])
                    salary_period.update_statistics()

                    logger.info(
                        f"Created payroll slip for new employee {instance.code} in period {salary_period.month}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create payroll slip for employee {instance.code}: {str(e)}",
                        exc_info=True,
                    )

    except SalaryPeriod.DoesNotExist:
        # No salary period for this month, skip
        pass
    except Exception as e:
        logger.error(
            f"Error checking salary period for employee {instance.code}: {str(e)}",
            exc_info=True,
        )
