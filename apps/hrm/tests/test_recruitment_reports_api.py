import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    HiredCandidateReport,
    RecruitmentChannel,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSource,
    RecruitmentSourceReport,
    StaffGrowthReport,
)

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class StaffGrowthReportAPITest(TransactionTestCase, APITestMixin):
    """Test cases for StaffGrowthReport API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        StaffGrowthReport.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

    def test_list_staff_growth_reports(self):
        """Test listing staff growth reports"""
        # Create test reports
        StaffGrowthReport.objects.create(
            report_date=date(2025, 10, 1),
            period_type="monthly",
            branch=self.branch,
            block=self.block,
            department=self.department,
            num_introductions=5,
            num_returns=2,
            num_new_hires=10,
            num_transfers=3,
            num_resignations=1,
        )

        url = reverse("hrm:staff-growth-report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["num_introductions"], 5)
        self.assertEqual(data[0]["num_new_hires"], 10)

    def test_create_staff_growth_report(self):
        """Test creating a staff growth report"""
        url = reverse("hrm:staff-growth-report-list")
        payload = {
            "report_date": "2025-10-15",
            "period_type": "monthly",
            "branch": self.branch.id,
            "block": self.block.id,
            "department": self.department.id,
            "num_introductions": 7,
            "num_returns": 3,
            "num_new_hires": 12,
            "num_transfers": 2,
            "num_resignations": 4,
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StaffGrowthReport.objects.count(), 1)
        report = StaffGrowthReport.objects.first()
        self.assertEqual(report.num_introductions, 7)
        self.assertEqual(report.num_new_hires, 12)

    def test_filter_staff_growth_reports_by_date_range(self):
        """Test filtering staff growth reports by date range"""
        StaffGrowthReport.objects.create(
            report_date=date(2025, 10, 1),
            period_type="monthly",
            branch=self.branch,
            num_introductions=5,
        )
        StaffGrowthReport.objects.create(
            report_date=date(2025, 11, 1),
            period_type="monthly",
            branch=self.branch,
            num_introductions=7,
        )

        url = reverse("hrm:staff-growth-report-list")
        response = self.client.get(url, {"report_date_after": "2025-10-15"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["num_introductions"], 7)


class RecruitmentSourceReportAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentSourceReport API endpoints"""

    def setUp(self):
        """Set up test data"""
        RecruitmentSourceReport.objects.all().delete()
        RecruitmentSource.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.source = RecruitmentSource.objects.create(name="LinkedIn", code="LI")

    def test_list_recruitment_source_reports(self):
        """Test listing recruitment source reports"""
        RecruitmentSourceReport.objects.create(
            report_date=date(2025, 10, 1),
            period_type="monthly",
            branch=self.branch,
            recruitment_source=self.source,
            org_unit_name="Hanoi Branch",
            org_unit_type="branch",
            num_hires=15,
        )

        url = reverse("hrm:recruitment-source-report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["num_hires"], 15)
        self.assertEqual(data[0]["org_unit_type"], "branch")

    def test_create_recruitment_source_report(self):
        """Test creating a recruitment source report"""
        url = reverse("hrm:recruitment-source-report-list")
        payload = {
            "report_date": "2025-10-15",
            "period_type": "monthly",
            "branch": self.branch.id,
            "recruitment_source": self.source.id,
            "org_unit_name": "Hanoi Branch",
            "org_unit_type": "branch",
            "num_hires": 20,
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecruitmentSourceReport.objects.count(), 1)


class RecruitmentChannelReportAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentChannelReport API endpoints"""

    def setUp(self):
        """Set up test data"""
        RecruitmentChannelReport.objects.all().delete()
        RecruitmentChannel.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.channel = RecruitmentChannel.objects.create(name="Job Website", code="JW")

    def test_list_recruitment_channel_reports(self):
        """Test listing recruitment channel reports"""
        RecruitmentChannelReport.objects.create(
            report_date=date(2025, 10, 1),
            period_type="monthly",
            branch=self.branch,
            recruitment_channel=self.channel,
            org_unit_name="Hanoi Branch",
            org_unit_type="branch",
            num_hires=25,
        )

        url = reverse("hrm:recruitment-channel-report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["num_hires"], 25)


class RecruitmentCostReportAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentCostReport API endpoints"""

    def setUp(self):
        """Set up test data"""
        RecruitmentCostReport.objects.all().delete()
        RecruitmentSource.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.source = RecruitmentSource.objects.create(name="LinkedIn", code="LI")

    def test_list_recruitment_cost_reports(self):
        """Test listing recruitment cost reports"""
        RecruitmentCostReport.objects.create(
            report_date=date(2025, 10, 1),
            period_type="monthly",
            branch=self.branch,
            recruitment_source=self.source,
            total_cost=Decimal("50000.00"),
            num_hires=10,
            avg_cost_per_hire=Decimal("5000.00"),
        )

        url = reverse("hrm:recruitment-cost-report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(Decimal(data[0]["total_cost"]), Decimal("50000.00"))
        self.assertEqual(data[0]["num_hires"], 10)


class HiredCandidateReportAPITest(TransactionTestCase, APITestMixin):
    """Test cases for HiredCandidateReport API endpoints"""

    def setUp(self):
        """Set up test data"""
        HiredCandidateReport.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

    def test_list_hired_candidate_reports(self):
        """Test listing hired candidate reports"""
        HiredCandidateReport.objects.create(
            report_date=date(2025, 10, 1),
            period_type="monthly",
            branch=self.branch,
            source_type="introduction",
            employee=self.employee,
            num_candidates_hired=3,
        )

        url = reverse("hrm:hired-candidate-report-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source_type"], "introduction")
        self.assertEqual(data[0]["num_candidates_hired"], 3)
