"""Tests for HRM dashboard API endpoints."""

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.core.models import Permission, Role
from apps.hrm.constants import AttendanceType, ProposalStatus, ProposalType, ProposalVerifierStatus
from apps.hrm.models import AttendanceRecord, Proposal, ProposalVerifier
from apps.hrm.utils.dashboard_cache import (
    HRM_DASHBOARD_CACHE_KEY,
    MANAGER_DASHBOARD_CACHE_KEY_PREFIX,
)
from apps.payroll.models import EmployeeKPIAssessment, KPIAssessmentPeriod, PenaltyTicket


class APITestMixin:
    """Helper to unwrap API responses."""

    def get_response_data(self, response):
        """Extract the underlying data payload from wrapped responses."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def clear_dashboard_cache(self):
        """Clear HRM dashboard cache to ensure test isolation."""
        cache.delete(HRM_DASHBOARD_CACHE_KEY)


@pytest.mark.django_db
class TestHRMDashboardAPI(APITestMixin):
    """Tests for HRM dashboard realtime endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user, employee, branch, block, department, position):
        """Set up authenticated HRM user with permission."""
        self.client = api_client
        self.user = user
        self.employee = employee

        permission = Permission.objects.create(
            code="hrm.dashboard.common.realtime",
            name="View HRM dashboard",
            description="View KPIs for HRM staff",
            module="HRM",
            submodule="HRM Dashboard",
        )
        role = Role.objects.create(code="HRM", name="HRM")
        role.permissions.add(permission)
        self.user.role = role
        self.user.save()

        # Clear cache to ensure test isolation
        self.clear_dashboard_cache()

    def test_realtime_dashboard_reports_correct_counts(self):
        """Ensure realtime endpoint returns the expected KPIs with navigation info."""
        # Arrange
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

        # Act
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hrm-common-dashboard-realtime")
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check proposals_pending structure
        proposals_pending = data["proposals_pending"]
        assert proposals_pending["key"] == "proposals_pending"
        assert "items" in proposals_pending

        # Find specific proposal items by key
        proposal_items = {item["key"]: item for item in proposals_pending["items"]}
        assert proposal_items["proposals_paid_leave"]["count"] == 1
        assert "/decisions-proposals/proposals/" in proposal_items["proposals_paid_leave"]["path"]
        assert proposal_items["proposals_paid_leave"]["query_params"]["status"] == ProposalStatus.PENDING

        assert proposal_items["proposals_late_exemption"]["count"] == 1

        # Check attendance_other_pending
        attendance = data["attendance_other_pending"]
        assert attendance["key"] == "attendance_other_pending"
        assert attendance["count"] == 1
        assert attendance["path"] == "/attendance/other-attendance"
        assert attendance["query_params"]["approve_status"] == AttendanceRecord.ApproveStatus.PENDING

        # Check timesheet_complaints_pending
        complaints = data["timesheet_complaints_pending"]
        assert complaints["key"] == "timesheet_complaints_pending"
        assert complaints["count"] == 2
        assert complaints["path"] == "/attendance/complaint"
        # Query params may have different key structures
        assert "proposal_status__in" in complaints["query_params"] or "status" in complaints["query_params"]

        # Check penalty_tickets_unpaid
        penalties = data["penalty_tickets_unpaid"]
        assert penalties["key"] == "penalty_tickets_unpaid"
        assert penalties["count"] == 2
        assert penalties["path"] == "/payroll/penalty-management"
        assert penalties["query_params"]["status"] == PenaltyTicket.Status.UNPAID

    def test_realtime_dashboard_returns_zero_counts_when_empty(self):
        """Ensure realtime endpoint returns zero counts when no data exists."""
        # Act
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hrm-common-dashboard-realtime")
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # All counts should be 0
        assert data["attendance_other_pending"]["count"] == 0
        assert data["timesheet_complaints_pending"]["count"] == 0
        assert data["penalty_tickets_unpaid"]["count"] == 0

        # All proposal items should have count 0
        for item in data["proposals_pending"]["items"]:
            assert item["count"] == 0

    def test_realtime_dashboard_uses_cache(self):
        """Ensure realtime endpoint uses cached data on subsequent requests."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hrm-common-dashboard-realtime")
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Act - first request should populate cache
        response1 = self.client.get(url)
        assert response1.status_code == status.HTTP_200_OK

        # Verify cache was populated
        cached_data = cache.get(HRM_DASHBOARD_CACHE_KEY)
        assert cached_data is not None

        # Act - second request should use cache
        with patch("apps.hrm.api.views.hrm_dashboard.HRMDashboardViewSet._build_dashboard_data") as mock_build:
            response2 = self.client.get(url)
            assert response2.status_code == status.HTTP_200_OK
            # _build_dashboard_data should not be called on cache hit
            mock_build.assert_not_called()

    def test_hrm_cache_invalidated_on_proposal_create(self):
        """Ensure cache is invalidated when a proposal is created."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hrm-common-dashboard-realtime")
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Populate cache
        self.client.get(url)
        assert cache.get(HRM_DASHBOARD_CACHE_KEY) is not None

        # Act - create a proposal (triggers signal)
        Proposal.objects.create(
            code="DX-PL-CACHE-001",
            created_by=self.employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )

        # Assert - cache should be invalidated
        assert cache.get(HRM_DASHBOARD_CACHE_KEY) is None

    @pytest.mark.django_db(transaction=True)
    def test_hrm_cache_invalidated_on_penalty_ticket_create(self, settings):
        """Ensure cache is invalidated when a penalty ticket is created."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hrm-common-dashboard-realtime")
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Populate cache
        self.client.get(url)
        assert cache.get(HRM_DASHBOARD_CACHE_KEY) is not None

        # Act - create a penalty ticket (triggers signal)
        PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            violation_count=1,
            amount=100000,
            month=date(2025, 1, 1),
            status=PenaltyTicket.Status.UNPAID,
        )

        # Assert - cache should be invalidated
        assert cache.get(HRM_DASHBOARD_CACHE_KEY) is None

    def test_hrm_cache_invalidated_on_attendance_record_create(self):
        """Ensure cache is invalidated when an OTHER attendance record is created."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:hrm-common-dashboard-realtime")
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Populate cache
        self.client.get(url)
        assert cache.get(HRM_DASHBOARD_CACHE_KEY) is not None

        # Act - create an OTHER attendance record (triggers signal)
        AttendanceRecord.objects.create(
            code="DD-OTHER-CACHE-001",
            attendance_type=AttendanceType.OTHER,
            attendance_code=self.employee.attendance_code,
            timestamp=timezone.now(),
            employee=self.employee,
            is_pending=True,
            is_valid=False,
        )

        # Assert - cache should be invalidated
        assert cache.get(HRM_DASHBOARD_CACHE_KEY) is None


@pytest.mark.django_db
class TestManagerDashboardAPI(APITestMixin):
    """Tests for Manager dashboard realtime endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user, employee, branch, block, department, position):
        """Set up authenticated manager user with permission."""
        self.client = api_client
        self.user = user
        self.employee = employee
        self.branch = branch
        self.block = block
        self.department = department
        self.position = position

        permission = Permission.objects.create(
            code="hrm.dashboard.manager.realtime",
            name="View Manager dashboard",
            description="View manager stats for proposals and KPI assessments",
            module="HRM",
            submodule="Manager Dashboard",
        )
        role = Role.objects.create(code="MANAGER", name="Manager")
        role.permissions.add(permission)
        self.user.role = role
        self.user.save()

    def _create_subordinate(self, code: str):
        """Create a subordinate employee for testing."""
        from apps.hrm.models import Employee

        return Employee.objects.create(
            code=code,
            fullname=f"Subordinate {code}",
            username=f"subordinate_{code}",
            email=f"subordinate_{code}@example.com",
            phone=f"090{code[-4:]}",
            attendance_code=f"ATT{code[-4:]}",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            citizen_id=f"ID{code[-8:]}0000",
            personal_email=f"subordinate_{code}_personal@example.com",
        )

    def test_manager_realtime_returns_correct_counts(self):
        """Ensure manager realtime endpoint returns the expected KPIs."""
        # Arrange - create a subordinate employee
        subordinate = self._create_subordinate("MV000002")

        # Create proposals that need verification by this manager
        proposal1 = Proposal.objects.create(
            code="DX-PL-MGR-001",
            created_by=subordinate,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )
        ProposalVerifier.objects.create(
            proposal=proposal1,
            employee=self.employee,
            status=ProposalVerifierStatus.PENDING,
        )

        proposal2 = Proposal.objects.create(
            code="DX-PL-MGR-002",
            created_by=subordinate,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )
        ProposalVerifier.objects.create(
            proposal=proposal2,
            employee=self.employee,
            status=ProposalVerifierStatus.PENDING,
        )

        # Create a verified proposal (should not be counted)
        proposal3 = Proposal.objects.create(
            code="DX-PL-MGR-003",
            created_by=subordinate,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
        )
        ProposalVerifier.objects.create(
            proposal=proposal3,
            employee=self.employee,
            status=ProposalVerifierStatus.VERIFIED,
        )

        # Create KPI assessments pending for this manager
        kpi_period1 = KPIAssessmentPeriod.objects.create(
            month=date.today().replace(day=1),
            kpi_config_snapshot={},
        )

        EmployeeKPIAssessment.objects.create(
            period=kpi_period1,
            employee=subordinate,
            manager=self.employee,
            finalized=False,
        )

        # Create finalized assessment (should not be counted)
        kpi_period2 = KPIAssessmentPeriod.objects.create(
            month=(date.today().replace(day=1) - timedelta(days=30)).replace(day=1),
            kpi_config_snapshot={},
        )
        EmployeeKPIAssessment.objects.create(
            period=kpi_period2,
            employee=subordinate,
            manager=self.employee,
            finalized=True,
        )

        # Act
        self.client.force_authenticate(user=self.user)
        cache.delete(f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{self.employee.id}")
        url = reverse("hrm:manager-dashboard-realtime")
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        # Check proposals_to_verify
        proposals_to_verify = data["proposals_to_verify"]
        assert proposals_to_verify["key"] == "proposals_to_verify"
        assert proposals_to_verify["count"] == 2
        assert proposals_to_verify["path"] == "/decisions-proposals/proposals/manage"
        assert proposals_to_verify["query_params"]["verifier_status"] == ProposalVerifierStatus.PENDING

        # Check kpi_assessments_pending
        kpi_pending = data["kpi_assessments_pending"]
        assert kpi_pending["key"] == "kpi_assessments_pending"
        assert kpi_pending["count"] == 1
        # Path should point to current KPI period evaluation
        assert kpi_pending["path"] == f"/kpi/manager/period-evaluation/{kpi_period1.id}"
        assert kpi_pending["query_params"]["status"] == EmployeeKPIAssessment.StatusChoices.WAITING_MANAGER

    def test_manager_realtime_returns_zero_counts_when_empty(self):
        """Ensure manager realtime endpoint returns zero counts when no data exists."""
        # Act
        self.client.force_authenticate(user=self.user)
        cache.delete(f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{self.employee.id}")
        url = reverse("hrm:manager-dashboard-realtime")
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert data["proposals_to_verify"]["count"] == 0
        assert data["kpi_assessments_pending"]["count"] == 0

    def test_manager_dashboard_uses_cache(self):
        """Ensure manager dashboard uses cached data on subsequent requests."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:manager-dashboard-realtime")
        cache_key = f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{self.employee.id}"
        cache.delete(cache_key)

        # Act - first request should populate cache
        response1 = self.client.get(url)
        assert response1.status_code == status.HTTP_200_OK

        # Verify cache was populated
        cached_data = cache.get(cache_key)
        assert cached_data is not None

        # Act - second request should use cache
        with patch("apps.hrm.api.views.manager_dashboard.ManagerDashboardViewSet._build_dashboard_data") as mock_build:
            response2 = self.client.get(url)
            assert response2.status_code == status.HTTP_200_OK
            mock_build.assert_not_called()

    def test_manager_cache_invalidated_on_proposal_verifier_create(self):
        """Ensure cache is invalidated when a proposal verifier is created."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:manager-dashboard-realtime")
        cache_key = f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{self.employee.id}"
        cache.delete(cache_key)

        # Populate cache
        self.client.get(url)
        assert cache.get(cache_key) is not None

        # Act - create a proposal verifier (triggers signal)
        proposal = Proposal.objects.create(
            code="DX-PL-CACHE-MGR-001",
            created_by=self.employee,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )
        ProposalVerifier.objects.create(
            proposal=proposal,
            employee=self.employee,
            status=ProposalVerifierStatus.PENDING,
        )

        # Assert - cache should be invalidated
        assert cache.get(cache_key) is None

    @pytest.mark.django_db(transaction=True)
    def test_manager_cache_invalidated_on_kpi_assessment_create(self, settings):
        """Ensure cache is invalidated when a KPI assessment is created."""
        settings.CELERY_TASK_ALWAYS_EAGER = True

        # Arrange
        self.client.force_authenticate(user=self.user)
        url = reverse("hrm:manager-dashboard-realtime")
        cache_key = f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{self.employee.id}"
        cache.delete(cache_key)

        # Populate cache
        self.client.get(url)
        assert cache.get(cache_key) is not None

        # Act - create a KPI assessment (triggers signal)
        subordinate = self._create_subordinate("MV000004")
        kpi_period = KPIAssessmentPeriod.objects.create(
            month=date.today().replace(day=1),
            kpi_config_snapshot={},
        )
        EmployeeKPIAssessment.objects.create(
            period=kpi_period,
            employee=subordinate,
            manager=self.employee,
            finalized=False,
        )

        # Assert - cache should be invalidated
        assert cache.get(cache_key) is None
