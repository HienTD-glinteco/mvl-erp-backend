from datetime import date
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentChannel,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)


@pytest.mark.django_db
class TestRecruitmentReportsSignals:
    """Test cases for recruitment report signal handlers."""

    @pytest.fixture
    def setup_data(self):
        """Set up common test data."""
        # Create organizational structure
        province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=province,
            administrative_unit=administrative_unit,
        )
        block = Block.objects.create(
            name="Business Block",
            code="BB",
            block_type=Block.BlockType.BUSINESS,
            branch=branch,
        )
        department = Department.objects.create(
            name="HR Department",
            code="HR",
            branch=branch,
            block=block,
        )

        # Create employees
        employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=branch,
            block=block,
            department=department,
            phone="3357059683",
            attendance_code="NGUYENVANA",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020003",
        )

        # Create job description and recruitment request
        job_description = JobDescription.objects.create(
            title="Software Engineer",
            responsibility="Develop software",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )
        recruitment_request = RecruitmentRequest.objects.create(
            name="Hiring Software Engineer",
            job_description=job_description,
            proposer=employee,
            branch=branch,
            block=block,
            department=department,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="1000-2000 USD",
            number_of_positions=5,
        )

        return {
            "branch": branch,
            "block": block,
            "department": department,
            "recruitment_request": recruitment_request,
            "employee": employee,
        }

    def test_cost_report_created_on_expense_save(self, setup_data):
        """Test that RecruitmentCostReport is created when RecruitmentExpense is saved."""
        source = RecruitmentSource.objects.create(name="LinkedIn", code="LI", allow_referral=False)
        channel = RecruitmentChannel.objects.create(
            name="Job Website", code="JW", belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE
        )

        expense_date = date(2025, 12, 10)
        expense = RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=channel,
            recruitment_request=setup_data["recruitment_request"],
            total_cost=Decimal("1000000.00"),
            num_candidates_hired=2,
        )

        # Check if RecruitmentCostReport was created
        report = RecruitmentCostReport.objects.filter(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
        ).first()

        assert report is not None
        assert report.total_cost == Decimal("1000000.00")
        assert report.num_hires == 2
        assert report.avg_cost_per_hire == Decimal("500000.00")
        assert report.month_key == "2025-12"

    def test_cost_report_aggregation(self, setup_data):
        """Test that multiple expenses for the same date/org/source_type are aggregated."""
        source = RecruitmentSource.objects.create(name="LinkedIn", code="LI", allow_referral=False)
        channel = RecruitmentChannel.objects.create(
            name="Job Website", code="JW", belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE
        )

        expense_date = date(2025, 12, 10)

        # Create first expense
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=channel,
            recruitment_request=setup_data["recruitment_request"],
            total_cost=Decimal("1000000.00"),
            num_candidates_hired=1,
        )

        # Create second expense
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=channel,
            recruitment_request=setup_data["recruitment_request"],
            total_cost=Decimal("2000000.00"),
            num_candidates_hired=1,
        )

        # Check aggregated report
        report = RecruitmentCostReport.objects.filter(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
        ).first()

        assert report is not None
        assert report.total_cost == Decimal("3000000.00")
        assert report.num_hires == 2
        assert report.avg_cost_per_hire == Decimal("1500000.00")

    def test_cost_report_update_on_expense_change(self, setup_data):
        """Test that RecruitmentCostReport is updated when RecruitmentExpense is modified."""
        source = RecruitmentSource.objects.create(name="LinkedIn", code="LI", allow_referral=False)
        channel = RecruitmentChannel.objects.create(
            name="Job Website", code="JW", belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE
        )

        expense_date = date(2025, 12, 10)
        expense = RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=channel,
            recruitment_request=setup_data["recruitment_request"],
            total_cost=Decimal("1000000.00"),
            num_candidates_hired=1,
        )

        # Update expense
        expense.total_cost = Decimal("1500000.00")
        expense.save()

        # Check updated report
        report = RecruitmentCostReport.objects.get(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
        )
        assert report.total_cost == Decimal("1500000.00")

    def test_cost_report_deletion(self, setup_data):
        """Test that RecruitmentCostReport is updated or deleted when RecruitmentExpense is deleted."""
        source = RecruitmentSource.objects.create(name="LinkedIn", code="LI", allow_referral=False)
        channel = RecruitmentChannel.objects.create(
            name="Job Website", code="JW", belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE
        )

        expense_date = date(2025, 12, 10)
        expense1 = RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=channel,
            recruitment_request=setup_data["recruitment_request"],
            total_cost=Decimal("1000000.00"),
            num_candidates_hired=1,
        )
        expense2 = RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=channel,
            recruitment_request=setup_data["recruitment_request"],
            total_cost=Decimal("2000000.00"),
            num_candidates_hired=1,
        )

        # Delete one expense
        expense1.delete()

        # Report should still exist but updated
        report = RecruitmentCostReport.objects.get(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
        )
        assert report.total_cost == Decimal("2000000.00")

        # Delete last expense
        expense2.delete()

        # Report should be deleted
        assert not RecruitmentCostReport.objects.filter(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
        ).exists()

    def test_source_type_mapping(self, setup_data):
        """Test mapping logic from expense to RecruitmentSourceType."""
        # Setup source types
        referral_source = RecruitmentSource.objects.create(name="Referral", code="R", allow_referral=True)
        dept_source = RecruitmentSource.objects.create(name="Dept", code="D", allow_referral=False)

        marketing_channel = RecruitmentChannel.objects.create(
            name="M", code="M", belong_to=RecruitmentChannel.BelongTo.MARKETING
        )
        job_channel = RecruitmentChannel.objects.create(
            name="J", code="J", belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE
        )
        internal_channel = RecruitmentChannel.objects.create(
            name="I", code="I", belong_to=RecruitmentChannel.BelongTo.OTHER
        )

        expense_date = date(2025, 12, 10)
        req = setup_data["recruitment_request"]

        # Create a second employee for referral tests
        employee2 = Employee.objects.create(
            fullname="Tran Thi B",
            username="tranthib",
            email="tranthib@example.com",
            branch=setup_data["branch"],
            block=setup_data["block"],
            department=setup_data["department"],
            phone="3512357609",
            attendance_code="TRANTHIB",
            date_of_birth="1990-01-01",
            personal_email="tranthib.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020004",
        )

        # 1. Referral source
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=referral_source,
            recruitment_channel=marketing_channel,
            recruitment_request=req,
            total_cost=100,
            referee=setup_data["employee"],
            referrer=employee2,
        )
        assert RecruitmentCostReport.objects.filter(source_type=RecruitmentSourceType.REFERRAL_SOURCE).exists()

        # 2. Marketing channel
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=dept_source,
            recruitment_channel=marketing_channel,
            recruitment_request=req,
            total_cost=200,
        )
        assert RecruitmentCostReport.objects.filter(source_type=RecruitmentSourceType.MARKETING_CHANNEL).exists()

        # 3. Job website channel
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=dept_source,
            recruitment_channel=job_channel,
            recruitment_request=req,
            total_cost=300,
        )
        assert RecruitmentCostReport.objects.filter(source_type=RecruitmentSourceType.JOB_WEBSITE_CHANNEL).exists()

        # 4. Fallback to recruitment department source
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=dept_source,
            recruitment_channel=internal_channel,
            recruitment_request=req,
            total_cost=400,
        )
        assert RecruitmentCostReport.objects.filter(
            source_type=RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE
        ).exists()

    def test_cost_report_separation_by_source_type(self, setup_data):
        """Test that expenses with different source_types are aggregated separately.

        This is a regression test for the bug where expenses from different
        channel types (e.g., marketing vs other) were incorrectly summed together.
        """
        source = RecruitmentSource.objects.create(name="LinkedIn", code="LI", allow_referral=False)

        # Create different channels
        marketing_channel = RecruitmentChannel.objects.create(
            name="Facebook Ads",
            code="FB",
            belong_to=RecruitmentChannel.BelongTo.MARKETING,
        )
        other_channel = RecruitmentChannel.objects.create(
            name="LinkedIn Jobs",
            code="LIJ",
            belong_to=RecruitmentChannel.BelongTo.OTHER,
        )

        expense_date = date(2025, 12, 10)
        req = setup_data["recruitment_request"]

        # Create expense for marketing channel: 12,000,000
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=marketing_channel,
            recruitment_request=req,
            total_cost=Decimal("12000000.00"),
            num_candidates_hired=1,
        )

        # Create expense for other channel: 2,500,000
        RecruitmentExpense.objects.create(
            date=expense_date,
            recruitment_source=source,
            recruitment_channel=other_channel,
            recruitment_request=req,
            total_cost=Decimal("2500000.00"),
            num_candidates_hired=1,
        )

        # Verify Marketing report only contains 12,000,000 (not 14,500,000)
        marketing_report = RecruitmentCostReport.objects.get(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.MARKETING_CHANNEL,
        )
        assert marketing_report.total_cost == Decimal("12000000.00")
        assert marketing_report.num_hires == 1

        # Verify Other channel goes to RECRUITMENT_DEPARTMENT_SOURCE
        dept_report = RecruitmentCostReport.objects.get(
            report_date=expense_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE,
        )
        assert dept_report.total_cost == Decimal("2500000.00")
        assert dept_report.num_hires == 1

    def test_returning_employee_report_on_work_history_create(self, setup_data):
        """Test that RETURNING_EMPLOYEE source type is updated when EmployeeWorkHistory RETURN_TO_WORK is created."""
        from apps.hrm.models import HiredCandidateReport, Position
        from apps.hrm.tasks.reports_recruitment.helpers import _increment_returning_employee_reports

        # Create position
        position = Position.objects.create(name="Engineer", code="ENG")

        # Create an employee
        employee = Employee.objects.create(
            fullname="Return Employee",
            username="return_emp",
            email="return_emp@example.com",
            branch=setup_data["branch"],
            block=setup_data["block"],
            department=setup_data["department"],
            position=position,
            phone="0349567893",
            attendance_code="RETURN_EMP",
            date_of_birth="1990-01-01",
            personal_email="return_emp.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020010",
            status=Employee.Status.RESIGNED,
            resignation_start_date=date(2025, 11, 1),
            resignation_reason=Employee.ResignationReason.VOLUNTARY_PERSONAL,
        )

        # Verify no report exists before
        return_date = date(2025, 12, 15)
        assert not RecruitmentCostReport.objects.filter(
            report_date=return_date,
            source_type=RecruitmentSourceType.RETURNING_EMPLOYEE,
        ).exists()

        # Directly call the helper function (simulating what the Celery task does)
        snapshot = {
            "previous": None,
            "current": {
                "date": return_date,
                "branch_id": setup_data["branch"].id,
                "block_id": setup_data["block"].id,
                "department_id": setup_data["department"].id,
                "employee_id": employee.id,
            },
        }
        _increment_returning_employee_reports("create", snapshot)

        # Check RecruitmentCostReport was created
        cost_report = RecruitmentCostReport.objects.filter(
            report_date=return_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.RETURNING_EMPLOYEE,
        ).first()

        assert cost_report is not None
        assert cost_report.num_hires == 1
        assert cost_report.total_cost == Decimal("0")
        assert cost_report.avg_cost_per_hire == Decimal("0")

        # Check HiredCandidateReport was created
        hired_report = HiredCandidateReport.objects.filter(
            report_date=return_date,
            branch=setup_data["branch"],
            source_type=RecruitmentSourceType.RETURNING_EMPLOYEE,
        ).first()

        assert hired_report is not None
        assert hired_report.num_candidates_hired == 1
