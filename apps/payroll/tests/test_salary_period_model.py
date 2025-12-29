"""Tests for SalaryPeriod model."""

from datetime import date

import pytest

from apps.payroll.models import SalaryPeriod


@pytest.mark.django_db
class TestSalaryPeriodModel:
    """Test SalaryPeriod model."""

    def test_create_salary_period(self, salary_config):
        """Test creating a salary period."""
        # Arrange
        month = date(2024, 1, 1)

        # Act
        period = SalaryPeriod.objects.create(month=month, salary_config_snapshot=salary_config.config)

        # Assert
        assert period.code.startswith("SP_")
        assert period.month == month
        assert period.status == SalaryPeriod.Status.ONGOING
        assert period.standard_working_days > 0
        assert period.salary_config_snapshot == salary_config.config

    def test_cannot_create_duplicate_month(self, salary_config):
        """Test that only one period per month is allowed."""
        # Arrange
        month = date(2024, 1, 1)
        SalaryPeriod.objects.create(month=month, salary_config_snapshot=salary_config.config)

        # Act & Assert
        with pytest.raises(Exception):  # Unique constraint violation
            SalaryPeriod.objects.create(month=month, salary_config_snapshot=salary_config.config)

    def test_can_complete_all_ready(self, salary_period, payroll_slip_ready):
        """Test period can be completed when all slips are READY."""
        # Arrange - payroll_slip_ready is already READY

        # Act
        can_complete = salary_period.can_complete()

        # Assert
        assert can_complete is True

    def test_cannot_complete_with_pending(self, salary_period, payroll_slip_pending):
        """Test period cannot be completed with PENDING slips."""
        # Act
        can_complete = salary_period.can_complete()

        # Assert
        assert can_complete is False

    def test_complete_period(self, salary_period, payroll_slip_ready, user):
        """Test completing a salary period."""
        # Act
        salary_period.complete(user=user)

        # Assert
        assert salary_period.status == SalaryPeriod.Status.COMPLETED
        assert salary_period.completed_by == user
        assert salary_period.completed_at is not None

        # Verify READY slips became DELIVERED
        payroll_slip_ready.refresh_from_db()
        assert payroll_slip_ready.status == payroll_slip_ready.Status.DELIVERED


@pytest.mark.django_db
class TestSalaryConfigSnapshot:
    """Test salary config snapshot functionality."""

    def test_period_stores_config_snapshot(self, salary_config):
        """Test that period stores config snapshot on creation."""
        # Arrange
        month = date(2024, 1, 1)

        # Act
        period = SalaryPeriod.objects.create(month=month, salary_config_snapshot=salary_config.config)

        # Assert
        assert period.salary_config_snapshot is not None
        assert period.salary_config_snapshot == salary_config.config
        assert "insurance_contributions" in period.salary_config_snapshot

    def test_old_period_unchanged_after_config_update(self, salary_period, salary_config):
        """Test that old periods remain unchanged when config is updated."""
        # Arrange
        import copy

        original_snapshot = copy.deepcopy(salary_period.salary_config_snapshot)

        # Act - Update salary config
        new_config = copy.deepcopy(salary_config.config)
        new_config["insurance_contributions"]["social_insurance"]["employee_rate"] = 0.09
        salary_config.config = new_config
        salary_config.save()

        # Assert - Old period snapshot unchanged
        salary_period.refresh_from_db()
        assert salary_period.salary_config_snapshot == original_snapshot
        assert (
            salary_period.salary_config_snapshot["insurance_contributions"]["social_insurance"]["employee_rate"]
            == 0.08
        )


@pytest.mark.django_db
class TestSalaryPeriodCodeGeneration:
    """Test salary period code generation."""

    def test_code_format(self, salary_config):
        """Test code is generated in format SP_YYYYMM."""
        # Arrange
        month = date(2024, 1, 1)

        # Act
        period = SalaryPeriod.objects.create(month=month, salary_config_snapshot=salary_config.config)

        # Assert
        assert period.code == "SP_202401"

    def test_code_different_months(self, salary_config):
        """Test code changes with different months."""
        # Act
        period1 = SalaryPeriod.objects.create(month=date(2024, 1, 1), salary_config_snapshot=salary_config.config)
        period2 = SalaryPeriod.objects.create(month=date(2024, 2, 1), salary_config_snapshot=salary_config.config)

        # Assert
        assert period1.code == "SP_202401"
        assert period2.code == "SP_202402"


@pytest.mark.django_db
class TestSalaryPeriodColoredValue:
    """Test colored value for salary period status."""

    def test_colored_status_ongoing(self, salary_period):
        """Test colored status for ONGOING status."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.ONGOING
        salary_period.save()

        # Act
        colored_status = salary_period.get_colored_value("status")

        # Assert
        assert colored_status["value"] == SalaryPeriod.Status.ONGOING
        assert colored_status["variant"] is not None

    def test_colored_status_completed(self, salary_period, payroll_slip_ready, user):
        """Test colored status for COMPLETED status."""
        # Arrange
        salary_period.complete(user=user)

        # Act
        colored_status = salary_period.get_colored_value("status")

        # Assert
        assert colored_status["value"] == SalaryPeriod.Status.COMPLETED
        assert colored_status["variant"] is not None
