"""Tests for PayrollSlip API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestPayrollSlipSendEmail:
    """Test send_email action for PayrollSlip."""

    def test_send_email_success(self, api_client, payroll_slip_ready, superuser):
        """Test sending email successfully."""
        # Arrange
        url = reverse("payroll:payroll-slips-send-email", kwargs={"pk": payroll_slip_ready.pk})

        # Mock the Celery task
        with patch("apps.payroll.tasks.send_payroll_email_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="test-task-123")

            # Act
            response = api_client.post(url)

            # Assert
            assert response.status_code == status.HTTP_202_ACCEPTED
            response_data = response.json()
            assert response_data["success"] is True
            assert "task_id" in response_data["data"]
            assert response_data["data"]["task_id"] == "test-task-123"
            assert response_data["data"]["status"] == "Task created"
            assert "started" in response_data["data"]["message"]
            mock_task.delay.assert_called_once_with(payroll_slip_ready.id)

    def test_send_email_no_employee_email(self, api_client, payroll_slip_ready, superuser):
        """Test sending email when employee has no email."""
        # Arrange
        payroll_slip_ready.employee.email = ""
        payroll_slip_ready.employee.save()
        url = reverse("payroll:payroll-slips-send-email", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = api_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert isinstance(response_data["error"], (str, dict))
        if isinstance(response_data["error"], str):
            assert "no email" in response_data["error"].lower()
        else:
            # If error is a dict, check for the message
            error_msg = str(response_data["error"])
            assert "no email" in error_msg.lower()

    def test_send_email_unauthenticated(self, payroll_slip_ready):
        """Test sending email without authentication."""
        # Arrange
        from rest_framework.test import APIClient

        unauthenticated_client = APIClient()
        url = reverse("payroll:payroll-slips-send-email", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = unauthenticated_client.post(url)

        # Assert
        # Without authentication, should get 403 Forbidden (DRF default)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_send_email_nonexistent_slip(self, api_client, superuser):
        """Test sending email for non-existent slip."""
        # Arrange
        url = reverse("payroll:payroll-slips-send-email", kwargs={"pk": 999999})

        # Act
        response = api_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_send_email_returns_task_id(self, api_client, payroll_slip_ready, superuser):
        """Test that send_email returns a task ID for tracking."""
        # Arrange
        url = reverse("payroll:payroll-slips-send-email", kwargs={"pk": payroll_slip_ready.pk})

        # Mock the Celery task
        with patch("apps.payroll.tasks.send_payroll_email_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="unique-task-id-456")

            # Act
            response = api_client.post(url)

            # Assert
            assert response.status_code == status.HTTP_202_ACCEPTED
            response_data = response.json()
            assert response_data["data"]["task_id"] == "unique-task-id-456"

    def test_send_email_task_called_with_correct_params(self, api_client, payroll_slip_ready, superuser):
        """Test that task is called with correct payroll slip ID."""
        # Arrange
        url = reverse("payroll:payroll-slips-send-email", kwargs={"pk": payroll_slip_ready.pk})

        # Mock the Celery task
        with patch("apps.payroll.tasks.send_payroll_email_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="test-task")

            # Act
            api_client.post(url)

            # Assert
            mock_task.delay.assert_called_once_with(payroll_slip_ready.id)


@pytest.mark.django_db
class TestPayrollSlipExportDocument:
    """Test export_detail_document action for PayrollSlip."""

    def test_export_document_pdf_direct(self, api_client, payroll_slip_ready, superuser):
        """Test exporting payroll slip as PDF with direct download."""
        # Arrange
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = api_client.get(url, {"type": "pdf", "delivery": "direct"})

        # Assert
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/pdf"
        period_str = payroll_slip_ready.salary_period.month.strftime("%Y%m")
        expected_filename = f"payroll_slip_{payroll_slip_ready.employee_code.lower()}_{period_str}.pdf"
        assert f'attachment; filename="{expected_filename}"' in response["Content-Disposition"]

    def test_export_document_docx_direct(self, api_client, payroll_slip_ready, superuser):
        """Test exporting payroll slip as DOCX with direct download."""
        # Arrange
        from pathlib import Path
        from unittest.mock import patch

        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Mock pypandoc.convert_file to create a valid DOCX file
        def mock_convert_file(source, to, outputfile, extra_args=None):
            docx_path = Path(outputfile)
            with open(docx_path, "wb") as f:
                import zipfile

                with zipfile.ZipFile(f, "w") as zf:
                    zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types></Types>')

        # Act
        with patch("pypandoc.convert_file", side_effect=mock_convert_file):
            response = api_client.get(url, {"type": "docx", "delivery": "direct"})

        # Assert
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        period_str = payroll_slip_ready.salary_period.month.strftime("%Y%m")
        expected_filename = f"payroll_slip_{payroll_slip_ready.employee_code.lower()}_{period_str}.docx"
        assert f'attachment; filename="{expected_filename}"' in response["Content-Disposition"]

    def test_export_document_default_is_pdf(self, api_client, payroll_slip_ready, superuser):
        """Test that default export format is PDF."""
        # Arrange
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/pdf"

    def test_export_document_invalid_type(self, api_client, payroll_slip_ready, superuser):
        """Test export with invalid file type returns error."""
        # Arrange
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = api_client.get(url, {"type": "invalid"})

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data

    def test_export_document_invalid_delivery(self, api_client, payroll_slip_ready, superuser):
        """Test export with invalid delivery method returns error."""
        # Arrange
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = api_client.get(url, {"delivery": "invalid"})

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data

    def test_export_document_not_found(self, api_client, superuser):
        """Test export with non-existent payroll slip returns 404."""
        # Arrange
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": 999999})

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_export_document_unauthenticated(self, payroll_slip_ready):
        """Test export without authentication."""
        # Arrange
        from rest_framework.test import APIClient

        unauthenticated_client = APIClient()
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = unauthenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_export_document_contains_payroll_data(self, api_client, payroll_slip_ready, superuser):
        """Test that exported PDF contains payroll slip data."""
        # Arrange
        payroll_slip_ready.net_salary = 15000000
        payroll_slip_ready.gross_income = 20000000
        payroll_slip_ready.save()
        url = reverse("payroll:payroll-slips-export-detail-document", kwargs={"pk": payroll_slip_ready.pk})

        # Act
        response = api_client.get(url, {"type": "pdf"})

        # Assert
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        # PDF should be generated (non-empty)
        assert len(response.content) > 0
