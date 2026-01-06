import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Branch,
    HiredCandidateReport,
    InterviewCandidate,
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


@pytest.mark.django_db
class TestRecruitmentDashboardAPI(APITestMixin):
    """Test cases for Recruitment Dashboard API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block, department, employee):
        """Set up test data"""
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        self.department = department
        self.employee = employee

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

        recruitment_candidate = RecruitmentCandidate.objects.create(
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
        interview_schedule = InterviewSchedule.objects.create(
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
        InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=interview_schedule,
            interview_time=interview_time,
        )

        # Act: Call the realtime dashboard API
        url = reverse("hrm:recruitment-dashboard-realtime")
        response = self.client.get(url)

        # Assert: Verify response structure and values
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "open_positions" in data
        assert "applicants_today" in data
        assert "hires_today" in data
        assert "interviews_today" in data
        assert "employees_today" in data

        # We created 2 job descriptions + 1 for candidate + 1 for interview = 4 total
        assert data["open_positions"] == 4
        assert data["applicants_today"] == 1
        assert data["hires_today"] == 3
        assert data["interviews_today"] == 1
        # 1 employee from fixture (default status is ACTIVE in conftest or wherever, wait, conftest uses ONBOARDING by default for dummy?)
        # Let's check Employee status.
        assert data["employees_today"] == 1


@pytest.mark.django_db
class TestRecruitmentDashboardIndividualChartsAPI(APITestMixin):
    """Test cases for individual chart endpoints in Recruitment Dashboard"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block, department, employee):
        """Set up test data"""
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        self.department = department
        self.employee = employee

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check for date fields
        assert "report_from_date" in data
        assert "report_to_date" in data
        assert "data" in data

        chart_data = data["data"]
        assert isinstance(chart_data, list)
        assert len(chart_data) == 2

        labels = [item["label"] for item in chart_data]
        assert "Experienced" in labels
        assert "Inexperienced" in labels

        experienced = next(item for item in chart_data if "Experienced" in item["label"])
        inexperienced = next(item for item in chart_data if "Inexperienced" in item["label"])

        assert experienced["count"] == 12
        assert experienced["percentage"] == 60.0
        assert inexperienced["count"] == 8
        assert inexperienced["percentage"] == 40.0

    def test_branch_breakdown_chart_endpoint(self):
        """Test branch breakdown chart endpoint"""
        # Arrange: Create test data for multiple branches
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.branch.province,
            administrative_unit=self.branch.administrative_unit,
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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check for date fields
        assert "report_from_date" in data
        assert "report_to_date" in data
        assert "data" in data

        chart_data = data["data"]
        assert isinstance(chart_data, list)
        assert len(chart_data) == 2

        for item in chart_data:
            assert "branch_name" in item
            assert "count" in item
            assert "percentage" in item

        total_hires = sum(item["count"] for item in chart_data)
        assert total_hires == 25

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check for date fields
        assert "report_from_date" in data
        assert "report_to_date" in data
        assert "data" in data

        chart_data = data["data"]
        assert isinstance(chart_data, list)
        assert len(chart_data) > 0

        for item in chart_data:
            assert "source_type" in item
            assert "total_cost" in item
            assert "percentage" in item

    def test_cost_by_branches_chart_endpoint(self):
        """Test cost by branches chart endpoint.

        Verifies that avg_cost is calculated as:
        total_cost / num_candidates_hired (from HiredCandidateReport)
        NOT total_cost / num_hires (from RecruitmentCostReport)
        """
        # Arrange: Create cost data
        cost_month_key = self.first_day_month.strftime("%Y-%m")
        hired_month_key = self.first_day_month.strftime("%m/%Y")

        # Create RecruitmentCostReport with total_cost=10,000,000 and num_hires=5
        RecruitmentCostReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=cost_month_key,
            total_cost=Decimal("10000000.00"),
            num_hires=5,  # This should NOT be used for avg_cost calculation
            avg_cost_per_hire=Decimal("2000000.00"),
        )

        # Create HiredCandidateReport with num_candidates_hired=2
        # This SHOULD be used for avg_cost calculation: 10,000,000 / 2 = 5,000,000
        HiredCandidateReport.objects.create(
            report_date=self.first_day_month,
            branch=self.branch,
            source_type=RecruitmentSourceType.MARKETING_CHANNEL.value,
            month_key=hired_month_key,
            num_candidates_hired=2,  # This should be used for avg_cost calculation
            num_experienced=1,
        )

        # Act: Call the cost by branches API
        url = reverse("hrm:recruitment-dashboard-cost-by-branches-chart")
        response = self.client.get(url)

        # Assert: Verify response structure
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check for date fields
        assert "report_from_date" in data
        assert "report_to_date" in data
        assert "data" in data

        chart_data = data["data"]
        assert isinstance(chart_data, dict)
        assert "months" in chart_data
        assert "data" in chart_data

        months = chart_data["months"]
        branches_data = chart_data["data"]

        assert len(months) == 1
        assert months[0] == cost_month_key
        assert len(branches_data) == 1

        branch_data = branches_data[0]
        assert branch_data["type"] == "branch"
        assert branch_data["name"] == self.branch.name
        assert "statistics" in branch_data

        # Verify avg_cost calculation uses num_candidates_hired (2), not num_hires (5)
        # Expected: 10,000,000 / 2 = 5,000,000
        stats = branch_data["statistics"][0]
        assert stats["total_cost"] == 10000000.00
        assert stats["total_hires"] == 2  # From HiredCandidateReport
        assert stats["avg_cost"] == 5000000.00  # 10,000,000 / 2

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check for date fields
        assert "report_from_date" in data
        assert "report_to_date" in data
        assert "data" in data

        chart_data = data["data"]
        assert isinstance(chart_data, list)
        assert len(chart_data) > 0

        for item in chart_data:
            assert "source_type" in item
            assert "count" in item
            assert "percentage" in item

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check for date fields
        assert "report_from_date" in data
        assert "report_to_date" in data
        assert "data" in data

        chart_data = data["data"]
        assert isinstance(chart_data, dict)
        assert "months" in chart_data
        assert "source_type_names" in chart_data
        assert "data" in chart_data

        assert isinstance(chart_data["months"], list)
        assert isinstance(chart_data["source_type_names"], list)
        assert isinstance(chart_data["data"], list)

        if len(chart_data["data"]) > 0:
            source_data = chart_data["data"][0]
            assert "type" in source_data
            assert "name" in source_data
            assert "statistics" in source_data
            assert source_data["type"] == "source_type"
            assert isinstance(source_data["statistics"], list)

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
            assert response.status_code == status.HTTP_200_OK, (
                f"Endpoint {endpoint_name} should return 200 with custom date range"
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
            assert response.status_code == status.HTTP_200_OK, (
                f"Endpoint {endpoint_name} should return 200 without filters"
            )
