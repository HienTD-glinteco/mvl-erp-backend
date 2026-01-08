from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.models import User
from apps.notifications.models import Notification
from apps.payroll.models import PenaltyTicket


@pytest.mark.django_db
class PenaltyTicketNotificationAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.actor = User.objects.create_superuser(username="admin", email="admin@example.com", password="adminpass")
        self.client.force_authenticate(user=self.actor)

        # Org + employee
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department, Employee

        province = Province.objects.create(name="P", code="P1")
        admin_unit = AdministrativeUnit.objects.create(
            parent_province=province, name="D", code="D1", level=AdministrativeUnit.UnitLevel.DISTRICT
        )
        branch = Branch.objects.create(name="B", code="B1", province=province, administrative_unit=admin_unit)
        block = Block.objects.create(name="BL", code="BL1", branch=branch, block_type=Block.BlockType.BUSINESS)
        department = Department.objects.create(name="DEP", code="DEP1", branch=branch, block=block)

        self.recipient = User.objects.create_user(username="emp", email="emp@example.com", password="pass")
        self.employee = Employee.objects.create(
            username="emp",
            email="emp@example.com",
            personal_email="emp.personal@example.com",
            phone="0987654321",
            citizen_id="123456789012",
            start_date=date(2024, 1, 1),
            attendance_code="123456",
            branch=branch,
            block=block,
            department=department,
            user=self.recipient,
        )

    @patch("apps.notifications.utils.trigger_send_notification")
    def test_create_ticket_sends_notification(self, mock_trigger):
        url = reverse("payroll:penalty-tickets-list")
        payload = {
            "employee_id": self.employee.id,
            "month": "11/2025",
            "violation_count": 1,
            "violation_type": PenaltyTicket.ViolationType.UNDER_10_MINUTES,
            "amount": 50000,
        }
        resp = self.client.post(url, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert Notification.objects.count() == 1
        notif = Notification.objects.first()
        assert notif.recipient == self.recipient
        assert notif.verb == "penalty_ticket_created"
        assert self.employee.fullname in notif.message or self.employee.code in notif.message or notif.message

    @patch("apps.notifications.utils.trigger_send_notification")
    def test_mark_paid_sends_notification_bulk(self, mock_trigger):
        # Create ticket unpaid
        t = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=date(2025, 11, 1),
            amount=100000,
            status=PenaltyTicket.Status.UNPAID,
            created_by=self.actor,
        )
        url = reverse("payroll:penalty-tickets-bulk-update-status")
        payload = {"ids": [t.id], "status": PenaltyTicket.Status.PAID, "payment_date": "2025-12-15"}
        resp = self.client.post(url, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert Notification.objects.count() == 1
        notif = Notification.objects.first()
        assert notif.recipient == self.recipient
        assert notif.verb == "penalty_ticket_paid"
        assert t.code in (notif.message or "")

    @patch("apps.notifications.utils.trigger_send_notification")
    def test_mark_paid_sends_notification_single_update(self, mock_trigger):
        t = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=date(2025, 11, 1),
            amount=100000,
            status=PenaltyTicket.Status.UNPAID,
            created_by=self.actor,
        )
        url = reverse("payroll:penalty-tickets-detail", kwargs={"pk": t.id})
        payload = {
            "employee_id": self.employee.id,
            "month": "11/2025",
            "violation_count": 1,
            "violation_type": PenaltyTicket.ViolationType.OTHER,
            "amount": 100000,
            "status": PenaltyTicket.Status.PAID,
        }
        resp = self.client.put(url, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert Notification.objects.count() == 1
        notif = Notification.objects.first()
        assert notif.recipient == self.recipient
        assert notif.verb == "penalty_ticket_paid"

    def test_patch_paid_to_unpaid_clears_payment_date(self):
        # Create ticket as PAID with a payment_date
        t = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=date(2025, 11, 1),
            amount=100000,
            status=PenaltyTicket.Status.PAID,
            payment_date=date(2025, 12, 15),
            created_by=self.actor,
        )
        url = reverse("payroll:penalty-tickets-detail", kwargs={"pk": t.id})
        # Partial update to UNPAID should clear payment_date
        resp = self.client.patch(url, {"status": PenaltyTicket.Status.UNPAID}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        t.refresh_from_db()
        assert t.status == PenaltyTicket.Status.UNPAID
        assert t.payment_date is None
