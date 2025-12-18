"""Tests for EmployeeCertificate auto-code generation."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import CertificateType
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeCertificate

User = get_user_model()


class EmployeeCertificateAutoCodeAPITest(TransactionTestCase):
    """Test cases for EmployeeCertificate auto-code generation."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeCertificate.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

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

        self.employee = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee",
            username="testemployee",
            email="testemployee@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date=date(2020, 1, 1),
            citizen_id="000000020100",
        )

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_create_certificate_auto_generates_code(self):
        """Test creating a certificate auto-generates code with correct prefix."""
        # Arrange
        cert_data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_code": "IELTS-123456",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
            "issuing_organization": "CertOrg",
        }

        # Act
        url = reverse("hrm:employee-certificate-list")
        response = self.client.post(url, cert_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated with correct prefix for foreign_language (CCNN)
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("CCNN"))

        # Verify in database
        certificate = EmployeeCertificate.objects.first()
        self.assertIsNotNone(certificate)
        self.assertEqual(certificate.code, response_data["code"])

    def test_certificate_code_format(self):
        """Test certificate code follows format {PREFIX}{id:09d} based on certificate_type."""
        # Create certificate with FOREIGN_LANGUAGE type
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Test Certificate",
            issue_date=date.today(),
        )

        # Verify code format - should start with CCNN for foreign_language
        self.assertTrue(certificate.code.startswith("CCNN"))
        # Extract number part (after CCNN prefix)
        number_part = certificate.code[4:]
        self.assertTrue(number_part.isdigit())
        self.assertEqual(len(number_part), 9)

    def test_multiple_certificates_unique_codes(self):
        """Test multiple certificates get unique codes with correct prefix."""
        certificates = []
        for i in range(3):
            cert = EmployeeCertificate.objects.create(
                employee=self.employee,
                certificate_type=CertificateType.FOREIGN_LANGUAGE,
                certificate_name=f"Test Certificate {i}",
                issue_date=date.today(),
            )
            certificates.append(cert)

        # Verify all codes are unique
        codes = [cert.code for cert in certificates]
        self.assertEqual(len(codes), len(set(codes)))

        # Verify all codes start with CCNN (foreign language prefix)
        for code in codes:
            self.assertTrue(code.startswith("CCNN"))

    def test_code_is_read_only_in_api(self):
        """Test that code field is read-only and cannot be set via API."""
        # Arrange
        cert_data = {
            "employee_id": self.employee.id,
            "certificate_type": "computer",
            "certificate_code": "MOS-123456",
            "certificate_name": "MS Office",
            "issue_date": "2024-06-01",
            "issuing_organization": "CertOrg",
            "code": "CUSTOM_CODE",  # This should be ignored
        }

        # Act
        url = reverse("hrm:employee-certificate-list")
        response = self.client.post(url, cert_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify custom code was ignored and auto-generated code was used
        self.assertNotEqual(response_data["code"], "CUSTOM_CODE")
        # Computer certificates should have CCTH prefix
        self.assertTrue(response_data["code"].startswith("CCTH"))

    def test_code_prefix_for_each_certificate_type(self):
        """Test that each certificate type generates the correct code prefix."""
        # Define expected prefixes for each certificate type
        prefix_mapping = {
            CertificateType.FOREIGN_LANGUAGE: "CCNN",
            CertificateType.COMPUTER: "CCTH",
            CertificateType.DIPLOMA: "BTN",
            CertificateType.OTHER: "CCK",
            CertificateType.BROKER_TRAINING_COMPLETION: "CCHMG",
            CertificateType.REAL_ESTATE_PRACTICE_LICENSE: "CCBDS",
        }

        for cert_type, expected_prefix in prefix_mapping.items():
            # Create certificate with specific type
            expiry_date = None
            if cert_type == CertificateType.REAL_ESTATE_PRACTICE_LICENSE:
                # Real estate practice license requires expiry_date
                expiry_date = date(2030, 12, 31)

            certificate = EmployeeCertificate.objects.create(
                employee=self.employee,
                certificate_type=cert_type,
                certificate_name=f"Test {cert_type}",
                issue_date=date.today(),
                expiry_date=expiry_date,
            )

            # Verify the code starts with the expected prefix
            self.assertTrue(
                certificate.code.startswith(expected_prefix),
                f"Certificate type {cert_type} should have prefix {expected_prefix}, but got code {certificate.code}",
            )

            # Verify the number part is 9 digits
            number_part = certificate.code[len(expected_prefix) :]
            self.assertTrue(number_part.isdigit(), f"Number part should be digits: {number_part}")
            self.assertEqual(len(number_part), 9, f"Number part should be 9 digits: {number_part}")

    def test_get_code_prefix_method(self):
        """Test the get_code_prefix method returns correct prefix for each certificate type."""
        prefix_mapping = {
            CertificateType.FOREIGN_LANGUAGE: "CCNN",
            CertificateType.COMPUTER: "CCTH",
            CertificateType.DIPLOMA: "BTN",
            CertificateType.OTHER: "CCK",
            CertificateType.BROKER_TRAINING_COMPLETION: "CCHMG",
            CertificateType.REAL_ESTATE_PRACTICE_LICENSE: "CCBDS",
        }

        for cert_type, expected_prefix in prefix_mapping.items():
            # Create an unsaved certificate instance to test the method
            certificate = EmployeeCertificate(
                employee=self.employee,
                certificate_type=cert_type,
                certificate_name=f"Test {cert_type}",
                issue_date=date.today(),
            )

            # Verify get_code_prefix returns the expected prefix
            self.assertEqual(
                certificate.get_code_prefix(),
                expected_prefix,
                f"Certificate type {cert_type} should return prefix {expected_prefix}",
            )
