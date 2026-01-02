"""Tests for Decision model and API."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status

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
            phone="0900000001",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
        )


@pytest.mark.django_db
class TestDecisionModel:
    """Test cases for Decision model."""

    def test_create_decision(self, employee):
        """Test creating a decision."""
        decision = Decision.objects.create(
            decision_number="QD-2025-001",
            name="Test Decision",
            signing_date=date(2025, 1, 15),
            signer=employee,
            effective_date=date(2025, 2, 1),
            reason="Test reason",
            content="Test content",
            note="Test note",
            signing_status=Decision.SigningStatus.DRAFT,
        )

        assert decision.decision_number == "QD-2025-001"
        assert decision.name == "Test Decision"
        assert decision.signing_date == date(2025, 1, 15)
        assert decision.signer == employee
        assert decision.effective_date == date(2025, 2, 1)
        assert decision.reason == "Test reason"
        assert decision.content == "Test content"
        assert decision.note == "Test note"
        assert decision.signing_status == Decision.SigningStatus.DRAFT

    def test_decision_str_representation(self, employee):
        """Test string representation of decision."""
        decision = Decision.objects.create(
            decision_number="QD-2025-002",
            name="String Test Decision",
            signing_date=date(2025, 1, 15),
            signer=employee,
            effective_date=date(2025, 2, 1),
        )

        assert str(decision) == "QD-2025-002 - String Test Decision"

    def test_decision_unique_number(self, employee):
        """Test that decision_number is unique."""
        Decision.objects.create(
            decision_number="QD-2025-003",
            name="First Decision",
            signing_date=date(2025, 1, 15),
            signer=employee,
            effective_date=date(2025, 2, 1),
        )

        with pytest.raises(Exception):
            Decision.objects.create(
                decision_number="QD-2025-003",
                name="Duplicate Decision",
                signing_date=date(2025, 1, 16),
                signer=employee,
                effective_date=date(2025, 2, 2),
            )

    def test_decision_signing_status_default(self, employee):
        """Test that default signing_status is DRAFT."""
        decision = Decision.objects.create(
            decision_number="QD-2025-004",
            name="Default Status Decision",
            signing_date=date(2025, 1, 15),
            signer=employee,
            effective_date=date(2025, 2, 1),
        )

        assert decision.signing_status == Decision.SigningStatus.DRAFT

    def test_decision_colored_value(self, employee):
        """Test colored value mapping using ColoredValueMixin."""
        decision = Decision.objects.create(
            decision_number="QD-2025-005",
            name="Color Test Decision",
            signing_date=date(2025, 1, 15),
            signer=employee,
            effective_date=date(2025, 2, 1),
            signing_status=Decision.SigningStatus.DRAFT,
        )

        colored_value = decision.get_colored_value("signing_status")
        assert colored_value["value"] == Decision.SigningStatus.DRAFT
        assert colored_value["variant"] == "GREY"

        # Test issued status
        decision.signing_status = Decision.SigningStatus.ISSUED
        decision.save()

        colored_value = decision.get_colored_value("signing_status")
        assert colored_value["value"] == Decision.SigningStatus.ISSUED
        assert colored_value["variant"] == "GREEN"

    def test_colored_signing_status_property(self, employee):
        """Test colored_signing_status property returns correct format for ColoredValueSerializer."""
        decision = Decision.objects.create(
            decision_number="QD-2025-006",
            name="Property Test Decision",
            signing_date=date(2025, 1, 15),
            signer=employee,
            effective_date=date(2025, 2, 1),
            signing_status=Decision.SigningStatus.DRAFT,
        )

        # Test draft status property
        assert decision.colored_signing_status["value"] == Decision.SigningStatus.DRAFT
        assert decision.colored_signing_status["variant"] == "GREY"

        # Test issued status property
        decision.signing_status = Decision.SigningStatus.ISSUED
        decision.save()

        assert decision.colored_signing_status["value"] == Decision.SigningStatus.ISSUED
        assert decision.colored_signing_status["variant"] == "GREEN"


@pytest.mark.django_db
class TestDecisionAPI(APITestMixin):
    """Test cases for Decision API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, employee):
        """Set up test client and user linked to employee."""
        self.client = api_client
        self.user = superuser
        self.employee = employee

    @pytest.fixture
    def test_file(self):
        """Create a confirmed file for tests that require attachment_ids."""
        return FileModel.objects.create(
            purpose="decision",
            file_name="test_attachment.pdf",
            file_path="uploads/decision/test_attachment.pdf",
            is_confirmed=True,
        )

    @pytest.fixture
    def decisions(self):
        """Create test decisions."""
        d1 = Decision.objects.create(
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

        d2 = Decision.objects.create(
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
        return d1, d2

    def test_list_decisions(self, decisions):
        """Test listing all decisions."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_retrieve_decision(self, decisions):
        """Test retrieving a single decision."""
        decision1, _ = decisions
        url = reverse("hrm:decision-detail", kwargs={"pk": decision1.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["decision_number"] == "QD-2025-001"
        assert data["name"] == "Salary Adjustment Decision"
        assert data["signing_date"] == "2025-01-15"
        assert data["signer"]["id"] == self.employee.id
        # In conftest.py, employee fullname is "Test Employee"
        assert data["signer"]["fullname"] == "Test Employee"
        assert data["signing_status"] == "issued"
        assert data["colored_signing_status"]["value"] == "issued"
        assert data["colored_signing_status"]["variant"] == "GREEN"

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

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert data["decision_number"] == "QD-2025-003"
        assert data["name"] == "New Test Decision"
        assert data["signer"]["id"] == self.employee.id
        assert len(data["attachments"]) == 1
        assert Decision.objects.count() == 1

    def test_create_decision_duplicate_number(self, test_file, decisions):
        """Test creating a decision with duplicate number."""
        url = reverse("hrm:decision-list")
        payload = {
            "decision_number": "QD-2025-001",  # Duplicate
            "name": "Duplicate Decision",
            "signing_date": "2025-02-01",
            "signer_id": self.employee.id,
            "effective_date": "2025-03-01",
            "attachment_ids": [test_file.id],
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = self.get_response_error(response)
        assert "decision_number" == error["errors"][0]["attr"]

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_decision(self, mock_s3_service_class, decisions):
        """Test updating a decision."""
        _, decision2 = decisions
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

        url = reverse("hrm:decision-detail", kwargs={"pk": decision2.pk})
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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["name"] == "Updated Decision Name"
        assert data["signing_status"] == "issued"
        assert data["colored_signing_status"]["value"] == "issued"
        assert data["colored_signing_status"]["variant"] == "GREEN"
        assert len(data["attachments"]) == 1

    def test_partial_update_decision(self, decisions):
        """Test partial update of a decision."""
        _, decision2 = decisions
        url = reverse("hrm:decision-detail", kwargs={"pk": decision2.pk})
        payload = {
            "signing_status": "issued",
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["signing_status"] == "issued"

    def test_delete_decision(self, decisions):
        """Test deleting a decision."""
        _, decision2 = decisions
        url = reverse("hrm:decision-detail", kwargs={"pk": decision2.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Verify soft delete (if using BaseModel) or hard delete
        assert Decision.objects.filter(pk=decision2.pk).count() == 0

    def test_filter_by_decision_number(self, decisions):
        """Test filtering decisions by decision_number."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"decision_number": "001"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["decision_number"] == "QD-2025-001"

    def test_filter_by_signing_status(self, decisions):
        """Test filtering decisions by signing_status."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"signing_status": "draft"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["signing_status"] == "draft"

    def test_filter_by_signing_date_range(self, decisions):
        """Test filtering decisions by signing date range."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"signing_date_from": "2025-01-18", "signing_date_to": "2025-01-25"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["decision_number"] == "QD-2025-002"

    def test_filter_by_signer(self, decisions):
        """Test filtering decisions by signer."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"signer": self.employee.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_search_by_decision_number(self, decisions):
        """Test searching decisions by decision_number."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"search": "QD-2025-001"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["decision_number"] == "QD-2025-001"

    def test_search_by_name(self, decisions):
        """Test searching decisions by name."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"search": "Salary Adjustment"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Salary Adjustment Decision"

    def test_ordering_by_signing_date(self, decisions):
        """Test ordering decisions by signing_date."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"ordering": "signing_date"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2
        # Ascending order - oldest first
        assert data[0]["decision_number"] == "QD-2025-001"
        assert data[1]["decision_number"] == "QD-2025-002"

    def test_ordering_by_signing_date_desc(self, decisions):
        """Test ordering decisions by signing_date descending."""
        url = reverse("hrm:decision-list")
        response = self.client.get(url, {"ordering": "-signing_date"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2
        # Descending order - newest first
        assert data[0]["decision_number"] == "QD-2025-002"
        assert data[1]["decision_number"] == "QD-2025-001"

    def test_export_xlsx(self, decisions):
        """Test XLSX export endpoint."""
        url = reverse("hrm:decision-export")
        response = self.client.get(url, {"delivery": "direct"})

        # Should return 200 or 206 (partial content for direct download)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_206_PARTIAL_CONTENT]

    def test_decision_signer_nested_serializer(self, decisions):
        """Test that signer is properly nested with employee details."""
        decision1, _ = decisions
        url = reverse("hrm:decision-detail", kwargs={"pk": decision1.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "signer" in data
        assert data["signer"]["id"] == self.employee.id
        # In conftest.py, employee code is random-like or specific
        assert data["signer"]["fullname"] == "Test Employee"
        assert data["signer"]["email"] == "test@example.com"

    def test_decision_attachments_empty(self, decisions):
        """Test that attachments field returns empty list when no attachments."""
        decision1, _ = decisions
        url = reverse("hrm:decision-detail", kwargs={"pk": decision1.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert "attachments" in data
        assert data["attachments"] == []

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

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert len(data["attachments"]) == 2
        attachment_names = [a["file_name"] for a in data["attachments"]]
        assert "document1.pdf" in attachment_names
        assert "document2.pdf" in attachment_names

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

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = self.get_response_error(response)
        assert "attachment_ids" in str(error)

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

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = self.get_response_error(response)
        assert "attachment_ids" in str(error)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_decision_attachments(self, mock_s3_service_class, decisions):
        """Test updating decision attachments."""
        decision1, _ = decisions
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

        url = reverse("hrm:decision-detail", kwargs={"pk": decision1.pk})
        payload = {
            "attachment_ids": [file1.id],
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["file_name"] == "new_attachment.pdf"

    def test_update_decision_clear_attachments_not_allowed(self, decisions):
        """Test that clearing all attachments with empty array is not allowed."""
        decision1, _ = decisions
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
        file1.object_id = decision1.pk
        file1.save()

        # Verify attachment is linked
        decision1.refresh_from_db()
        assert decision1.attachments.count() == 1

        # Try to clear attachments by passing empty array - should fail
        url = reverse("hrm:decision-detail", kwargs={"pk": decision1.pk})
        payload = {
            "attachment_ids": [],
        }
        response = self.client.patch(url, payload, format="json")

        # Empty attachment_ids is not allowed (allow_empty=False)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = self.get_response_error(response)
        assert "attachment_ids" in str(error)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_decision_without_attachment_ids_preserves_existing(self, mock_s3_service_class, decisions):
        """Test that not providing attachment_ids preserves existing attachments."""
        decision1, _ = decisions
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
        file1.object_id = decision1.pk
        file1.save()

        # Update decision without attachment_ids
        url = reverse("hrm:decision-detail", kwargs={"pk": decision1.pk})
        payload = {
            "name": "Updated Name Only",
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        # Attachment should still be there
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["file_name"] == "existing_attachment.pdf"

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
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = self.get_response_error(response)
        assert "attachment_ids" in str(error)
