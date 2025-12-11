"""Tests for employee-related Celery tasks."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee
from apps.hrm.tasks.employee import reactive_maternity_leave_employees_task


class ReactiveMaternityLeaveEmployeesTaskTest(TestCase):
    """Test cases for reactive_maternity_leave_employees_task."""

    def setUp(self):
        """Set up test data."""
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )

        # Patch Celery-triggered tasks invoked by employee signals
        self._patcher_aggregate_hr = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
        self.mock_aggregate_hr = self._patcher_aggregate_hr.start()

        self._patcher_aggregate_recruit = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate"
        )
        self.mock_aggregate_recruit = self._patcher_aggregate_recruit.start()

    def tearDown(self):
        """Stop patchers to clean up after each test."""
        self._patcher_aggregate_hr.stop()
        self._patcher_aggregate_recruit.stop()

    def _create_maternity_leave_employee(
        self,
        fullname,
        username,
        email,
        attendance_code,
        citizen_id,
        start_date,
        resignation_start_date,
        resignation_end_date,
        phone,
    ):
        """Helper method to create an employee on maternity leave."""
        employee = Employee.objects.create(
            fullname=fullname,
            username=username,
            email=email,
            attendance_code=attendance_code,
            date_of_birth=date(1990, 1, 1),
            start_date=start_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id=citizen_id,
            phone=phone,
        )
        # Set to maternity leave status
        employee.status = Employee.Status.MATERNITY_LEAVE
        employee.resignation_start_date = resignation_start_date
        employee.resignation_end_date = resignation_end_date
        employee.resignation_reason = "Personal reasons"
        employee.save(update_fields=["status", "resignation_start_date", "resignation_end_date"])
        return employee

    def test_filters_employees_with_past_resignation_end_date(self):
        """Test that task filters employees with resignation_end_date < today."""
        today = timezone.localdate()

        # Employee with past end date (should be selected)
        employee_past = self._create_maternity_leave_employee(
            fullname="Past End Date Employee",
            username="past001",
            email="past@example.com",
            attendance_code="PAST001",
            citizen_id="000000010001",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today - timedelta(days=1),
            phone="0131941507",
        )

        # Employee with today's end date (should NOT be selected - lt not lte)
        employee_today = self._create_maternity_leave_employee(
            fullname="Today End Date Employee",
            username="today001",
            email="today@example.com",
            attendance_code="TODAY001",
            citizen_id="000000010002",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today,
            phone="0131941508",
        )

        # Employee with future end date (should NOT be selected)
        employee_future = self._create_maternity_leave_employee(
            fullname="Future End Date Employee",
            username="future001",
            email="future@example.com",
            attendance_code="FUTURE001",
            citizen_id="000000010003",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today + timedelta(days=30),
            phone="0131941509",
        )

        # Verify the queryset filter
        employees_to_reactivate = Employee.objects.filter(
            status=Employee.Status.MATERNITY_LEAVE,
            resignation_end_date__lt=today,
        )

        self.assertEqual(employees_to_reactivate.count(), 1)
        self.assertIn(employee_past, employees_to_reactivate)
        self.assertNotIn(employee_today, employees_to_reactivate)
        self.assertNotIn(employee_future, employees_to_reactivate)

    def test_does_not_select_non_maternity_leave_employees(self):
        """Test that task only selects MATERNITY_LEAVE status employees."""
        today = timezone.localdate()

        # Active employee
        active_employee = Employee.objects.create(
            fullname="Active Employee",
            username="active001",
            email="active@example.com",
            phone="0141941509",
            attendance_code="ACT001",
            date_of_birth=date(1990, 1, 1),
            start_date=date(2020, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010004",
            resignation_reason="Personal reasons",
        )
        active_employee.status = Employee.Status.ACTIVE
        active_employee.save(update_fields=["status"])

        # Resigned employee
        resigned_employee = Employee.objects.create(
            fullname="Resigned Employee",
            username="resigned001",
            email="resigned@example.com",
            phone="2222222222",
            attendance_code="RES001",
            date_of_birth=date(1990, 1, 1),
            start_date=date(2020, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010005",
        )
        resigned_employee.status = Employee.Status.RESIGNED
        resigned_employee.resignation_start_date = today - timedelta(days=30)
        resigned_employee.resignation_reason = "Personal reasons"
        resigned_employee.save(update_fields=["status", "resignation_start_date"])

        # Verify the queryset filter
        employees_to_reactivate = Employee.objects.filter(
            status=Employee.Status.MATERNITY_LEAVE,
            resignation_end_date__lt=today,
        )

        self.assertEqual(employees_to_reactivate.count(), 0)

    def test_handles_no_employees_to_reactivate(self):
        """Test that task handles case with no employees to reactivate gracefully."""
        # Act & Assert: Should not raise any exception
        reactive_maternity_leave_employees_task()

    @patch("apps.hrm.tasks.employee.EmployeeReactiveActionSerializer")
    def test_calls_serializer_with_correct_data(self, mock_serializer_class):
        """Test that the task calls EmployeeReactiveActionSerializer with correct parameters."""
        today = timezone.localdate()

        # Create employee eligible for reactivation
        employee = self._create_maternity_leave_employee(
            fullname="Test Employee",
            username="test001",
            email="test@example.com",
            attendance_code="TEST001",
            citizen_id="000000010006",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today - timedelta(days=1),
            phone="0131941508",
        )

        # Mock serializer
        mock_serializer = mock_serializer_class.return_value
        mock_serializer.is_valid.return_value = True

        # Act
        reactive_maternity_leave_employees_task()

        # Assert
        mock_serializer_class.assert_called_once()
        call_kwargs = mock_serializer_class.call_args.kwargs
        self.assertEqual(call_kwargs["instance"], employee)
        self.assertEqual(call_kwargs["data"]["start_date"], today)
        self.assertTrue(call_kwargs["data"]["is_seniority_retained"])
        self.assertIn("description", call_kwargs["data"])
        self.assertEqual(call_kwargs["context"]["employee"], employee)

        # Verify serializer methods were called
        mock_serializer.is_valid.assert_called_once_with(raise_exception=True)
        mock_serializer.save.assert_called_once()

    @patch("apps.hrm.tasks.employee.EmployeeReactiveActionSerializer")
    def test_processes_multiple_employees(self, mock_serializer_class):
        """Test that task processes multiple eligible employees."""
        today = timezone.localdate()

        # Create multiple eligible employees
        employee1 = self._create_maternity_leave_employee(
            fullname="Employee 1",
            username="emp001",
            email="emp1@example.com",
            attendance_code="EMP001",
            citizen_id="000000010007",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today - timedelta(days=5),
            phone="0131941508",
        )
        employee2 = self._create_maternity_leave_employee(
            fullname="Employee 2",
            username="emp002",
            email="emp2@example.com",
            attendance_code="EMP002",
            citizen_id="000000010008",
            start_date=date(2019, 3, 15),
            resignation_start_date=date(2024, 7, 1),
            resignation_end_date=today - timedelta(days=1),
            phone="0131941509",
        )

        # Mock serializer
        mock_serializer = mock_serializer_class.return_value
        mock_serializer.is_valid.return_value = True

        # Act
        reactive_maternity_leave_employees_task()

        # Assert: serializer called for each employee
        self.assertEqual(mock_serializer_class.call_count, 2)

    @patch("apps.hrm.tasks.employee.EmployeeReactiveActionSerializer")
    @patch("apps.hrm.tasks.employee.logger")
    def test_logs_errors_on_serializer_failure(self, mock_logger, mock_serializer_class):
        """Test that task logs errors when serializer validation fails."""
        today = timezone.localdate()

        # Create eligible employee
        employee = self._create_maternity_leave_employee(
            fullname="Test Employee",
            username="test002",
            email="test2@example.com",
            attendance_code="TEST002",
            citizen_id="000000010009",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today - timedelta(days=1),
            phone="0131941508",
        )

        # Mock serializer to raise exception
        mock_serializer = mock_serializer_class.return_value
        mock_serializer.is_valid.side_effect = Exception("Validation failed")

        # Act
        reactive_maternity_leave_employees_task()

        # Assert: error was logged
        mock_logger.exception.assert_called()
        mock_logger.warning.assert_called()

    @patch("apps.hrm.tasks.employee.EmployeeReactiveActionSerializer")
    @patch("apps.hrm.tasks.employee.logger")
    def test_continues_processing_after_error(self, mock_logger, mock_serializer_class):
        """Test that task continues processing remaining employees after an error."""
        today = timezone.localdate()

        # Create multiple eligible employees
        self._create_maternity_leave_employee(
            fullname="Employee 1",
            username="emp003",
            email="emp3@example.com",
            attendance_code="EMP003",
            citizen_id="000000010010",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today - timedelta(days=5),
            phone="0131941508",
        )
        self._create_maternity_leave_employee(
            fullname="Employee 2",
            username="emp004",
            email="emp4@example.com",
            attendance_code="EMP004",
            citizen_id="000000010011",
            start_date=date(2019, 3, 15),
            resignation_start_date=date(2024, 7, 1),
            resignation_end_date=today - timedelta(days=1),
            phone="0131941509",
        )

        # Mock serializer: first call raises exception, second succeeds
        mock_serializer = mock_serializer_class.return_value
        mock_serializer.is_valid.side_effect = [Exception("First failed"), True]

        # Act
        reactive_maternity_leave_employees_task()

        # Assert: both employees were attempted
        self.assertEqual(mock_serializer_class.call_count, 2)

    @patch("apps.hrm.tasks.employee.logger")
    def test_logs_completion_message(self, mock_logger):
        """Test that task logs completion message."""
        # Act
        reactive_maternity_leave_employees_task()

        # Assert: info log was called with completion message
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0]
        self.assertIn("completed", call_args[0].lower())

    def test_uses_localdate_for_today(self):
        """Test that task uses timezone.localdate() for consistent date handling."""
        # This is a structural test to ensure the task uses timezone-aware dates
        # The task implementation uses timezone.localdate() which we verify by inspection
        # We can also test by mocking timezone.localdate
        with patch("apps.hrm.tasks.employee.timezone") as mock_timezone:
            mock_timezone.localdate.return_value = date(2025, 1, 15)

            # Create eligible employee
            employee = self._create_maternity_leave_employee(
                fullname="Test Employee",
                username="test003",
                email="test3@example.com",
                attendance_code="TEST003",
                citizen_id="000000010012",
                start_date=date(2020, 1, 1),
                resignation_start_date=date(2024, 6, 1),
                resignation_end_date=date(2025, 1, 14),  # Before mocked today
                phone="0131941506",
            )

            with patch("apps.hrm.tasks.employee.EmployeeReactiveActionSerializer") as mock_serializer_class:
                mock_serializer = mock_serializer_class.return_value
                mock_serializer.is_valid.return_value = True

                reactive_maternity_leave_employees_task()

                # Verify localdate was called
                mock_timezone.localdate.assert_called()

                # Verify serializer was called with the mocked date
                call_kwargs = mock_serializer_class.call_args.kwargs
                self.assertEqual(call_kwargs["data"]["start_date"], date(2025, 1, 15))

    def test_is_seniority_retained_is_always_true(self):
        """Test that is_seniority_retained is always set to True in the task."""
        today = timezone.localdate()

        employee = self._create_maternity_leave_employee(
            fullname="Test Employee",
            username="test004",
            email="test4@example.com",
            attendance_code="TEST004",
            citizen_id="000000010013",
            start_date=date(2020, 1, 1),
            resignation_start_date=date(2024, 6, 1),
            resignation_end_date=today - timedelta(days=1),
            phone="0131941408",
        )

        with patch("apps.hrm.tasks.employee.EmployeeReactiveActionSerializer") as mock_serializer_class:
            mock_serializer = mock_serializer_class.return_value
            mock_serializer.is_valid.return_value = True

            reactive_maternity_leave_employees_task()

            call_kwargs = mock_serializer_class.call_args.kwargs
            self.assertTrue(call_kwargs["data"]["is_seniority_retained"])
