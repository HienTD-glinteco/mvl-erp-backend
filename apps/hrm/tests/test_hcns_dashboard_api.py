"""Tests for HCNS dashboard API endpoints."""

import json
from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.core.models import Permission, Role
from apps.hrm.constants import AttendanceType, ProposalStatus, ProposalType
from apps.hrm.models import AttendanceRecord, Proposal
from apps.payroll.models import PenaltyTicket


class APITestMixin:
    """Helper to unwrap API responses."""

    def get_response_data(self, response):
        """Extract the underlying data payload from wrapped responses."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content


@pytest.mark.django_db
class TestHCNSDashboardAPI(APITestMixin):
    """Tests for HCNS dashboard realtime endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user, employee, branch, block, department, position):
        """Set up authenticated HCNS user with permission."""
        self.client = api_client
        self.user = user
        self.employee = employee

        permission = Permission.objects.create(
            code="hrm.hcns_dashboard.realtime",
            name="View HCNS dashboard",
            description="View KPIs for HCNS staff",
            module="HRM",
            submodule="HCNS Dashboard",
        )
        role = Role.objects.create(code="HCNS", name="HCNS")
        role.permissions.add(permission)
        self.user.role = role
        self.user.save()

    def test_realtime_dashboard_reports_correct_counts(self):
        """Ensure realtime endpoint returns the expected KPIs."""
        Proposal.objects.create(
            code="DX-PL-0001",
            created_by=self.employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )
        today = timezone.localdate()
        Proposal.objects.create(
            code="DX-LATE-0001",
            created_by=self.employee,
            proposal_type=ProposalType.LATE_EXEMPTION,
            proposal_status=ProposalStatus.PENDING,
            late_exemption_start_date=today,
            late_exemption_end_date=today + timedelta(days=7),
            late_exemption_minutes=15,
        )
        Proposal.objects.create(
            code="DX-TSC-0001",
            created_by=self.employee,
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.PENDING,
        )
        Proposal.objects.create(
            code="DX-TSC-0002",
            created_by=self.employee,
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.PENDING,
        )
        Proposal.objects.create(
            code="DX-UNKNOWN-0001",
            created_by=self.employee,
            proposal_type=None,
            proposal_status=ProposalStatus.PENDING,
        )

        PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            violation_count=1,
            amount=100000,
            month=date(2025, 1, 1),
            status=PenaltyTicket.Status.UNPAID,
        )
        PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            violation_count=2,
            amount=50000,
            month=date(2025, 1, 1),
            status=PenaltyTicket.Status.UNPAID,
        )
        PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            violation_count=1,
            amount=25000,
            month=date(2025, 1, 1),
            status=PenaltyTicket.Status.PAID,
        )

        AttendanceRecord.objects.create(
            code="DD-OTHER-001",
            attendance_type=AttendanceType.OTHER,
            attendance_code=self.employee.attendance_code,
            timestamp=timezone.now(),
            employee=self.employee,
            is_pending=True,
            is_valid=False,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hcns-dashboard-realtime")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert data["proposals_pending"][ProposalType.PAID_LEAVE] == 1
        assert data["proposals_pending"][ProposalType.LATE_EXEMPTION] == 1
        assert data["proposals_pending"][ProposalType.TIMESHEET_ENTRY_COMPLAINT] == 2
        assert data["proposals_pending"]["unknown"] == 1
        assert data["attendance_other_pending"] == 1
        assert data["timesheet_complaints_pending"] == 2
        assert data["penalty_tickets_unpaid"] == 2
