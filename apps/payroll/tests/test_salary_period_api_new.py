"""Tests for new salary period API endpoints."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from apps.payroll.models import PayrollSlip, SalaryPeriod


def get_response_data(response):
    """Helper to extract data from JSON response."""
    return json.loads(response.content)


@pytest.mark.django_db
class TestSalaryPeriodCreateAPI:
    """Test async salary period creation API."""

    @patch("apps.payroll.tasks.create_salary_period_task.delay")
    def test_create_salary_period_returns_task_id(self, mock_task, api_client, salary_config):
        """Test creating salary period returns task ID."""
        # Arrange
        mock_task.return_value = MagicMock(id="test-task-id-123")

        data = {
            "month": "1/2024",
        }

        # Act
        response = api_client.post("/api/payroll/salary-periods/", data, format="json")

        # Assert
        import json

        response_data = json.loads(response.content)
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "task_id" in response_data["data"]
        assert response_data["data"]["task_id"] == "test-task-id-123"
        assert mock_task.called

    def test_create_with_custom_deadlines(self, api_client, salary_config):
        """Test creating period with custom deadlines."""
        # Arrange
        data = {
            "month": "1/2024",
            "proposal_deadline": "2024-02-03",
            "kpi_assessment_deadline": "2024-02-07",
        }

        # Act
        with patch("apps.payroll.tasks.create_salary_period_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="task-123")
            response = api_client.post("/api/payroll/salary-periods/", data, format="json")

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_cannot_create_with_uncompleted_previous(self, api_client, salary_period):
        """Test cannot create new period when previous is not completed."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        data = {
            "month": "2/2024",  # Next month after salary_period
        }

        # Act
        response = api_client.post("/api/payroll/salary-periods/", data, format="json")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not completed" in str(response_data).lower()


@pytest.mark.django_db
class TestSalaryPeriodUpdateAPI:
    """Test salary period update deadlines API."""

    def test_update_deadlines(self, api_client, salary_period):
        """Test updating period deadlines."""
        # Arrange
        data = {
            "proposal_deadline": "2024-02-10",
            "kpi_assessment_deadline": "2024-02-15",
        }

        # Act
        response = api_client.patch(f"/api/payroll/salary-periods/{salary_period.id}/", data, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        salary_period.refresh_from_db()
        assert salary_period.proposal_deadline == date(2024, 2, 10)
        assert salary_period.kpi_assessment_deadline == date(2024, 2, 15)


@pytest.mark.django_db
class TestSalaryPeriodRecalculateAPI:
    """Test async recalculation API."""

    @patch("apps.payroll.tasks.recalculate_salary_period_task.delay")
    def test_recalculate_returns_task_id(self, mock_task, api_client, salary_period):
        """Test recalculate returns task ID."""
        # Arrange
        mock_task.return_value = MagicMock(id="recalc-task-123")

        # Act
        response = api_client.post(f"/api/payroll/salary-periods/{salary_period.id}/recalculate/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "task_id" in response_data["data"]
        assert response_data["data"]["task_id"] == "recalc-task-123"

    def test_cannot_recalculate_completed(self, api_client, salary_period):
        """Test cannot recalculate completed period."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.COMPLETED
        salary_period.save()

        # Act
        response = api_client.post(f"/api/payroll/salary-periods/{salary_period.id}/recalculate/")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTaskStatusAPI:
    """Test Celery task status checking API."""

    @patch("celery.result.AsyncResult")
    def test_check_task_status_success(self, mock_result, api_client):
        """Test checking successful task status."""
        # Arrange
        mock_task = MagicMock()
        mock_task.state = "SUCCESS"
        mock_task.result = {"period_id": 1, "total_employees": 50}
        mock_result.return_value = mock_task

        # Act
        response = api_client.get("/api/payroll/salary-periods/task-status/test-task-123/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        assert response_data["data"]["state"] == "SUCCESS"
        assert "result" in response_data["data"]

    @patch("celery.result.AsyncResult")
    def test_check_task_status_progress(self, mock_result, api_client):
        """Test checking task in progress."""
        # Arrange
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = {"current": 25, "total": 50}
        mock_result.return_value = mock_task

        # Act
        response = api_client.get("/api/payroll/salary-periods/task-status/test-task-123/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        assert response_data["data"]["state"] == "PROGRESS"
        assert "meta" in response_data["data"]


@pytest.mark.django_db
class TestReadySlipsAPI:
    """Test ready slips endpoint."""

    def test_ready_ongoing_period(self, api_client, salary_period, payroll_slip_ready):
        """Test getting ready slips for ongoing period."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        # Should return READY slips from this and previous periods
        assert len(response_data["data"]["results"]) >= 1

    def test_ready_completed_period(self, api_client, salary_period, payroll_slip_ready):
        """Test getting delivered slips for completed period."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.COMPLETED
        salary_period.save()

        # Mark slip as delivered
        payroll_slip_ready.status = PayrollSlip.Status.DELIVERED
        payroll_slip_ready.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        # Should return only DELIVERED slips from this period
        assert len(response_data["data"]["results"]) >= 1


@pytest.mark.django_db
class TestNotReadySlipsAPI:
    """Test not-ready slips endpoint."""

    def test_not_ready_ongoing_period(self, api_client, salary_period, payroll_slip_pending):
        """Test getting pending/hold slips for ongoing period."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        # Should return PENDING/HOLD slips from this and previous periods
        assert len(response_data["data"]["results"]) >= 1

    def test_not_ready_completed_period(self, api_client, salary_period, payroll_slip_pending):
        """Test getting pending/hold slips for completed period."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.COMPLETED
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        # Should return only PENDING/HOLD slips from this period
        assert len(response_data["data"]["results"]) >= 1
