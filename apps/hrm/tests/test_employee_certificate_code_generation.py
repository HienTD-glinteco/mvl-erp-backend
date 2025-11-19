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
        """Test creating a certificate auto-generates code."""
        # Arrange
        cert_data = {
            "employee_id": self.employee.id,
            "certificate_type": "foreign_language",
            "certificate_code": "IELTS-123456",
            "certificate_name": "IELTS 7.0",
            "issue_date": "2024-06-01",
        }

        # Act
        url = reverse("hrm:employee-certificate-list")
        response = self.client.post(url, cert_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("EC"))

        # Verify in database
        certificate = EmployeeCertificate.objects.first()
        self.assertIsNotNone(certificate)
        self.assertEqual(certificate.code, response_data["code"])

    def test_certificate_code_format(self):
        """Test certificate code follows format EC{id:03d}."""
        # Create certificate
        certificate = EmployeeCertificate.objects.create(
            employee=self.employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Test Certificate",
            issue_date=date.today(),
        )

        # Verify code format
        self.assertTrue(certificate.code.startswith("EC"))
        # Extract number part
        number_part = certificate.code[2:]
        self.assertTrue(number_part.isdigit())
        self.assertGreaterEqual(len(number_part), 3)

    def test_multiple_certificates_unique_codes(self):
        """Test multiple certificates get unique codes."""
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

        # Verify all codes start with EC
        for code in codes:
            self.assertTrue(code.startswith("EC"))

    def test_code_is_read_only_in_api(self):
        """Test that code field is read-only and cannot be set via API."""
        # Arrange
        cert_data = {
            "employee_id": self.employee.id,
            "certificate_type": "computer",
            "certificate_code": "MOS-123456",
            "certificate_name": "MS Office",
            "issue_date": "2024-06-01",
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
        self.assertTrue(response_data["code"].startswith("EC"))
