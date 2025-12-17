import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import CertificateType
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeCertificate, Position

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
            phone="0900200001",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
            citizen_id="000000020000",
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
                # REAL_ESTATE_PRACTICE_LICENSE requires expiry_date
                expiry_date = (
                    date.today() + timedelta(days=365)
                    if cert_type == CertificateType.REAL_ESTATE_PRACTICE_LICENSE
                    else None
                )
                certificate = EmployeeCertificate.objects.create(
                    employee=self.employee,
                    certificate_type=cert_type,
                    certificate_code=f"TEST-{cert_type}",
                    certificate_name=f"Test {display_name}",
                    issue_date=date.today(),
                    expiry_date=expiry_date,
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

    def test_status_valid_no_expiry_date(self):
        """Test status is VALID when no expiry_date is set"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        self.assertEqual(certificate.status, EmployeeCertificate.Status.VALID)

    def test_status_expired(self):
        """Test status is EXPIRED when current date > expiry_date"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today() - timedelta(days=100),
            expiry_date=date.today() - timedelta(days=1),
        )
        self.assertEqual(certificate.status, EmployeeCertificate.Status.EXPIRED)

    def test_status_near_expiry(self):
        """Test status is NEAR_EXPIRY when expiry is within threshold"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=15),  # Within 30 days
        )
        self.assertEqual(certificate.status, EmployeeCertificate.Status.NEAR_EXPIRY)

    def test_status_valid_with_expiry_beyond_threshold(self):
        """Test status is VALID when expiry is beyond threshold"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),  # More than 30 days
        )
        self.assertEqual(certificate.status, EmployeeCertificate.Status.VALID)

    def test_status_near_expiry_at_threshold(self):
        """Test status is NEAR_EXPIRY when exactly at threshold (30 days)"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
        )
        self.assertEqual(certificate.status, EmployeeCertificate.Status.NEAR_EXPIRY)

    def test_status_updates_on_save(self):
        """Test status is automatically updated when certificate is saved"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        self.assertEqual(certificate.status, EmployeeCertificate.Status.VALID)

        # Update expiry_date to trigger status change
        certificate.expiry_date = date.today() - timedelta(days=1)
        certificate.save()
        self.assertEqual(certificate.status, EmployeeCertificate.Status.EXPIRED)

    def test_colored_status(self):
        """Test colored_status property returns correct variant"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        colored = certificate.colored_status
        self.assertEqual(colored["value"], EmployeeCertificate.Status.VALID)
        self.assertEqual(colored["variant"], "GREEN")

    def test_create_certificate_with_effective_date(self):
        """Test creating a certificate with effective_date"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            effective_date=date.today() + timedelta(days=15),
            expiry_date=date.today() + timedelta(days=365),
        )
        self.assertEqual(certificate.effective_date, date.today() + timedelta(days=15))

    def test_effective_date_can_be_null(self):
        """Test that effective_date can be null"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
        )
        self.assertIsNone(certificate.effective_date)

    def test_clean_effective_date_less_than_expiry_date(self):
        """Test that clean passes when effective_date < expiry_date"""
        certificate = EmployeeCertificate(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            effective_date=date.today() + timedelta(days=15),
            expiry_date=date.today() + timedelta(days=365),
        )
        # Should not raise ValidationError
        certificate.clean()

    def test_clean_effective_date_greater_than_expiry_date_fails(self):
        """Test that clean fails when effective_date > expiry_date"""
        certificate = EmployeeCertificate(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            effective_date=date.today() + timedelta(days=400),
            expiry_date=date.today() + timedelta(days=365),
        )
        with self.assertRaises(ValidationError) as context:
            certificate.clean()
        self.assertIn("effective_date", context.exception.message_dict)

    def test_clean_effective_date_equal_to_expiry_date_fails(self):
        """Test that clean fails when effective_date == expiry_date"""
        expiry = date.today() + timedelta(days=365)
        certificate = EmployeeCertificate(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            effective_date=expiry,
            expiry_date=expiry,
        )
        with self.assertRaises(ValidationError) as context:
            certificate.clean()
        self.assertIn("effective_date", context.exception.message_dict)

    def test_clean_no_expiry_date_with_effective_date(self):
        """Test that clean passes when effective_date is set but no expiry_date"""
        certificate = EmployeeCertificate(
            employee=self.employee,
            certificate_type=CertificateType.DIPLOMA,
            certificate_name="Bachelor's Degree",
            issue_date=date.today(),
            effective_date=date.today() + timedelta(days=15),
        )
        # Should not raise ValidationError
        certificate.clean()

    def test_real_estate_license_requires_expiry_date(self):
        """Test that REAL_ESTATE_PRACTICE_LICENSE requires expiry_date"""
        certificate = EmployeeCertificate(
            employee=self.employee,
            certificate_type=CertificateType.REAL_ESTATE_PRACTICE_LICENSE,
            certificate_name="Real Estate Broker License",
            issue_date=date.today(),
        )
        with self.assertRaises(ValidationError) as context:
            certificate.clean()
        self.assertIn("expiry_date", context.exception.message_dict)

    def test_real_estate_license_with_expiry_date(self):
        """Test that REAL_ESTATE_PRACTICE_LICENSE can be created with expiry_date"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.REAL_ESTATE_PRACTICE_LICENSE,
            certificate_name="Real Estate Broker License",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        self.assertEqual(certificate.certificate_type, CertificateType.REAL_ESTATE_PRACTICE_LICENSE)
        self.assertIsNotNone(certificate.expiry_date)

    def test_issuing_organization_optional(self):
        """Test that issuing_organization is optional (can be null)"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            issuing_organization=None,
        )
        self.assertIsNone(certificate.issuing_organization)

    def test_issuing_organization_can_be_blank(self):
        """Test that issuing_organization can be blank"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="ICDL",
            issue_date=date.today(),
            issuing_organization="",
        )
        self.assertEqual(certificate.issuing_organization, "")


class EmployeeCertificateAPITest(TestCase):
    """Test cases for EmployeeCertificate API"""

    def setUp(self):
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
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
            phone="0900200002",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
            citizen_id="000000020001",
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
            "employee_id": self.employee.id,
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
        # Verify nested employee is returned using full EmployeeSerializer
        self.assertIn("employee", result_data)
        self.assertEqual(result_data["employee"]["id"], self.employee.id)
        self.assertEqual(result_data["employee"]["code"], self.employee.code)
        self.assertEqual(result_data["employee"]["fullname"], self.employee.fullname)
        # EmployeeSerializer includes these additional fields
        self.assertIn("branch", result_data["employee"])
        self.assertIn("block", result_data["employee"])
        self.assertIn("department", result_data["employee"])
        self.assertIn("email", result_data["employee"])

    def test_create_certificate_without_code(self):
        """Test creating a certificate without certificate code"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
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
            "employee_id": self.employee.id,
            "certificate_type": "invalid_type",
            "certificate_name": "Test Certificate",
            "issue_date": "2024-06-01",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_certificate_missing_issuing_organization(self):
        """Test creating a certificate without issuing_organization is allowed (optional field)"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
        }
        response = self.client.post(url, data, format="json")
        # issuing_organization is optional, so creation should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result_data = self.get_response_data(response)
        self.assertEqual(result_data["certificate_type"], "foreign_language")
        self.assertEqual(result_data["certificate_name"], "IELTS 7.0")
        # issuing_organization should be None or empty
        self.assertIn(result_data.get("issuing_organization"), [None, ""])

    def test_create_real_estate_license_without_expiry_date_fails(self):
        """Test that creating REAL_ESTATE_PRACTICE_LICENSE without expiry_date fails"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "real_estate_practice_license",
            "certificate_name": "Real Estate Broker License",
            "issue_date": "2024-06-01",
            "issuing_organization": "Real Estate Authority",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content.decode())
        self.assertFalse(response_data["success"])

    def test_create_real_estate_license_with_expiry_date_succeeds(self):
        """Test that creating REAL_ESTATE_PRACTICE_LICENSE with expiry_date succeeds"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "real_estate_practice_license",
            "certificate_name": "Real Estate Broker License",
            "issue_date": "2024-06-01",
            "expiry_date": "2026-06-01",
            "issuing_organization": "Real Estate Authority",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result_data = self.get_response_data(response)
        self.assertEqual(result_data["certificate_type"], "real_estate_practice_license")
        self.assertEqual(result_data["expiry_date"], "2026-06-01")

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
            expiry_date=date.today() + timedelta(days=365),  # Required for this type
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
            phone="0900200003",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
            citizen_id="000000020002",
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
        self.assertEqual(result_data[0]["employee"]["id"], self.employee.id)

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
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_code": "IELTS-987654",
            "certificate_name": "IELTS 8.0",
            "issue_date": "2024-06-01",
            "issuing_organization": "British Council",
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
                    "employee_id": self.employee.id,
                    "certificate_type": cert_type,
                    "certificate_code": f"TEST-{cert_type}",
                    "certificate_name": f"Test {display_name}",
                    "issue_date": "2024-06-01",
                    "issuing_organization": "Test Org",
                }
                # REAL_ESTATE_PRACTICE_LICENSE requires expiry_date
                if cert_type == CertificateType.REAL_ESTATE_PRACTICE_LICENSE:
                    data["expiry_date"] = "2026-06-01"
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
            patch("apps.files.api.serializers.mixins.cache") as mock_cache,
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
                "employee_id": self.employee.id,
                "certificate_type": "foreign_language",
                "certificate_code": "IELTS-123456789",
                "certificate_name": "IELTS 7.0",
                "issue_date": "2024-06-01",
                "expiry_date": "2026-06-01",
                "issuing_organization": "British Council",
                "notes": "English proficiency certificate",
                "files": {"attachment": file_token},
            }

            response = self.client.post(url, cert_data, format="json")

            # Assert: Check response
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            response_data = self.get_response_data(response)

            # Check that attachment is populated with FileModel data
            self.assertIsNotNone(response_data["attachment"])
            self.assertEqual(response_data["attachment"]["file_name"], "ielts_certificate.pdf")
            self.assertEqual(response_data["attachment"]["purpose"], "employee_certificate")
            self.assertTrue(response_data["attachment"]["is_confirmed"])

            # Check database
            certificate = EmployeeCertificate.objects.get(pk=response_data["id"])
            self.assertIsNotNone(certificate.attachment)
            self.assertEqual(certificate.attachment.file_name, "ielts_certificate.pdf")
            self.assertEqual(certificate.attachment.purpose, "employee_certificate")
            self.assertTrue(certificate.attachment.is_confirmed)

            # Check FileModel was created
            self.assertEqual(FileModel.objects.count(), 1)
            file_record = FileModel.objects.first()
            self.assertEqual(file_record.file_name, "ielts_certificate.pdf")
            self.assertEqual(file_record.uploaded_by, self.user)

    def test_create_certificate_with_file_and_no_token(self):
        """Test creating a certificate without file token still works"""
        url = reverse("hrm:employee-certificate-list")
        cert_data = {
            "employee_id": self.employee.id,
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

        # Attachment should be None/null
        self.assertIsNone(response_data["attachment"])

        # Check database
        certificate = EmployeeCertificate.objects.get(pk=response_data["id"])
        self.assertIsNone(certificate.attachment)

    def test_create_certificate_with_invalid_file_token(self):
        """Test creating a certificate with invalid file token"""
        from unittest.mock import patch

        from django.core.cache import cache

        # Clear cache so token is invalid
        cache.clear()

        with (
            patch("apps.files.api.serializers.mixins.cache") as mock_cache,
            patch("apps.files.utils.S3FileUploadService") as mock_s3_service,
        ):
            # Mock cache to return None (token not found)
            mock_cache.get.return_value = None

            url = reverse("hrm:employee-certificate-list")
            cert_data = {
                "employee_id": self.employee.id,
                "certificate_type": "diploma",
                "certificate_code": "DIPLOMA-111",
                "certificate_name": "Bachelor Degree",
                "issue_date": "2024-06-01",
                "files": {"attachment": "invalid-token-123"},
            }

            response = self.client.post(url, cert_data, format="json")

            # Should return 400 Bad Request due to invalid token
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_field_in_api_response(self):
        """Test that status field is included in API response"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertIn("status", result_data)
        self.assertIn("status_display", result_data)
        self.assertIn("colored_status", result_data)
        self.assertEqual(result_data["status"], "Valid")
        self.assertEqual(result_data["colored_status"]["variant"], "GREEN")

    def test_status_field_is_read_only(self):
        """Test that status field cannot be set via API"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": date.today().strftime("%Y-%m-%d"),
            "expiry_date": (date.today() + timedelta(days=60)).strftime("%Y-%m-%d"),
            "issuing_organization": "British Council",
            "status": "expired",  # Try to set status manually
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        # Status should be VALID (computed), not EXPIRED (from request)
        self.assertEqual(result_data["status"], "Valid")

    def test_filter_by_status_valid(self):
        """Test filtering certificates by VALID status"""
        # Create certificates with different statuses
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Valid Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Near Expiry Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=15),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.DIPLOMA,
            certificate_name="Expired Certificate",
            issue_date=date.today() - timedelta(days=100),
            expiry_date=date.today() - timedelta(days=1),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"status": "Valid"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Valid Certificate")

    def test_filter_by_status_near_expiry(self):
        """Test filtering certificates by NEAR_EXPIRY status"""
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Valid Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Near Expiry Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=15),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"status": "Near Expiry"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Near Expiry Certificate")

    def test_filter_by_status_expired(self):
        """Test filtering certificates by EXPIRED status"""
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Valid Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.DIPLOMA,
            certificate_name="Expired Certificate",
            issue_date=date.today() - timedelta(days=100),
            expiry_date=date.today() - timedelta(days=1),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"status": "Expired"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Expired Certificate")

    def test_create_certificate_with_training_specialization(self):
        """Test creating a certificate with training_specialization field"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "diploma",
            "certificate_name": "Bachelor of Science",
            "issue_date": "2020-06-01",
            "issuing_organization": "Test University",
            "training_specialization": "Computer Science",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["training_specialization"], "Computer Science")

    def test_create_certificate_with_graduation_diploma(self):
        """Test creating a certificate with graduation_diploma field"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "diploma",
            "certificate_name": "Bachelor of Engineering",
            "issue_date": "2020-06-01",
            "issuing_organization": "Test University",
            "graduation_diploma": "Bachelor's Degree",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["graduation_diploma"], "Bachelor's Degree")

    def test_create_certificate_with_all_new_fields(self):
        """Test creating a certificate with both training_specialization and graduation_diploma"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "diploma",
            "certificate_name": "Master of Science",
            "issue_date": "2022-06-01",
            "issuing_organization": "Test University",
            "training_specialization": "Software Engineering",
            "graduation_diploma": "Master's Degree",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["training_specialization"], "Software Engineering")
        self.assertEqual(result_data["graduation_diploma"], "Master's Degree")

    def test_update_certificate_with_new_fields(self):
        """Test updating a certificate's new fields"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.DIPLOMA,
            certificate_name="Bachelor's Degree",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "diploma",
            "certificate_name": "Bachelor's Degree",
            "issue_date": date.today().strftime("%Y-%m-%d"),
            "issuing_organization": "Test University",
            "training_specialization": "Information Technology",
            "graduation_diploma": "Bachelor's Degree",
        }
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["training_specialization"], "Information Technology")
        self.assertEqual(result_data["graduation_diploma"], "Bachelor's Degree")

        # Verify in database
        certificate.refresh_from_db()
        self.assertEqual(certificate.training_specialization, "Information Technology")
        self.assertEqual(certificate.graduation_diploma, "Bachelor's Degree")

    def test_certificate_new_fields_are_optional(self):
        """Test that training_specialization and graduation_diploma are optional"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "TOEFL",
            "issue_date": "2024-06-01",
            "issuing_organization": "ETS",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        # New fields should be None when not provided
        self.assertIsNone(result_data["training_specialization"])
        self.assertIsNone(result_data["graduation_diploma"])

    def test_employee_serializer_in_response(self):
        """Test that employee field uses full EmployeeSerializer instead of nested"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Test Certificate",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)

        # Verify employee field uses EmployeeSerializer
        employee_data = result_data["employee"]
        self.assertIn("id", employee_data)
        self.assertIn("code", employee_data)
        self.assertIn("fullname", employee_data)
        # These fields are specific to EmployeeSerializer (not in EmployeeNestedSerializer)
        self.assertIn("branch", employee_data)
        self.assertIn("block", employee_data)
        self.assertIn("department", employee_data)
        self.assertIn("email", employee_data)
        self.assertIn("start_date", employee_data)

    def test_create_certificate_with_effective_date(self):
        """Test creating a certificate with effective_date field"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
            "effective_date": "2024-06-15",
            "expiry_date": "2026-06-01",
            "issuing_organization": "British Council",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["effective_date"], "2024-06-15")
        self.assertEqual(result_data["expiry_date"], "2026-06-01")

    def test_effective_date_is_optional(self):
        """Test that effective_date is optional"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "TOEFL",
            "issue_date": "2024-06-01",
            "expiry_date": "2026-06-01",
            "issuing_organization": "ETS",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertIsNone(result_data["effective_date"])

    def test_effective_date_must_be_less_than_expiry_date(self):
        """Test that effective_date must be less than expiry_date"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
            "effective_date": "2026-06-02",  # After expiry_date
            "expiry_date": "2026-06-01",
            "issuing_organization": "British Council",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response_data = json.loads(response.content.decode())
        self.assertFalse(response_data["success"])

    def test_effective_date_equal_to_expiry_date_fails(self):
        """Test that effective_date equal to expiry_date fails validation"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
            "effective_date": "2026-06-01",  # Equal to expiry_date
            "expiry_date": "2026-06-01",
            "issuing_organization": "British Council",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_effective_date_without_expiry_date_succeeds(self):
        """Test that effective_date without expiry_date is allowed"""
        url = reverse("hrm:employee-certificate-list")
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "diploma",
            "certificate_name": "Bachelor of Science",
            "issue_date": "2024-06-01",
            "effective_date": "2024-06-15",
            "issuing_organization": "Test University",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["effective_date"], "2024-06-15")
        self.assertIsNone(result_data["expiry_date"])

    def test_update_certificate_with_effective_date(self):
        """Test updating a certificate's effective_date"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": date.today().strftime("%Y-%m-%d"),
            "effective_date": (date.today() + timedelta(days=15)).strftime("%Y-%m-%d"),
            "expiry_date": (date.today() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "issuing_organization": "British Council",
        }
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(result_data["effective_date"], (date.today() + timedelta(days=15)).strftime("%Y-%m-%d"))

        # Verify in database
        certificate.refresh_from_db()
        self.assertEqual(certificate.effective_date, date.today() + timedelta(days=15))

    def test_update_with_invalid_effective_date_fails(self):
        """Test updating certificate with invalid effective_date fails"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            effective_date=date.today() + timedelta(days=15),
            expiry_date=date.today() + timedelta(days=365),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_name": "IELTS 7.0",
            "issue_date": date.today().strftime("%Y-%m-%d"),
            "effective_date": (date.today() + timedelta(days=400)).strftime("%Y-%m-%d"),  # After expiry
            "expiry_date": (date.today() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "issuing_organization": "British Council",
        }
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_effective_date_range(self):
        """Test filtering certificates by effective_date range"""
        today = date.today()
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Old Certificate",
            issue_date=today - timedelta(days=365),
            effective_date=today - timedelta(days=360),
            expiry_date=today + timedelta(days=365),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="New Certificate",
            issue_date=today - timedelta(days=30),
            effective_date=today - timedelta(days=25),
            expiry_date=today + timedelta(days=365),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"effective_date_from": (today - timedelta(days=30)).strftime("%Y-%m-%d")})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "New Certificate")

    def test_effective_date_field_in_response(self):
        """Test that effective_date field is included in API response"""
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="IELTS 7.0",
            issue_date=date.today(),
            effective_date=date.today() + timedelta(days=15),
            expiry_date=date.today() + timedelta(days=365),
        )

        url = reverse("hrm:employee-certificate-detail", kwargs={"pk": certificate.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertIn("effective_date", result_data)
        self.assertEqual(result_data["effective_date"], (date.today() + timedelta(days=15)).strftime("%Y-%m-%d"))

    def test_filter_by_multiple_statuses(self):
        """Test filtering certificates by multiple status values"""
        # Create certificates with different statuses
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Valid Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=60),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Near Expiry Certificate",
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=15),
        )
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.DIPLOMA,
            certificate_name="Expired Certificate",
            issue_date=date.today() - timedelta(days=100),
            expiry_date=date.today() - timedelta(days=1),
        )

        url = reverse("hrm:employee-certificate-list")
        # Test filtering by multiple statuses (Valid and Near Expiry)
        response = self.client.get(url, {"status": ["Valid", "Near Expiry"]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 2)
        statuses = [cert["status"] for cert in result_data]
        self.assertIn("Valid", statuses)
        self.assertIn("Near Expiry", statuses)
        self.assertNotIn("Expired", statuses)

    def test_filter_by_branch(self):
        """Test filtering certificates by employee branch"""
        # Create another branch and employee
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )
        employee2 = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee 2",
            username="testemployee2_branch",
            email="test2_branch@example.com",
            phone="0900200010",
            branch=branch2,
            block=block2,
            department=department2,
            start_date=date(2020, 1, 1),
            citizen_id="000000020010",
        )

        # Create certificates for both employees
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Certificate Branch 1",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=employee2,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Certificate Branch 2",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"branch": self.branch.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Certificate Branch 1")

    def test_filter_by_block(self):
        """Test filtering certificates by employee block"""
        # Create another block
        block2 = Block.objects.create(
            code="KH003",
            name="Test Block 3",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        department2 = Department.objects.create(
            code="PB003",
            name="Test Department 3",
            branch=self.branch,
            block=block2,
        )
        employee2 = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee 3",
            username="testemployee3_block",
            email="test3_block@example.com",
            phone="0900200011",
            branch=self.branch,
            block=block2,
            department=department2,
            start_date=date(2020, 1, 1),
            citizen_id="000000020011",
        )

        # Create certificates for both employees
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Certificate Block 1",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=employee2,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Certificate Block 2",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"block": self.block.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Certificate Block 1")

    def test_filter_by_department(self):
        """Test filtering certificates by employee department"""
        # Create another department
        department2 = Department.objects.create(
            code="PB004",
            name="Test Department 4",
            branch=self.branch,
            block=self.block,
        )
        employee2 = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee 4",
            username="testemployee4_dept",
            email="test4_dept@example.com",
            phone="0900200012",
            branch=self.branch,
            block=self.block,
            department=department2,
            start_date=date(2020, 1, 1),
            citizen_id="000000020012",
        )

        # Create certificates for both employees
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Certificate Dept 1",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=employee2,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Certificate Dept 2",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"department": self.department.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Certificate Dept 1")

    def test_filter_by_position(self):
        """Test filtering certificates by employee position"""
        # Create positions
        position1 = Position.objects.create(
            code="VT001",
            name="Test Position 1",
        )
        position2 = Position.objects.create(
            code="VT002",
            name="Test Position 2",
        )

        # Update employee with position
        self.employee.position = position1
        self.employee.save()

        # Create another employee with different position
        employee2 = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee 5",
            username="testemployee5_pos",
            email="test5_pos@example.com",
            phone="0900200013",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=position2,
            start_date=date(2020, 1, 1),
            citizen_id="000000020013",
        )

        # Create certificates for both employees
        EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Certificate Position 1",
            issue_date=date.today(),
        )
        EmployeeCertificate.objects.create(
            employee=employee2,
            certificate_type=CertificateType.COMPUTER,
            certificate_name="Certificate Position 2",
            issue_date=date.today(),
        )

        url = reverse("hrm:employee-certificate-list")
        response = self.client.get(url, {"position": position1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result_data = self.get_response_data(response)
        self.assertEqual(len(result_data), 1)
        self.assertEqual(result_data[0]["certificate_name"], "Certificate Position 1")
