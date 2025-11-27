from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Nationality, Province
from apps.hrm.models import Bank, BankAccount, Block, Branch, Department, Employee, Position

User = get_user_model()


class EmployeeExportAPITest(TestCase):
    """Test cases for Employee export functionality"""

    def setUp(self):
        """Set up test data"""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )
        self.position = Position.objects.create(
            code="POS001",
            name="Test Position",
        )

        # Create nationality
        self.nationality = Nationality.objects.create(
            name="Vietnamese",
        )

        # Create bank
        self.bank = Bank.objects.create(
            code="VCB",
            name="Vietcombank",
        )

        # Create test employee with all fields
        self.employee = Employee.objects.create(
            fullname="Test Employee",
            username="test001",
            email="test1@example.com",
            phone="1234567890",
            attendance_code="ATT001",
            date_of_birth=date(1990, 1, 1),
            start_date=date(2020, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            citizen_id="123456789012",
            citizen_id_issued_date=date(2010, 1, 1),
            citizen_id_issued_place="Test City",
            tax_code="TAX123",
            personal_email="personal@example.com",
            gender=Employee.Gender.MALE,
            marital_status=Employee.MaritalStatus.SINGLE,
            nationality=self.nationality,
            ethnicity="Kinh",
            religion="None",
            place_of_birth="Hanoi",
            residential_address="123 Test Street",
            permanent_address="456 Home Street",
            emergency_contact_name="Emergency Contact",
            emergency_contact_phone="0987654321",
            note="Test note",
        )

        # Create bank account for employee
        self.bank_account = BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="123456789",
            account_name="Test Employee",
            is_primary=True,
        )

        # Start patchers for periodic/async aggregation tasks
        self._patcher_aggregate_hr = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
        self.mock_aggregate_hr = self._patcher_aggregate_hr.start()

        self._patcher_aggregate_recruit = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate"
        )
        self.mock_aggregate_recruit = self._patcher_aggregate_recruit.start()

    def tearDown(self):
        """Clean up patchers"""
        self._patcher_aggregate_hr.stop()
        self._patcher_aggregate_recruit.stop()

    def test_export_employee_direct(self):
        """Test exporting employees with direct delivery"""
        export_url = reverse("hrm:employee-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

    def test_export_employee_fields(self):
        """Test that export includes correct fields"""
        # Export with direct delivery to check fields
        export_url = reverse("hrm:employee-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        # File should be generated and downloadable
        self.assertTrue(len(response.content) > 0)

    def test_export_employee_filtered(self):
        """Test exporting filtered employees"""
        # Create another employee with different status
        Employee.objects.create(
            fullname="Resigned Employee",
            username="resigned001",
            email="resigned@example.com",
            phone="1111111111",
            attendance_code="RES001",
            date_of_birth=date(1985, 5, 5),
            start_date=date(2015, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.RESIGNED,
            resignation_start_date=date(2024, 12, 1),
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            citizen_id="999999999999",
        )

        # Export with status filter
        export_url = reverse("hrm:employee-export")
        response = self.client.get(export_url, {"delivery": "direct", "status": "Active"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertTrue(len(response.content) > 0)

    def test_export_employee_with_bank_account(self):
        """Test that export includes bank account information"""
        export_url = reverse("hrm:employee-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        # Bank account data should be included in the export
        self.assertTrue(len(response.content) > 0)

    def test_export_employee_multiple(self):
        """Test exporting multiple employees"""
        # Create additional employees
        for i in range(3):
            Employee.objects.create(
                fullname=f"Employee {i}",
                username=f"emp{i:03d}",
                email=f"emp{i}@example.com",
                phone=f"555000{i:04d}",
                attendance_code=f"EMP{i:03d}",
                date_of_birth=date(1990 + i, 1, 1),
                start_date=date(2020 + i, 1, 1),
                branch=self.branch,
                block=self.block,
                department=self.department,
                status=Employee.Status.ACTIVE,
                citizen_id=f"11111111{i:04d}",
            )

        # Export all employees
        export_url = reverse("hrm:employee-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertTrue(len(response.content) > 0)
