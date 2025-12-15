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

        # Create employee
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            phone="0123456789",
            attendance_code="EMP001",
            citizen_id="000123456789",
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

        # Hires today: three hired candidates on open requests
        hires_request = RecruitmentRequest.objects.create(
            name="Hires Request",
            job_description=JobDescription.objects.first(),
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2200 USD",
            number_of_positions=3,
        )

        RecruitmentCandidate.objects.create(
            name="Hired Candidate 1",
            email="hire1@example.com",
            phone="0999999991",
            branch=self.branch,
            recruitment_source=self.source_no_referral,
            recruitment_channel=self.channel_marketing,
            recruitment_request=hires_request,
            submitted_date=self.today,
            onboard_date=self.today,
            status=RecruitmentCandidate.Status.HIRED,
            citizen_id="0999999991",
        )
        RecruitmentCandidate.objects.create(
            name="Hired Candidate 2",
            email="hire2@example.com",
            phone="0999999992",
            branch=self.branch,
            recruitment_source=self.source_no_referral,
            recruitment_channel=self.channel_marketing,
            recruitment_request=hires_request,
            submitted_date=self.today,
            onboard_date=self.today,
            status=RecruitmentCandidate.Status.HIRED,
            citizen_id="0999999992",
        )
        RecruitmentCandidate.objects.create(
            name="Hired Candidate 3",
            email="hire3@example.com",
            phone="0999999993",
            branch=self.branch,
            recruitment_source=self.source_no_referral,
            recruitment_channel=self.channel_marketing,
            recruitment_request=hires_request,
            submitted_date=self.today,
            onboard_date=self.today,
            status=RecruitmentCandidate.Status.HIRED,
            citizen_id="0999999993",
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
        self.assertIn("employees_today", data)

        # We created 2 job descriptions + 1 for candidate + 1 for interview + 3 for hires = 7 total open positions
        self.assertEqual(data["open_positions"], 7)
        self.assertEqual(data["applicants_today"], 1)
        self.assertEqual(data["hires_today"], 3)
        self.assertEqual(data["interviews_today"], 1)
        # 1 employee from setUp (default status is ONBOARDING)
        self.assertEqual(data["employees_today"], 1)


class RecruitmentDashboardIndividualChartsAPITest(TransactionTestCase, APITestMixin):
    """Test cases for individual chart endpoints in Recruitment Dashboard"""

    def setUp(self):
        """Set up test data"""
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

        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            phone="0123456789",
            attendance_code="EMP001",
            citizen_id="000123456789",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Set up test dates
        self.today = date.today()
        self.first_day_month = self.today.replace(day=1)
        if self.today.month == 12:
            self.last_day_month = date(self.today.year + 1, 1, 1) - timedelta(days=1)
        else:
            self.last_day_month = date(self.today.year, self.today.month + 1, 1) - timedelta(days=1)

    def test_experience_breakdown_chart_endpoint(self):
        """Test experience breakdown chart endpoint"""
        # Arrange: Create test data
        month_key = self.first_day_month.strftime("%m/%Y")

        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=20,
            num_experienced=12,
        )

        # Act: Call the experience breakdown API
        url = reverse("hrm:recruitment-dashboard-experience-breakdown-chart")
        response = self.client.get(url)

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check for date fields
        self.assertIn("report_from_date", data)
        self.assertIn("report_to_date", data)
        self.assertIn("data", data)

        chart_data = data["data"]
        self.assertIsInstance(chart_data, list)
        self.assertEqual(len(chart_data), 2)

        labels = [item["label"] for item in chart_data]
        self.assertIn("Experienced", labels)
        self.assertIn("Inexperienced", labels)

        experienced = next(item for item in chart_data if "Experienced" in item["label"])
        inexperienced = next(item for item in chart_data if "Inexperienced" in item["label"])

        self.assertEqual(experienced["count"], 12)
        self.assertEqual(experienced["percentage"], 60.0)
        self.assertEqual(inexperienced["count"], 8)
        self.assertEqual(inexperienced["percentage"], 40.0)

    def test_branch_breakdown_chart_endpoint(self):
        """Test branch breakdown chart endpoint"""
        # Arrange: Create test data for multiple branches
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        month_key = self.first_day_month.strftime("%m/%Y")

        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=10,
            num_experienced=5,
        )

        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=branch2,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=15,
            num_experienced=8,
        )

        # Act: Call the branch breakdown API
        url = reverse("hrm:recruitment-dashboard-branch-breakdown-chart")
        response = self.client.get(url)

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check for date fields
        self.assertIn("report_from_date", data)
        self.assertIn("report_to_date", data)
        self.assertIn("data", data)

        chart_data = data["data"]
        self.assertIsInstance(chart_data, list)
        self.assertEqual(len(chart_data), 2)

        for item in chart_data:
            self.assertIn("branch_name", item)
            self.assertIn("count", item)
            self.assertIn("percentage", item)

        total_hires = sum(item["count"] for item in chart_data)
        self.assertEqual(total_hires, 25)

    def test_cost_breakdown_chart_endpoint(self):
        """Test cost breakdown chart endpoint"""
        # Arrange: Create cost data
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

        # Act: Call the cost breakdown API
        url = reverse("hrm:recruitment-dashboard-cost-breakdown-chart")
        response = self.client.get(url)

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check for date fields
        self.assertIn("report_from_date", data)
        self.assertIn("report_to_date", data)
        self.assertIn("data", data)

        chart_data = data["data"]
        self.assertIsInstance(chart_data, list)
        self.assertGreater(len(chart_data), 0)

        for item in chart_data:
            self.assertIn("source_type", item)
            self.assertIn("total_cost", item)
            self.assertIn("percentage", item)

    def test_cost_by_branches_chart_endpoint(self):
        """Test cost by branches chart endpoint"""
        # Arrange: Create cost data
        cost_month_key = self.first_day_month.strftime("%Y-%m")

        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=cost_month_key,
            total_cost=Decimal("10000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        # Act: Call the cost by branches API
        url = reverse("hrm:recruitment-dashboard-cost-by-branches-chart")
        response = self.client.get(url)

        # Assert: Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check for date fields
        self.assertIn("report_from_date", data)
        self.assertIn("report_to_date", data)
        self.assertIn("data", data)

        chart_data = data["data"]
        self.assertIsInstance(chart_data, dict)
        self.assertIn("months", chart_data)
        self.assertIn("data", chart_data)

        months = chart_data["months"]
        branches_data = chart_data["data"]

        self.assertEqual(len(months), 1)
        self.assertEqual(months[0], cost_month_key)
        self.assertEqual(len(branches_data), 1)

        branch_data = branches_data[0]
        self.assertEqual(branch_data["type"], "branch")
        self.assertEqual(branch_data["name"], "Hanoi Branch")
        self.assertIn("statistics", branch_data)

    def test_source_type_breakdown_chart_endpoint(self):
        """Test source type breakdown chart endpoint"""
        # Arrange: Create cost data with different source types
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

        # Act: Call the source type breakdown API
        url = reverse("hrm:recruitment-dashboard-source-type-breakdown-chart")
        response = self.client.get(url)

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check for date fields
        self.assertIn("report_from_date", data)
        self.assertIn("report_to_date", data)
        self.assertIn("data", data)

        chart_data = data["data"]
        self.assertIsInstance(chart_data, list)
        self.assertGreater(len(chart_data), 0)

        for item in chart_data:
            self.assertIn("source_type", item)
            self.assertIn("count", item)
            self.assertIn("percentage", item)

    def test_monthly_trends_chart_endpoint(self):
        """Test monthly trends chart endpoint"""
        # Arrange: Create data for multiple months
        month1 = self.first_day_month
        month1_key = month1.strftime("%Y-%m")

        if month1.month == 1:
            month2 = month1.replace(year=month1.year - 1, month=12)
        else:
            month2 = month1.replace(month=month1.month - 1)
        month2_key = month2.strftime("%Y-%m")

        RecruitmentCostReport.objects.create(
            report_date=month1,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month1_key,
            total_cost=Decimal("10000000.00"),
            num_hires=10,
            avg_cost_per_hire=Decimal("1000000.00"),
        )

        RecruitmentCostReport.objects.create(
            report_date=month2,
            branch=self.branch,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month2_key,
            total_cost=Decimal("6000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("1200000.00"),
        )

        # Act: Call the monthly trends API with custom date range
        url = reverse("hrm:recruitment-dashboard-monthly-trends-chart")
        response = self.client.get(
            url,
            {
                "from_date": month2.isoformat(),
                "to_date": month1.isoformat(),
            },
        )

        # Assert: Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check for date fields
        self.assertIn("report_from_date", data)
        self.assertIn("report_to_date", data)
        self.assertIn("data", data)

        chart_data = data["data"]
        self.assertIsInstance(chart_data, dict)
        self.assertIn("months", chart_data)
        self.assertIn("source_type_names", chart_data)
        self.assertIn("data", chart_data)

        self.assertIsInstance(chart_data["months"], list)
        self.assertIsInstance(chart_data["source_type_names"], list)
        self.assertIsInstance(chart_data["data"], list)

        if len(chart_data["data"]) > 0:
            source_data = chart_data["data"][0]
            self.assertIn("type", source_data)
            self.assertIn("name", source_data)
            self.assertIn("statistics", source_data)
            self.assertEqual(source_data["type"], "source_type")
            self.assertIsInstance(source_data["statistics"], list)

    def test_individual_chart_endpoints_with_custom_date_range(self):
        """Test all individual chart endpoints accept custom date range"""
        # Arrange: Create test data
        start_date = self.first_day_month
        end_date = self.first_day_month + timedelta(days=15)
        month_key = start_date.strftime("%m/%Y")
        cost_month_key = start_date.strftime("%Y-%m")

        HiredCandidateReport.objects.create(
            report_date=start_date,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month_key,
            num_candidates_hired=8,
            num_experienced=5,
        )

        RecruitmentCostReport.objects.create(
            report_date=start_date,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=cost_month_key,
            total_cost=Decimal("3000000.00"),
            num_hires=8,
            avg_cost_per_hire=Decimal("375000.00"),
        )

        # Test all endpoints with custom date range
        date_params = {
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
        }

        endpoints = [
            "hrm:recruitment-dashboard-experience-breakdown-chart",
            "hrm:recruitment-dashboard-branch-breakdown-chart",
            "hrm:recruitment-dashboard-cost-breakdown-chart",
            "hrm:recruitment-dashboard-cost-by-branches-chart",
            "hrm:recruitment-dashboard-source-type-breakdown-chart",
            "hrm:recruitment-dashboard-monthly-trends-chart",
        ]

        for endpoint_name in endpoints:
            url = reverse(endpoint_name)
            response = self.client.get(url, date_params)
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Endpoint {endpoint_name} should return 200 with custom date range",
            )

    def test_individual_chart_endpoints_without_filters(self):
        """Test all individual chart endpoints work without filters (use defaults)"""
        # No data needed - testing empty responses

        endpoints = [
            "hrm:recruitment-dashboard-experience-breakdown-chart",
            "hrm:recruitment-dashboard-branch-breakdown-chart",
            "hrm:recruitment-dashboard-cost-breakdown-chart",
            "hrm:recruitment-dashboard-cost-by-branches-chart",
            "hrm:recruitment-dashboard-source-type-breakdown-chart",
            "hrm:recruitment-dashboard-monthly-trends-chart",
        ]

        for endpoint_name in endpoints:
            url = reverse(endpoint_name)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Endpoint {endpoint_name} should return 200 without filters",
            )
