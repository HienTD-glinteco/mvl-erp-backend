import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    HiredCandidateReport,
    JobDescription,
    RecruitmentChannel,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
    RecruitmentSourceReport,
    StaffGrowthReport,
)
from apps.hrm.utils import get_week_key_from_date

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


class RecruitmentReportsAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Recruitment Reports API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        HiredCandidateReport.objects.all().delete()
        RecruitmentCostReport.objects.all().delete()
        RecruitmentChannelReport.objects.all().delete()
        RecruitmentSourceReport.objects.all().delete()
        StaffGrowthReport.objects.all().delete()
        RecruitmentExpense.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        RecruitmentSource.objects.all().delete()
        RecruitmentChannel.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
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

        # Create employee for referral source
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            phone="0123456789",
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000020033",
        )

        # Create another employee for referral tests
        self.employee2 = Employee.objects.create(
            fullname="Tran Van B",
            username="tranvanb",
            email="tranvanb@example.com",
            phone="0987654321",
            attendance_code="EMP002",
            date_of_birth="1991-01-01",
            personal_email="tranvanb.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000020034",
        )

        # Create recruitment sources and channels
        self.source_referral = RecruitmentSource.objects.create(
            name="Employee Referral",
            allow_referral=True,
        )

        self.source_no_referral = RecruitmentSource.objects.create(
            name="Direct Application",
            allow_referral=False,
        )

        self.channel_marketing = RecruitmentChannel.objects.create(
            name="Facebook Ads",
            belong_to=RecruitmentChannel.BelongTo.MARKETING,
        )

        self.channel_job_website = RecruitmentChannel.objects.create(
            name="VietnamWorks",
            belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE,
        )

        # Set up test dates
        self.today = date.today()
        self.first_day_month = self.today.replace(day=1)
        if self.today.month == 12:
            self.last_day_month = date(self.today.year + 1, 1, 1) - timedelta(days=1)
        else:
            self.last_day_month = date(self.today.year, self.today.month + 1, 1) - timedelta(days=1)

    def test_staff_growth_report_month_aggregation(self):
        """Test staff growth report with monthly aggregation"""
        # Arrange: Create test data
        StaffGrowthReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            block=self.block,
            department=self.department,
            num_introductions=5,
            num_returns=2,
            num_recruitment_source=10,
            num_transfers=3,
            num_resignations=1,
        )

        # Add another day's data
        StaffGrowthReport.objects.create(
            report_date=self.first_day_month + timedelta(days=1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            num_introductions=3,
            num_returns=1,
            num_recruitment_source=5,
            num_transfers=2,
            num_resignations=0,
        )

        # Act: Call the API
        url = reverse("hrm:recruitment-reports-staff-growth")
        response = self.client.get(url, {"period_type": "month"})

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        # Verify aggregated values
        report = data[0]
        self.assertEqual(report["period_type"], "month")
        self.assertEqual(report["num_introductions"], 8)  # 5 + 3
        self.assertEqual(report["num_returns"], 3)  # 2 + 1
        self.assertEqual(report["num_recruitment_source"], 15)  # 10 + 5
        self.assertEqual(report["num_transfers"], 5)  # 3 + 2
        self.assertEqual(report["num_resignations"], 1)  # 1 + 0

    def test_recruitment_source_report_nested_structure(self):
        """Test recruitment source report returns nested organizational structure"""
        # Arrange: Create test data
        RecruitmentSourceReport.objects.create(
            report_date=self.today,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_source=self.source_referral,
            num_hires=10,
        )

        RecruitmentSourceReport.objects.create(
            report_date=self.today,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_source=self.source_no_referral,
            num_hires=5,
        )

        # Act: Call the API
        url = reverse("hrm:recruitment-reports-recruitment-source")
        response = self.client.get(url)

        # Assert: Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("sources", data)
        self.assertIn("data", data)
        self.assertIsInstance(data["sources"], list)
        self.assertIsInstance(data["data"], list)

        # Verify sources are listed
        self.assertIn("Employee Referral", data["sources"])
        self.assertIn("Direct Application", data["sources"])

        # Verify nested structure
        self.assertGreater(len(data["data"]), 0)
        branch_data = data["data"][0]
        self.assertEqual(branch_data["type"], "branch")
        self.assertIn("children", branch_data)
        self.assertIn("statistics", branch_data)

    def test_recruitment_channel_report_nested_structure(self):
        """Test recruitment channel report returns nested organizational structure"""
        # Arrange: Create test data
        RecruitmentChannelReport.objects.create(
            report_date=self.today,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_channel=self.channel_marketing,
            num_hires=8,
        )

        RecruitmentChannelReport.objects.create(
            report_date=self.today,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_channel=self.channel_job_website,
            num_hires=12,
        )

        # Act: Call the API
        url = reverse("hrm:recruitment-reports-recruitment-channel")
        response = self.client.get(url)

        # Assert: Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("channels", data)
        self.assertIn("data", data)
        self.assertIsInstance(data["channels"], list)
        self.assertIsInstance(data["data"], list)

        # Verify channels are listed
        self.assertIn("Facebook Ads", data["channels"])
        self.assertIn("VietnamWorks", data["channels"])

    def test_recruitment_cost_report_aggregation(self):
        """Test recruitment cost report with monthly aggregation"""
        # Arrange: Create test data for current month
        month_key = self.first_day_month.strftime("%Y-%m")

        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month_key,
            total_cost=Decimal("5000000.00"),
            num_hires=10,
            avg_cost_per_hire=Decimal("500000.00"),
        )

        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month + timedelta(days=1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            total_cost=Decimal("8000000.00"),
            num_hires=15,
            avg_cost_per_hire=Decimal("533333.33"),
        )

        # Act: Call the API
        url = reverse("hrm:recruitment-reports-recruitment-cost")
        response = self.client.get(url)

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("months", data)
        self.assertIn("data", data)

        # Verify months include Total column
        self.assertIn("Total", data["months"])

        # Verify data structure
        self.assertIsInstance(data["data"], list)
        for source_data in data["data"]:
            self.assertIn("source_type", source_data)
            self.assertIn("months", source_data)
            self.assertIsInstance(source_data["months"], list)
            for month_data in source_data["months"]:
                self.assertIn("total", month_data)
                self.assertIn("count", month_data)
                self.assertIn("avg", month_data)

    def test_hired_candidate_report_month_aggregation(self):
        """Test hired candidate report with monthly aggregation"""
        # Arrange: Create test data
        month_key = self.first_day_month.strftime("%m/%Y")
        week_key = get_week_key_from_date(self.first_day_month)

        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month_key,
            week_key=week_key,
            employee=self.employee,
            num_candidates_hired=5,
            num_experienced=3,
        )

        week_key2 = get_week_key_from_date(self.first_day_month + timedelta(days=1))
        HiredCandidateReport.objects.create(
            report_date=self.first_day_month + timedelta(days=1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            week_key=week_key2,
            num_candidates_hired=10,
            num_experienced=7,
        )

        # Act: Call the API
        url = reverse("hrm:recruitment-reports-hired-candidate")
        response = self.client.get(url, {"period_type": "month"})

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("period_type", data)
        self.assertEqual(data["period_type"], "month")
        self.assertIn("labels", data)
        self.assertIn("data", data)

        # Verify labels include Total
        self.assertIn("Total", data["labels"])

        # Verify data structure includes source types
        self.assertIsInstance(data["data"], list)
        source_types = [item["name"] for item in data["data"]]
        self.assertIn("Referral Source", source_types)
        self.assertIn("Marketing Channel", source_types)

        # Verify referral source has children (employee breakdown)
        referral_data = next(
            item for item in data["data"] if item["type"] == "source_type" and "Referral" in item["name"]
        )
        self.assertIn("children", referral_data)
        if referral_data["children"]:
            self.assertGreater(len(referral_data["children"]), 0)

    def test_hired_candidate_report_week_aggregation(self):
        """Test hired candidate report with weekly aggregation"""
        # Arrange: Create test data for a week
        monday = self.today - timedelta(days=self.today.weekday())
        week_key = get_week_key_from_date(monday)
        month_key = self.first_day_month.strftime("%m/%Y")

        HiredCandidateReport.objects.create(
            report_date=monday,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month_key,
            week_key=week_key,
            employee=self.employee,
            num_candidates_hired=3,
            num_experienced=2,
        )

        week_key2 = get_week_key_from_date(monday + timedelta(days=2))
        HiredCandidateReport.objects.create(
            report_date=monday + timedelta(days=2),
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            week_key=week_key2,
            num_candidates_hired=5,
            num_experienced=3,
        )

        # Act: Call the API with week period type
        url = reverse("hrm:recruitment-reports-hired-candidate")
        response = self.client.get(url, {"period_type": "week"})

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("period_type", data)
        self.assertEqual(data["period_type"], "week")
        self.assertIn("labels", data)
        self.assertIn("data", data)

        # Verify week label format (should contain "Tuần")
        week_labels = [label for label in data["labels"] if "Tuần" in label or label == "Total"]
        self.assertGreater(len(week_labels), 0)

    def test_referral_cost_report_single_month(self):
        """Test referral cost report for a single month"""
        # Arrange: Create test data with referral expenses
        test_request = RecruitmentRequest.objects.create(
            name="Test Request",
            job_description=JobDescription.objects.create(
                title="Test Job",
                responsibility="Test",
                requirement="Test",
                benefit="Test",
                proposed_salary="1000 USD",
            ),
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="1000 USD",
            number_of_positions=1,
        )

        RecruitmentExpense.objects.create(
            date=self.first_day_month,
            recruitment_source=self.source_referral,
            recruitment_channel=self.channel_marketing,
            recruitment_request=test_request,
            referee=self.employee2,
            referrer=self.employee,
            total_cost=Decimal("500000.00"),
            activity="Referral bonus",
        )

        RecruitmentExpense.objects.create(
            date=self.first_day_month + timedelta(days=5),
            recruitment_source=self.source_referral,
            recruitment_channel=self.channel_marketing,
            recruitment_request=test_request,
            referee=self.employee2,
            referrer=self.employee,
            total_cost=Decimal("300000.00"),
            activity="Referral bonus",
        )

        # Act: Call the API
        url = reverse("hrm:recruitment-reports-referral-cost")
        month_param = self.first_day_month.strftime("%m/%Y")
        response = self.client.get(url, {"month": month_param})

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("data", data)
        self.assertIn("summary_total", data)

        # Verify summary total
        expected_total = Decimal("800000.00")
        self.assertEqual(Decimal(str(data["summary_total"])), expected_total)

        # Verify department grouping
        self.assertIsInstance(data["data"], list)
        self.assertGreater(len(data["data"]), 0)
        dept_data = data["data"][0]
        self.assertIn("name", dept_data)
        self.assertIn("items", dept_data)

    def test_staff_growth_report_with_filters(self):
        """Test staff growth report with branch, block, and department filters"""
        # Arrange: Create test data
        StaffGrowthReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            block=self.block,
            department=self.department,
            num_recruitment_source=10,
        )

        # Act: Call API with filters
        url = reverse("hrm:recruitment-reports-staff-growth")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "branch": self.branch.id,
                "block": self.block.id,
                "department": self.department.id,
            },
        )

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertGreater(len(data), 0)

    def test_recruitment_cost_report_date_range_filter(self):
        """Test recruitment cost report with custom date range"""
        # Arrange: Create test data
        start_date = self.first_day_month
        end_date = self.first_day_month + timedelta(days=10)
        month_key = start_date.strftime("%Y-%m")

        RecruitmentCostReport.objects.create(
            report_date=start_date,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            total_cost=Decimal("1000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("200000.00"),
        )

        # Act: Call API with date range
        url = reverse("hrm:recruitment-reports-recruitment-cost")
        response = self.client.get(
            url,
            {
                "from_date": start_date.isoformat(),
                "to_date": end_date.isoformat(),
            },
        )

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("data", data)

    def test_hired_candidate_report_invalid_period_type(self):
        """Test hired candidate report with invalid period type returns error"""
        # Act: Call API with invalid period type
        url = reverse("hrm:recruitment-reports-hired-candidate")
        response = self.client.get(url, {"period_type": "invalid"})

        # Assert: Verify error response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_referral_cost_report_invalid_month_format(self):
        """Test referral cost report with invalid month format returns error"""
        # Act: Call API with invalid month format
        url = reverse("hrm:recruitment-reports-referral-cost")
        response = self.client.get(url, {"month": "2025-10"})  # Wrong format

        # Assert: Verify error response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
