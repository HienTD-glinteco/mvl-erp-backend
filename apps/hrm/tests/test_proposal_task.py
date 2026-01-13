"""Tests for proposal-related Celery tasks."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Block, Branch, Department, Employee, Position, Proposal
from apps.hrm.tasks.proposal import update_employee_status_from_approved_leave_proposals

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_employee(db):
    """Create a test employee for proposal task tests."""
    from apps.core.models import AdministrativeUnit, Province, User

    province = Province.objects.create(name="Test Province Task", code="TPT")
    admin_unit = AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit Task",
        code="TAUT",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )
    branch = Branch.objects.create(
        name="Test Branch Task",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(name="Test Block Task", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(
        name="Test Dept Task", branch=branch, block=block, function=Department.DepartmentFunction.BUSINESS
    )
    position = Position.objects.create(name="Developer Task")

    user = User.objects.create_user(
        username="user_task_001",
        email="task001@example.com",
        password="testpass123",
    )

    employee = Employee.objects.create(
        code="MV_TASK_001",
        fullname="Task Test Employee",
        username="user_task_001",
        email="task001@example.com",
        phone="0988807001",
        attendance_code="88007",
        citizen_id="888000000007",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
        user=user,
    )
    return employee


@pytest.fixture
def second_employee(test_employee):
    """Create a second test employee."""
    from apps.core.models import User

    user = User.objects.create_user(
        username="user_task_002",
        email="task002@example.com",
        password="testpass123",
    )

    employee = Employee.objects.create(
        code="MV_TASK_002",
        fullname="Task Test Employee 2",
        username="user_task_002",
        email="task002@example.com",
        phone="0988807002",
        attendance_code="88008",
        citizen_id="888000000008",
        branch=test_employee.branch,
        block=test_employee.block,
        department=test_employee.department,
        position=test_employee.position,
        start_date=date(2020, 1, 1),
        status=Employee.Status.ACTIVE,
        user=user,
        personal_email="task002_personal@example.com",
    )
    return employee


class TestUpdateEmployeeStatusFromApprovedLeaveProposals:
    """Tests for update_employee_status_from_approved_leave_proposals task."""

    def test_unpaid_leave_updates_employee_status(self, test_employee):
        """Test that approved unpaid leave proposal updates employee status."""
        today = timezone.localdate()

        # Create approved unpaid leave proposal that includes today
        Proposal.objects.create(
            code="DX_TASK_UNPAID_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            unpaid_leave_start_date=today - timedelta(days=5),
            unpaid_leave_end_date=today + timedelta(days=5),
            created_by=test_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify employee status was updated
        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.UNPAID_LEAVE
        assert test_employee.resignation_start_date == today - timedelta(days=5)
        assert test_employee.resignation_end_date == today + timedelta(days=5)

    def test_maternity_leave_updates_employee_status(self, test_employee):
        """Test that approved maternity leave proposal updates employee status."""
        today = timezone.localdate()

        # Create approved maternity leave proposal that includes today
        Proposal.objects.create(
            code="DX_TASK_MAT_001",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            maternity_leave_start_date=today - timedelta(days=10),
            maternity_leave_end_date=today + timedelta(days=80),
            created_by=test_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify employee status was updated
        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.MATERNITY_LEAVE
        assert test_employee.resignation_start_date == today - timedelta(days=10)
        assert test_employee.resignation_end_date == today + timedelta(days=80)

    def test_pending_proposal_does_not_update_status(self, test_employee):
        """Test that pending proposals do not update employee status."""
        today = timezone.localdate()

        # Create pending unpaid leave proposal
        Proposal.objects.create(
            code="DX_TASK_PENDING_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
            unpaid_leave_start_date=today - timedelta(days=5),
            unpaid_leave_end_date=today + timedelta(days=5),
            created_by=test_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify employee status was NOT updated
        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.ACTIVE

    def test_rejected_proposal_does_not_update_status(self, test_employee):
        """Test that rejected proposals do not update employee status."""
        today = timezone.localdate()

        # Create rejected unpaid leave proposal
        Proposal.objects.create(
            code="DX_TASK_REJECT_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.REJECTED,
            unpaid_leave_start_date=today - timedelta(days=5),
            unpaid_leave_end_date=today + timedelta(days=5),
            approval_note="Rejected",
            created_by=test_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify employee status was NOT updated
        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.ACTIVE

    def test_future_proposal_does_not_update_status(self, test_employee):
        """Test that future leave proposals do not update employee status."""
        today = timezone.localdate()

        # Create approved unpaid leave proposal in the future
        Proposal.objects.create(
            code="DX_TASK_FUTURE_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            unpaid_leave_start_date=today + timedelta(days=10),
            unpaid_leave_end_date=today + timedelta(days=20),
            created_by=test_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify employee status was NOT updated
        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.ACTIVE

    def test_past_proposal_does_not_update_status(self, test_employee):
        """Test that past leave proposals do not update employee status."""
        today = timezone.localdate()

        # Create approved unpaid leave proposal in the past
        Proposal.objects.create(
            code="DX_TASK_PAST_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            unpaid_leave_start_date=today - timedelta(days=30),
            unpaid_leave_end_date=today - timedelta(days=10),
            created_by=test_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify employee status was NOT updated
        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.ACTIVE

    def test_already_on_leave_does_not_update_again(self, test_employee):
        """Test that employees already on leave are not updated again."""
        today = timezone.localdate()

        # Set employee status to UNPAID_LEAVE already
        test_employee.status = Employee.Status.UNPAID_LEAVE
        test_employee.resignation_start_date = today - timedelta(days=5)
        test_employee.resignation_end_date = today + timedelta(days=5)
        test_employee.save()

        # Create approved unpaid leave proposal
        Proposal.objects.create(
            code="DX_TASK_ALREADY_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            unpaid_leave_start_date=today - timedelta(days=5),
            unpaid_leave_end_date=today + timedelta(days=5),
            created_by=test_employee,
        )

        # Run the task - should not trigger update since status is already UNPAID_LEAVE
        update_employee_status_from_approved_leave_proposals()

        test_employee.refresh_from_db()
        assert test_employee.status == Employee.Status.UNPAID_LEAVE

    def test_multiple_employees_updated(self, test_employee, second_employee):
        """Test that multiple employees with approved leave proposals are updated."""
        today = timezone.localdate()

        # Create approved unpaid leave for first employee
        Proposal.objects.create(
            code="DX_TASK_MULTI_001",
            proposal_type=ProposalType.UNPAID_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            unpaid_leave_start_date=today - timedelta(days=5),
            unpaid_leave_end_date=today + timedelta(days=5),
            created_by=test_employee,
        )

        # Create approved maternity leave for second employee
        Proposal.objects.create(
            code="DX_TASK_MULTI_002",
            proposal_type=ProposalType.MATERNITY_LEAVE,
            proposal_status=ProposalStatus.APPROVED,
            maternity_leave_start_date=today - timedelta(days=10),
            maternity_leave_end_date=today + timedelta(days=80),
            created_by=second_employee,
        )

        # Run the task
        update_employee_status_from_approved_leave_proposals()

        # Verify both employees were updated
        test_employee.refresh_from_db()
        second_employee.refresh_from_db()

        assert test_employee.status == Employee.Status.UNPAID_LEAVE
        assert second_employee.status == Employee.Status.MATERNITY_LEAVE
