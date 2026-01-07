"""Tests for My Penalty Tickets API endpoints."""

from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Permission, Role, User
from apps.hrm.constants import EmployeeType
from apps.hrm.models import Employee
from apps.payroll.models import PenaltyTicket
from apps.payroll.tests.conftest import random_code, random_digits


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def permission_list(db):
    """Create list permission."""
    return Permission.objects.create(
        code="payroll.my_penalty_ticket.list",
        name="List my penalty tickets",
        description="View list of my penalty tickets",
        module="Payroll",
        submodule="My Penalty Tickets",
    )


@pytest.fixture
def permission_retrieve(db):
    """Create retrieve permission."""
    return Permission.objects.create(
        code="payroll.my_penalty_ticket.retrieve",
        name="View my penalty ticket",
        description="View detail of my penalty ticket",
        module="Payroll",
        submodule="My Penalty Tickets",
    )


@pytest.fixture
def role_with_permissions(db, permission_list, permission_retrieve):
    """Create role with my penalty ticket permissions."""
    role = Role.objects.create(
        code="EMPLOYEE",
        name="Employee",
        description="Employee role",
    )
    role.permissions.add(permission_list, permission_retrieve)
    return role


@pytest.fixture
def user_with_employee(role_with_permissions, employee):
    """Create user with associated employee."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    user.role = role_with_permissions
    user.save()

    employee.user = user
    employee.save()
    return user


@pytest.fixture
def user_without_employee(role_with_permissions):
    """Create user without associated employee."""
    user = User.objects.create_user(
        username="noemployee",
        email="noemployee@example.com",
        password="testpass123",
    )
    user.role = role_with_permissions
    user.save()
    return user


@pytest.fixture
def penalty_ticket_for_user(user_with_employee):
    """Create penalty ticket for user's employee."""
    employee = user_with_employee.employee
    return PenaltyTicket.objects.create(
        employee=employee,
        employee_code=employee.code,
        employee_name=employee.fullname,
        violation_count=1,
        violation_type=PenaltyTicket.ViolationType.UNIFORM_ERROR,
        amount=100000,
        month=date(2025, 1, 1),
        status=PenaltyTicket.Status.UNPAID,
    )


@pytest.fixture
def other_employee_penalty_ticket(branch, block, department, position):
    """Create penalty ticket for another employee."""
    suffix = random_code(length=6)
    other_employee = Employee.objects.create(
        code=f"OTHER{suffix}",
        fullname="Other Employee",
        username=f"other{suffix}",
        email=f"other{suffix}@example.com",
        personal_email=f"other{suffix}.personal@example.com",
        status=Employee.Status.ACTIVE,
        code_type=Employee.CodeType.MV,
        employee_type=EmployeeType.OFFICIAL,
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2024, 1, 1),
        attendance_code=random_digits(6),
        citizen_id=random_digits(12),
        phone=f"09{random_digits(8)}",
    )
    return PenaltyTicket.objects.create(
        employee=other_employee,
        employee_code=other_employee.code,
        employee_name=other_employee.fullname,
        violation_count=1,
        violation_type=PenaltyTicket.ViolationType.OTHER,
        amount=50000,
        month=date(2025, 1, 1),
        status=PenaltyTicket.Status.UNPAID,
    )


@pytest.mark.django_db
class TestMyPenaltyTicketListAPI:
    """Test cases for listing my penalty tickets."""

    def test_list_my_penalty_tickets_success(self, api_client, user_with_employee, penalty_ticket_for_user):
        """Test authenticated user can list their own penalty tickets."""
        api_client.force_authenticate(user=user_with_employee)
        url = reverse("mobile-payroll:my-penalty-ticket-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["code"] == penalty_ticket_for_user.code

    def test_list_excludes_other_employees_tickets(
        self, api_client, user_with_employee, penalty_ticket_for_user, other_employee_penalty_ticket
    ):
        """Test user only sees their own penalty tickets."""
        api_client.force_authenticate(user=user_with_employee)
        url = reverse("mobile-payroll:my-penalty-ticket-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["count"] == 1
        codes = [r["code"] for r in data["data"]["results"]]
        assert penalty_ticket_for_user.code in codes
        assert other_employee_penalty_ticket.code not in codes

    def test_list_requires_authentication(self, api_client):
        """Test unauthenticated user cannot list penalty tickets."""
        url = reverse("mobile-payroll:my-penalty-ticket-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_requires_employee_record(self, api_client, user_without_employee):
        """Test user without employee record gets permission denied."""
        api_client.force_authenticate(user=user_without_employee)
        url = reverse("mobile-payroll:my-penalty-ticket-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMyPenaltyTicketRetrieveAPI:
    """Test cases for retrieving my penalty ticket details."""

    def test_retrieve_my_penalty_ticket_success(self, api_client, user_with_employee, penalty_ticket_for_user):
        """Test authenticated user can retrieve their own penalty ticket."""
        api_client.force_authenticate(user=user_with_employee)
        url = reverse("mobile-payroll:my-penalty-ticket-detail", kwargs={"pk": penalty_ticket_for_user.pk})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["code"] == penalty_ticket_for_user.code

    def test_cannot_retrieve_other_employees_ticket(
        self, api_client, user_with_employee, other_employee_penalty_ticket
    ):
        """Test user cannot retrieve another employee's penalty ticket."""
        api_client.force_authenticate(user=user_with_employee)
        url = reverse("mobile-payroll:my-penalty-ticket-detail", kwargs={"pk": other_employee_penalty_ticket.pk})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_requires_authentication(self, api_client, penalty_ticket_for_user):
        """Test unauthenticated user cannot retrieve penalty ticket."""
        url = reverse("mobile-payroll:my-penalty-ticket-detail", kwargs={"pk": penalty_ticket_for_user.pk})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
