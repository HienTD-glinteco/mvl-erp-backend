from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.files.models import FileModel
from apps.hrm.constants import ContractImportMode
from apps.imports.constants import FILE_PURPOSE_IMPORT_TEMPLATE


@pytest.fixture
def import_file(db):
    """Create a confirmed file for import testing."""
    return FileModel.objects.create(
        file_name="test.xlsx",
        file_path="imports/test.xlsx",
        purpose="contract_import",
        size=100,
        is_confirmed=True,
    )


@pytest.fixture
def template_file_create(db):
    """Create a template file for create mode."""
    return FileModel.objects.create(
        file_name="hrm_creation_contract_template.xlsx",
        file_path="templates/hrm_creation_contract_template.xlsx",
        purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
        size=5000,
        is_confirmed=True,
    )


@pytest.fixture
def template_file_update(db):
    """Create a template file for update mode."""
    return FileModel.objects.create(
        file_name="hrm_update_contract_template.xlsx",
        file_path="templates/hrm_update_contract_template.xlsx",
        purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
        size=5000,
        is_confirmed=True,
    )


@pytest.mark.django_db
class TestContractImportAPI:
    def setup_method(self):
        # Patch S3 service for all tests in this class to avoid AWS calls
        self.s3_patcher = patch("apps.files.models.S3FileUploadService")
        self.mock_s3_service = self.s3_patcher.start()
        self.mock_s3_service.return_value.generate_download_url.return_value = "https://example.com/download"
        self.mock_s3_service.return_value.generate_view_url.return_value = "https://example.com/view"

    def teardown_method(self):
        self.s3_patcher.stop()

    def test_import_template_default(self, api_client, template_file_create):
        """Test getting default import template (create mode)."""
        url = reverse("hrm:contract-import-template")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json().get("data")
        assert data["file_id"] == template_file_create.id
        assert "hrm_creation_contract_template" in data["file_name"]

    def test_import_template_create_mode(self, api_client, template_file_create):
        """Test getting import template for create mode."""
        url = reverse("hrm:contract-import-template")
        response = api_client.get(url, {"mode": ContractImportMode.CREATE})

        assert response.status_code == status.HTTP_200_OK
        data = response.json().get("data")
        assert data["file_id"] == template_file_create.id

    def test_import_template_update_mode(self, api_client, template_file_update):
        """Test getting import template for update mode."""
        url = reverse("hrm:contract-import-template")
        response = api_client.get(url, {"mode": ContractImportMode.UPDATE})

        assert response.status_code == status.HTTP_200_OK
        data = response.json().get("data")
        assert data["file_id"] == template_file_update.id

    def test_start_import_create_mode(self, api_client, import_file):
        """Test starting import in create mode."""
        url = reverse("hrm:contract-start-import")
        data = {"file_id": import_file.id, "options": {"mode": ContractImportMode.CREATE}}

        with patch("apps.imports.tasks.import_job_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="task-id")
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_task.assert_called_once()

    def test_start_import_update_mode(self, api_client, import_file):
        """Test starting import in update mode."""
        url = reverse("hrm:contract-start-import")
        data = {"file_id": import_file.id, "options": {"mode": ContractImportMode.UPDATE}}

        with patch("apps.imports.tasks.import_job_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="task-id")
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_task.assert_called_once()

    def test_start_import_invalid_mode(self, api_client, import_file):
        """Test starting import with invalid mode."""
        url = reverse("hrm:contract-start-import")
        data = {"file_id": import_file.id, "options": {"mode": "invalid_mode"}}

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # The ValidationError comes from Serializer validation of choices
        assert "mode" in str(response.json())
