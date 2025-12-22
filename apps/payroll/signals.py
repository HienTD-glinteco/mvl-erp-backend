"""Signals for payroll app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment
from apps.payroll.utils import update_department_assessment_status


@receiver(post_save, sender=EmployeeKPIAssessment)
def update_department_status_on_employee_assessment_save(sender, instance, **kwargs):
    """Update department assessment status when employee assessment is saved.

    This signal triggers when an EmployeeKPIAssessment is saved and:
    1. Finds the corresponding DepartmentKPIAssessment
    2. Recalculates is_finished (all employees graded)
    3. Recalculates is_valid_unit_control if finished
    """
    # Only update if employee has a department
    if not instance.employee or not instance.employee.department:
        return

    # Find corresponding department assessment
    try:
        dept_assessment = DepartmentKPIAssessment.objects.get(
            period=instance.period, department=instance.employee.department
        )
    except DepartmentKPIAssessment.DoesNotExist:
        # No department assessment exists yet
        return

    # Update department status
    update_department_assessment_status(dept_assessment)
