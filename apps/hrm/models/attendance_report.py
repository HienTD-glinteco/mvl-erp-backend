from django.db import models
from django.utils.translation import gettext as _

from apps.hrm.constants import AttendanceType
from apps.hrm.models.attendance_record import AttendanceRecord
from apps.hrm.models.employee import Employee
from apps.hrm.models.organization import Block, Branch, Department
from apps.realestate.models import Project
from libs.models import BaseReportModel


class AttendanceDailyReport(BaseReportModel):
    """Daily attendance report for each employee.

    Stores the first attendance record of the day for each employee.
    Used for generating attendance reports by method, project, and organization.

    Attributes:
        report_date: Date of the report (inherited from BaseReportModel)
        employee: The employee
        branch: Branch of the employee at the time of attendance
        block: Block of the employee at the time of attendance
        department: Department of the employee at the time of attendance
        project: Project the employee is working on (optional)
        attendance_method: The method used for attendance (device, wifi, geolocation, etc.)
        attendance_record: Link to the source attendance record
    """

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendance_daily_reports",
        verbose_name="Employee",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Branch",
        null=True,
        blank=True,
    )
    block = models.ForeignKey(
        Block,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Block",
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Department",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Project",
    )
    attendance_method = models.CharField(
        max_length=20,
        choices=AttendanceType.choices,
        verbose_name="Attendance method",
    )
    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports",
        verbose_name="Attendance record",
    )

    class Meta:
        verbose_name = _("Attendance Daily Report")
        verbose_name_plural = _("Attendance Daily Reports")
        db_table = "hrm_attendance_daily_report"
        unique_together = [["report_date", "employee"]]
        indexes = [
            models.Index(fields=["report_date"]),
            models.Index(fields=["branch", "block", "department"]),
            models.Index(fields=["project"]),
            models.Index(fields=["attendance_method"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.report_date}"
