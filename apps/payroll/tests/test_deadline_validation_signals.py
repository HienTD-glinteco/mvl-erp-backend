"""Tests for proposal deadline validation via signals."""

from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.hrm.constants import ProposalType
from apps.hrm.models import Proposal
from apps.payroll.models import SalaryPeriod


@pytest.mark.django_db
class TestProposalDeadlineValidationSignal:
    """Test proposal deadline validation via pre_save signal."""

    def test_timesheet_complaint_after_deadline_rejected(self, salary_config, employee):
        """Test TIMESHEET_ENTRY_COMPLAINT cannot be created after deadline."""
        # Arrange - Create period with deadline in the past
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            proposal = Proposal(
                created_by=employee,
                proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
                timesheet_entry_complaint_complaint_date=date(2024, 1, 15),
            )
            proposal.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_paid_leave_after_deadline_rejected(self, salary_config, employee):
        """Test PAID_LEAVE cannot be created after deadline."""
        # Arrange
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            proposal = Proposal(
                created_by=employee,
                proposal_type=ProposalType.PAID_LEAVE,
                paid_leave_start_date=date(2024, 1, 15),
                paid_leave_end_date=date(2024, 1, 17),
            )
            proposal.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_unpaid_leave_after_deadline_rejected(self, salary_config, employee):
        """Test UNPAID_LEAVE cannot be created after deadline."""
        # Arrange
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            proposal = Proposal(
                created_by=employee,
                proposal_type=ProposalType.UNPAID_LEAVE,
                unpaid_leave_start_date=date(2024, 1, 15),
                unpaid_leave_end_date=date(2024, 1, 17),
            )
            proposal.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_maternity_leave_after_deadline_rejected(self, salary_config, employee):
        """Test MATERNITY_LEAVE cannot be created after deadline."""
        # Arrange
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            proposal = Proposal(
                created_by=employee,
                proposal_type=ProposalType.MATERNITY_LEAVE,
                maternity_leave_start_date=date(2024, 1, 15),
                maternity_leave_end_date=date(2024, 5, 15),
            )
            proposal.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_post_maternity_benefits_after_deadline_rejected(self, salary_config, employee):
        """Test POST_MATERNITY_BENEFITS cannot be created after deadline."""
        # Arrange
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            proposal = Proposal(
                created_by=employee,
                proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
                post_maternity_benefits_start_date=date(2024, 1, 15),
                post_maternity_benefits_end_date=date(2024, 3, 15),
            )
            proposal.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_proposal_before_deadline_allowed(self, salary_config, employee):
        """Test proposal can be created before deadline."""
        # Arrange - deadline in future
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=tomorrow,
        )

        # Act
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_date=date(2024, 1, 15),
        )

        # Assert
        assert proposal.id is not None

    def test_proposal_update_after_deadline_allowed(self, salary_config, employee):
        """Test proposal can be updated (approved) after deadline."""
        # Arrange - Create period with deadline in future, create proposal
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=tomorrow,
        )

        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.PAID_LEAVE,
            paid_leave_start_date=date(2024, 1, 15),
            paid_leave_end_date=date(2024, 1, 17),
        )

        # Act - Update deadline to past and try to update proposal
        salary_period.proposal_deadline = (timezone.now() - timedelta(days=1)).date()
        salary_period.save()

        proposal.approval_note = "Approved"
        proposal.save()  # Should not raise error

        # Assert
        assert proposal.approval_note == "Approved"

    def test_non_salary_affecting_proposal_not_validated(self, salary_config, employee, department, position):
        """Test non-salary-affecting proposals are not validated."""
        # Arrange - Create period with deadline in past
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Act
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.JOB_TRANSFER,  # Doesn't affect salary
            job_transfer_effective_date=date(2024, 1, 15),
            job_transfer_new_department=department,
            job_transfer_new_position=position,
        )

        # Assert
        assert proposal.id is not None

    def test_proposal_without_salary_period_allowed(self, employee):
        """Test proposal can be created when salary period doesn't exist."""
        # Act
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            timesheet_entry_complaint_complaint_date=date(2025, 1, 15),
        )

        # Assert
        assert proposal.id is not None


@pytest.mark.django_db
class TestKPIAssessmentDeadlineValidationSignal:
    """Test KPI assessment deadline validation via pre_save signal."""

    def test_kpi_assessment_creation_always_allowed(self, salary_period, kpi_assessment_period, employee):
        """Test KPI assessment can be created even after deadline."""
        # Arrange
        from apps.payroll.models import EmployeeKPIAssessment

        # Set KPI deadline to past
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period.kpi_assessment_deadline = yesterday
        salary_period.save()

        # Act - Initial creation is always allowed
        assessment = EmployeeKPIAssessment.objects.create(
            period=kpi_assessment_period,
            employee=employee,
            manager=employee,
        )

        # Assert
        assert assessment.id is not None

    def test_manager_scoring_after_deadline_rejected(self, salary_period, kpi_assessment_period, employee):
        """Test manager cannot score assessment after deadline."""
        # Arrange
        from apps.payroll.models import EmployeeKPIAssessment

        # Set KPI deadline to past
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period.kpi_assessment_deadline = yesterday
        salary_period.save()

        assessment = EmployeeKPIAssessment.objects.create(
            period=kpi_assessment_period,
            employee=employee,
            manager=employee,
        )

        # Act & Assert - Manager scoring after deadline
        assessment.manager_assessment_date = timezone.now().date()
        assessment.total_manager_score = 80

        with pytest.raises(ValidationError) as exc_info:
            assessment.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_hrm_edit_after_deadline_allowed(self, salary_period, kpi_assessment_period, employee):
        """Test HRM can edit assessment after deadline."""
        # Arrange
        from apps.payroll.models import EmployeeKPIAssessment

        # Set KPI deadline to past
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period.kpi_assessment_deadline = yesterday
        salary_period.save()

        assessment = EmployeeKPIAssessment.objects.create(
            period=kpi_assessment_period,
            employee=employee,
            manager=employee,
        )

        # Act - HRM editing after deadline
        assessment.hrm_assessed = True
        assessment.grade_hrm = "A"
        assessment.save()  # Should not raise error

        # Assert
        assert assessment.grade_hrm == "A"

    def test_manager_scoring_before_deadline_allowed(self, salary_period, kpi_assessment_period, employee):
        """Test manager can score assessment before deadline."""
        # Arrange
        from apps.payroll.models import EmployeeKPIAssessment

        # Set KPI deadline to future
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        salary_period.kpi_assessment_deadline = tomorrow
        salary_period.save()

        assessment = EmployeeKPIAssessment.objects.create(
            period=kpi_assessment_period,
            employee=employee,
            manager=employee,
        )

        # Act - Manager scoring before deadline
        assessment.manager_assessment_date = timezone.now().date()
        assessment.total_manager_score = 85
        assessment.save()

        # Assert
        assert assessment.total_manager_score == 85

    def test_kpi_assessment_without_salary_period_allowed(self, employee):
        """Test KPI assessment can be submitted when salary period doesn't exist."""
        # Arrange
        from apps.payroll.models import EmployeeKPIAssessment, KPIAssessmentPeriod

        # Simple KPI config
        kpi_config = {
            "grading_criteria": {
                "A": {"min_score": 90, "percentage": 0.1},
                "B": {"min_score": 80, "percentage": 0.05},
            }
        }

        # Create period for month without salary period
        kpi_period_future = KPIAssessmentPeriod.objects.create(month=date(2025, 6, 1), kpi_config_snapshot=kpi_config)

        # Act
        assessment = EmployeeKPIAssessment.objects.create(
            period=kpi_period_future,
            employee=employee,
            manager=employee,
        )

        # Assert
        assert assessment.id is not None


@pytest.mark.django_db
class TestOvertimeEntryDeadlineValidationSignal:
    """Test overtime entry deadline validation via pre_save signal."""

    def test_overtime_entry_after_deadline_rejected(self, salary_config, employee):
        """Test ProposalOvertimeEntry cannot be created after deadline."""
        # Arrange - Create period with deadline in the past
        yesterday = (timezone.now() - timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=yesterday,
        )

        # Create an overtime proposal first
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.OVERTIME_WORK,
        )

        # Act & Assert - Try to add entry after deadline
        from apps.hrm.models import ProposalOvertimeEntry

        with pytest.raises(ValidationError) as exc_info:
            entry = ProposalOvertimeEntry(
                proposal=proposal,
                date=date(2024, 1, 15),
                start_time=time(18, 0),
                end_time=time(20, 0),
            )
            entry.save()

        assert "deadline" in str(exc_info.value).lower()

    def test_overtime_entry_before_deadline_allowed(self, salary_config, employee):
        """Test ProposalOvertimeEntry can be created before deadline."""
        # Arrange - Create period with deadline in the future
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        salary_period = SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
            proposal_deadline=tomorrow,
        )

        # Create an overtime proposal first
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.OVERTIME_WORK,
        )

        # Act - Create entry before deadline
        from apps.hrm.models import ProposalOvertimeEntry

        entry = ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2024, 1, 15),
            start_time=time(18, 0),
            end_time=time(20, 0),
        )

        # Assert
        assert entry.id is not None

    def test_overtime_entry_without_salary_period_allowed(self, employee):
        """Test ProposalOvertimeEntry can be created when no salary period exists."""
        # Arrange - No salary period created
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.OVERTIME_WORK,
        )

        # Act - Create entry when no period exists
        from apps.hrm.models import ProposalOvertimeEntry

        entry = ProposalOvertimeEntry.objects.create(
            proposal=proposal,
            date=date(2024, 6, 15),
            start_time=time(18, 0),
            end_time=time(20, 0),
        )

        # Assert
        assert entry.id is not None
