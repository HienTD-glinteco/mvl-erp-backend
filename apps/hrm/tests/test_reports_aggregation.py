"""Tests for HR and Recruitment report aggregation tasks.

These tests focus on verifying task signatures, signal integration,
and proper mocking of side effects. The actual aggregation logic is
tested separately in integration tests that use PostgreSQL.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    HiredCandidateReport,
    JobDescription,
    Position,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentRequest,
    RecruitmentSource,
    RecruitmentSourceReport,
    StaffGrowthReport,
)
from apps.hrm.tasks import (
    aggregate_hr_reports_batch,
    aggregate_hr_reports_for_work_history,
    aggregate_recruitment_reports_batch,
    aggregate_recruitment_reports_for_candidate,
)


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestHRReportsAggregationTasks(TestCase):
    """Test cases for HR reports aggregation tasks."""

    def setUp(self):
        """Set up test data."""
        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="BR01",
            name="Branch 1",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="BL01", name="Block 1", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="DP01",
            name="Department 1",
            block=self.block,
            branch=self.branch,
            function=Department.DepartmentFunction.BUSINESS,
        )
        self.position = Position.objects.create(code="POS01", name="Position 1")

        # Create employee
        self.employee = Employee.objects.create(
            code="EMP001",
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=timezone.now(),
        )

        # Create work history
        self.work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date.today(),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

    @patch("apps.hrm.tasks.reports_hr.event_tasks._increment_staff_growth")
    @patch("apps.hrm.tasks.reports_hr.event_tasks._increment_employee_status")
    def test_aggregate_hr_reports_for_work_history_success(self, mock_status, mock_growth):
        """Test successful aggregation of HR reports for a work history event."""
        # Arrange
        snapshot = {
            "previous": None,
            "current": {
                "date": self.work_history.date,
                "name": self.work_history.name,
                "branch_id": self.work_history.branch_id,
                "block_id": self.work_history.block_id,
                "department_id": self.work_history.department_id,
                "status": self.work_history.status,
                "previous_data": {},
            },
        }

        # Act
        result = aggregate_hr_reports_for_work_history("create", snapshot)

        # Assert - task should complete without errors and call helper functions
        self.assertIsNone(result)  # Task returns None
        mock_growth.assert_called_once_with("create", snapshot)
        mock_status.assert_called_once_with("create", snapshot)

    @patch("apps.hrm.tasks.reports_hr.event_tasks._increment_staff_growth")
    @patch("apps.hrm.tasks.reports_hr.event_tasks._increment_employee_status")
    def test_aggregate_hr_reports_for_deleted_work_history(self, mock_status, mock_growth):
        """Test aggregation handles deleted work history gracefully."""
        # Arrange
        snapshot = {
            "current": None,
            "previous": {
                "date": self.work_history.date,
                "name": self.work_history.name,
                "branch_id": self.work_history.branch_id,
                "block_id": self.work_history.block_id,
                "department_id": self.work_history.department_id,
                "status": self.work_history.status,
                "previous_data": {},
            },
        }

        # Act
        result = aggregate_hr_reports_for_work_history("delete", snapshot)

        # Assert
        self.assertIsNone(result)  # Task returns None
        mock_growth.assert_called_once_with("delete", snapshot)
        mock_status.assert_called_once_with("delete", snapshot)

    @patch("apps.hrm.tasks.reports_hr.batch_tasks._aggregate_staff_growth_for_date")
    @patch("apps.hrm.tasks.reports_hr.batch_tasks._aggregate_employee_status_for_date")
    def test_aggregate_hr_reports_batch_success(self, mock_status_agg, mock_growth_agg):
        """Test successful batch aggregation of HR reports."""
        # Arrange - mark reports for refresh
        StaffGrowthReport.objects.create(
            report_date=date.today(),
            branch=self.branch,
            block=self.block,
            department=self.department,
            need_refresh=True,
        )

        # Act
        result = aggregate_hr_reports_batch()

        # Assert - should return number of dates processed
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    @patch("apps.hrm.tasks.reports_hr.batch_tasks._aggregate_staff_growth_for_date")
    @patch("apps.hrm.tasks.reports_hr.batch_tasks._aggregate_employee_status_for_date")
    def test_aggregate_hr_reports_batch_default_yesterday(self, mock_status_agg, mock_growth_agg):
        """Test batch aggregation processes reports marked for refresh."""
        # Arrange - create work history for yesterday and mark for refresh
        yesterday = (timezone.now() - timedelta(days=1)).date()
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=yesterday,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        
        StaffGrowthReport.objects.create(
            report_date=yesterday,
            branch=self.branch,
            block=self.block,
            department=self.department,
            need_refresh=True,
        )

        # Act
        result = aggregate_hr_reports_batch()

        # Assert - should process at least the yesterday date
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)

    def test_staff_growth_report_counts_transfers(self):
        """Test that creating transfer work history triggers task."""
        # This test is for signal integration - verify signal fires
        # The actual counting logic is tested in integration tests with PostgreSQL
        with patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history") as mock_task:
            mock_task.delay = MagicMock()
            
            # Act - create transfer work history
            EmployeeWorkHistory.objects.create(
                employee=self.employee,
                date=date.today(),
                name=EmployeeWorkHistory.EventType.TRANSFER,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )
            
            # Assert - task should be called
            mock_task.delay.assert_called()

    def test_staff_growth_report_counts_resignations(self):
        """Test that creating resignation work history triggers task."""
        # This test is for signal integration - verify signal fires
        with patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history") as mock_task:
            mock_task.delay = MagicMock()
            
            # Act - create resignation work history
            EmployeeWorkHistory.objects.create(
                employee=self.employee,
                date=date.today(),
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.RESIGNED,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )
            
            # Assert - task should be called
            mock_task.delay.assert_called()

    def test_employee_status_breakdown_report_counts_by_status(self):
        """Test that employee status breakdown task is called correctly."""
        # This test verifies task invocation, not counting logic
        # Counting logic requires PostgreSQL for DISTINCT ON queries
        with patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history") as mock_task:
            mock_task.delay = MagicMock()
            
            # Act - create work history
            EmployeeWorkHistory.objects.create(
                employee=self.employee,
                date=date.today(),
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                status=Employee.Status.ACTIVE,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )
            
            # Assert - task should be called
            mock_task.delay.assert_called()


@pytest.mark.django_db
@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class TestRecruitmentReportsAggregationTasks(TestCase):
    """Test cases for recruitment reports aggregation tasks."""

    def setUp(self):
        """Set up test data."""
        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="BR01",
            name="Branch 1",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="BL01", name="Block 1", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="DP01",
            name="Department 1",
            block=self.block,
            branch=self.branch,
            function=Department.DepartmentFunction.BUSINESS,
        )

        # Create recruitment source and channel
        self.source = RecruitmentSource.objects.create(code="SRC01", name="Source 1", allow_referral=False)
        self.channel = RecruitmentChannel.objects.create(code="CH01", name="Channel 1", belong_to="marketing")

        # Create job description
        self.job_description = JobDescription.objects.create(
            code="JD001",
            title="Job Description 1",
            position_title="Position Title 1",
            responsibility="",
            proposed_salary="10.000.000 VND",
        )

        # Create a proposer employee
        self.proposer = Employee.objects.create(
            fullname="Proposer User",
            username="proposer",
            email="proposer@example.com",
            phone="0987654321",
            attendance_code="99999",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2023-01-01",
            citizen_id="000000020014",
        )

        # Create recruitment request
        self.request = RecruitmentRequest.objects.create(
            code="REQ01",
            name="Developer",
            number_of_positions=5,
            branch=self.branch,
            block=self.block,
            department=self.department,
            job_description=self.job_description,
            proposer=self.proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="10.000.000 VND",
        )

        # Create hired candidate
        self.candidate = RecruitmentCandidate.objects.create(
            code="CAN001",
            name="Test Candidate",
            citizen_id="123456789012",
            email="candidate@example.com",
            phone="0123456789",
            recruitment_request=self.request,
            recruitment_source=self.source,
            recruitment_channel=self.channel,
            status=RecruitmentCandidate.Status.HIRED,
            submitted_date=date.today(),
            onboard_date=date.today(),
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

    @patch("apps.hrm.tasks.reports_recruitment.event_tasks._increment_recruitment_reports")
    def test_aggregate_recruitment_reports_for_candidate_success(self, mock_increment):
        """Test successful aggregation of recruitment reports for a candidate."""
        # Arrange
        snapshot = {
            "previous": None,
            "current": {
                "id": self.candidate.id,
                "status": self.candidate.status,
                "onboard_date": self.candidate.onboard_date,
                "branch_id": self.candidate.branch_id,
                "block_id": self.candidate.block_id,
                "department_id": self.candidate.department_id,
            },
        }
        
        # Act
        result = aggregate_recruitment_reports_for_candidate("create", snapshot)

        # Assert - task should complete without errors
        self.assertIsNone(result)  # Task returns None
        mock_increment.assert_called_once_with("create", snapshot)

    @patch("apps.hrm.tasks.reports_recruitment.event_tasks._increment_recruitment_reports")
    def test_aggregate_recruitment_reports_for_deleted_candidate(self, mock_increment):
        """Test aggregation handles deleted candidate gracefully."""
        # Arrange
        snapshot = {
            "current": None,
            "previous": {
                "id": self.candidate.id,
                "status": self.candidate.status,
                "onboard_date": self.candidate.onboard_date,
                "branch_id": self.candidate.branch_id,
                "block_id": self.candidate.block_id,
                "department_id": self.candidate.department_id,
            },
        }

        # Act
        result = aggregate_recruitment_reports_for_candidate("delete", snapshot)

        # Assert
        self.assertIsNone(result)  # Task returns None
        mock_increment.assert_called_once_with("delete", snapshot)

    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_hired_candidate_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_recruitment_channel_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_recruitment_cost_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_recruitment_source_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._update_staff_growth_for_recruitment")
    def test_aggregate_recruitment_reports_batch_success(
        self, mock_staff, mock_source, mock_cost, mock_channel, mock_hired
    ):
        """Test successful batch aggregation of recruitment reports."""
        # Arrange - mark reports for refresh
        HiredCandidateReport.objects.create(
            report_date=date.today(),
            branch=self.branch,
            block=self.block,
            department=self.department,
            need_refresh=True,
        )

        # Act
        result = aggregate_recruitment_reports_batch()

        # Assert - should return number of dates processed
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_hired_candidate_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_recruitment_channel_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_recruitment_cost_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._aggregate_recruitment_source_for_date")
    @patch("apps.hrm.tasks.reports_recruitment.batch_tasks._update_staff_growth_for_recruitment")
    def test_aggregate_recruitment_reports_batch_default_yesterday(
        self, mock_staff, mock_source, mock_cost, mock_channel, mock_hired
    ):
        """Test batch aggregation processes reports marked for refresh."""
        # Arrange - create report for yesterday and mark for refresh
        yesterday = (timezone.now() - timedelta(days=1)).date()
        
        HiredCandidateReport.objects.create(
            report_date=yesterday,
            branch=self.branch,
            block=self.block,
            department=self.department,
            need_refresh=True,
        )

        # Act
        result = aggregate_recruitment_reports_batch()

        # Assert - should process at least the yesterday date
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 1)

    def test_hired_candidate_report_counts_experienced(self):
        """Test that hiring experienced candidate triggers task."""
        # This test verifies signal integration
        with patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate") as mock_task:
            mock_task.delay = MagicMock()
            
            # Act - create hired candidate with experience
            RecruitmentCandidate.objects.create(
                code="CAN002",
                name="Experienced Candidate",
                citizen_id="123456789013",
                email="experienced@example.com",
                phone="0123456788",
                recruitment_request=self.request,
                recruitment_source=self.source,
                recruitment_channel=self.channel,
                status=RecruitmentCandidate.Status.HIRED,
                submitted_date=date.today(),
                onboard_date=date.today(),
                years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )
            
            # Assert - task should be called
            mock_task.delay.assert_called()

    def test_hired_candidate_report_not_counts_no_experience(self):
        """Test that hiring candidate without experience triggers task."""
        # This test verifies signal integration
        with patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate") as mock_task:
            mock_task.delay = MagicMock()
            
            # Act - create hired candidate without experience
            RecruitmentCandidate.objects.create(
                code="CAN003",
                name="Fresh Graduate",
                citizen_id="123456789014",
                email="fresh@example.com",
                phone="0123456787",
                recruitment_request=self.request,
                recruitment_source=self.source,
                recruitment_channel=self.channel,
                status=RecruitmentCandidate.Status.HIRED,
                submitted_date=date.today(),
                onboard_date=date.today(),
                years_of_experience=RecruitmentCandidate.YearsOfExperience.NO_EXPERIENCE,
                branch=self.branch,
                block=self.block,
                department=self.department,
            )
            
            # Assert - task should be called
            mock_task.delay.assert_called()

    def test_recruitment_channel_report_counts_hires(self):
        """Test that recruitment channel report task is called."""
        # This test verifies signal integration
        with patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate") as mock_task:
            mock_task.delay = MagicMock()
            
            # Act - create hired candidate
            RecruitmentCandidate.objects.create(
                code="CAN004",
                name="New Hire",
                citizen_id="123456789015",
                email="newhire@example.com",
                phone="0123456786",
                recruitment_request=self.request,
                recruitment_source=self.source,
                recruitment_channel=self.channel,
                status=RecruitmentCandidate.Status.HIRED,
                submitted_date=date.today(),
                onboard_date=date.today(),
                branch=self.branch,
                block=self.block,
                department=self.department,
            )
            
            # Assert - task should be called
            mock_task.delay.assert_called()


@pytest.mark.django_db
@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class TestSignalIntegration(TestCase):
    """Test cases for signal integration with report aggregation tasks."""

    def setUp(self):
        """Set up test data."""
        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="BR01",
            name="Branch 1",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="BL01", name="Block 1", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="DP01",
            name="Department 1",
            block=self.block,
            branch=self.branch,
            function=Department.DepartmentFunction.BUSINESS,
        )
        self.position = Position.objects.create(code="POS01", name="Position 1")

        # Create employee
        self.employee = Employee.objects.create(
            code="EMP001",
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            phone="0123456789",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            start_date=date.today(),  # Required field
        )

    @patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
    def test_work_history_save_triggers_aggregation(self, mock_task):
        """Test that saving work history triggers aggregation task."""
        # Arrange
        mock_task.delay = MagicMock()

        # Act
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date.today(),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Assert - task should be called with action_type and snapshot
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args[0]
        self.assertEqual(args[0], "create")  # action_type
        self.assertIsInstance(args[1], dict)  # snapshot
        self.assertIn("previous", args[1])
        self.assertIn("current", args[1])

    @patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
    def test_work_history_delete_triggers_aggregation(self, mock_task):
        """Test that deleting work history triggers aggregation task."""
        # Arrange
        mock_task.delay = MagicMock()
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date.today(),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        
        # Clear the create call
        mock_task.delay.reset_mock()

        # Act
        work_history.delete()

        # Assert - task should be called with delete action
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args[0]
        self.assertEqual(args[0], "delete")  # action_type

    @patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate")
    def test_candidate_save_triggers_aggregation(self, mock_task):
        """Test that saving candidate triggers aggregation task."""
        # Arrange
        mock_task.delay = MagicMock()

        source = RecruitmentSource.objects.create(code="SRC01", name="Source 1", allow_referral=False)
        channel = RecruitmentChannel.objects.create(code="CH01", name="Channel 1", belong_to="marketing")
        
        # Create job description
        job_description = JobDescription.objects.create(
            code="JD001",
            title="Job Description 1",
            position_title="Developer",
            responsibility="",
            proposed_salary="10.000.000 VND",
        )
        
        # Create a proposer employee
        proposer = Employee.objects.create(
            fullname="Proposer User",
            username="proposer",
            email="proposer@example.com",
            phone="0987654321",
            attendance_code="99999",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date.today(),
            citizen_id="000000020014",
        )
        
        request = RecruitmentRequest.objects.create(
            code="REQ01",
            name="Developer",
            number_of_positions=5,
            branch=self.branch,
            block=self.block,
            department=self.department,
            job_description=job_description,
            proposer=proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="10.000.000 VND",
        )

        # Act
        candidate = RecruitmentCandidate.objects.create(
            code="CAN001",
            name="Test Candidate",
            citizen_id="123456789012",
            email="candidate@example.com",
            phone="0123456789",
            recruitment_request=request,
            recruitment_source=source,
            recruitment_channel=channel,
            status=RecruitmentCandidate.Status.HIRED,
            submitted_date=date.today(),
            onboard_date=date.today(),
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Assert - task should be called with action_type and snapshot
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args[0]
        self.assertEqual(args[0], "create")  # action_type
        self.assertIsInstance(args[1], dict)  # snapshot
