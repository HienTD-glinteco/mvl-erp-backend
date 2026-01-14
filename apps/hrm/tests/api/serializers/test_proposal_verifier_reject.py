"""
Tests for ProposalVerifierRejectSerializer.

This module tests the ProposalVerifierRejectSerializer change where
verified_time is set to timezone.now() instead of None when rejecting.
"""

from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework import serializers as drf_serializers

from apps.core.models import AdministrativeUnit, Province, User
from apps.hrm.api.serializers.proposal import ProposalVerifierRejectSerializer
from apps.hrm.constants import ProposalStatus, ProposalType, ProposalVerifierStatus
from apps.hrm.models import Block, Branch, Department, Employee, Position, Proposal, ProposalVerifier

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def setup_data(transactional_db):
    """Set up test fixtures for ProposalVerifierRejectSerializer tests."""
    # Explicitly delete all existing data to ensure clean state
    ProposalVerifier.objects.all().delete()
    Proposal.objects.all().delete()

    # Create province and administrative unit
    province = Province.objects.create(name="Test Province", code="TP01")
    admin_unit = AdministrativeUnit.objects.create(
        name="Test District",
        code="TD01",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )

    # Create branch
    branch = Branch.objects.create(
        code="BR001",
        name="Test Branch",
        province=province,
        administrative_unit=admin_unit,
    )

    # Create block
    block = Block.objects.create(
        code="BLK001",
        name="Test Block",
        block_type=Block.BlockType.BUSINESS,
        branch=branch,
    )

    # Create department
    department = Department.objects.create(
        code="DEPT001",
        name="Test Department",
        branch=branch,
        block=block,
    )

    # Create position
    position = Position.objects.create(code="POS001", name="Test Position")

    # Create users
    leader_user = User.objects.create_user(username="leader", email="leader@example.com", password="testpass123")
    employee_user = User.objects.create_user(username="employee", email="employee@example.com", password="testpass123")

    # Create employees
    leader = Employee.objects.create(
        code="EMP001",
        user=leader_user,
        fullname="Leader Test",
        username="leader_emp",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=timezone.now().date(),
        email="leader.work@example.com",
        personal_email="leader.personal@example.com",
        phone="0901234567",
        citizen_id="001234567890",
    )
    employee = Employee.objects.create(
        code="EMP002",
        user=employee_user,
        fullname="Employee Test",
        username="employee_emp",
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=timezone.now().date(),
        email="employee.work@example.com",
        personal_email="employee.personal@example.com",
        phone="0907654321",
        citizen_id="009876543210",
    )

    # Set leader as department leader
    department.leader = leader
    department.save()

    # Create proposal
    proposal = Proposal.objects.create(
        code="PROP001",
        proposal_date=timezone.now().date(),
        proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
        proposal_status=ProposalStatus.PENDING,
        created_by=employee,
        timesheet_entry_complaint_complaint_reason="Test complaint",
    )

    # A verifier is automatically created for timesheet complaint proposals
    # Use it instead of creating a new one
    if proposal.verifiers.count() > 0:
        verifier = proposal.verifiers.first()
        verifier.status = ProposalVerifierStatus.VERIFIED
        verifier.verified_time = timezone.now()
        verifier.save()
    else:
        # Create proposal verifier manually if not auto-created
        verifier = ProposalVerifier.objects.create(
            proposal=proposal,
            employee=employee,
            status=ProposalVerifierStatus.VERIFIED,
            verified_time=timezone.now(),
        )

    return {
        "leader_user": leader_user,
        "employee_user": employee_user,
        "leader": leader,
        "employee": employee,
        "verifier": verifier,
    }


def test_update_sets_verified_time_to_now(setup_data):
    """Test that update() sets verified_time to current time when rejecting."""
    # Arrange
    old_verified_time = setup_data["verifier"].verified_time
    request = MagicMock()
    request.user = setup_data["leader_user"]
    context = {"request": request}

    serializer = ProposalVerifierRejectSerializer(
        instance=setup_data["verifier"],
        data={"note": "Rejection note"},
        context=context,
    )

    # Act
    assert serializer.is_valid(raise_exception=True)
    updated_verifier = serializer.save()

    # Assert
    assert updated_verifier.verified_time is not None
    assert updated_verifier.verified_time != old_verified_time
    assert updated_verifier.status == ProposalVerifierStatus.NOT_VERIFIED


def test_update_sets_status_to_not_verified(setup_data):
    """Test that update() sets status to NOT_VERIFIED."""
    # Arrange
    request = MagicMock()
    request.user = setup_data["leader_user"]
    context = {"request": request}

    serializer = ProposalVerifierRejectSerializer(
        instance=setup_data["verifier"],
        data={},
        context=context,
    )

    # Act
    assert serializer.is_valid(raise_exception=True)
    updated_verifier = serializer.save()

    # Assert
    assert updated_verifier.status == ProposalVerifierStatus.NOT_VERIFIED


def test_update_with_note(setup_data):
    """Test that update() saves note when provided."""
    # Arrange
    request = MagicMock()
    request.user = setup_data["leader_user"]
    context = {"request": request}

    note_text = "This is a rejection note"
    serializer = ProposalVerifierRejectSerializer(
        instance=setup_data["verifier"],
        data={"note": note_text},
        context=context,
    )

    # Act
    assert serializer.is_valid(raise_exception=True)
    updated_verifier = serializer.save()

    # Assert
    assert updated_verifier.note == note_text


def test_update_without_note(setup_data):
    """Test that update() works without note."""
    # Arrange
    setup_data["verifier"].note = "Existing note"
    setup_data["verifier"].save()

    request = MagicMock()
    request.user = setup_data["leader_user"]
    context = {"request": request}

    serializer = ProposalVerifierRejectSerializer(
        instance=setup_data["verifier"],
        data={},
        context=context,
    )

    # Act
    assert serializer.is_valid(raise_exception=True)
    updated_verifier = serializer.save()

    # Assert
    assert updated_verifier.note == "Existing note"


def test_validate_only_department_leader_can_reject(setup_data):
    """Test that only department leader can reject."""
    # Arrange
    request = MagicMock()
    request.user = setup_data["employee_user"]
    context = {"request": request}

    serializer = ProposalVerifierRejectSerializer(
        instance=setup_data["verifier"],
        data={},
        context=context,
    )

    # Act & Assert
    with pytest.raises(drf_serializers.ValidationError) as exc_info:
        serializer.is_valid(raise_exception=True)

    assert "Only the department leader can reject this proposal" in str(exc_info.value)


def test_validate_requires_instance(setup_data):
    """Test that validation requires an existing instance."""
    # Arrange
    request = MagicMock()
    request.user = setup_data["leader_user"]
    context = {"request": request}

    serializer = ProposalVerifierRejectSerializer(
        data={},
        context=context,
    )

    # Act & Assert
    with pytest.raises(drf_serializers.ValidationError) as exc_info:
        serializer.is_valid(raise_exception=True)

    assert "This serializer requires an existing verifier instance" in str(exc_info.value)


def test_verified_time_is_recent(setup_data):
    """Test that verified_time is set to a recent timestamp."""
    # Arrange
    request = MagicMock()
    request.user = setup_data["leader_user"]
    context = {"request": request}

    serializer = ProposalVerifierRejectSerializer(
        instance=setup_data["verifier"],
        data={},
        context=context,
    )

    # Act
    before_update = timezone.now()
    assert serializer.is_valid(raise_exception=True)
    updated_verifier = serializer.save()
    after_update = timezone.now()

    # Assert
    assert updated_verifier.verified_time >= before_update
    assert updated_verifier.verified_time <= after_update
