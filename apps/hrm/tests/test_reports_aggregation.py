"""Tests for HR and Recruitment report aggregation tasks."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase
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

    def test_aggregate_hr_reports_for_work_history_success(self):
        """Test successful aggregation of HR reports for a work history event."""
        # Act
        result = aggregate_hr_reports_for_work_history(self.work_history.id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["work_history_id"], self.work_history.id)
        self.assertEqual(result["report_date"], str(self.work_history.date))
        self.assertIsNone(result["error"])

        # Verify reports were created
        self.assertTrue(
            StaffGrowthReport.objects.filter(
                report_date=self.work_history.date,
                branch=self.branch,
                block=self.block,
                department=self.department,
            ).exists()
        )

        self.assertTrue(
            EmployeeStatusBreakdownReport.objects.filter(
                report_date=self.work_history.date,
                branch=self.branch,
                block=self.block,
                department=self.department,
            ).exists()
        )

    def test_aggregate_hr_reports_for_deleted_work_history(self):
        """Test aggregation handles deleted work history gracefully."""
        # Arrange
        deleted_id = 99999

        # Act
        result = aggregate_hr_reports_for_work_history(deleted_id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["work_history_id"], deleted_id)
        self.assertIn("skipped", result.get("message", ""))

    def test_aggregate_hr_reports_batch_success(self):
        """Test successful batch aggregation of HR reports."""
        # Arrange
        target_date = date.today()

        # Act
        result = aggregate_hr_reports_batch(target_date.isoformat())

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["target_date"], str(target_date))
        self.assertGreaterEqual(result["org_units_processed"], 1)
        self.assertIsNone(result["error"])

    def test_aggregate_hr_reports_batch_default_yesterday(self):
        """Test batch aggregation defaults to yesterday when no date provided."""
        # Arrange - create work history for yesterday
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

        # Act
        result = aggregate_hr_reports_batch()

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["target_date"], str(yesterday))

    def test_staff_growth_report_counts_transfers(self):
        """Test that staff growth report correctly counts transfers."""
        # Arrange
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date.today(),
            name=EmployeeWorkHistory.EventType.TRANSFER,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act
        aggregate_hr_reports_for_work_history(self.work_history.id)

        # Assert
        report = StaffGrowthReport.objects.get(
            report_date=date.today(),
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.num_transfers, 1)

    def test_staff_growth_report_counts_resignations(self):
        """Test that staff growth report correctly counts resignations."""
        # Arrange
        EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date.today(),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act
        aggregate_hr_reports_for_work_history(self.work_history.id)

        # Assert
        report = StaffGrowthReport.objects.get(
            report_date=date.today(),
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.num_resignations, 1)

    def test_employee_status_breakdown_report_counts_by_status(self):
        """Test that employee status breakdown correctly counts by status."""
        # Arrange - create employees with different statuses
        Employee.objects.create(
            code="EMP002",
            fullname="Test Employee 2",
            username="testuser2",
            email="test2@example.com",
            phone="0123456788",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ONBOARDING,
        )

        Employee.objects.create(
            code="EMP003",
            fullname="Test Employee 3",
            username="testuser3",
            email="test3@example.com",
            phone="0123456787",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.RESIGNED,
        )

        # Act
        aggregate_hr_reports_for_work_history(self.work_history.id)

        # Assert
        report = EmployeeStatusBreakdownReport.objects.get(
            report_date=date.today(),
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        self.assertEqual(report.count_active, 1)
        self.assertEqual(report.count_onboarding, 1)
        self.assertEqual(report.count_resigned, 1)
        self.assertEqual(report.total_not_resigned, 2)


@pytest.mark.django_db
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

    def test_aggregate_recruitment_reports_for_candidate_success(self):
        """Test successful aggregation of recruitment reports for a candidate."""
        # Act
        result = aggregate_recruitment_reports_for_candidate(self.candidate.id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["candidate_id"], self.candidate.id)
        self.assertEqual(result["report_date"], str(self.candidate.onboard_date))
        self.assertIsNone(result["error"])

        # Verify reports were created
        self.assertTrue(
            RecruitmentSourceReport.objects.filter(
                report_date=self.candidate.onboard_date,
                branch=self.branch,
                block=self.block,
                department=self.department,
                recruitment_source=self.source,
            ).exists()
        )

        self.assertTrue(
            RecruitmentChannelReport.objects.filter(
                report_date=self.candidate.onboard_date,
                branch=self.branch,
                block=self.block,
                department=self.department,
                recruitment_channel=self.channel,
            ).exists()
        )

    def test_aggregate_recruitment_reports_for_deleted_candidate(self):
        """Test aggregation handles deleted candidate gracefully."""
        # Arrange
        deleted_id = 99999

        # Act
        result = aggregate_recruitment_reports_for_candidate(deleted_id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["candidate_id"], deleted_id)
        self.assertIn("skipped", result.get("message", ""))

    def test_aggregate_recruitment_reports_batch_success(self):
        """Test successful batch aggregation of recruitment reports."""
        # Arrange
        target_date = date.today()

        # Act
        result = aggregate_recruitment_reports_batch(target_date.isoformat())

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["target_date"], str(target_date))
        self.assertGreaterEqual(result["org_units_processed"], 1)
        self.assertIsNone(result["error"])

    def test_aggregate_recruitment_reports_batch_default_yesterday(self):
        """Test batch aggregation defaults to yesterday when no date provided."""
        # Arrange - create hired candidate for yesterday
        yesterday = (timezone.now() - timedelta(days=1)).date()
        RecruitmentCandidate.objects.create(
            code="CAN002",
            name="Test Candidate 2",
            citizen_id="123456789013",
            email="candidate2@example.com",
            phone="0123456788",
            recruitment_request=self.request,
            recruitment_source=self.source,
            recruitment_channel=self.channel,
            status=RecruitmentCandidate.Status.HIRED,
            submitted_date=yesterday,
            onboard_date=yesterday,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Act
        result = aggregate_recruitment_reports_batch()

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["target_date"], str(yesterday))

    def test_recruitment_source_report_counts_hires(self):
        """Test that recruitment source report correctly counts hires."""
        # Act
        aggregate_recruitment_reports_for_candidate(self.candidate.id)

        # Assert
        report = RecruitmentSourceReport.objects.get(
            report_date=self.candidate.onboard_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_source=self.source,
        )
        self.assertEqual(report.num_hires, 1)

    def test_recruitment_channel_report_counts_hires(self):
        """Test that recruitment channel report correctly counts hires."""
        # Act
        aggregate_recruitment_reports_for_candidate(self.candidate.id)

        # Assert
        report = RecruitmentChannelReport.objects.get(
            report_date=self.candidate.onboard_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_channel=self.channel,
        )
        self.assertEqual(report.num_hires, 1)

    def test_hired_candidate_report_counts_experienced(self):
        """Test that hired candidate report correctly counts experienced candidates."""
        # Act
        aggregate_recruitment_reports_for_candidate(self.candidate.id)

        # Assert
        report = HiredCandidateReport.objects.get(
            report_date=self.candidate.onboard_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL,
        )
        self.assertEqual(report.num_candidates_hired, 1)
        self.assertEqual(report.num_experienced, 1)  # Candidate has 1-3 years experience

    def test_hired_candidate_report_not_counts_no_experience(self):
        """Test that hired candidate report doesn't count no experience candidates."""
        # Arrange - create candidate with no experience
        no_exp_candidate = RecruitmentCandidate.objects.create(
            code="CAN003",
            name="Test Candidate 3",
            citizen_id="123456789014",
            email="candidate3@example.com",
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

        # Act
        aggregate_recruitment_reports_for_candidate(no_exp_candidate.id)

        # Assert
        report = HiredCandidateReport.objects.get(
            report_date=no_exp_candidate.onboard_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL,
        )
        # Should have 2 total hires (from previous test + this one)
        self.assertEqual(report.num_candidates_hired, 2)
        # Should still have only 1 experienced (from previous test)
        self.assertEqual(report.num_experienced, 1)

    def test_recruitment_cost_report_aggregation(self):
        """Test that recruitment cost report aggregates costs correctly."""
        # Act
        aggregate_recruitment_reports_for_candidate(self.candidate.id)

        # Assert
        report = RecruitmentCostReport.objects.get(
            report_date=self.candidate.onboard_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL,
        )
        self.assertEqual(report.num_hires, 1)
        # Cost would be 0 unless we add expenses
        self.assertEqual(report.total_cost, Decimal("0"))
        self.assertEqual(report.avg_cost_per_hire, Decimal("0"))


@pytest.mark.django_db
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
        )

    @patch("apps.hrm.tasks.reports_hr.aggregate_hr_reports_for_work_history")
    def test_work_history_save_triggers_aggregation(self, mock_task):
        """Test that saving work history triggers aggregation task."""
        # Arrange
        mock_task.delay = Mock()

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

        # Assert
        mock_task.delay.assert_called_once_with(work_history.id)

    @patch("apps.hrm.tasks.reports_hr.aggregate_hr_reports_batch")
    def test_work_history_delete_triggers_batch_aggregation(self, mock_task):
        """Test that deleting work history triggers batch aggregation task."""
        # Arrange
        mock_task.delay = Mock()
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date.today(),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
            branch=self.branch,
            block=self.block,
            department=self.department,
        )
        work_history_date = work_history.date

        # Act
        work_history.delete()

        # Assert
        mock_task.delay.assert_called_once_with(target_date=work_history_date.isoformat())

    @patch("apps.hrm.tasks.reports_recruitment.aggregate_recruitment_reports_for_candidate")
    def test_candidate_save_triggers_aggregation(self, mock_task):
        """Test that saving candidate triggers aggregation task."""
        # Arrange
        mock_task.delay = Mock()

        source = RecruitmentSource.objects.create(code="SRC01", name="Source 1", allow_referral=False)
        channel = RecruitmentChannel.objects.create(code="CH01", name="Channel 1", belong_to="marketing")
        request = RecruitmentRequest.objects.create(
            code="REQ01",
            position_name="Developer",
            quantity=5,
            branch=self.branch,
            block=self.block,
            department=self.department,
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

        # Assert
        mock_task.delay.assert_called_once_with(candidate.id)
