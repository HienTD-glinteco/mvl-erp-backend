from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import CertificateType
from apps.hrm.models import EmployeeCertificate


@pytest.mark.django_db
class TestEmployeeCertificateAutoCodeAPI:
    """Test cases for EmployeeCertificate auto-code generation."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user, employee):
        self.client = api_client
        self.user = user
        self.employee = employee

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
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
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify code was auto-generated with correct prefix for foreign_language (CCNN)
        assert "code" in response_data
        assert response_data["code"].startswith("CCNN")

        # Verify in database
        certificate = EmployeeCertificate.objects.first()
        assert certificate is not None
        assert certificate.code == response_data["code"]

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
        assert certificate.code.startswith("CCNN")
        # Extract number part (after CCNN prefix)
        number_part = certificate.code[4:]
        assert number_part.isdigit()
        assert len(number_part) == 9

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
        assert len(codes) == len(set(codes))

        # Verify all codes start with CCNN (foreign language prefix)
        for code in codes:
            assert code.startswith("CCNN")

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
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify custom code was ignored and auto-generated code was used
        assert response_data["code"] != "CUSTOM_CODE"
        # Computer certificates should have CCTH prefix
        assert response_data["code"].startswith("CCTH")

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
            assert certificate.code.startswith(expected_prefix), (
                f"Certificate type {cert_type} should have prefix {expected_prefix}, but got code {certificate.code}"
            )

            # Verify the number part is 9 digits
            number_part = certificate.code[len(expected_prefix) :]
            assert number_part.isdigit(), f"Number part should be digits: {number_part}"
            assert len(number_part) == 9, f"Number part should be 9 digits: {number_part}"

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
            assert certificate.get_code_prefix() == expected_prefix, (
                f"Certificate type {cert_type} should return prefix {expected_prefix}"
            )
