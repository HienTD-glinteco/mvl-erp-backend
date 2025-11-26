"""Tests for Decision model and API."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.files.models import FileModel
from apps.hrm.models import Block, Branch, Decision, Department, Employee

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content

    def get_response_error(self, response):
        """Extract error from wrapped API response."""
        content = json.loads(response.content.decode())
        return content.get("error")


class DecisionTestMixin:
    """Mixin to create common test fixtures for Decision tests."""

    def create_employee_fixtures(self):
        """Create Province, Branch, Block, Department, and Employee fixtures."""
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

        self.employee = Employee.objects.create(
            code="MV000001",
            fullname="John Doe",
            email="john.doe@example.com",
            username="johndoe",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
        )


class DecisionModelTest(TransactionTestCase, DecisionTestMixin):
    """Test cases for Decision model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.create_employee_fixtures()

    def test_create_decision(self):
        """Test creating a decision."""
        decision = Decision.objects.create(
            decision_number="QD-2025-001",
            name="Test Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
            reason="Test reason",
            content="Test content",
            note="Test note",
            signing_status=Decision.SigningStatus.DRAFT,
        )

        self.assertEqual(decision.decision_number, "QD-2025-001")
        self.assertEqual(decision.name, "Test Decision")
        self.assertEqual(decision.signing_date, date(2025, 1, 15))
        self.assertEqual(decision.signer, self.employee)
        self.assertEqual(decision.effective_date, date(2025, 2, 1))
        self.assertEqual(decision.reason, "Test reason")
        self.assertEqual(decision.content, "Test content")
        self.assertEqual(decision.note, "Test note")
        self.assertEqual(decision.signing_status, Decision.SigningStatus.DRAFT)

    def test_decision_str_representation(self):
        """Test string representation of decision."""
        decision = Decision.objects.create(
            decision_number="QD-2025-002",
            name="String Test Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
        )

        self.assertEqual(str(decision), "QD-2025-002 - String Test Decision")

    def test_decision_unique_number(self):
        """Test that decision_number is unique."""
        Decision.objects.create(
            decision_number="QD-2025-003",
            name="First Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
        )

        with self.assertRaises(Exception):
            Decision.objects.create(
                decision_number="QD-2025-003",
                name="Duplicate Decision",
                signing_date=date(2025, 1, 16),
                signer=self.employee,
                effective_date=date(2025, 2, 2),
            )

    def test_decision_signing_status_default(self):
        """Test that default signing_status is DRAFT."""
        decision = Decision.objects.create(
            decision_number="QD-2025-004",
            name="Default Status Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
        )

        self.assertEqual(decision.signing_status, Decision.SigningStatus.DRAFT)

    def test_decision_colored_value(self):
        """Test colored value mapping using ColoredValueMixin."""
        decision = Decision.objects.create(
            decision_number="QD-2025-005",
            name="Color Test Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
            signing_status=Decision.SigningStatus.DRAFT,
        )

        colored_value = decision.get_colored_value("signing_status")
        self.assertEqual(colored_value["value"], Decision.SigningStatus.DRAFT)
        self.assertEqual(colored_value["variant"], "GREY")

        # Test issued status
        decision.signing_status = Decision.SigningStatus.ISSUED
        decision.save()

        colored_value = decision.get_colored_value("signing_status")
        self.assertEqual(colored_value["value"], Decision.SigningStatus.ISSUED)
        self.assertEqual(colored_value["variant"], "GREEN")

    def test_colored_signing_status_property(self):
        """Test colored_signing_status property returns correct format for ColoredValueSerializer."""
        decision = Decision.objects.create(
            decision_number="QD-2025-006",
            name="Property Test Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
            signing_status=Decision.SigningStatus.DRAFT,
        )

        # Test draft status property
        self.assertEqual(decision.colored_signing_status["value"], Decision.SigningStatus.DRAFT)
        self.assertEqual(decision.colored_signing_status["variant"], "GREY")

        # Test issued status property
        decision.signing_status = Decision.SigningStatus.ISSUED
        decision.save()

        self.assertEqual(decision.colored_signing_status["value"], Decision.SigningStatus.ISSUED)
        self.assertEqual(decision.colored_signing_status["variant"], "GREEN")


class DecisionAPITest(TransactionTestCase, APITestMixin, DecisionTestMixin):
    """Test cases for Decision API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Clear existing data
        Decision.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create employee fixtures
        self.create_employee_fixtures()

        # Create a confirmed file for tests that require attachment_ids
        self.test_file = FileModel.objects.create(
            purpose="decision",
            file_name="test_attachment.pdf",
            file_path="uploads/decision/test_attachment.pdf",
            is_confirmed=True,
        )

        # Create test decisions
        self.decision1 = Decision.objects.create(
            decision_number="QD-2025-001",
            name="Salary Adjustment Decision",
            signing_date=date(2025, 1, 15),
            signer=self.employee,
            effective_date=date(2025, 2, 1),
            reason="Annual salary review",
            content="Salary adjustment content",
            note="Approved by HR",
            signing_status=Decision.SigningStatus.ISSUED,
        )

        self.decision2 = Decision.objects.create(
            decision_number="QD-2025-002",
            name="Employee Promotion Decision",
            signing_date=date(2025, 1, 20),
            signer=self.employee,
            effective_date=date(2025, 3, 1),
            reason="Performance evaluation",
            content="Promotion content",
            note="Draft version",
            signing_status=Decision.SigningStatus.DRAFT,
        )

    def test_list_decisions(self):
        """Test listing all decisions."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_retrieve_decision(self):
        """Test retrieving a single decision."""
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["decision_number"], "QD-2025-001")
        self.assertEqual(data["name"], "Salary Adjustment Decision")
        self.assertEqual(data["signing_date"], "2025-01-15")
        self.assertEqual(data["signer"]["id"], self.employee.id)
        self.assertEqual(data["signer"]["fullname"], "John Doe")
        self.assertEqual(data["signing_status"], "issued")
        self.assertEqual(data["colored_signing_status"]["value"], "issued")
        self.assertEqual(data["colored_signing_status"]["variant"], "GREEN")

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_create_decision(self, mock_s3_service_class):
        """Test creating a new decision."""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/test.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/test.pdf"

        # Create a file for this test
        test_file = FileModel.objects.create(
            purpose="decision",
            file_name="create_test.pdf",
            file_path="uploads/decision/create_test.pdf",
            is_confirmed=True,
        )

        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-003",
            "name": "New Test Decision",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "reason": "New test reason",
            "content": "New test content",
            "note": "New test note",
            "signing_status": "draft",
            "attachment_ids": [test_file.id],
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(data["decision_number"], "QD-2025-003")
        self.assertEqual(data["name"], "New Test Decision")
        self.assertEqual(data["signer"]["id"], self.employee.id)
        self.assertEqual(len(data["attachments"]), 1)
        self.assertEqual(Decision.objects.count(), 3)

    def test_create_decision_duplicate_number(self):
        """Test creating a decision with duplicate number."""
        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-001",  # Duplicate
            "name": "Duplicate Decision",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "attachment_ids": [self.test_file.id],
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = self.get_response_error(response)
        self.assertEqual("decision_number", error["errors"][0]["attr"])

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_decision(self, mock_s3_service_class):
        """Test updating a decision."""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/test.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/test.pdf"

        # Create a file for the update
        update_file = FileModel.objects.create(
            purpose="decision",
            file_name="update_test.pdf",
            file_path="uploads/decision/update_test.pdf",
            is_confirmed=True,
        )

        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision2.pk})
        payload = {
            "decision_number": "QD-2025-002",
            "name": "Updated Decision Name",
            "signing_date": "2025-01-20",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "signing_status": "issued",
            "attachment_ids": [update_file.id],
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "Updated Decision Name")
        self.assertEqual(data["signing_status"], "issued")
        self.assertEqual(data["colored_signing_status"]["value"], "issued")
        self.assertEqual(data["colored_signing_status"]["variant"], "GREEN")
        self.assertEqual(len(data["attachments"]), 1)

    def test_partial_update_decision(self):
        """Test partial update of a decision."""
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision2.pk})
        payload = {
            "signing_status": "issued",
        }
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["signing_status"], "issued")

    def test_delete_decision(self):
        """Test deleting a decision."""
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision2.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Verify soft delete (if using BaseModel) or hard delete
        self.assertEqual(Decision.objects.filter(pk=self.decision2.pk).count(), 0)

    def test_filter_by_decision_number(self):
        """Test filtering decisions by decision_number."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"decision_number": "001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["decision_number"], "QD-2025-001")

    def test_filter_by_signing_status(self):
        """Test filtering decisions by signing_status."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"signing_status": "draft"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["signing_status"], "draft")

    def test_filter_by_signing_date_range(self):
        """Test filtering decisions by signing date range."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"signing_date_from": "2025-01-18", "signing_date_to": "2025-01-25"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["decision_number"], "QD-2025-002")

    def test_filter_by_signer(self):
        """Test filtering decisions by signer."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"signer": self.employee.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_search_by_decision_number(self):
        """Test searching decisions by decision_number."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"search": "QD-2025-001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["decision_number"], "QD-2025-001")

    def test_search_by_name(self):
        """Test searching decisions by name."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"search": "Salary Adjustment"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Salary Adjustment Decision")

    def test_ordering_by_signing_date(self):
        """Test ordering decisions by signing_date."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"ordering": "signing_date"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        # Ascending order - oldest first
        self.assertEqual(data[0]["decision_number"], "QD-2025-001")
        self.assertEqual(data[1]["decision_number"], "QD-2025-002")

    def test_ordering_by_signing_date_desc(self):
        """Test ordering decisions by signing_date descending."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"ordering": "-signing_date"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        # Descending order - newest first
        self.assertEqual(data[0]["decision_number"], "QD-2025-002")
        self.assertEqual(data[1]["decision_number"], "QD-2025-001")

    def test_export_xlsx(self):
        """Test XLSX export endpoint."""
        url = reverse("hrm:decision-export")
        response = self.client.get(url, {"delivery": "direct"})

        # Should return 200 or 206 (partial content for direct download)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_206_PARTIAL_CONTENT])

    def test_decision_signer_nested_serializer(self):
        """Test that signer is properly nested with employee details."""
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("signer", data)
        self.assertEqual(data["signer"]["id"], self.employee.id)
        self.assertEqual(data["signer"]["code"], "MV000001")
        self.assertEqual(data["signer"]["fullname"], "John Doe")
        self.assertEqual(data["signer"]["email"], "john.doe@example.com")

    def test_decision_attachments_empty(self):
        """Test that attachments field returns empty list when no attachments."""
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertIn("attachments", data)
        self.assertEqual(data["attachments"], [])

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_create_decision_with_attachments(self, mock_s3_service_class):
        """Test creating a decision with attachment_ids."""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/test.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/test.pdf"

        # Create confirmed file records
        file1 = FileModel.objects.create(
            purpose="decision",
            file_name="document1.pdf",
            file_path="uploads/decision/document1.pdf",
            is_confirmed=True,
        )
        file2 = FileModel.objects.create(
            purpose="decision",
            file_name="document2.pdf",
            file_path="uploads/decision/document2.pdf",
            is_confirmed=True,
        )

        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-ATT-001",
            "name": "Decision with Attachments",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "attachment_ids": [file1.id, file2.id],
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(len(data["attachments"]), 2)
        attachment_names = [a["file_name"] for a in data["attachments"]]
        self.assertIn("document1.pdf", attachment_names)
        self.assertIn("document2.pdf", attachment_names)

    def test_create_decision_with_invalid_attachment_ids(self):
        """Test creating a decision with non-existent attachment IDs."""
        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-ATT-002",
            "name": "Decision with Invalid Attachments",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "attachment_ids": [99999, 99998],  # Non-existent IDs
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = self.get_response_error(response)
        self.assertIn("attachment_ids", str(error))

    def test_create_decision_with_unconfirmed_attachment(self):
        """Test creating a decision with unconfirmed file ID."""
        # Create unconfirmed file record
        unconfirmed_file = FileModel.objects.create(
            purpose="decision",
            file_name="unconfirmed.pdf",
            file_path="uploads/tmp/unconfirmed.pdf",
            is_confirmed=False,  # Not confirmed
        )

        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-ATT-003",
            "name": "Decision with Unconfirmed Attachment",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "attachment_ids": [unconfirmed_file.id],
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = self.get_response_error(response)
        self.assertIn("attachment_ids", str(error))

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_decision_attachments(self, mock_s3_service_class):
        """Test updating decision attachments."""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/test.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/test.pdf"

        # Create confirmed file records
        file1 = FileModel.objects.create(
            purpose="decision",
            file_name="new_attachment.pdf",
            file_path="uploads/decision/new_attachment.pdf",
            is_confirmed=True,
        )

        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision1.pk})
        payload = {
            "attachment_ids": [file1.id],
        }
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data["attachments"]), 1)
        self.assertEqual(data["attachments"][0]["file_name"], "new_attachment.pdf")

    def test_update_decision_clear_attachments_not_allowed(self):
        """Test that clearing all attachments with empty array is not allowed."""
        # First, create a decision with attachments
        file1 = FileModel.objects.create(
            purpose="decision",
            file_name="to_be_cleared.pdf",
            file_path="uploads/decision/to_be_cleared.pdf",
            is_confirmed=True,
        )

        # Link attachment to decision1
        content_type = ContentType.objects.get_for_model(Decision)
        file1.content_type = content_type
        file1.object_id = self.decision1.pk
        file1.save()

        # Verify attachment is linked
        self.decision1.refresh_from_db()
        self.assertEqual(self.decision1.attachments.count(), 1)

        # Try to clear attachments by passing empty array - should fail
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision1.pk})
        payload = {
            "attachment_ids": [],
        }
        response = self.client.patch(url, payload, format="json")

        # Empty attachment_ids is not allowed (allow_empty=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = self.get_response_error(response)
        self.assertIn("attachment_ids", str(error))

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_decision_without_attachment_ids_preserves_existing(self, mock_s3_service_class):
        """Test that not providing attachment_ids preserves existing attachments."""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/test.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/test.pdf"

        # First, create and link an attachment
        file1 = FileModel.objects.create(
            purpose="decision",
            file_name="existing_attachment.pdf",
            file_path="uploads/decision/existing_attachment.pdf",
            is_confirmed=True,
        )

        # Link attachment to decision1
        content_type = ContentType.objects.get_for_model(Decision)
        file1.content_type = content_type
        file1.object_id = self.decision1.pk
        file1.save()

        # Update decision without attachment_ids
        url = reverse("hrm:decision-detail", kwargs={"pk": self.decision1.pk})
        payload = {
            "name": "Updated Name Only",
        }
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        # Attachment should still be there
        self.assertEqual(len(data["attachments"]), 1)
        self.assertEqual(data["attachments"][0]["file_name"], "existing_attachment.pdf")

    def test_create_decision_with_empty_attachment_ids_not_allowed(self):
        """Test creating a decision with empty attachment_ids array is not allowed."""
        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-ATT-004",
            "name": "Decision with Empty Attachments",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "attachment_ids": [],
        }
        response = self.client.post(url, payload, format="json")

        # Empty attachment_ids is not allowed (allow_empty=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = self.get_response_error(response)
        self.assertIn("attachment_ids", str(error))

    def test_create_decision_without_attachment_ids_not_allowed(self):
        """Test creating a decision without attachment_ids field is not allowed."""
        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-ATT-005",
            "name": "Decision without Attachments Field",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
        }
        response = self.client.post(url, payload, format="json")

        # Missing attachment_ids is not allowed (required=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = self.get_response_error(response)
        self.assertIn("attachment_ids", str(error))
