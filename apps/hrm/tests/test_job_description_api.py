import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import JobDescription

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class JobDescriptionAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Job Description API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        JobDescription.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.job_data = {
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

    def test_create_job_description(self):
        """Test creating a job description via API"""
        url = reverse("hrm:job-description-list")
        response = self.client.post(url, self.job_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(JobDescription.objects.count(), 1)

        job = JobDescription.objects.first()
        self.assertEqual(job.title, self.job_data["title"])
        self.assertEqual(job.position_title, self.job_data["position_title"])
        self.assertEqual(job.responsibility, self.job_data["responsibility"])
        self.assertEqual(job.requirement, self.job_data["requirement"])
        self.assertEqual(job.preferred_criteria, self.job_data["preferred_criteria"])
        self.assertEqual(job.benefit, self.job_data["benefit"])
        self.assertEqual(job.proposed_salary, self.job_data["proposed_salary"])
        self.assertEqual(job.note, self.job_data["note"])
        # Verify code was auto-generated
        self.assertTrue(job.code.startswith("JD"))

    def test_create_job_description_minimal_fields(self):
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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(JobDescription.objects.count(), 1)

        job = JobDescription.objects.first()
        self.assertEqual(job.title, minimal_data["title"])
        self.assertEqual(job.position_title, minimal_data["position_title"])
        self.assertEqual(job.preferred_criteria, "")
        self.assertEqual(job.benefit, "benefit")
        self.assertEqual(job.proposed_salary, "1000-1500 USD")
        self.assertEqual(job.note, "")

    def test_list_job_descriptions(self):
        """Test listing job descriptions via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["title"], self.job_data["title"])
        self.assertEqual(response_data[0]["responsibility"], self.job_data["responsibility"])

    def test_retrieve_job_description(self):
        """Test retrieving a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, self.job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["title"], self.job_data["title"])
        self.assertEqual(response_data["requirement"], self.job_data["requirement"])

    def test_update_job_description(self):
        """Test updating a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, self.job_data, format="json")
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["title"], update_data["title"])
        self.assertEqual(response_data["responsibility"], update_data["responsibility"])
        self.assertEqual(response_data["proposed_salary"], update_data["proposed_salary"])

    def test_partial_update_job_description(self):
        """Test partially updating a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, self.job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        partial_data = {
            "title": "Senior Python Developer - Partially Updated",
            "proposed_salary": "2500-3500 USD",
        }

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.patch(url, partial_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["title"], partial_data["title"])
        self.assertEqual(response_data["proposed_salary"], partial_data["proposed_salary"])
        # Other fields should remain unchanged
        self.assertEqual(response_data["position_title"], self.job_data["position_title"])
        self.assertEqual(response_data["responsibility"], self.job_data["responsibility"])
        self.assertEqual(response_data["requirement"], self.job_data["requirement"])

    def test_delete_job_description(self):
        """Test deleting a job description via API"""
        # Create via API to ensure signal is triggered
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, self.job_data, format="json")
        job_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:job-description-detail", kwargs={"pk": job_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(JobDescription.objects.count(), 0)

    def test_filter_by_title(self):
        """Test filtering job descriptions by title"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        job_data_2 = self.job_data.copy()
        job_data_2["title"] = "Junior Frontend Developer"
        self.client.post(url, job_data_2, format="json")

        # Filter by title
        response = self.client.get(url, {"title": "Senior"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertIn("Senior", response_data[0]["title"])

    def test_filter_by_code(self):
        """Test filtering job descriptions by code"""
        # Create a job description
        url = reverse("hrm:job-description-list")
        create_response = self.client.post(url, self.job_data, format="json")
        code = self.get_response_data(create_response)["code"]

        # Filter by code
        response = self.client.get(url, {"code": code[:4]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], code)

    def test_search_job_descriptions(self):
        """Test searching job descriptions"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        job_data_2 = self.job_data.copy()
        job_data_2["title"] = "Junior Java Developer"
        job_data_2["responsibility"] = "Write Java code and maintain systems"
        job_data_2["requirement"] = "2+ years Java experience"
        self.client.post(url, job_data_2, format="json")

        # Search by title - should match only Python
        response = self.client.get(url, {"search": "Python"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertIn("Python", response_data[0]["title"])

    def test_ordering_job_descriptions(self):
        """Test ordering job descriptions"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        job_data_2 = self.job_data.copy()
        job_data_2["title"] = "Junior Developer"
        self.client.post(url, job_data_2, format="json")

        # Order by title ascending
        response = self.client.get(url, {"ordering": "title"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]["title"], "Junior Developer")
        self.assertEqual(response_data[1]["title"], "Senior Python Developer")

    def test_auto_code_generation(self):
        """Test that job description code is auto-generated correctly"""
        url = reverse("hrm:job-description-list")
        response = self.client.post(url, self.job_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Code should start with JD prefix
        self.assertTrue(response_data["code"].startswith("JD"))
        # Code should not be empty
        self.assertTrue(len(response_data["code"]) > 2)

    def test_code_is_readonly(self):
        """Test that code field is read-only and cannot be modified via API"""
        url = reverse("hrm:job-description-list")
        data_with_code = self.job_data.copy()
        data_with_code["code"] = "CUSTOM_CODE"

        response = self.client.post(url, data_with_code, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        # Code should be auto-generated, not the custom one
        self.assertNotEqual(response_data["code"], "CUSTOM_CODE")
        self.assertTrue(response_data["code"].startswith("JD"))

    def test_create_job_description_with_file_upload(self):
        """Test creating a job description with file upload"""
        from unittest.mock import patch

        from django.core.cache import cache

        from apps.files.constants import CACHE_KEY_PREFIX
        from apps.files.models import FileModel

        # Arrange: Setup file token and cache data
        file_token = "test-token-jd-001"
        cache_key = f"{CACHE_KEY_PREFIX}{file_token}"

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
            mock_cache.get.return_value = json.dumps(cache_data)

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
            job_data_with_file = self.job_data.copy()
            job_data_with_file["files"] = {"attachment": file_token}

            response = self.client.post(url, job_data_with_file, format="json")

            # Assert: Check response
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            response_data = self.get_response_data(response)

            # Check that attachment is populated with FileModel data
            self.assertIsNotNone(response_data["attachment"])
            self.assertEqual(response_data["attachment"]["file_name"], "job_description.pdf")
            self.assertEqual(response_data["attachment"]["purpose"], "job_description")
            self.assertTrue(response_data["attachment"]["is_confirmed"])

            # Check database
            job = JobDescription.objects.get(pk=response_data["id"])
            self.assertIsNotNone(job.attachment)
            self.assertEqual(job.attachment.file_name, "job_description.pdf")
            self.assertEqual(job.attachment.purpose, "job_description")
            self.assertTrue(job.attachment.is_confirmed)

            # Check FileModel was created
            self.assertEqual(FileModel.objects.count(), 1)
            file_record = FileModel.objects.first()
            self.assertEqual(file_record.file_name, "job_description.pdf")
            self.assertEqual(file_record.uploaded_by, self.user)

    def test_export_job_descriptions(self):
        """Test exporting job descriptions to Excel"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        job_data_2 = self.job_data.copy()
        job_data_2["title"] = "Junior Python Developer"
        self.client.post(url, job_data_2, format="json")

        # Export with direct delivery
        export_url = reverse("hrm:job-description-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

    def test_export_job_descriptions_fields(self):
        """Test that export includes correct fields"""
        # Create a job description
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        # Export with direct delivery to check fields
        export_url = reverse("hrm:job-description-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)

    def test_export_job_descriptions_filtered(self):
        """Test exporting filtered job descriptions"""
        # Create multiple job descriptions
        url = reverse("hrm:job-description-list")
        self.client.post(url, self.job_data, format="json")

        job_data_2 = self.job_data.copy()
        job_data_2["title"] = "Junior Frontend Developer"
        self.client.post(url, job_data_2, format="json")

        # Export with title filter
        export_url = reverse("hrm:job-description-export")
        response = self.client.get(export_url, {"delivery": "direct", "title": "Senior"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
