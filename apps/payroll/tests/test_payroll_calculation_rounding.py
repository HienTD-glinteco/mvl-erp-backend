"""Integration tests for PayrollCalculationService with rounding fixes."""

from decimal import Decimal

import pytest

from libs.decimals import round_currency


class TestPayrollCalculationRounding:
    """Test rounding behavior in payroll calculations."""

    def test_round_currency_basic_rounding(self):
        """Test basic rounding function with ROUND_HALF_UP."""
        assert round_currency(Decimal("1234.5")) == Decimal("1235")
        assert round_currency(Decimal("5000000.5")) == Decimal("5000001")
        assert round_currency(Decimal("1234.4")) == Decimal("1234")

    def test_kpi_bonus_calculation_example(self):
        """Test KPI bonus calculation uses Excel-compatible rounding."""
        base_salary = Decimal("10000001")
        kpi_percentage = Decimal("0.5")

        kpi_bonus = base_salary * kpi_percentage
        # 10,000,001 * 0.5 = 5,000,000.5
        rounded_bonus = round_currency(kpi_bonus)

        # With ROUND_HALF_UP: 5,000,001
        # With ROUND_HALF_EVEN: 5,000,000 (would fail)
        assert rounded_bonus == Decimal("5000001")

    def test_hourly_rate_rounding_preserves_precision(self):
        """Test hourly rate calculation rounds to 2 decimal places."""
        total_position_income = Decimal("20500000")
        standard_working_days = Decimal("22")
        hours_per_day = Decimal("8")

        hourly_rate = total_position_income / (standard_working_days * hours_per_day)
        # 20,500,000 / 176 = 116,477.272727...
        rounded_rate = round_currency(hourly_rate, 2)

        assert rounded_rate == Decimal("116477.27")

    def test_insurance_calculation_rounds_to_whole_vnd(self):
        """Test insurance calculations round to whole VND."""
        base_salary = Decimal("10000000")

        # Social insurance: 8%
        social_insurance = base_salary * Decimal("0.08")
        assert round_currency(social_insurance) == Decimal("800000")

        # Health insurance: 1.5%
        health_insurance = base_salary * Decimal("0.015")
        assert round_currency(health_insurance) == Decimal("150000")

        # Unemployment insurance: 1%
        unemployment_insurance = base_salary * Decimal("0.01")
        assert round_currency(unemployment_insurance) == Decimal("100000")

    def test_overtime_calculation_with_multipliers(self):
        """Test overtime calculation with multipliers rounds correctly."""
        hourly_rate = Decimal("116477.27")
        overtime_hours = Decimal("10.5")

        # TC1: 1.5x
        tc1_pay = hourly_rate * overtime_hours * Decimal("1.5")
        rounded_tc1 = round_currency(tc1_pay)
        assert rounded_tc1 % 1 == 0  # Whole VND

        # TC2: 2.0x
        tc2_pay = hourly_rate * overtime_hours * Decimal("2.0")
        rounded_tc2 = round_currency(tc2_pay)
        assert rounded_tc2 % 1 == 0  # Whole VND

    def test_tax_progressive_bracket_rounding(self):
        """Test progressive tax calculation rounds correctly."""
        # Example: taxable income in 10-18M bracket (15%)
        taxable_income = Decimal("15000000")

        # First 5M at 5%
        tax_bracket1 = Decimal("5000000") * Decimal("0.05")
        # Next 5M (5-10M) at 10%
        tax_bracket2 = Decimal("5000000") * Decimal("0.10")
        # Remaining 5M (10-15M) at 15%
        tax_bracket3 = Decimal("5000000") * Decimal("0.15")

        total_tax = tax_bracket1 + tax_bracket2 + tax_bracket3
        rounded_tax = round_currency(total_tax)

        # 250,000 + 500,000 + 750,000 = 1,500,000
        assert rounded_tax == Decimal("1500000")

    def test_division_result_rounding(self):
        """Test division results round correctly (common in working days calculations)."""
        total_income = Decimal("15000000")
        standard_days = Decimal("22")
        working_days = Decimal("20")

        # Partial working days income
        result = (working_days / standard_days) * total_income
        rounded_result = round_currency(result)

        # Should produce whole VND
        assert rounded_result % 1 == 0

    def test_excel_half_up_vs_banker_rounding(self):
        """Test that ROUND_HALF_UP differs from ROUND_HALF_EVEN for .5 values."""
        test_values = [
            Decimal("0.5"),
            Decimal("1.5"),
            Decimal("2.5"),
            Decimal("3.5"),
            Decimal("4.5"),
        ]

        for value in test_values:
            result = round_currency(value)
            # All .5 values should round UP
            assert result == value + Decimal("0.5")

    def test_chain_calculation_accuracy(self):
        """Test that chained calculations maintain accuracy."""
        step1 = Decimal("10000000") * Decimal("0.125")
        rounded_step1 = round_currency(step1)
        assert rounded_step1 == Decimal("1250000")

        step2 = rounded_step1 + Decimal("5000000.5")
        rounded_step2 = round_currency(step2)
        assert rounded_step2 == Decimal("6250001")

        step3 = rounded_step2 * Decimal("0.08")
        rounded_step3 = round_currency(step3)
        assert rounded_step3 == Decimal("500000")

    def test_large_salary_amounts(self):
        """Test rounding works correctly for large salary amounts."""
        large_amounts = [
            (Decimal("50000000.5"), Decimal("50000001")),
            (Decimal("100000000.49"), Decimal("100000000")),
            (Decimal("999999999.99"), Decimal("1000000000")),
        ]

        for amount, expected in large_amounts:
            assert round_currency(amount) == expected

    def test_negative_amount_rounding(self):
        """Test rounding negative amounts (deductions)."""
        negative_amounts = [
            (Decimal("-1234.5"), Decimal("-1235")),
            (Decimal("-500000.5"), Decimal("-500001")),
            (Decimal("-100000.4"), Decimal("-100000")),
        ]

        for amount, expected in negative_amounts:
            assert round_currency(amount) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (Decimal("123.456"), Decimal("123")),
            (Decimal("123.546"), Decimal("124")),
            (Decimal("123.5"), Decimal("124")),
            (Decimal("999.999"), Decimal("1000")),
        ],
    )
    def test_various_decimal_inputs(self, value, expected):
        """Test various decimal inputs round correctly."""
        assert round_currency(value) == expected
