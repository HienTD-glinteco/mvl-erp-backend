import json
from datetime import date, datetime, time, timedelta
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
    InterviewSchedule,
    JobDescription,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentCostReport,
    RecruitmentRequest,
    RecruitmentSource,
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


class RecruitmentDashboardAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Recruitment Dashboard API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        InterviewSchedule.objects.all().delete()
        RecruitmentCandidate.objects.all().delete()
        HiredCandidateReport.objects.all().delete()
        RecruitmentCostReport.objects.all().delete()
        JobDescription.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        RecruitmentChannel.objects.all().delete()
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

        # Create employee
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

        # Set up test dates
        self.today = date.today()
        self.first_day_month = self.today.replace(day=1)
        if self.today.month == 12:
            self.last_day_month = date(self.today.year + 1, 1, 1) - timedelta(days=1)
        else:
            self.last_day_month = date(self.today.year, self.today.month + 1, 1) - timedelta(days=1)

    def test_realtime_dashboard_basic(self):
        """Test realtime dashboard endpoint returns correct KPIs"""
        # Arrange: Create test data for today
        # Open positions
        RecruitmentRequest.objects.create(
            name="Test Request 1",
            job_description=JobDescription.objects.create(
                title="Python Developer",
                position_title="Senior Python Developer",
                responsibility="Develop backend",
                requirement="Python experience",
                benefit="Good salary",
                proposed_salary="2000 USD",
            ),
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000 USD",
            number_of_positions=1,
        )

        RecruitmentRequest.objects.create(
            name="Test Request 2",
            job_description=JobDescription.objects.create(
                title="Frontend Developer",
                position_title="Senior Frontend Developer",
                responsibility="Develop UI",
                requirement="React experience",
                benefit="Good salary",
                proposed_salary="1800 USD",
            ),
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="1800 USD",
            number_of_positions=1,
        )

        # Applicants today
        test_recruitment_request = RecruitmentRequest.objects.create(
            name="Test Request for Candidate",
            job_description=JobDescription.objects.first(),
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000 USD",
            number_of_positions=1,
        )

        RecruitmentCandidate.objects.create(
            name="Test Candidate 1",
            email="candidate1@example.com",
            phone="0987654321",
            branch=self.branch,
            recruitment_source=self.source_no_referral,
            recruitment_channel=self.channel_marketing,
            recruitment_request=test_recruitment_request,
            submitted_date=self.today,
        )

        # Hires today
        month_key = self.today.strftime("%m/%Y")
        HiredCandidateReport.objects.create(
            report_date=self.today,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=3,
            num_experienced=2,
        )

        # Interviews today
        interview_time = datetime.combine(self.today, time(10, 0))
        InterviewSchedule.objects.create(
            recruitment_request=RecruitmentRequest.objects.create(
                name="Test Request",
                job_description=JobDescription.objects.first(),
                department=self.department,
                proposer=self.employee,
                recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
                status=RecruitmentRequest.Status.OPEN,
                proposed_salary="2000 USD",
                number_of_positions=1,
            ),
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            time=interview_time,
            location="Office",
            title="Test Interview",
        )

        # Act: Call the realtime dashboard API
        url = reverse("hrm:recruitment-dashboard-realtime")
        response = self.client.get(url)

        # Assert: Verify response structure and values
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("open_positions", data)
        self.assertIn("applicants_today", data)
        self.assertIn("hires_today", data)
        self.assertIn("interviews_today", data)

        # We created 2 job descriptions + 1 for candidate + 1 for interview = 4 total
        self.assertEqual(data["open_positions"], 4)
        self.assertEqual(data["applicants_today"], 1)
        self.assertEqual(data["hires_today"], 3)
        self.assertEqual(data["interviews_today"], 1)

    def test_charts_dashboard_default_date_range(self):
        """Test charts dashboard with default (current month) date range"""
        # Arrange: Create test data for current month
        month_key = self.first_day_month.strftime("%m/%Y")

        # Experience breakdown data
        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=10,
            num_experienced=6,
        )

        # Branch breakdown data
        HiredCandidateReport.objects.create(
            report_date=self.first_day_month + timedelta(days=1),
            branch=self.branch,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month_key,
            num_candidates_hired=5,
            num_experienced=3,
        )

        # Cost breakdown data
        cost_month_key = self.first_day_month.strftime("%Y-%m")
        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=cost_month_key,
            total_cost=Decimal("5000000.00"),
            num_hires=10,
            avg_cost_per_hire=Decimal("500000.00"),
        )

        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=cost_month_key,
            total_cost=Decimal("2000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("400000.00"),
        )

        # Act: Call the charts dashboard API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("experience_breakdown", data)
        self.assertIn("branch_breakdown", data)
        self.assertIn("cost_breakdown", data)
        self.assertIn("source_type_breakdown", data)
        self.assertIn("monthly_trends", data)

        # Verify experience breakdown
        exp_breakdown = data["experience_breakdown"]
        self.assertEqual(len(exp_breakdown), 2)  # Experienced and Inexperienced
        labels = [item["label"] for item in exp_breakdown]
        self.assertIn("Experienced", labels)
        self.assertIn("Inexperienced", labels)

        # Verify cost breakdown
        cost_breakdown = data["cost_breakdown"]
        self.assertGreater(len(cost_breakdown), 0)
        for item in cost_breakdown:
            self.assertIn("source_type", item)
            self.assertIn("total_cost", item)
            self.assertIn("percentage", item)

        # Verify source type breakdown
        source_breakdown = data["source_type_breakdown"]
        self.assertGreater(len(source_breakdown), 0)
        for item in source_breakdown:
            self.assertIn("source_type", item)
            self.assertIn("count", item)
            self.assertIn("percentage", item)

        # Verify monthly trends
        monthly_trends = data["monthly_trends"]
        self.assertIsInstance(monthly_trends, list)
        if len(monthly_trends) > 0:
            trend = monthly_trends[0]
            self.assertIn("month", trend)
            self.assertIn("referral_source", trend)
            self.assertIn("marketing_channel", trend)
            self.assertIn("job_website_channel", trend)
            self.assertIn("recruitment_department_source", trend)
            self.assertIn("returning_employee", trend)

    def test_charts_dashboard_custom_date_range(self):
        """Test charts dashboard with custom date range"""
        # Arrange: Create test data
        start_date = self.first_day_month
        end_date = self.first_day_month + timedelta(days=15)
        month_key = start_date.strftime("%m/%Y")

        HiredCandidateReport.objects.create(
            report_date=start_date,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=8,
            num_experienced=5,
        )

        # Act: Call API with custom date range
        url = reverse("hrm:recruitment-dashboard-charts")
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
        self.assertIn("experience_breakdown", data)
        self.assertIn("monthly_trends", data)

    def test_charts_dashboard_branch_breakdown(self):
        """Test charts dashboard branch breakdown calculation"""
        # Arrange: Create data for multiple branches
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        month_key = self.first_day_month.strftime("%m/%Y")

        # Branch 1 hires
        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=10,
            num_experienced=5,
        )

        # Branch 2 hires
        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=branch2,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=15,
            num_experienced=8,
        )

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify branch breakdown
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        branch_breakdown = data["branch_breakdown"]
        self.assertEqual(len(branch_breakdown), 2)

        # Verify percentages
        total_hires = sum(item["count"] for item in branch_breakdown)
        self.assertEqual(total_hires, 25)  # 10 + 15

        for item in branch_breakdown:
            expected_percentage = round((item["count"] / total_hires * 100), 1)
            self.assertEqual(item["percentage"], expected_percentage)

    def test_charts_dashboard_experience_breakdown_percentages(self):
        """Test experience breakdown percentage calculation"""
        # Arrange: Create mixed experience data
        month_key = self.first_day_month.strftime("%m/%Y")

        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=20,
            num_experienced=12,  # 60% experienced, 40% inexperienced
        )

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify percentages
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        exp_breakdown = data["experience_breakdown"]
        experienced = next(item for item in exp_breakdown if "Experienced" in item["label"])
        inexperienced = next(item for item in exp_breakdown if "Inexperienced" in item["label"])

        self.assertEqual(experienced["count"], 12)
        self.assertEqual(experienced["percentage"], 60.0)
        self.assertEqual(inexperienced["count"], 8)
        self.assertEqual(inexperienced["percentage"], 40.0)

    def test_charts_dashboard_empty_data(self):
        """Test charts dashboard with no data returns empty structures"""
        # Act: Call the charts API with no data
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify response has correct structure even with no data
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("experience_breakdown", data)
        self.assertIn("branch_breakdown", data)
        self.assertIn("cost_breakdown", data)
        self.assertIn("source_type_breakdown", data)
        self.assertIn("monthly_trends", data)

        # Verify lists are empty
        self.assertEqual(len(data["experience_breakdown"]), 2)  # Always has 2 categories
        self.assertEqual(len(data["branch_breakdown"]), 0)
        self.assertEqual(len(data["cost_breakdown"]), 0)
        self.assertEqual(len(data["source_type_breakdown"]), 0)
        self.assertEqual(len(data["monthly_trends"]), 0)

    def test_realtime_dashboard_no_data(self):
        """Test realtime dashboard with no data returns zeros"""
        # Act: Call the realtime API with no data
        url = reverse("hrm:recruitment-dashboard-realtime")
        response = self.client.get(url)

        # Assert: Verify response has zeros
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["open_positions"], 0)
        self.assertEqual(data["applicants_today"], 0)
        self.assertEqual(data["hires_today"], 0)
        self.assertEqual(data["interviews_today"], 0)

    def test_charts_dashboard_invalid_date_format(self):
        """Test charts dashboard with invalid date format"""
        # Act: Call API with invalid date format
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url, {"from_date": "invalid-date"})

        # Assert: Verify response (DRF may handle invalid dates gracefully or return error)
        # We just check the API doesn't crash
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
