"""Tests for RecruitmentRequest serializer."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.api.serializers import RecruitmentRequestSerializer
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentRequest,
)

User = get_user_model()


class RecruitmentRequestSerializerTest(TestCase):
    """Test cases for RecruitmentRequestSerializer."""

    def setUp(self):
        """Set up test data."""
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

        # Create employee as proposer
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            phone="0123456789",
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create a recruitment request for testing
        self.recruitment_request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type="NEW_HIRE",
            status="DRAFT",
            proposed_salary="2000-3000 USD",
            number_of_positions=2,
        )

    def test_serializer_read_returns_nested_objects(self):
        """Test that serializer returns nested objects for read operations."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert: Check nested objects are returned
        self.assertIn("job_description", data)
        self.assertIsInstance(data["job_description"], dict)
        self.assertEqual(data["job_description"]["id"], self.job_description.id)
        self.assertEqual(data["job_description"]["title"], self.job_description.title)

        self.assertIn("branch", data)
        self.assertIsInstance(data["branch"], dict)
        self.assertEqual(data["branch"]["id"], self.branch.id)

        self.assertIn("block", data)
        self.assertIsInstance(data["block"], dict)
        self.assertEqual(data["block"]["id"], self.block.id)

        self.assertIn("department", data)
        self.assertIsInstance(data["department"], dict)
        self.assertEqual(data["department"]["id"], self.department.id)

        self.assertIn("proposer", data)
        self.assertIsInstance(data["proposer"], dict)
        self.assertEqual(data["proposer"]["id"], self.employee.id)

    def test_serializer_write_accepts_id_fields(self):
        """Test that serializer accepts _id fields for write operations."""
        # Arrange
        data = {
            "name": "Frontend Developer Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "REPLACEMENT",
            "status": "OPEN",
            "proposed_salary": "1500-2500 USD",
            "number_of_positions": 3,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        self.assertEqual(instance.name, data["name"])
        self.assertEqual(instance.job_description_id, data["job_description_id"])
        self.assertEqual(instance.department_id, data["department_id"])
        self.assertEqual(instance.proposer_id, data["proposer_id"])
        self.assertEqual(instance.recruitment_type, data["recruitment_type"])
        self.assertEqual(instance.status, data["status"])
        self.assertEqual(instance.proposed_salary, data["proposed_salary"])
        self.assertEqual(instance.number_of_positions, data["number_of_positions"])

    def test_serializer_includes_colored_status(self):
        """Test that serializer includes colored_status field."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert
        self.assertIn("colored_status", data)
        self.assertIsInstance(data["colored_status"], dict)
        self.assertIn("value", data["colored_status"])
        self.assertIn("variant", data["colored_status"])
        self.assertEqual(data["colored_status"]["value"], "DRAFT")

    def test_serializer_includes_colored_recruitment_type(self):
        """Test that serializer includes colored_recruitment_type field."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert
        self.assertIn("colored_recruitment_type", data)
        self.assertIsInstance(data["colored_recruitment_type"], dict)
        self.assertIn("value", data["colored_recruitment_type"])
        self.assertIn("variant", data["colored_recruitment_type"])
        self.assertEqual(data["colored_recruitment_type"]["value"], "NEW_HIRE")

    def test_serializer_includes_number_of_candidates(self):
        """Test that serializer includes number_of_candidates field."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert
        self.assertIn("number_of_candidates", data)
        self.assertEqual(data["number_of_candidates"], 0)

    def test_serializer_includes_number_of_hires(self):
        """Test that serializer includes number_of_hires field."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert
        self.assertIn("number_of_hires", data)
        self.assertEqual(data["number_of_hires"], 0)

    def test_validate_number_of_positions_less_than_one(self):
        """Test validation fails when number_of_positions is less than 1."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 0,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("number_of_positions", serializer.errors)

    def test_validate_number_of_positions_negative(self):
        """Test validation fails when number_of_positions is negative."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": -1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("number_of_positions", serializer.errors)

    def test_validate_number_of_positions_valid(self):
        """Test validation passes when number_of_positions is valid."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 5,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_required_fields_validation(self):
        """Test that required fields are validated."""
        # Arrange: Empty data
        data = {}

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
        self.assertIn("job_description_id", serializer.errors)
        self.assertIn("proposer_id", serializer.errors)
        self.assertIn("recruitment_type", serializer.errors)
        self.assertIn("proposed_salary", serializer.errors)

    def test_department_id_is_optional(self):
        """Test that department_id is optional."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()
        self.assertIsNone(instance.department)

    def test_department_id_can_be_null(self):
        """Test that department_id can be explicitly set to null."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": None,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()
        self.assertIsNone(instance.department)

    def test_read_only_fields_cannot_be_written(self):
        """Test that read-only fields are ignored during write operations."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
            # Try to set read-only fields
            "code": "CUSTOM_CODE",
            "number_of_candidates": 100,
            "number_of_hires": 50,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        # Read-only fields should not be set from data
        self.assertNotEqual(instance.code, "CUSTOM_CODE")
        self.assertTrue(instance.code.startswith("RR"))

    def test_status_is_write_only(self):
        """Test that status field is write-only."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert: status should not be in the serialized data directly
        # (it's available through colored_status instead)
        self.assertNotIn("status", data)
        self.assertIn("colored_status", data)

    def test_recruitment_type_is_write_only(self):
        """Test that recruitment_type field is write-only."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert: recruitment_type should not be in the serialized data directly
        # (it's available through colored_recruitment_type instead)
        self.assertNotIn("recruitment_type", data)
        self.assertIn("colored_recruitment_type", data)

    def test_update_with_partial_data(self):
        """Test updating with partial data (PATCH behavior)."""
        # Arrange
        partial_data = {
            "name": "Updated Position Name",
            "number_of_positions": 5,
        }

        # Act
        serializer = RecruitmentRequestSerializer(
            instance=self.recruitment_request,
            data=partial_data,
            partial=True,
        )

        # Assert
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        self.assertEqual(instance.name, partial_data["name"])
        self.assertEqual(instance.number_of_positions, partial_data["number_of_positions"])
        # Other fields should remain unchanged
        self.assertEqual(instance.job_description_id, self.job_description.id)
        self.assertEqual(instance.recruitment_type, "NEW_HIRE")

    def test_default_fields_attribute(self):
        """Test that default_fields attribute is correctly defined."""
        # Arrange & Act
        default_fields = RecruitmentRequestSerializer.default_fields

        # Assert: Check all expected fields are in default_fields
        expected_fields = [
            "id",
            "code",
            "name",
            "job_description",
            "job_description_id",
            "branch",
            "block",
            "department",
            "department_id",
            "proposer",
            "proposer_id",
            "recruitment_type",
            "status",
            "colored_status",
            "colored_recruitment_type",
            "proposed_salary",
            "number_of_positions",
            "number_of_candidates",
            "number_of_hires",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            self.assertIn(field, default_fields, f"Field '{field}' is missing from default_fields")

    def test_meta_fields_include_all_necessary_fields(self):
        """Test that Meta.fields includes all necessary fields."""
        # Arrange & Act
        meta_fields = RecruitmentRequestSerializer.Meta.fields

        # Assert
        expected_fields = [
            "id",
            "code",
            "name",
            "job_description",
            "job_description_id",
            "branch",
            "block",
            "department",
            "department_id",
            "proposer",
            "proposer_id",
            "recruitment_type",
            "status",
            "colored_status",
            "colored_recruitment_type",
            "proposed_salary",
            "number_of_positions",
            "number_of_candidates",
            "number_of_hires",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            self.assertIn(field, meta_fields, f"Field '{field}' is missing from Meta.fields")

    def test_meta_read_only_fields_are_correct(self):
        """Test that Meta.read_only_fields are correctly defined."""
        # Arrange & Act
        read_only_fields = RecruitmentRequestSerializer.Meta.read_only_fields

        # Assert
        expected_read_only = [
            "id",
            "code",
            "job_description",
            "branch",
            "block",
            "department",
            "proposer",
            "colored_status",
            "colored_recruitment_type",
            "number_of_candidates",
            "number_of_hires",
            "created_at",
            "updated_at",
        ]

        for field in expected_read_only:
            self.assertIn(field, read_only_fields, f"Field '{field}' should be read-only")

    def test_validate_calls_model_clean_method(self):
        """Test that serializer validate method calls model's clean method."""
        # Arrange: Create data that would fail model validation
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": -5,  # Invalid - will fail model clean
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        # The error should come from model validation
        self.assertIn("number_of_positions", serializer.errors)

    def test_branch_and_block_auto_set_from_department(self):
        """Test that branch and block are automatically set from department."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()

        # Assert: branch and block should be auto-set from department
        self.assertEqual(instance.branch, self.department.branch)
        self.assertEqual(instance.block, self.department.block)

    def test_serializer_with_all_fields(self):
        """Test serialization includes all expected fields."""
        # Arrange & Act
        serializer = RecruitmentRequestSerializer(instance=self.recruitment_request)
        data = serializer.data

        # Assert: Check all fields are present
        expected_fields = [
            "id",
            "code",
            "name",
            "job_description",
            "branch",
            "block",
            "department",
            "proposer",
            "colored_status",
            "colored_recruitment_type",
            "proposed_salary",
            "number_of_positions",
            "number_of_candidates",
            "number_of_hires",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            self.assertIn(field, data, f"Field '{field}' is missing from serialized data")

    def test_invalid_job_description_id(self):
        """Test validation fails with invalid job_description_id."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": 99999,  # Non-existent ID
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("job_description_id", serializer.errors)

    def test_invalid_department_id(self):
        """Test validation fails with invalid department_id."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": 99999,  # Non-existent ID
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("department_id", serializer.errors)

    def test_invalid_proposer_id(self):
        """Test validation fails with invalid proposer_id."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": 99999,  # Non-existent ID
            "recruitment_type": "NEW_HIRE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("proposer_id", serializer.errors)

    def test_invalid_recruitment_type(self):
        """Test validation fails with invalid recruitment_type."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "INVALID_TYPE",
            "status": "DRAFT",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("recruitment_type", serializer.errors)

    def test_invalid_status(self):
        """Test validation fails with invalid status."""
        # Arrange
        data = {
            "name": "Test Position",
            "job_description_id": self.job_description.id,
            "department_id": self.department.id,
            "proposer_id": self.employee.id,
            "recruitment_type": "NEW_HIRE",
            "status": "INVALID_STATUS",
            "proposed_salary": "2000-3000 USD",
            "number_of_positions": 1,
        }

        # Act
        serializer = RecruitmentRequestSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)
