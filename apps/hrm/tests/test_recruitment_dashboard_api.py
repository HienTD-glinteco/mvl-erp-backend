import json
from datetime import date

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
    JobDescription,
    RecruitmentCandidate,
    RecruitmentChannel,
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
            return content["data"]
        return content


class DashboardRealtimeDataAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Dashboard Realtime Data API endpoint"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        RecruitmentCandidate.objects.all().delete()
        RecruitmentRequest.objects.all().delete()
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

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create recruitment source and channel
        self.source = RecruitmentSource.objects.create(name="LinkedIn", code="LI")
        self.channel = RecruitmentChannel.objects.create(name="Job Website", code="JW")

    def test_dashboard_realtime_data(self):
        """Test dashboard realtime data endpoint"""
        # Create open recruitment requests
        RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
            number_of_positions=2,
        )

        RecruitmentRequest.objects.create(
            name="Frontend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
            number_of_positions=1,
        )

        # Create candidates submitted today
        today = date.today()
        RecruitmentCandidate.objects.create(
            name="John Doe",
            citizen_id="123456789012",
            email="john@example.com",
            phone="0123456789",
            recruitment_request=RecruitmentRequest.objects.first(),
            recruitment_source=self.source,
            recruitment_channel=self.channel,
            submitted_date=today,
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        url = reverse("hrm:dashboard-realtime")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Verify KPI data
        self.assertIn("open_positions", data)
        self.assertIn("applicants_today", data)
        self.assertIn("hires_today", data)
        self.assertIn("interviews_today", data)

        self.assertEqual(data["open_positions"], 2)
        self.assertEqual(data["applicants_today"], 1)


class DashboardChartDataAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Dashboard Chart Data API endpoint"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        RecruitmentCandidate.objects.all().delete()
        RecruitmentRequest.objects.all().delete()
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

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create recruitment source and channel
        self.source = RecruitmentSource.objects.create(name="LinkedIn", code="LI")
        self.channel = RecruitmentChannel.objects.create(name="Job Website", code="JW")

        # Create recruitment request
        self.recruitment_request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
            number_of_positions=2,
        )

    def test_dashboard_chart_data(self):
        """Test dashboard chart data endpoint"""
        # Create candidates with various experience levels
        RecruitmentCandidate.objects.create(
            name="John Doe",
            citizen_id="123456789012",
            email="john@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.source,
            recruitment_channel=self.channel,
            submitted_date=date.today(),
            years_of_experience=2,
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        RecruitmentCandidate.objects.create(
            name="Jane Smith",
            citizen_id="123456789013",
            email="jane@example.com",
            phone="0123456780",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.source,
            recruitment_channel=self.channel,
            submitted_date=date.today(),
            years_of_experience=5,
            status=RecruitmentCandidate.Status.HIRED,
            branch=self.branch,
            onboard_date=date.today(),
        )

        url = reverse("hrm:dashboard-charts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Verify chart data structure
        self.assertIn("experience_breakdown", data)
        self.assertIn("source_breakdown", data)
        self.assertIn("channel_breakdown", data)
        self.assertIn("branch_breakdown", data)
        self.assertIn("cost_breakdown", data)
        self.assertIn("hire_ratio", data)

        # Verify experience breakdown
        self.assertIsInstance(data["experience_breakdown"], list)

        # Verify source breakdown
        self.assertIsInstance(data["source_breakdown"], list)

        # Verify hire ratio
        self.assertIn("total_applicants", data["hire_ratio"])
        self.assertIn("total_hires", data["hire_ratio"])
        self.assertIn("hire_ratio", data["hire_ratio"])
        self.assertEqual(data["hire_ratio"]["total_applicants"], 2)
        self.assertEqual(data["hire_ratio"]["total_hires"], 1)
