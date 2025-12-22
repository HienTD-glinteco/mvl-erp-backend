from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeWorkHistory,
    Position,
)

User = get_user_model()


class EmployeeTypeConversionReportAPITest(TransactionTestCase):
    """API tests for Employee Type Conversion Report list endpoint."""

    def setUp(self):
        # Clean state
        EmployeeWorkHistory.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        # Superuser to bypass permission checks
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001", name="Main Branch", province=self.province, administrative_unit=self.admin_unit
        )
        self.block = Block.objects.create(
            code="KH001", name="Main Block", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )

        # Two departments under same block
        self.dept1 = Department.objects.create(code="PB001", name="Dept 1", block=self.block, branch=self.branch)
        self.dept2 = Department.objects.create(code="PB002", name="Dept 2", block=self.block, branch=self.branch)

        self.position = Position.objects.create(code="CV001", name="Developer")

        # Two employees in different departments
        self.emp1 = Employee.objects.create(
            fullname="Alice",
            username="alice",
            email="alice@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.dept1,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000020211",
            attendance_code="11111",
            phone="0123456701",
        )

        self.emp2 = Employee.objects.create(
            fullname="Bob",
            username="bob",
            email="bob@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.dept2,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000020212",
            attendance_code="22222",
            phone="0123456702",
        )

        # Create type-conversion work history records
        EmployeeWorkHistory.objects.create(
            employee=self.emp1,
            date=date(2025, 1, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
            old_employee_type="MV",
            new_employee_type="OS",
        )

        EmployeeWorkHistory.objects.create(
            employee=self.emp2,
            date=date(2025, 1, 2),
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
            old_employee_type="MV",
            new_employee_type="OS",
        )

    def get_response_data(self, response):
        content = response.json()
        return content.get("data", content)

    def test_list_nested_structure(self):
        url = reverse("hrm:employee-type-conversion-reports-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = self.get_response_data(response)

        # Expect one branch
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

        branch_item = data[0]
        self.assertEqual(branch_item["name"], self.branch.name)

        # Block level
        self.assertIn("children", branch_item)
        blocks = branch_item["children"]
        self.assertGreaterEqual(len(blocks), 1)

        block_item = blocks[0]
        self.assertEqual(block_item["name"], self.block.name)

        # Departments under block
        departments = block_item.get("children", [])
        dept_names = {d["name"] for d in departments}
        self.assertIn(self.dept1.name, dept_names)
        self.assertIn(self.dept2.name, dept_names)

        # Each department should have its child records
        for dept in departments:
            if dept["name"] == self.dept1.name:
                self.assertEqual(len(dept["children"]), 1)
                record = dept["children"][0]
                self.assertIn("employee", record)
                self.assertEqual(record["employee"]["fullname"], self.emp1.fullname)
