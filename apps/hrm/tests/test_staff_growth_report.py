from datetime import date

import pytest

from apps.hrm.models import (
    Employee,
    EmployeeWorkHistory,
    StaffGrowthReport,
)


@pytest.mark.django_db
class TestStaffGrowthReportDistinctCount:
    """Test that event counts are distinct per employee per timeframe."""

    @pytest.fixture(autouse=True)
    def enable_celery_eager(self, settings):
        """Enable eager execution for Celery tasks in these tests."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

    @pytest.fixture
    def setup_data(self, branch, block, department):
        """Set up common test data."""
        return {
            "branch": branch,
            "block": block,
            "department": department,
        }

    def test_same_employee_multiple_resignations_counted_once(self, setup_data, employee):
        """Employee with 2 resignations in same month counted once."""
        department = setup_data["department"]

        # Trigger event 1
        EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )

        # Trigger event 2
        EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 10),
        )

        # Check monthly report
        report = StaffGrowthReport.objects.filter(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=department,
        ).first()

        assert report is not None
        assert report.num_resignations == 1  # Not 2!

    def test_different_employees_counted_separately(self, setup_data, employee_factory):
        """Different employees counted separately."""
        department = setup_data["department"]

        emp1 = employee_factory(fullname="Emp 1")
        emp2 = employee_factory(fullname="Emp 2")

        EmployeeWorkHistory.objects.create(
            employee=emp1,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )
        EmployeeWorkHistory.objects.create(
            employee=emp2,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 10),
        )

        report = StaffGrowthReport.objects.filter(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=department,
        ).first()

        assert report is not None
        assert report.num_resignations == 2

    def test_same_employee_different_months_counted_separately(self, setup_data, employee):
        """Same employee in different months counted in each month."""
        department = setup_data["department"]

        EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )
        EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 2, 5),
        )

        jan_report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH, timeframe_key="01/2026", department=department
        )
        feb_report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH, timeframe_key="02/2026", department=department
        )

        assert jan_report.num_resignations == 1
        assert feb_report.num_resignations == 1

    def test_weekly_and_monthly_updated_together(self, setup_data, employee):
        """Both weekly and monthly reports updated for each event."""
        department = setup_data["department"]

        EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )

        weekly = StaffGrowthReport.objects.filter(
            timeframe_type=StaffGrowthReport.TimeframeType.WEEK, department=department
        )
        monthly = StaffGrowthReport.objects.filter(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH, department=department
        )

        assert weekly.exists()
        assert monthly.exists()

    def test_delete_work_history_updates_report(self, setup_data, employee):
        """Deleting work history decrements count if it was the only one."""
        department = setup_data["department"]

        wh = EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )

        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=department,
        )
        assert report.num_resignations == 1

        wh.delete()

        report.refresh_from_db()
        assert report.num_resignations == 0

    def test_delete_duplicate_work_history_does_not_decrement(self, setup_data, employee):
        """Deleting a duplicate work history does not decrement count."""
        department = setup_data["department"]

        wh1 = EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )

        wh2 = EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 10),
        )

        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=department,
        )
        assert report.num_resignations == 1

        wh2.delete()

        report.refresh_from_db()
        assert report.num_resignations == 1  # Still 1 because wh1 exists

    def test_update_event_date_moves_count_between_timeframes(self, setup_data, employee):
        """Updating event date from one month to another moves count correctly."""
        department = setup_data["department"]

        # Create event in January
        wh = EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 15),
        )

        # Verify January report has count
        jan_report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=department,
        )
        assert jan_report.num_resignations == 1

        # Update event date to February
        wh.date = date(2026, 2, 15)
        wh.save()

        # January should now have 0
        jan_report.refresh_from_db()
        assert jan_report.num_resignations == 0

        # February should have 1
        feb_report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="02/2026",
            department=department,
        )
        assert feb_report.num_resignations == 1

    def test_update_event_within_same_timeframe_no_change(self, setup_data, employee):
        """Updating event date within same month doesn't change count."""
        department = setup_data["department"]

        # Create event on Jan 5
        wh = EmployeeWorkHistory.objects.create(
            employee=employee,
            department=department,
            branch=setup_data["branch"],
            block=setup_data["block"],
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )

        report = StaffGrowthReport.objects.get(
            timeframe_type=StaffGrowthReport.TimeframeType.MONTH,
            timeframe_key="01/2026",
            department=department,
        )
        assert report.num_resignations == 1

        # Update to Jan 20 (same month)
        wh.date = date(2026, 1, 20)
        wh.save()

        # Count should remain 1
        report.refresh_from_db()
        assert report.num_resignations == 1
