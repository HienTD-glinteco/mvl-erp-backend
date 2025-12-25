"""Tests for penalty management API endpoints."""

import json
from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.models import User
from apps.payroll.models import PenaltyTicket


@pytest.mark.django_db
class PenaltyTicketAPITest(APITestCase):
    """Test cases for PenaltyTicket API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create superuser to bypass RoleBasedPermission
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        # Create test organization structure
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department, Employee

        self.province = Province.objects.create(name="Test Province", code="TP01")
        self.admin_unit = AdministrativeUnit.objects.create(
            parent_province=self.province,
            name="Test District",
            code="TD01",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        self.branch = Branch.objects.create(
            name="Test Branch",
            code="BR01",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            name="Test Block",
            code="BL01",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            name="Test Department",
            code="D01",
            branch=self.branch,
            block=self.block,
        )
        self.employee = Employee.objects.create(
            username="emp001",
            email="emp001@test.com",
            phone="0987654321",
            citizen_id="123456789012",
            start_date=date(2024, 1, 1),
            attendance_code="123456",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        self.month = date(2025, 11, 1)

    def test_create_penalty_ticket(self):
        """Test creating a penalty ticket."""
        url = reverse("payroll:penalty-tickets-list")
        payload = {
            "employee_id": self.employee.id,
            "month": "11/2025",
            "violation_count": 2,
            "violation_type": "OVER_10_MINUTES",
            "amount": 100000,
            "note": "Uniform violation - missing name tag",
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])

        data = response_data["data"]
        self.assertIn("code", data)
        self.assertTrue(data["code"].startswith("RVF-202511-"))
        self.assertEqual(data["month"], "11/2025")
        self.assertEqual(data["violation_count"], 2)
        self.assertEqual(data["violation_type"], "OVER_10_MINUTES")
        self.assertEqual(data["amount"], 100000)
        self.assertEqual(data["payment_status"], "UNPAID")
        self.assertEqual(data["payroll_status"], "NOT_CALCULATED")

        ticket = PenaltyTicket.objects.get(id=data["id"])
        self.assertEqual(ticket.created_by, self.user)
        self.assertEqual(ticket.updated_by, self.user)

    def test_create_penalty_ticket_requires_authentication(self):
        """Unauthenticated requests must be rejected."""
        client = APIClient()
        url = reverse("payroll:penalty-tickets-list")
        payload = {
            "employee_id": self.employee.id,
            "month": "11/2025",
            "violation_count": 1,
            "violation_type": "UNDER_10_MINUTES",
            "amount": 50000,
        }

        response = client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])

    def test_list_penalty_tickets(self):
        """Test listing penalty tickets."""
        # Create test tickets
        PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=self.month,
            violation_count=1,
            violation_type="UNDER_10_MINUTES",
            amount=100000,
            created_by=self.user,
        )

        url = reverse("payroll:penalty-tickets-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])

        data = response_data["data"]
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)

    def test_update_penalty_ticket(self):
        """Test updating a penalty ticket."""
        ticket = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=self.month,
            amount=100000,
            note="Original note",
            created_by=self.user,
        )

        url = reverse("payroll:penalty-tickets-detail", kwargs={"pk": ticket.id})
        payload = {
            "employee_id": self.employee.id,
            "month": "11/2025",
            "violation_count": 3,
            "violation_type": "UNIFORM_ERROR",
            "payment_status": "PAID",
            "payroll_status": "NOT_CALCULATED",
            "amount": 150000,
            "note": "Updated note",
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = json.loads(response.content)
        data = response_data["data"]
        self.assertEqual(data["amount"], 150000)
        self.assertEqual(data["note"], "Updated note")
        self.assertEqual(data["violation_count"], 3)
        self.assertEqual(data["violation_type"], "UNIFORM_ERROR")
        self.assertEqual(data["payment_status"], "PAID")

    def test_delete_penalty_ticket(self):
        """Test deleting a penalty ticket."""
        ticket = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=self.month,
            amount=100000,
            created_by=self.user,
        )

        url = reverse("payroll:penalty-tickets-detail", kwargs={"pk": ticket.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify ticket was deleted
        self.assertFalse(PenaltyTicket.objects.filter(id=ticket.id).exists())

    def test_update_payment_status_action(self):
        """Test bulk payment status update."""
        ticket = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=self.month,
            amount=80000,
            created_by=self.user,
        )

        url = reverse("payroll:penalty-tickets-update-payment-status")
        payload = {"ids": [ticket.id], "payment_status": "PAID"}

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["data"]["updated_count"], 1)

        ticket.refresh_from_db()
        self.assertEqual(ticket.payment_status, "PAID")
        self.assertEqual(ticket.updated_by, self.user)
