import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import CertificateType
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeCertificate

User = get_user_model()


class EmployeeCertificateModelTest(TestCase):
    """Test cases for EmployeeCertificate model"""

    def setUp(self):
        # Create test data
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
            code_type="MV",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
        )

    def test_create_certificate_with_code(self):
        """Test creating a certificate with a certificate code"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_code="IELTS-123456789",
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        self.assertEqual(certificate.certificate_code, "IELTS-123456789")
        self.assertEqual(certificate.certificate_type, CertificateType.FOREIGN_LANGUAGE)

    def test_create_certificate_without_code(self):
        """Test creating a certificate without a certificate code"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="ICDL",
            issue_date=date.today(),
        )
        self.assertEqual(certificate.certificate_code, "")
        self.assertEqual(certificate.certificate_type, CertificateType.COMPUTER)

    def test_certificate_type_choices(self):
        """Test all certificate type choices are valid"""
        for cert_type, display_name in CertificateType.choices:
            with self.subTest(cert_type=cert_type):
                certificate = EmployeeCertificate.objects.create(
                    employee=self.employee,
                    certificate_type=cert_type,
                    certificate_code=f"TEST-{cert_type}",
                    certificate_name=f"Test {display_name}",
                    issue_date=date.today(),
                )
                self.assertEqual(certificate.certificate_type, cert_type)
                self.assertEqual(certificate.certificate_code, f"TEST-{cert_type}")

    def test_certificate_str_with_code_and_name(self):
        """Test string representation with certificate_code and certificate_name"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_code="IELTS-123456",
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        self.assertEqual(str(certificate), "IELTS-123456 - IELTS 7.0")

    def test_certificate_str_with_name_only(self):
        """Test string representation with certificate_name only"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        self.assertEqual(str(certificate), "IELTS 7.0")

    def test_certificate_str_with_code_only(self):
        """Test string representation with certificate_code only"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_code="IELTS-123456",
            issue_date=date.today(),
        )
        self.assertIn("IELTS-123456", str(certificate))

    def test_certificate_str_minimal(self):
        """Test string representation with minimal data"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            issue_date=date.today(),
        )
        self.assertIn("Foreign language certificate", str(certificate))


class EmployeeCertificateAPITest(TestCase):
    """Test cases for EmployeeCertificate API"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test data
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
            code_type="MV",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
        )

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

    def test_create_certificate_with_code(self):
        """Test creating a certificate with certificate code"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_code": "IELTS-123456789",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
            "expiry_date": "2026-06-01",
            "issuing_organization": "British Council",
            "notes": "English proficiency certificate",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["certificate_type"], "foreign_language")
        self.assertEqual(result_data["certificate_code"], "IELTS-123456789")
        self.assertEqual(result_data["certificate_name"], "IELTS 7.0")

    def test_create_certificate_without_code(self):
        """Test creating a certificate without certificate code"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
            "expiry_date": "2026-06-01",
            "issuing_organization": "British Council",
            "notes": "English proficiency certificate",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["certificate_type"], "foreign_language")
        self.assertEqual(result_data["certificate_code"], "")
        self.assertEqual(result_data["certificate_name"], "IELTS 7.0")

    def test_create_certificate_with_invalid_type(self):
        """Test creating a certificate with invalid certificate_type"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee": self.employee.id,
            "certificate_type": "invalid_type",
            "certificate_name": "Test Certificate",
            "issue_date": "2024-06-01",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_certificates(self):
        """Test listing certificates"""
        # Create test certificates
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.REAL_ESTATE_PRACTICE_LICENSE,
            certificate_name="Real Estate Broker License",
            issue_date=date.today() - timedelta(days=30),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 2)

    def test_filter_by_certificate_type(self):
        """Test filtering by certificate_type"""
        # Create certificates of different types
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="ICDL",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"certificate_type": "foreign_language"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_type"], "foreign_language")

    def test_filter_by_multiple_certificate_types(self):
        """Test filtering by multiple certificate_types (comma-separated)"""
        # Create certificates of different types
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="ICDL",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.DIPLOMA,
            certificate_name="Bachelor's Degree",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"certificate_types": "foreign_language,computer"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 2)
        cert_types = [cert["certificate_type"] for cert in result_data]
        self.assertIn("foreign_language", cert_types)
        self.assertIn("computer", cert_types)
        self.assertNotIn("diploma", cert_types)

    def test_filter_by_employee(self):
        """Test filtering by employee"""
        # Create another employee
        employee2 = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee 2",
            username="testemployee2",
            email="test2@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
        )

        # Create certificates for both employees
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=employee2,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="ICDL",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"employee": self.employee.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["employee"], self.employee.id)

    def test_update_certificate_code(self):
        """Test updating certificate code"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_code="IELTS-123456",
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        data = {
            "employee": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_code": "IELTS-987654",
            "certificate_name": "IELTS 8.0",
            "issue_date": "2024-06-01",
        }
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["certificate_type"], "foreign_language")
        self.assertEqual(result_data["certificate_code"], "IELTS-987654")

        # Verify in database
        certificate.refresh_from_db()
        self.assertEqual(certificate.certificate_code, "IELTS-987654")

    def test_retrieve_certificate(self):
        """Test retrieving a specific certificate"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_code="IELTS-123456",
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["id"], certificate.id)
        self.assertEqual(result_data["certificate_type"], "foreign_language")
        self.assertEqual(result_data["certificate_code"], "IELTS-123456")

    def test_delete_certificate(self):
        """Test deleting a certificate"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify certificate is deleted
        self.assertFalse(EmployeeCertificate.objects.filter(id=certificate.id).exists())

    def test_certificate_type_choices_api(self):
        """Test all certificate type choices work correctly via API"""
        url = reverse("hrm:employee-certificate-list")
        for cert_type, display_name in CertificateType.choices:
            with self.subTest(cert_type=cert_type):
                data = {
                    "employee": self.employee.id,
                    "certificate_type": cert_type,
                    "certificate_code": f"TEST-{cert_type}",
                    "certificate_name": f"Test {display_name}",
                    "issue_date": "2024-06-01",
                }
                response = self.client.post(url, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                result_data = self.get_response_data(response)
                self.assertEqual(result_data["certificate_type"], cert_type)
                self.assertEqual(result_data["certificate_code"], f"TEST-{cert_type}")

    def test_search_by_certificate_name(self):
        """Test searching certificates by name"""
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="TOEIC 850",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"search": "IELTS"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertIn("IELTS", result_data[0]["certificate_name"])

    def test_filter_by_issue_date_range(self):
        """Test filtering by issue_date range"""
        today = date.today()
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Old Certificate",
            issue_date=today - timedelta(days=365),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="New Certificate",
            issue_date=today,
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"issue_date_from": (today - timedelta(days=30)).strftime("%Y-%m-%d")})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "New Certificate")

    def test_create_certificate_with_file_upload(self):
        """Test creating a certificate with file upload via FileConfirmSerializerMixin"""
        from unittest.mock import patch

        from django.core.cache import cache

        from apps.files.constants import CACHE_KEY_PREFIX
        from apps.files.models import FileModel

        # Arrange: Setup file token and cache data
        file_token = "test-token-cert-001"
        cache_key = f"{CACHE_KEY_PREFIX}{file_token}"

        # Clear cache before test
        cache.clear()

        with (
            patch("libs.drf.serializers.mixins.cache") as mock_cache,
            patch("apps.files.utils.S3FileUploadService") as mock_s3_service,
            patch("apps.files.utils.s3_utils.S3FileUploadService") as mock_s3_service_model,
        ):
            # Mock cache to return file metadata
            cache_data = {
                "file_name": "ielts_certificate.pdf",
                "file_type": "application/pdf",
                "purpose": "employee_certificate",
                "file_path": "uploads/tmp/test-token-cert-001/ielts_certificate.pdf",
            }
            mock_cache.get.return_value = json.dumps(cache_data)

            # Mock S3 service for file confirmation
            mock_instance = mock_s3_service.return_value
            mock_instance.check_file_exists.return_value = True
            mock_instance.generate_permanent_path.return_value = "uploads/employee_certificate/1/ielts_certificate.pdf"
            mock_instance.move_file.return_value = True
            mock_instance.get_file_metadata.return_value = {
                "size": 1024000,
                "content_type": "application/pdf",
                "etag": "abc123",
            }

            # Mock S3 service for view/download URLs in FileModel properties
            mock_instance_model = mock_s3_service_model.return_value
            mock_instance_model.generate_view_url.return_value = "https://example.com/view/ielts_certificate.pdf"
            mock_instance_model.generate_download_url.return_value = (
                "https://example.com/download/ielts_certificate.pdf"
            )

            # Act: Create certificate with file token
            url = reverse("hrm:employee-certificate-list")
            cert_data = {
                "employee": self.employee.id,
                "certificate_type": "foreign_language",
                "certificate_code": "IELTS-123456789",
                "certificate_name": "IELTS 7.0",
                "issue_date": "2024-06-01",
                "expiry_date": "2026-06-01",
                "issuing_organization": "British Council",
                "notes": "English proficiency certificate",
                "files": {"file": file_token},
            }

            response = self.client.post(url, cert_data, format="json")

            # Assert: Check response
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            response_data = self.get_response_data(response)

            # Check that file is populated with FileModel data
            self.assertIsNotNone(response_data["file"])
            self.assertEqual(response_data["file"]["file_name"], "ielts_certificate.pdf")
            self.assertEqual(response_data["file"]["purpose"], "employee_certificate")
            self.assertTrue(response_data["file"]["is_confirmed"])

            # Check database
            certificate = EmployeeCertificate.objects.get(pk=response_data["id"])
            self.assertIsNotNone(certificate.file)
            self.assertEqual(certificate.file.file_name, "ielts_certificate.pdf")
            self.assertEqual(certificate.file.purpose, "employee_certificate")
            self.assertTrue(certificate.file.is_confirmed)

            # Check FileModel was created
            self.assertEqual(FileModel.objects.count(), 1)
            file_record = FileModel.objects.first()
            self.assertEqual(file_record.file_name, "ielts_certificate.pdf")
            self.assertEqual(file_record.uploaded_by, self.user)

    def test_create_certificate_with_file_and_no_token(self):
        """Test creating a certificate without file token still works"""
        url = reverse("hrm:employee-certificate-list")
        cert_data = {
            "employee": self.employee.id,
            "certificate_type": "computer",
            "certificate_code": "MOS-987654321",
            "certificate_name": "Microsoft Office Specialist",
            "issue_date": "2024-01-15",
            "issuing_organization": "Microsoft",
            "notes": "Excel Expert certification",
        }

        response = self.client.post(url, cert_data, format="json")

        # Assert: Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # File should be None/null
        self.assertIsNone(response_data["file"])

        # Check database
        certificate = EmployeeCertificate.objects.get(pk=response_data["id"])
        self.assertIsNone(certificate.file)

    def test_create_certificate_with_invalid_file_token(self):
        """Test creating a certificate with invalid file token"""
        from unittest.mock import patch

        from django.core.cache import cache

        # Clear cache so token is invalid
        cache.clear()

        with (
            patch("libs.drf.serializers.mixins.cache") as mock_cache,
            patch("apps.files.utils.S3FileUploadService") as mock_s3_service,
        ):
            # Mock cache to return None (token not found)
            mock_cache.get.return_value = None

            url = reverse("hrm:employee-certificate-list")
            cert_data = {
                "employee": self.employee.id,
                "certificate_type": "diploma",
                "certificate_code": "DIPLOMA-111",
                "certificate_name": "Bachelor Degree",
                "issue_date": "2024-06-01",
                "files": {"file": "invalid-token-123"},
            }

            response = self.client.post(url, cert_data, format="json")

            # Should return 400 Bad Request due to invalid token
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
