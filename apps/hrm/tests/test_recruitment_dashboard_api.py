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
        self.assertIn("employees_today", data)

        # We created 2 job descriptions + 1 for candidate + 1 for interview = 4 total
        self.assertEqual(data["open_positions"], 4)
        self.assertEqual(data["applicants_today"], 1)
        self.assertEqual(data["hires_today"], 3)
        self.assertEqual(data["interviews_today"], 1)
        # 1 employee from setUp (default status is ONBOARDING)
        self.assertEqual(data["employees_today"], 1)

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
        self.assertIsInstance(monthly_trends, dict)
        self.assertIn("months", monthly_trends)
        self.assertIn("source_type_names", monthly_trends)
        self.assertIn("data", monthly_trends)
        self.assertIsInstance(monthly_trends["months"], list)
        self.assertIsInstance(monthly_trends["source_type_names"], list)
        self.assertIsInstance(monthly_trends["data"], list)
        if len(monthly_trends["data"]) > 0:
            source_data = monthly_trends["data"][0]
            self.assertIn("type", source_data)
            self.assertIn("name", source_data)
            self.assertIn("statistics", source_data)
            self.assertEqual(source_data["type"], "source_type")
            self.assertIsInstance(source_data["statistics"], list)

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
        # monthly_trends is a dict with empty lists
        self.assertIsInstance(data["monthly_trends"], dict)
        self.assertEqual(len(data["monthly_trends"]["months"]), 0)
        self.assertEqual(len(data["monthly_trends"]["data"]), 0)

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
        # Still has 1 employee from setUp with ONBOARDING status
        self.assertEqual(data["employees_today"], 1)

    def test_realtime_dashboard_total_employees_count(self):
        """Test realtime dashboard counts total employees except RESIGNED"""
        # Arrange: Create employees with different statuses
        # Active employee
        Employee.objects.create(
            fullname="Active Employee",
            username="active_emp",
            email="active@example.com",
            phone="0111111111",
            attendance_code="EMP002",
            citizen_id="001234567890",
            date_of_birth="1990-01-01",
            personal_email="active.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.ACTIVE,
        )

        # Onboarding employee (already have 1 from setUp)
        Employee.objects.create(
            fullname="Onboarding Employee",
            username="onboarding_emp",
            email="onboarding@example.com",
            phone="0222222222",
            attendance_code="EMP003",
            citizen_id="002234567890",
            date_of_birth="1990-01-01",
            personal_email="onboarding.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.ONBOARDING,
        )

        # Resigned employee - should NOT be counted
        Employee.objects.create(
            fullname="Resigned Employee",
            username="resigned_emp",
            email="resigned@example.com",
            phone="0333333333",
            attendance_code="EMP004",
            citizen_id="003234567890",
            date_of_birth="1990-01-01",
            personal_email="resigned.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.RESIGNED,
            resignation_start_date=self.today,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_PERSONAL,
        )

        # Maternity leave employee - should NOT be counted
        Employee.objects.create(
            fullname="Maternity Leave Employee",
            username="maternity_emp",
            email="maternity@example.com",
            phone="0444444444",
            attendance_code="EMP005",
            citizen_id="004234567890",
            date_of_birth="1990-01-01",
            personal_email="maternity.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.MATERNITY_LEAVE,
            resignation_start_date=self.today,
            resignation_end_date=self.today,
        )

        # Unpaid leave employee - should NOT be counted
        Employee.objects.create(
            fullname="Unpaid Leave Employee",
            username="unpaid_emp",
            email="unpaid@example.com",
            phone="0555555555",
            attendance_code="EMP006",
            citizen_id="005234567890",
            date_of_birth="1990-01-01",
            personal_email="unpaid.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.UNPAID_LEAVE,
            resignation_start_date=self.today,
            resignation_end_date=self.today,
        )

        # Act: Call the realtime API
        url = reverse("hrm:recruitment-dashboard-realtime")
        response = self.client.get(url)

        # Assert: Verify total employees except RESIGNEDare counted
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Should NOT count: RESIGNED, MATERNITY_LEAVE, UNPAID_LEAVE
        self.assertEqual(data["employees_today"], 5)

    def test_charts_dashboard_invalid_date_format(self):
        """Test charts dashboard with invalid date format"""
        # Act: Call API with invalid date format
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url, {"from_date": "invalid-date"})

        # Assert: Verify response (DRF may handle invalid dates gracefully or return error)
        # We just check the API doesn't crash
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_cost_by_branches_single_branch_single_month(self):
        """Test cost_by_branches with single branch and single month"""
        # Arrange: Create cost data for one branch and one month
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

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify cost_by_branches structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        self.assertIn("months", cost_by_branches)
        self.assertIn("data", cost_by_branches)

        months = cost_by_branches["months"]
        branches_data = cost_by_branches["data"]

        self.assertEqual(len(months), 1)
        self.assertEqual(months[0], cost_month_key)
        self.assertEqual(len(branches_data), 1)

        branch_data = branches_data[0]
        self.assertEqual(branch_data["type"], "branch")
        self.assertEqual(branch_data["name"], "Hanoi Branch")
        self.assertIn("statistics", branch_data)

        statistics = branch_data["statistics"]
        self.assertEqual(len(statistics), 1)
        self.assertEqual(statistics[0]["total_cost"], 10000000.0)
        self.assertEqual(statistics[0]["total_hires"], 5)
        self.assertEqual(statistics[0]["avg_cost"], 2000000.0)

    def test_cost_by_branches_multiple_branches_single_month(self):
        """Test cost_by_branches with multiple branches in single month"""
        # Arrange: Create second branch
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        cost_month_key = self.first_day_month.strftime("%Y-%m")

        # Branch 1 cost data
        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=cost_month_key,
            total_cost=Decimal("15000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("3000000.00"),
        )

        # Branch 2 cost data
        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=branch2,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=cost_month_key,
            total_cost=Decimal("8000000.00"),
            num_hires=4,
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify both branches are in result
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        branches_data = cost_by_branches["data"]
        months = cost_by_branches["months"]

        self.assertEqual(len(months), 1)
        self.assertEqual(len(branches_data), 2)

        # Verify branches are sorted by name
        branch_names = [item["name"] for item in branches_data]
        self.assertEqual(branch_names, ["HCMC Branch", "Hanoi Branch"])

        # Verify each branch has correct statistics
        hcmc_branch = next(item for item in branches_data if item["name"] == "HCMC Branch")
        hanoi_branch = next(item for item in branches_data if item["name"] == "Hanoi Branch")

        self.assertEqual(len(hcmc_branch["statistics"]), 1)
        self.assertEqual(hcmc_branch["statistics"][0]["total_cost"], 8000000.0)
        self.assertEqual(hcmc_branch["statistics"][0]["total_hires"], 4)

        self.assertEqual(len(hanoi_branch["statistics"]), 1)
        self.assertEqual(hanoi_branch["statistics"][0]["total_cost"], 15000000.0)
        self.assertEqual(hanoi_branch["statistics"][0]["total_hires"], 5)

    def test_cost_by_branches_multiple_months(self):
        """Test cost_by_branches with multiple months"""
        # Arrange: Create data for two months
        month1 = self.first_day_month
        month1_key = month1.strftime("%Y-%m")

        if month1.month == 1:
            month2 = month1.replace(year=month1.year - 1, month=12)
        else:
            month2 = month1.replace(month=month1.month - 1)
        month2_key = month2.strftime("%Y-%m")

        # Month 1 data
        RecruitmentCostReport.objects.create(
            report_date=month1,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month1_key,
            total_cost=Decimal("10000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        # Month 2 data
        RecruitmentCostReport.objects.create(
            report_date=month2,
            branch=self.branch,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month2_key,
            total_cost=Decimal("6000000.00"),
            num_hires=3,
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        # Act: Call the charts API with custom date range
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(
            url,
            {
                "from_date": month2.isoformat(),
                "to_date": month1.isoformat(),
            },
        )

        # Assert: Verify branch has statistics for both months
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        branches_data = cost_by_branches["data"]
        months = cost_by_branches["months"]

        self.assertEqual(len(months), 2)
        self.assertEqual(len(branches_data), 1)

        branch_data = branches_data[0]
        statistics = branch_data["statistics"]
        self.assertEqual(len(statistics), 2)  # Two months

        # Verify statistics are ordered by month_key
        self.assertEqual(statistics[0]["total_cost"], 6000000.0)
        self.assertEqual(statistics[0]["total_hires"], 3)
        self.assertEqual(statistics[1]["total_cost"], 10000000.0)
        self.assertEqual(statistics[1]["total_hires"], 5)

    def test_cost_by_branches_missing_month_data_fills_default(self):
        """Test cost_by_branches fills default values for missing month-branch combinations"""
        # Arrange: Create two branches and data for only one branch in a month
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        month1 = self.first_day_month
        month1_key = month1.strftime("%Y-%m")

        if month1.month == 1:
            month2 = month1.replace(year=month1.year - 1, month=12)
        else:
            month2 = month1.replace(month=month1.month - 1)
        month2_key = month2.strftime("%Y-%m")

        # Branch 1 has data for both months
        RecruitmentCostReport.objects.create(
            report_date=month1,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month1_key,
            total_cost=Decimal("10000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        RecruitmentCostReport.objects.create(
            report_date=month2,
            branch=self.branch,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=month2_key,
            total_cost=Decimal("8000000.00"),
            num_hires=4,
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        # Branch 2 has data only for month 1
        RecruitmentCostReport.objects.create(
            report_date=month1,
            branch=branch2,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=month1_key,
            total_cost=Decimal("5000000.00"),
            num_hires=2,
            avg_cost_per_hire=Decimal("2500000.00"),
        )

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(
            url,
            {
                "from_date": month2.isoformat(),
                "to_date": month1.isoformat(),
            },
        )

        # Assert: Verify both branches have same number of statistics (with defaults)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        branches_data = cost_by_branches["data"]
        months = cost_by_branches["months"]

        self.assertEqual(len(months), 2)
        self.assertEqual(len(branches_data), 2)

        # Both branches should have 2 statistics items (one per month)
        for branch in branches_data:
            self.assertEqual(len(branch["statistics"]), 2)

        # HCMC Branch should have default values for month2
        hcmc_branch = next(item for item in branches_data if item["name"] == "HCMC Branch")
        self.assertEqual(hcmc_branch["statistics"][0]["total_cost"], 0.0)
        self.assertEqual(hcmc_branch["statistics"][0]["total_hires"], 0)
        self.assertEqual(hcmc_branch["statistics"][0]["avg_cost"], 0.0)
        self.assertEqual(hcmc_branch["statistics"][1]["total_cost"], 5000000.0)
        self.assertEqual(hcmc_branch["statistics"][1]["total_hires"], 2)

    def test_cost_by_branches_zero_hires_division(self):
        """Test cost_by_branches handles zero hires (division by zero)"""
        # Arrange: Create data with zero hires
        cost_month_key = self.first_day_month.strftime("%Y-%m")

        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=cost_month_key,
            total_cost=Decimal("5000000.00"),
            num_hires=0,  # Zero hires
            avg_cost_per_hire=Decimal("0.00"),
        )

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify avg_cost is 0 when no hires
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        branches_data = cost_by_branches["data"]
        self.assertEqual(len(branches_data), 1)

        statistics = branches_data[0]["statistics"]
        self.assertEqual(statistics[0]["total_hires"], 0)
        self.assertEqual(statistics[0]["avg_cost"], 0.0)

    def test_cost_by_branches_aggregates_multiple_source_types(self):
        """Test cost_by_branches aggregates data from multiple source types in same month"""
        # Arrange: Create multiple source types for same branch/month
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

        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=cost_month_key,
            total_cost=Decimal("5000000.00"),
            num_hires=5,
            avg_cost_per_hire=Decimal("1000000.00"),
        )

        # Act: Call the charts API
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify aggregation
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        branches_data = cost_by_branches["data"]
        self.assertEqual(len(branches_data), 1)

        statistics = branches_data[0]["statistics"]
        self.assertEqual(len(statistics), 1)

        # Total cost should be sum: 10M + 5M = 15M
        self.assertEqual(statistics[0]["total_cost"], 15000000.0)
        # Total hires should be sum: 5 + 5 = 10
        self.assertEqual(statistics[0]["total_hires"], 10)
        # Average cost should be: 15M / 10 = 1.5M
        self.assertEqual(statistics[0]["avg_cost"], 1500000.0)

    def test_cost_by_branches_empty_data(self):
        """Test cost_by_branches returns empty list when no data"""
        # Act: Call the charts API with no cost data
        url = reverse("hrm:recruitment-dashboard-charts")
        response = self.client.get(url)

        # Assert: Verify empty structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        cost_by_branches = data["cost_by_branches"]
        self.assertIn("months", cost_by_branches)
        self.assertIn("data", cost_by_branches)
        self.assertEqual(len(cost_by_branches["data"]), 0)
        self.assertEqual(len(cost_by_branches["months"]), 0)
