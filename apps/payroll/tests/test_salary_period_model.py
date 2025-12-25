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
        period = SalaryPeriod.objects.create(
            month=month, salary_config_snapshot=salary_config.config
        )

        # Assert
        assert period.code == "SP-202401"
        assert period.month == month
        assert period.status == SalaryPeriod.Status.ONGOING
        assert period.standard_working_days > 0
        assert period.salary_config_snapshot == salary_config.config

    def test_cannot_create_duplicate_month(self, salary_config):
        """Test that only one period per month is allowed."""
        # Arrange
        month = date(2024, 1, 1)
        SalaryPeriod.objects.create(
            month=month, salary_config_snapshot=salary_config.config
        )

        # Act & Assert
        with pytest.raises(Exception):  # Unique constraint violation
            SalaryPeriod.objects.create(
                month=month, salary_config_snapshot=salary_config.config
            )

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
        period = SalaryPeriod.objects.create(
            month=month, salary_config_snapshot=salary_config.config
        )

        # Assert
        assert period.salary_config_snapshot is not None
        assert period.salary_config_snapshot == salary_config.config
        assert "insurance_contributions" in period.salary_config_snapshot

    def test_old_period_unchanged_after_config_update(self, salary_period, salary_config):
        """Test that old periods remain unchanged when config is updated."""
        # Arrange
        original_snapshot = salary_period.salary_config_snapshot.copy()

        # Act - Update salary config
        new_config = salary_config.config.copy()
        new_config["insurance_contributions"]["social_insurance"]["employee_rate"] = 0.09
        salary_config.config = new_config
        salary_config.save()

        # Assert - Old period snapshot unchanged
        salary_period.refresh_from_db()
        assert salary_period.salary_config_snapshot == original_snapshot
        assert (
            salary_period.salary_config_snapshot["insurance_contributions"]["social_insurance"][
                "employee_rate"
            ]
            == 0.08
        )
