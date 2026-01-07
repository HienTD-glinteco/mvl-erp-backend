from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import HiredCandidateReport
from apps.hrm.utils import get_week_key_from_date

User = get_user_model()


@pytest.mark.django_db
class TestHiredCandidateReportFixes:
    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, branch, block, department, employee):
        self.client = api_client
        self.user = superuser
        self.branch = branch
        self.block = block
        self.department = department
        self.employee = employee

        # Date: Jan 1, 2026 (Thursday)
        self.report_date = date(2026, 1, 1)
        self.week_key = get_week_key_from_date(self.report_date)
        self.month_key = self.report_date.strftime("%m/%Y")

        HiredCandidateReport.objects.create(
            report_date=self.report_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            source_type=RecruitmentSourceType.REFERRAL_SOURCE.value,
            month_key=self.month_key,
            week_key=self.week_key,
            employee=self.employee,
            num_candidates_hired=1,
            num_experienced=0,
        )

    def test_bug_week_labels_and_data_consistency(self):
        """
        Reproduce Bug 1 and 2:
        - View uses ISO week (Week 1 2026) -> Key: "Week 1 - 01/2026"
        - DB uses Week of Month -> Key: "Week 5 - 12/2025"
        - Result: Data missing in response.
        """
        url = reverse("hrm:recruitment-reports-hired-candidate")
        # Filter for the week of Jan 1 - Jan 7 2026
        response = self.client.get(url, {"period_type": "week", "from_date": "2026-01-01", "to_date": "2026-01-07"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        print(f"\nGenerated Week Key in DB: {self.week_key}")
        print(f"Response Labels: {data['labels']}")

        # Check DATA (Bug 1)
        # Match by name "Referral Source" (English)
        referral_stats = next(item for item in data["data"] if item["name"] == "Referral Source")

        total_hired = sum(referral_stats["statistics"])
        print(f"Total Hired in Response: {total_hired}")

        # Total Hired sums weekly stats + Total column.
        # We expect [1, 0, 1] -> sum is 2.
        assert total_hired == 2, f"Expected 2 (1 hire + 1 total), got {total_hired}. Week key mismatch likely."
