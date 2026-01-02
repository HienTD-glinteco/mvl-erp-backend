from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.hrm.models import JobDescription


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestJobDescriptionAPI(APITestMixin):
    """Test cases for Job Description API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def job_data(self):
        return {
            "title": "Senior Python Developer",
            "position_title": "Senior Backend Developer",
            "responsibility": "Develop and maintain backend services",
            "requirement": "5+ years Python experience",
            "preferred_criteria": "Experience with Django and FastAPI",
            "benefit": "Competitive salary and benefits",
            "proposed_salary": "2000-3000 USD",
            "note": "Remote work available",
            "attachment": "",
        }

    def test_create_job_description(self, job_data):
        """Test creating a job description via API"""
        url = reverse("hrm:job-description-list")
        response = self.client.post(url, job_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert JobDescription.objects.count() == 1

        job = JobDescription.objects.first()
        assert job.title == job_data["title"]
        assert job.position_title == job_data["position_title"]
        assert job.responsibility == job_data["responsibility"]
        assert job.requirement == job_data["requirement"]
        assert job.preferred_criteria == job_data["preferred_criteria"]
        assert job.benefit == job_data["benefit"]
        assert job.proposed_salary == job_data["proposed_salary"]
        assert job.note == job_data["note"]
        # Verify code was auto-generated
        assert job.code.startswith("JD")

    def test_create_job_description_minimal_fields(self, job_data):
        """Test creating a job description with only required fields"""
        url = reverse("hrm:job-description-list")
        minimal_data = {
            "title": "Junior Developer",
            "position_title": "Junior Software Engineer",
            "responsibility": "Learn and grow",
            "requirement": "Basic programming knowledge",
            "benefit": "benefit",
            "proposed_salary": "1000-1500 USD",
        }
        response = self.client.post(url, minimal_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert JobDescription.objects.count() == 1

        job = JobDescription.objects.first()
        assert job.title == minimal_data["title"]
        assert job.position_title == minimal_data["position_title"]
        assert job.preferred_criteria == ""
        assert job.benefit == "benefit"
        assert job.proposed_salary == "1000-1500 USD"
        assert job.note == ""

    def test_list_job_descriptions(self, job_data):
        """Test listing job descriptions via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["title"] == job_data["title"]
        assert response_data[0]["responsibility"] == job_data["responsibility"]

    def test_retrieve_job_description(self, job_data):
        """Test retrieving a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["title"] == job_data["title"]
        assert response_data["requirement"] == job_data["requirement"]

    def test_update_job_description(self, job_data):
        """Test updating a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        update_data = {
            "title": "Senior Python Developer - Updated",
            "position_title": "Senior Backend Developer - Updated",
            "responsibility": "Lead backend development",
            "requirement": "7+ years Python experience",
            "preferred_criteria": "Experience with Django, FastAPI, and microservices",
            "benefit": "Competitive salary, benefits, and stock options",
            "proposed_salary": "3000-4000 USD",
            "note": "Fully remote",
        }

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.put(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["title"] == update_data["title"]
        assert response_data["responsibility"] == update_data["responsibility"]
        assert response_data["proposed_salary"] == update_data["proposed_salary"]

    def test_partial_update_job_description(self, job_data):
        """Test partially updating a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        partial_data = {
            "title": "Senior Python Developer - Partially Updated",
            "proposed_salary": "2500-3500 USD",
        }

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.patch(url, partial_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["title"] == partial_data["title"]
        assert response_data["proposed_salary"] == partial_data["proposed_salary"]
        # Other fields should remain unchanged
        assert response_data["position_title"] == job_data["position_title"]
        assert response_data["responsibility"] == job_data["responsibility"]
        assert response_data["requirement"] == job_data["requirement"]

    def test_delete_job_description(self, job_data):
        """Test deleting a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert JobDescription.objects.count() == 0

    def test_filter_by_title(self, job_data):
        """Test filtering job descriptions by title"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        job_data_2 = job_data.copy()
        job_data_2["title"] = "Junior Frontend Developer"
        self.client.post(url, job_data_2, format="json")

        # Filter by title
        response = self.client.get(url, {"title": "Senior"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert "Senior" in response_data[0]["title"]

    def test_filter_by_code(self, job_data):
        """Test filtering job descriptions by code"""
        # Create a job description
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, job_data, format="json")
        code = self.get_response_data(create_response)["code"]

        # Filter by code
        response = self.client.get(url, {"code": code[:4]})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["code"] == code

    def test_search_job_descriptions(self, job_data):
        """Test searching job descriptions"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        job_data_2 = job_data.copy()
        job_data_2["title"] = "Junior Java Developer"
        job_data_2["responsibility"] = "Write Java code and maintain systems"
        job_data_2["requirement"] = "2+ years Java experience"
        self.client.post(url, job_data_2, format="json")

        # Search by title - should match only Python
        response = self.client.get(url, {"search": "Python"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert "Python" in response_data[0]["title"]

    def test_ordering_job_descriptions(self, job_data):
        """Test ordering job descriptions"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        job_data_2 = job_data.copy()
        job_data_2["title"] = "Junior Developer"
        self.client.post(url, job_data_2, format="json")

        # Order by title ascending
        response = self.client.get(url, {"ordering": "title"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        assert response_data[0]["title"] == "Junior Developer"
        assert response_data[1]["title"] == "Senior Python Developer"

    def test_auto_code_generation(self, job_data):
        """Test that job description code is auto-generated correctly"""
        url = reverse("hrm:job-description-list")
        response = self.client.post(url, job_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Code should start with JD prefix
        assert response_data["code"].startswith("JD")
        # Code should not be empty
        assert len(response_data["code"]) > 2

    def test_code_is_readonly(self, job_data):
        """Test that code field is read-only and cannot be modified via API"""
        url = reverse("hrm:job-description-list")
        data_with_code = job_data.copy()
        data_with_code["code"] = "CUSTOM_CODE"

        response = self.client.post(url, data_with_code, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        # Code should be auto-generated, not the custom one
        assert response_data["code"] != "CUSTOM_CODE"
        assert response_data["code"].startswith("JD")

    def test_create_job_description_with_file_upload(self, job_data, superuser):
        """Test creating a job description with file upload"""
        import json as json_module

        from django.core.cache import cache

        from apps.files.models import FileModel

        # Arrange: Setup file token and cache data
        file_token = "test-token-jd-001"

        # Clear cache before test
        cache.clear()

        with (
            patch("apps.files.api.serializers.mixins.cache") as mock_cache,
            patch("apps.files.utils.S3FileUploadService") as mock_s3_service,
            patch("apps.files.utils.s3_utils.S3FileUploadService") as mock_s3_service_model,
        ):
            # Mock cache to return file metadata
            cache_data = {
                "file_name": "job_description.pdf",
                "file_type": "application/pdf",
                "purpose": "job_description",
                "file_path": "uploads/tmp/test-token-jd-001/job_description.pdf",
            }
            mock_cache.get.return_value = json_module.dumps(cache_data)

            # Mock S3 service for file confirmation
            mock_instance = mock_s3_service.return_value
            mock_instance.check_file_exists.return_value = True
            mock_instance.generate_permanent_path.return_value = "uploads/job_description/1/job_description.pdf"
            mock_instance.move_file.return_value = True
            mock_instance.get_file_metadata.return_value = {
                "size": 123456,
                "content_type": "application/pdf",
                "etag": "abc123",
            }

            # Mock S3 service for view/download URLs in FileModel properties
            mock_instance_model = mock_s3_service_model.return_value
            mock_instance_model.generate_view_url.return_value = "https://example.com/view/job_description.pdf"
            mock_instance_model.generate_download_url.return_value = "https://example.com/download/job_description.pdf"

            # Act: Create job description with file token
            url = reverse("hrm:job-description-list")
            job_data_with_file = job_data.copy()
            job_data_with_file["files"] = {"attachment": file_token}

            response = self.client.post(url, job_data_with_file, format="json")

            # Assert: Check response
            assert response.status_code == status.HTTP_201_CREATED
            response_data = self.get_response_data(response)

            # Check that attachment is populated with FileModel data
            assert response_data["attachment"] is not None
            assert response_data["attachment"]["file_name"] == "job_description.pdf"
            assert response_data["attachment"]["purpose"] == "job_description"
            assert response_data["attachment"]["is_confirmed"] is True

            # Check database
            job = JobDescription.objects.get(pk=response_data["id"])
            assert job.attachment is not None
            assert job.attachment.file_name == "job_description.pdf"
            assert job.attachment.purpose == "job_description"
            assert job.attachment.is_confirmed is True

            # Check FileModel was created
            assert FileModel.objects.count() == 1
            file_record = FileModel.objects.first()
            assert file_record.file_name == "job_description.pdf"
            assert file_record.uploaded_by == superuser

    def test_export_job_descriptions(self, job_data):
        """Test exporting job descriptions to Excel"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        job_data_2 = job_data.copy()
        job_data_2["title"] = "Junior Python Developer"
        self.client.post(url, job_data_2, format="json")

        # Export with direct delivery
        export_url = reverse("hrm:job-description-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]

    def test_export_job_descriptions_fields(self, job_data):
        """Test that export includes correct fields without attachment"""
        # Create a job description
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        # Export with direct delivery to check fields
        export_url = reverse("hrm:job-description-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT

    def test_export_serializer_excludes_attachment(self, job_data):
        """Test that export serializer does not include attachment field"""
        from apps.hrm.api.serializers import JobDescriptionExportSerializer

        serializer = JobDescriptionExportSerializer()
        field_names = list(serializer.fields.keys())

        assert "attachment" not in field_names
        assert "title" in field_names
        assert "code" in field_names

    def test_viewset_uses_export_serializer_for_export_action(self, job_data):
        """Test that ViewSet uses JobDescriptionExportSerializer for export action"""
        from apps.hrm.api.serializers import (
            JobDescriptionExportSerializer,
            JobDescriptionSerializer,
        )
        from apps.hrm.api.views import JobDescriptionViewSet

        # Test export action uses export serializer
        viewset = JobDescriptionViewSet()
        viewset.action = "export"
        assert viewset.get_serializer_class() == JobDescriptionExportSerializer

        # Test other actions use default serializer
        viewset.action = "list"
        assert viewset.get_serializer_class() == JobDescriptionSerializer

        viewset.action = "retrieve"
        assert viewset.get_serializer_class() == JobDescriptionSerializer

    def test_export_job_descriptions_filtered(self, job_data):
        """Test exporting filtered job descriptions"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        job_data_2 = job_data.copy()
        job_data_2["title"] = "Junior Frontend Developer"
        self.client.post(url, job_data_2, format="json")

        # Export with title filter
        export_url = reverse("hrm:job-description-export")
        response = self.client.get(export_url, {"delivery": "direct", "title": "Senior"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT

    def test_filter_by_created_at_gte(self, job_data):
        """Test filtering job descriptions by created_at greater than or equal"""
        # Create a job description
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        # Use local date to match timezone-aware DB date extraction
        base_date = timezone.localdate()
        yesterday = base_date - timedelta(days=1)
        tomorrow = base_date + timedelta(days=1)

        # Filter by created_at__date >= yesterday (should return the job)
        response = self.client.get(url, {"created_at__date__gte": yesterday.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1

        # Filter by created_at__date >= tomorrow (should return nothing)
        response = self.client.get(url, {"created_at__date__gte": tomorrow.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0

    def test_filter_by_created_at_lte(self, job_data):
        """Test filtering job descriptions by created_at less than or equal"""
        # Create a job description
        url = reverse("hrm:job-description-list")
        self.client.post(url, job_data, format="json")

        # Use local date to match timezone-aware DB date extraction
        base_date = timezone.localdate()
        yesterday = base_date - timedelta(days=1)
        tomorrow = base_date + timedelta(days=1)

        # Filter by created_at__date <= tomorrow (should return the job)
        response = self.client.get(url, {"created_at__date__lte": tomorrow.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1

        # Filter by created_at__date <= yesterday (should return nothing)
        response = self.client.get(url, {"created_at__date__lte": yesterday.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0
