from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
    StaffGrowthReport,
)


class StaffGrowthReportModelTest(TestCase):
    """Test cases for StaffGrowthReport model"""

    def setUp(self):
        """Set up test data"""
        # Create organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            code="BB",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

        self.department = Department.objects.create(
            name="HR Department",
            code="HR",
            branch=self.branch,
            block=self.block,
        )

    def test_create_staff_growth_report(self):
        """Test creating a staff growth report"""
        report = StaffGrowthReport.objects.create(
            report_date=date(2025, 10, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            num_introductions=5,
            num_returns=2,
            num_new_hires=10,
            num_transfers=3,
            num_resignations=1,
        )

        self.assertEqual(report.num_introductions, 5)
        self.assertEqual(report.num_returns, 2)
        self.assertEqual(report.num_new_hires, 10)
        self.assertEqual(report.num_transfers, 3)
        self.assertEqual(report.num_resignations, 1)
        self.assertEqual(report.period_type, "monthly")

    def test_staff_growth_report_unique_constraint(self):
        """Test unique constraint on report_date, period_type, and organizational units"""
        StaffGrowthReport.objects.create(
            report_date=date(2025, 10, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            num_introductions=5,
        )

        # Attempting to create a duplicate should fail
        with self.assertRaises(Exception):
            StaffGrowthReport.objects.create(
                report_date=date(2025, 10, 1),
                branch=self.branch,
                block=self.block,
                department=self.department,
                num_introductions=10,
            )


class RecruitmentSourceReportModelTest(TestCase):
    """Test cases for RecruitmentSourceReport model"""

    def setUp(self):
        """Set up test data"""
        from apps.hrm.models import RecruitmentSource

        # Create organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.source = RecruitmentSource.objects.create(name="LinkedIn", code="LI")

    def test_create_recruitment_source_report(self):
        """Test creating a recruitment source report"""
        report = RecruitmentSourceReport.objects.create(
            report_date=date(2025, 10, 1),
            branch=self.branch,
            recruitment_source=self.source,
            num_hires=15,
        )

        self.assertEqual(report.num_hires, 15)
        self.assertEqual(report.recruitment_source, self.source)


class RecruitmentChannelReportModelTest(TestCase):
    """Test cases for RecruitmentChannelReport model"""

    def setUp(self):
        """Set up test data"""
        from apps.hrm.models import RecruitmentChannel

        # Create organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.channel = RecruitmentChannel.objects.create(name="Job Website", code="JW")

    def test_create_recruitment_channel_report(self):
        """Test creating a recruitment channel report"""
        report = RecruitmentChannelReport.objects.create(
            report_date=date(2025, 10, 1),
            branch=self.branch,
            recruitment_channel=self.channel,
            num_hires=20,
        )

        self.assertEqual(report.num_hires, 20)
        self.assertEqual(report.recruitment_channel, self.channel)


class RecruitmentCostReportModelTest(TestCase):
    """Test cases for RecruitmentCostReport model"""

    def setUp(self):
        """Set up test data"""
        from apps.hrm.models import RecruitmentSource

        # Create organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.source = RecruitmentSource.objects.create(name="LinkedIn", code="LI")

    def test_create_recruitment_cost_report(self):
        """Test creating a recruitment cost report"""
        report = RecruitmentCostReport.objects.create(
            report_date=date(2025, 10, 1),
            month_key="2025-10",
            source_type="referral_source",
            branch=self.branch,
            total_cost=Decimal("50000.00"),
            num_hires=10,
            avg_cost_per_hire=Decimal("5000.00"),
        )

        self.assertEqual(report.total_cost, Decimal("50000.00"))
        self.assertEqual(report.num_hires, 10)
        self.assertEqual(report.avg_cost_per_hire, Decimal("5000.00"))


class HiredCandidateReportModelTest(TestCase):
    """Test cases for HiredCandidateReport model"""

    def setUp(self):
        """Set up test data"""
        # Create organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            code="BB",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

        self.department = Department.objects.create(
            name="HR Department",
            code="HR",
            branch=self.branch,
            block=self.block,
        )

        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

    def test_create_hired_candidate_report_with_employee(self):
        """Test creating a hired candidate report with employee (introduction source)"""
        report = HiredCandidateReport.objects.create(
            report_date=date(2025, 10, 1),
            month_key="10/2025",
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type="introduction",
            employee=self.employee,
            num_candidates_hired=3,
        )

        self.assertEqual(report.source_type, "introduction")
        self.assertEqual(report.employee, self.employee)
        self.assertEqual(report.num_candidates_hired, 3)

    def test_create_hired_candidate_report_without_employee(self):
        """Test creating a hired candidate report without employee (recruitment/return source)"""
        report = HiredCandidateReport.objects.create(
            report_date=date(2025, 10, 1),
            month_key="10/2025",
            branch=self.branch,
            source_type="recruitment",
            num_candidates_hired=15,
        )

        self.assertEqual(report.source_type, "recruitment")
        self.assertIsNone(report.employee)
        self.assertEqual(report.num_candidates_hired, 15)
