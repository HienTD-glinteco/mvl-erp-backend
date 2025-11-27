from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee


class EmployeeCitizenIdTest(TestCase):
    """Test cases for Employee citizen_id field constraints"""

    def setUp(self):
        """Set up test data"""
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

    def test_citizen_id_required(self):
        """Test that citizen_id is required"""
        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            # citizen_id not provided
        )

        with self.assertRaises(ValidationError) as context:
            # Provide temporary code so field-level validation for `code` does not block
            employee.code = "TEMP_TEST"
            employee.full_clean()

        self.assertIn("citizen_id", context.exception.error_dict)

    def test_citizen_id_length_validation(self):
        """Test that citizen_id must be between 9 and 12 digits"""
        valid_ids = ["123456789", "123456789012"]
        invalid_ids = ["12345", "1234567890123"]

        for citizen_id in valid_ids:
            with self.subTest(citizen_id=citizen_id):
                employee = Employee(
                    fullname="John Doe",
                    username=f"johndoe_{citizen_id}",
                    email=f"john_{citizen_id}@example.com",
                    phone="0123456789",
                    attendance_code="12345",
                    start_date="2024-01-01",
                    branch=self.branch,
                    block=self.block,
                    department=self.department,
                    citizen_id=citizen_id,
                )
                # Provide temporary code so full_clean doesn't fail on 'code' field
                employee.code = f"TEMP_{citizen_id}"
                # Validate in Python first to ensure field validators run
                employee.full_clean()
                # Then persist to DB
                employee.save()

        for citizen_id in invalid_ids:
            with self.subTest(citizen_id=citizen_id):
                employee = Employee(
                    fullname="John Doe",
                    username=f"johndoe_{citizen_id}",
                    email=f"john_{citizen_id}@example.com",
                    phone="0123456789",
                    attendance_code="12345",
                    start_date="2024-01-01",
                    branch=self.branch,
                    block=self.block,
                    department=self.department,
                    citizen_id=citizen_id,
                )
                with self.assertRaises(ValidationError) as context:
                    # Provide temporary code so full_clean doesn't fail on 'code' field
                    employee.code = f"TEMP_{citizen_id}"
                    # Run validators before any DB write to catch length errors
                    employee.full_clean()
                self.assertIn("citizen_id", context.exception.error_dict)

    def test_citizen_id_must_be_numeric(self):
        """Test that citizen_id must contain only digits"""
        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="12345678901A",  # Contains letter
        )

        with self.assertRaises(ValidationError) as context:
            # Provide temporary code so field-level validation for `code` does not block
            employee.code = "TEMP_TEST"
            employee.full_clean()

        self.assertIn("citizen_id", context.exception.error_dict)

    def test_citizen_id_unique(self):
        """Test that citizen_id must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        # Try to create another employee with same citizen_id
        with self.assertRaises(IntegrityError):
            Employee.objects.create(
                fullname="Jane Doe",
                username="janedoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="123456789",  # Same as first employee
            )

    def test_valid_citizen_id(self):
        """Test creating employee with valid citizen_id"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        self.assertEqual(employee.citizen_id, "123456789")


class EmployeeTaxCodeTest(TestCase):
    """Test cases for Employee tax_code field constraints"""

    def setUp(self):
        """Set up test data"""
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

    def test_tax_code_can_be_null(self):
        """Test that tax_code can be null"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789012",
            # tax_code not provided
        )

        self.assertEqual(employee.tax_code, "")

    def test_tax_code_unique_when_not_null(self):
        """Test that tax_code must be unique when not null"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789012",
            tax_code="TAX123456",
        )

        # Try to create another employee with same tax_code
        with self.assertRaises(IntegrityError):
            Employee.objects.create(
                fullname="Jane Doe",
                username="janedoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="098765432109",
                tax_code="TAX123456",  # Same as first employee
            )

    def test_multiple_employees_with_empty_tax_code(self):
        """Test that multiple employees can have empty tax_code"""
        employee1 = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789012",
            tax_code="",  # Empty
        )

        employee2 = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0987654321",
            attendance_code="54321",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="098765432109",
            tax_code="",  # Empty
        )

        self.assertEqual(employee1.tax_code, "")
        self.assertEqual(employee2.tax_code, "")

    def test_valid_tax_code(self):
        """Test creating employee with valid tax_code"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789012",
            tax_code="TAX123456",
        )

        self.assertEqual(employee.tax_code, "TAX123456")
