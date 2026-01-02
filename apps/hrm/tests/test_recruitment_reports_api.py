import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
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


@pytest.mark.django_db
class TestRecruitmentReportsAPI(APITestMixin):
    """Test cases for Recruitment Reports API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block, department, employee):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        self.department = department
        self.employee = employee

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify aggregated values
        report = data[0]
        assert report["period_type"] == "month"
        assert report["num_introductions"] == 8  # 5 + 3
        assert report["num_returns"] == 3  # 2 + 1
        assert report["num_recruitment_source"] == 15  # 10 + 5
        assert report["num_transfers"] == 5  # 3 + 2
        assert report["num_resignations"] == 1  # 1 + 0

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "sources" in data
        assert "data" in data
        assert isinstance(data["sources"], list)
        assert isinstance(data["data"], list)

        # Verify sources are listed
        assert "Employee Referral" in data["sources"]
        assert "Direct Application" in data["sources"]

        # Verify nested structure
        assert len(data["data"]) > 0
        branch_data = data["data"][0]
        assert branch_data["type"] == "branch"
        assert "children" in branch_data
        assert "statistics" in branch_data

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "channels" in data
        assert "data" in data
        assert isinstance(data["channels"], list)
        assert isinstance(data["data"], list)

        # Verify channels are listed
        assert "Facebook Ads" in data["channels"]
        assert "VietnamWorks" in data["channels"]

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "months" in data
        assert "data" in data

        # Verify months include Total column
        assert "Total" in data["months"]

        # Verify data structure
        assert isinstance(data["data"], list)
        for source_data in data["data"]:
            assert "source_type" in source_data
            assert "months" in source_data
            assert isinstance(source_data["months"], list)
            for month_data in source_data["months"]:
                assert "total" in month_data
                assert "count" in month_data
                assert "avg" in month_data

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "period_type" in data
        assert data["period_type"] == "month"
        assert "labels" in data
        assert "data" in data

        # Verify labels include Total
        assert "Total" in data["labels"]

        # Verify data structure includes source types
        assert isinstance(data["data"], list)
        source_types = [item["name"] for item in data["data"]]
        assert "Referral Source" in source_types
        assert "Marketing Channel" in source_types

        # Verify referral source has children (employee breakdown)
        referral_data = next(
            item for item in data["data"] if item["type"] == "source_type" and "Referral" in item["name"]
        )
        assert "children" in referral_data
        if referral_data["children"]:
            assert len(referral_data["children"]) > 0

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "period_type" in data
        assert data["period_type"] == "week"
        assert "labels" in data
        assert "data" in data

        # Verify week label format (should contain "Tuần")
        week_labels = [label for label in data["labels"] if "Tuần" in label or label == "Total"]
        assert len(week_labels) > 0

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "data" in data
        assert "summary_total" in data

        # Verify summary total
        expected_total = Decimal("800000.00")
        assert Decimal(str(data["summary_total"])) == expected_total

        # Verify department grouping
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        dept_data = data["data"][0]
        assert "name" in dept_data
        assert "items" in dept_data

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) > 0

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
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "data" in data

    def test_hired_candidate_report_invalid_period_type(self):
        """Test hired candidate report with invalid period type returns error"""
        # Act: Call API with invalid period type
        url = reverse("hrm:recruitment-reports-hired-candidate")
        response = self.client.get(url, {"period_type": "invalid"})

        # Assert: Verify error response
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_referral_cost_report_invalid_month_format(self):
        """Test referral cost report with invalid month format returns error"""
        # Act: Call API with invalid month format
        url = reverse("hrm:recruitment-reports-referral-cost")
        response = self.client.get(url, {"month": "2025-10"})  # Wrong format

        # Assert: Verify error response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
