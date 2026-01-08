"""Tests for business progressive salary calculation."""

from decimal import Decimal

import pytest

from apps.payroll.services.payroll_calculation import PayrollCalculationService


@pytest.mark.django_db
class TestBusinessProgressiveSalaryCalculation:
    """Test business progressive salary calculation logic."""

    def test_business_progressive_salary_subtracts_base_and_kpi(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that business progressive salary = tier_amount - base_salary - kpi_salary."""
        # Arrange - Configure salary config with M1 tier
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M1",
                    "amount": 30000000,  # Total tier amount
                    "criteria": [
                        {"name": "revenue", "min": 100000000},
                        {"name": "transaction_count", "min": 5},
                    ],
                },
                {
                    "code": "M0",
                    "amount": 5007600,  # base_salary + kpi_salary
                    "criteria": [
                        {"name": "revenue", "min": 50000000},
                        {"name": "transaction_count", "min": 1},
                    ],
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("3000000")
        contract.kpi_salary = Decimal("2007600")
        contract.save()

        # Create sales data that meets M1 criteria
        from apps.payroll.models import SalesRevenue

        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=220000000,  # Total revenue
            transaction_count=6,  # Total count
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # business_progressive_salary = 30000000 - 3000000 - 2007600 = 24992400
        expected_progressive = Decimal("30000000") - Decimal("3000000") - Decimal("2007600")
        assert payroll_slip.business_grade == "M1"
        assert payroll_slip.business_progressive_salary == expected_progressive
        assert payroll_slip.sales_revenue == Decimal("220000000")
        assert payroll_slip.sales_transaction_count == 6

    def test_business_progressive_salary_zero_when_tier_amount_less_than_base_plus_kpi(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that business progressive salary is 0 when tier_amount < base_salary + kpi_salary."""
        # Arrange - M0 tier amount equals base + kpi
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M0",
                    "amount": 5007600,  # = base_salary (3000000) + kpi_salary (2007600)
                    "criteria": [
                        {"name": "revenue", "min": 50000000},
                        {"name": "transaction_count", "min": 1},
                    ],
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("3000000")
        contract.kpi_salary = Decimal("2007600")
        contract.save()

        # Create sales data that meets M0 criteria
        from apps.payroll.models import SalesRevenue

        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=60000000,
            transaction_count=2,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # business_progressive_salary = 5007600 - 3000000 - 2007600 = 0
        assert payroll_slip.business_grade == "M0"
        assert payroll_slip.business_progressive_salary == Decimal("0")

    def test_business_progressive_salary_zero_when_tier_amount_less_than_components(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test floor at 0 when tier_amount < (base_salary + kpi_salary)."""
        # Arrange - Tier amount less than base + kpi
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M0",
                    "amount": 4000000,  # Less than base (3000000) + kpi (2007600)
                    "criteria": [
                        {"name": "revenue", "min": 50000000},
                        {"name": "transaction_count", "min": 1},
                    ],
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("3000000")
        contract.kpi_salary = Decimal("2007600")
        contract.save()

        # Create sales data
        from apps.payroll.models import SalesRevenue

        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=60000000,
            transaction_count=2,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # business_progressive_salary = max(0, 4000000 - 3000000 - 2007600) = 0
        assert payroll_slip.business_progressive_salary == Decimal("0")

    def test_business_progressive_salary_no_sales_data(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test business progressive salary when employee has no sales."""
        # Arrange
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M1",
                    "amount": 30000000,
                    "criteria": [
                        {"name": "revenue", "min": 100000000},
                        {"name": "transaction_count", "min": 5},
                    ],
                },
                {
                    "code": "M0",
                    "amount": 0,
                    "criteria": [],  # Default tier with no criteria
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("3000000")
        contract.kpi_salary = Decimal("2007600")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.sales_revenue == Decimal("0")
        assert payroll_slip.sales_transaction_count == 0
        assert payroll_slip.business_grade == "M0"
        # business_progressive_salary = max(0, 0 - 3000000 - 2007600) = 0
        assert payroll_slip.business_progressive_salary == Decimal("0")

    def test_business_progressive_salary_tier_selection_by_highest_qualified(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that highest qualifying tier is selected."""
        # Arrange - Multiple tiers, employee qualifies for M2
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M3",
                    "amount": 50000000,
                    "criteria": [
                        {"name": "revenue", "min": 500000000},
                        {"name": "transaction_count", "min": 20},
                    ],
                },
                {
                    "code": "M2",
                    "amount": 35000000,
                    "criteria": [
                        {"name": "revenue", "min": 200000000},
                        {"name": "transaction_count", "min": 10},
                    ],
                },
                {
                    "code": "M1",
                    "amount": 25000000,
                    "criteria": [
                        {"name": "revenue", "min": 100000000},
                        {"name": "transaction_count", "min": 5},
                    ],
                },
                {
                    "code": "M0",
                    "amount": 5007600,
                    "criteria": [
                        {"name": "revenue", "min": 50000000},
                        {"name": "transaction_count", "min": 1},
                    ],
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("3000000")
        contract.kpi_salary = Decimal("2007600")
        contract.save()

        # Create sales data that meets M2 criteria (but not M3)
        from apps.payroll.models import SalesRevenue

        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=250000000,  # Total revenue
            transaction_count=10,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Total revenue = 250000000, count = 10 -> qualifies for M2
        assert payroll_slip.sales_revenue == Decimal("250000000")
        assert payroll_slip.sales_transaction_count == 10
        assert payroll_slip.business_grade == "M2"
        # business_progressive_salary = 35000000 - 3000000 - 2007600 = 29992400
        expected_progressive = Decimal("35000000") - Decimal("3000000") - Decimal("2007600")
        assert payroll_slip.business_progressive_salary == expected_progressive

    def test_business_progressive_salary_uses_sales_revenue_data(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that calculation uses SalesRevenue model data."""
        # Arrange
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M1",
                    "amount": 30000000,
                    "criteria": [
                        {"name": "revenue", "min": 100000000},
                        {"name": "transaction_count", "min": 5},
                    ],
                },
                {
                    "code": "M0",
                    "amount": 5007600,
                    "criteria": [
                        {"name": "revenue", "min": 50000000},
                        {"name": "transaction_count", "min": 1},
                    ],
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("3000000")
        contract.kpi_salary = Decimal("2007600")
        contract.save()

        # Create sales revenue data
        from apps.payroll.models import SalesRevenue

        # Revenue: 80M, count=4 (should match M0, not M1)
        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=80000000,
            transaction_count=4,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Revenue=80M, count=4 -> M0
        assert payroll_slip.sales_revenue == Decimal("80000000")
        assert payroll_slip.sales_transaction_count == 4
        assert payroll_slip.business_grade == "M0"
        # business_progressive_salary = 5007600 - 3000000 - 2007600 = 0
        assert payroll_slip.business_progressive_salary == Decimal("0")

    def test_business_progressive_salary_included_in_total_position_income(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that business progressive salary is included in total position income."""
        # Arrange
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M1",
                    "amount": 30000000,
                    "criteria": [
                        {"name": "revenue", "min": 100000000},
                        {"name": "transaction_count", "min": 5},
                    ],
                },
            ],
        }
        salary_period.save()

        contract.base_salary = Decimal("10000000")
        contract.kpi_salary = Decimal("5000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.other_allowance = Decimal("500000")
        contract.save()

        # Create sales data that meets M1 criteria
        from apps.payroll.models import SalesRevenue

        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=125000000,
            transaction_count=5,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # business_progressive_salary = 30000000 - 10000000 - 5000000 = 15000000
        expected_progressive = Decimal("15000000")
        assert payroll_slip.business_progressive_salary == expected_progressive

        # total_position_income = base + kpi + allowances + kpi_bonus + business_progressive
        expected_total = (
            Decimal("10000000")  # base_salary
            + Decimal("5000000")  # kpi_salary
            + Decimal("1000000")  # lunch_allowance
            + Decimal("500000")  # phone_allowance
            + Decimal("500000")  # other_allowance
            + payroll_slip.kpi_bonus  # from KPI assessment (if any)
            + Decimal("15000000")  # business_progressive_salary
        )
        assert payroll_slip.total_position_income == expected_total

    def test_business_progressive_salary_with_different_base_kpi_values(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test calculation with various base_salary and kpi_salary combinations."""
        # Arrange
        salary_period.salary_config_snapshot["business_progressive_salary"] = {
            "apply_on": "base_salary",
            "tiers": [
                {
                    "code": "M1",
                    "amount": 20000000,
                    "criteria": [
                        {"name": "revenue", "min": 100000000},
                        {"name": "transaction_count", "min": 5},
                    ],
                },
            ],
        }
        salary_period.save()

        # Different salary structures
        test_cases = [
            # (base_salary, kpi_salary, expected_progressive)
            (Decimal("8000000"), Decimal("3000000"), Decimal("9000000")),  # 20M - 8M - 3M
            (Decimal("10000000"), Decimal("5000000"), Decimal("5000000")),  # 20M - 10M - 5M
            (Decimal("12000000"), Decimal("8000000"), Decimal("0")),  # 20M - 12M - 8M = 0 (floor)
            (Decimal("5000000"), Decimal("2000000"), Decimal("13000000")),  # 20M - 5M - 2M
        ]

        from apps.payroll.models import SalesRevenue

        # Create sales data that meets M1 criteria
        SalesRevenue.objects.create(
            employee=employee,
            month=salary_period.month,
            revenue=125000000,
            transaction_count=5,
        )

        for base, kpi, expected in test_cases:
            # Update contract
            contract.base_salary = base
            contract.kpi_salary = kpi
            contract.save()

            # Recalculate
            payroll_slip.refresh_from_db()
            calculator = PayrollCalculationService(payroll_slip)
            calculator.calculate()

            # Assert
            payroll_slip.refresh_from_db()
            assert payroll_slip.business_progressive_salary == expected, (
                f"Failed for base={base}, kpi={kpi}: expected {expected}, got {payroll_slip.business_progressive_salary}"
            )
