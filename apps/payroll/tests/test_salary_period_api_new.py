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
        payroll_slip_ready.payment_period = salary_period
        payroll_slip_ready.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        # Should return only DELIVERED slips from this period
        assert len(response_data["data"]["results"]) >= 1

    def test_ready_filter_by_employee_code(self, api_client, salary_period, payroll_slip_ready):
        """Test filtering ready slips by employee code."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        employee_code = payroll_slip_ready.employee_code

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/ready/?employee_code={employee_code}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        assert all(slip["employee_code"] == employee_code for slip in response_data["data"]["results"])

    def test_ready_filter_by_employee_code_icontains(self, api_client, salary_period, payroll_slip_ready):
        """Test filtering ready slips by employee code with icontains."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        employee_code_part = payroll_slip_ready.employee_code[:3]

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/ready/?employee_code__icontains={employee_code_part}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        assert all(
            employee_code_part.upper() in slip["employee_code"].upper() for slip in response_data["data"]["results"]
        )

    def test_ready_filter_by_department_name(self, api_client, salary_period, payroll_slip_ready):
        """Test filtering ready slips by department name."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        department_name = payroll_slip_ready.department_name

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/ready/?department_name={department_name}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        if response_data["data"]["results"]:
            assert all(slip["department_name"] == department_name for slip in response_data["data"]["results"])

    def test_ready_filter_by_position_name(self, api_client, salary_period, payroll_slip_ready):
        """Test filtering ready slips by position name."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        position_name = payroll_slip_ready.position_name

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/ready/?position_name={position_name}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        if response_data["data"]["results"]:
            assert all(slip["position_name"] == position_name for slip in response_data["data"]["results"])

    def test_ready_filter_by_has_unpaid_penalty(self, api_client, salary_period, payroll_slip_ready):
        """Test filtering ready slips by has_unpaid_penalty."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/?has_unpaid_penalty=true")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_ready_search_by_employee_code(self, api_client, salary_period, payroll_slip_ready):
        """Test searching ready slips by employee code."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        search_term = payroll_slip_ready.employee_code[:3]

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/?search={search_term}")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_ready_search_by_employee_name(self, api_client, salary_period, payroll_slip_ready):
        """Test searching ready slips by employee name."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        search_term = payroll_slip_ready.employee_name.split()[0] if payroll_slip_ready.employee_name else "test"

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/?search={search_term}")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_ready_ordering_by_employee_code(self, api_client, salary_period, payroll_slip_ready):
        """Test ordering ready slips by employee code."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/?ordering=employee_code")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_ready_ordering_by_gross_income_desc(self, api_client, salary_period, payroll_slip_ready):
        """Test ordering ready slips by gross income descending."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/ready/?ordering=-gross_income")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK


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

    def test_not_ready_filter_by_employee_code(self, api_client, salary_period, payroll_slip_pending):
        """Test filtering not-ready slips by employee code."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        employee_code = payroll_slip_pending.employee_code

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?employee_code={employee_code}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        assert all(slip["employee_code"] == employee_code for slip in response_data["data"]["results"])

    def test_not_ready_filter_by_employee_code_icontains(self, api_client, salary_period, payroll_slip_pending):
        """Test filtering not-ready slips by employee code with icontains."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        employee_code_part = payroll_slip_pending.employee_code[:3]

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?employee_code__icontains={employee_code_part}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        assert all(
            employee_code_part.upper() in slip["employee_code"].upper() for slip in response_data["data"]["results"]
        )

    def test_not_ready_filter_by_department_name(self, api_client, salary_period, payroll_slip_pending):
        """Test filtering not-ready slips by department name."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        department_name = payroll_slip_pending.department_name

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?department_name={department_name}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        if response_data["data"]["results"]:
            assert all(slip["department_name"] == department_name for slip in response_data["data"]["results"])

    def test_not_ready_filter_by_position_name(self, api_client, salary_period, payroll_slip_pending):
        """Test filtering not-ready slips by position name."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        position_name = payroll_slip_pending.position_name

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?position_name={position_name}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
        if response_data["data"]["results"]:
            assert all(slip["position_name"] == position_name for slip in response_data["data"]["results"])

    def test_not_ready_filter_by_has_unpaid_penalty(self, api_client, salary_period, payroll_slip_pending):
        """Test filtering not-ready slips by has_unpaid_penalty."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?has_unpaid_penalty=true")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_not_ready_filter_by_need_resend_email(self, api_client, salary_period, payroll_slip_pending):
        """Test filtering not-ready slips by need_resend_email."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?need_resend_email=false")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_not_ready_search_by_employee_code(self, api_client, salary_period, payroll_slip_pending):
        """Test searching not-ready slips by employee code."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        search_term = payroll_slip_pending.employee_code[:3]

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?search={search_term}")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_not_ready_search_by_employee_name(self, api_client, salary_period, payroll_slip_pending):
        """Test searching not-ready slips by employee name."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        search_term = payroll_slip_pending.employee_name.split()[0] if payroll_slip_pending.employee_name else "test"

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?search={search_term}")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_not_ready_ordering_by_employee_code(self, api_client, salary_period, payroll_slip_pending):
        """Test ordering not-ready slips by employee code."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?ordering=employee_code")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_not_ready_ordering_by_net_salary_desc(self, api_client, salary_period, payroll_slip_pending):
        """Test ordering not-ready slips by net salary descending."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        response = api_client.get(f"/api/payroll/salary-periods/{salary_period.id}/not-ready/?ordering=-net_salary")

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK

    def test_not_ready_multiple_filters(self, api_client, salary_period, payroll_slip_pending):
        """Test combining multiple filters on not-ready slips."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()
        employee_code = payroll_slip_pending.employee_code
        department_name = payroll_slip_pending.department_name

        # Act
        response = api_client.get(
            f"/api/payroll/salary-periods/{salary_period.id}/not-ready/"
            f"?employee_code={employee_code}&department_name={department_name}"
        )

        # Assert
        response_data = get_response_data(response)
        assert response.status_code == status.HTTP_200_OK
