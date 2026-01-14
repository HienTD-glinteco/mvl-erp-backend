"""Tests for libs.decimals module."""

from decimal import Decimal

import pytest

from libs.decimals import round_currency


class TestRoundCurrency:
    """Test round_currency function for Excel-compatible rounding."""

    def test_round_half_up_whole_number(self):
        """Test that 0.5 rounds up (Excel behavior)."""
        assert round_currency(Decimal("1234.5")) == Decimal("1235")
        assert round_currency(Decimal("1235.5")) == Decimal("1236")
        assert round_currency(Decimal("5000000.5")) == Decimal("5000001")

    def test_round_down_less_than_half(self):
        """Test that values < 0.5 round down."""
        assert round_currency(Decimal("1234.4")) == Decimal("1234")
        assert round_currency(Decimal("1234.1")) == Decimal("1234")
        assert round_currency(Decimal("5000000.49")) == Decimal("5000000")

    def test_round_up_more_than_half(self):
        """Test that values > 0.5 round up."""
        assert round_currency(Decimal("1234.6")) == Decimal("1235")
        assert round_currency(Decimal("1234.9")) == Decimal("1235")
        assert round_currency(Decimal("5000000.51")) == Decimal("5000001")

    def test_round_complex_decimals(self):
        """Test rounding with multiple decimal places."""
        assert round_currency(Decimal("1234.567")) == Decimal("1235")
        assert round_currency(Decimal("1234.123")) == Decimal("1234")
        assert round_currency(Decimal("9999.999")) == Decimal("10000")

    def test_round_negative_numbers(self):
        """Test rounding negative numbers."""
        assert round_currency(Decimal("-1234.5")) == Decimal("-1235")
        assert round_currency(Decimal("-1234.4")) == Decimal("-1234")
        assert round_currency(Decimal("-1234.6")) == Decimal("-1235")

    def test_round_zero_and_small_numbers(self):
        """Test rounding zero and small numbers."""
        assert round_currency(Decimal("0")) == Decimal("0")
        assert round_currency(Decimal("0.5")) == Decimal("1")
        assert round_currency(Decimal("0.4")) == Decimal("0")
        assert round_currency(Decimal("0.9")) == Decimal("1")

    def test_round_large_numbers(self):
        """Test rounding large salary amounts."""
        assert round_currency(Decimal("50000000.5")) == Decimal("50000001")
        assert round_currency(Decimal("100000000.49")) == Decimal("100000000")
        assert round_currency(Decimal("999999999.99")) == Decimal("1000000000")

    def test_round_with_two_decimal_places(self):
        """Test rounding with 2 decimal places (for hourly rate)."""
        assert round_currency(Decimal("123.456"), 2) == Decimal("123.46")
        assert round_currency(Decimal("123.454"), 2) == Decimal("123.45")
        assert round_currency(Decimal("123.455"), 2) == Decimal("123.46")

    def test_round_with_four_decimal_places(self):
        """Test rounding with 4 decimal places (for KPI percentage)."""
        assert round_currency(Decimal("0.12345"), 4) == Decimal("0.1235")
        assert round_currency(Decimal("0.12344"), 4) == Decimal("0.1234")
        assert round_currency(Decimal("0.12346"), 4) == Decimal("0.1235")

    def test_round_preserves_type(self):
        """Test that result is always Decimal type."""
        result = round_currency(Decimal("1234.5"))
        assert isinstance(result, Decimal)

    def test_round_payroll_examples(self):
        """Test realistic payroll calculation scenarios."""
        # KPI bonus: base_salary * kpi_percentage
        kpi_bonus = Decimal("10000000") * Decimal("0.125")  # 1,250,000
        assert round_currency(kpi_bonus) == Decimal("1250000")

        # Insurance: base_salary * rate
        insurance = Decimal("20000000") * Decimal("0.08")  # 1,600,000
        assert round_currency(insurance) == Decimal("1600000")

        # Tax calculation example
        tax = Decimal("5000000") * Decimal("0.10")  # 500,000
        assert round_currency(tax) == Decimal("500000")

    def test_round_division_results(self):
        """Test rounding results from division operations."""
        # Actual working days income calculation
        total_income = Decimal("15000000")
        standard_days = Decimal("22")
        working_days = Decimal("20")

        result = (working_days / standard_days) * total_income
        assert round_currency(result) == Decimal("13636364")

    def test_round_hourly_rate_calculation(self):
        """Test hourly rate calculation with 2 decimal places."""
        total_position_income = Decimal("15000000")
        standard_working_days = Decimal("22")
        hours_per_day = Decimal("8")

        hourly_rate = total_position_income / (standard_working_days * hours_per_day)
        assert round_currency(hourly_rate, 2) == Decimal("85227.27")

    def test_round_overtime_calculation(self):
        """Test overtime pay calculation."""
        hourly_rate = Decimal("85227.27")
        overtime_hours = Decimal("10.5")
        overtime_multiplier = Decimal("1.5")

        overtime_pay = hourly_rate * overtime_hours * overtime_multiplier
        # 85227.27 * 10.5 * 1.5 = 1342329.5025 -> rounds to 1342330
        assert round_currency(overtime_pay) == Decimal("1342330")

    def test_round_progressive_tax_bracket(self):
        """Test progressive tax calculation rounding."""
        taxable_income = Decimal("18000000")
        bracket_threshold = Decimal("5000000")
        tax_rate = Decimal("0.10")

        tax = (taxable_income - bracket_threshold) * tax_rate
        assert round_currency(tax) == Decimal("1300000")

    def test_round_chain_calculations(self):
        """Test that rounding at each step produces consistent results."""
        # Simulate multi-step calculation
        step1 = Decimal("10000000") * Decimal("0.125")
        rounded_step1 = round_currency(step1)

        step2 = rounded_step1 + Decimal("5000000.5")
        rounded_step2 = round_currency(step2)

        step3 = rounded_step2 * Decimal("0.08")
        final_result = round_currency(step3)

        assert rounded_step1 == Decimal("1250000")
        assert rounded_step2 == Decimal("6250001")
        assert final_result == Decimal("500000")

    @pytest.mark.parametrize(
        "value,expected",
        [
            (Decimal("0.5"), Decimal("1")),
            (Decimal("1.5"), Decimal("2")),
            (Decimal("2.5"), Decimal("3")),
            (Decimal("3.5"), Decimal("4")),
            (Decimal("4.5"), Decimal("5")),
        ],
    )
    def test_round_half_up_pattern(self, value, expected):
        """Test that all .5 values consistently round up."""
        assert round_currency(value) == expected

    @pytest.mark.parametrize(
        "decimal_places,value,expected",
        [
            (0, Decimal("1234.567"), Decimal("1235")),
            (1, Decimal("1234.567"), Decimal("1234.6")),
            (2, Decimal("1234.567"), Decimal("1234.57")),
            (3, Decimal("1234.567"), Decimal("1234.567")),
            (4, Decimal("1234.567"), Decimal("1234.5670")),
        ],
    )
    def test_round_various_decimal_places(self, decimal_places, value, expected):
        """Test rounding with various decimal place settings."""
        assert round_currency(value, decimal_places) == expected

    def test_excel_compatibility_examples(self):
        """Test examples that would differ from ROUND_HALF_EVEN."""
        # These would round differently with banker's rounding
        test_cases = [
            (Decimal("0.5"), Decimal("1")),  # banker's: 0
            (Decimal("1.5"), Decimal("2")),  # banker's: 2 (same)
            (Decimal("2.5"), Decimal("3")),  # banker's: 2
            (Decimal("3.5"), Decimal("4")),  # banker's: 4 (same)
            (Decimal("4.5"), Decimal("5")),  # banker's: 4
            (Decimal("5.5"), Decimal("6")),  # banker's: 6 (same)
        ]

        for value, expected in test_cases:
            assert round_currency(value) == expected
