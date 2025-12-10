import pytest

from apps.payroll.utils.kpi_helpers import (
    calc_grade_from_percent,
    validate_kpi_config_structure,
    validate_unit_distribution,
)


class TestCalcGradeFromPercent:
    """Test cases for calc_grade_from_percent function"""

    def setup_method(self):
        """Set up test data"""
        self.config = {
            "name": "Test Config",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {
                    "min": 60,
                    "max": 70,
                    "possible_codes": ["C", "D"],
                    "default_code": "C",
                    "label": "Average or Poor",
                },
                {
                    "min": 70,
                    "max": 90,
                    "possible_codes": ["B", "C"],
                    "default_code": "B",
                    "label": "Good or Average",
                },
                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
            ],
            "unit_control": {},
        }

    def test_single_grade_low_percent(self):
        """TC-1: percent 59.9 -> match range 0-60 -> possible_codes ['D'] -> grade 'D'"""
        result = calc_grade_from_percent(self.config, 59.9)
        assert result["grade"] == "D"
        assert result["ambiguous"] is False

    def test_ambiguous_manual_policy(self):
        """TC-2: percent 60 -> match 60-70 -> possible_codes ['C','D']; ambiguous_assignment='manual'"""
        result = calc_grade_from_percent(self.config, 60)
        assert result["ambiguous"] is True
        assert set(result["possible_codes"]) == {"C", "D"}
        assert result["suggested"] == "C"

    def test_ambiguous_auto_prefer_highest(self):
        """TC-3: percent 60, ambiguous_assignment='auto_prefer_highest' -> choose 'C' (C tốt hơn D)"""
        config = self.config.copy()
        config["ambiguous_assignment"] = "auto_prefer_highest"
        result = calc_grade_from_percent(config, 60)
        assert result["grade"] == "C"
        assert result["ambiguous"] is False

    def test_ambiguous_auto_prefer_default(self):
        """Test auto_prefer_default policy uses default_code"""
        config = self.config.copy()
        config["ambiguous_assignment"] = "auto_prefer_default"
        result = calc_grade_from_percent(config, 60)
        assert result["grade"] == "C"
        assert result["ambiguous"] is False

    def test_ambiguous_auto_prefer_first(self):
        """Test auto_prefer_first policy uses first in possible_codes"""
        config = self.config.copy()
        config["ambiguous_assignment"] = "auto_prefer_first"
        result = calc_grade_from_percent(config, 60)
        assert result["grade"] == "C"
        assert result["ambiguous"] is False

    def test_single_grade_high_percent(self):
        """Test high percent gets grade A"""
        result = calc_grade_from_percent(self.config, 95)
        assert result["grade"] == "A"
        assert result["ambiguous"] is False

    def test_no_match(self):
        """Test percent outside all ranges returns None"""
        result = calc_grade_from_percent(self.config, 120)
        assert result["grade"] is None
        assert result["ambiguous"] is False

    def test_edge_case_min_inclusive(self):
        """Test that min is inclusive"""
        result = calc_grade_from_percent(self.config, 0)
        assert result["grade"] == "D"

    def test_edge_case_max_exclusive(self):
        """Test that max is exclusive"""
        result = calc_grade_from_percent(self.config, 60)
        # Should match 60-70 range, not 0-60
        assert result["ambiguous"] is True
        assert "C" in result["possible_codes"]


class TestValidateUnitDistribution:
    """Test cases for validate_unit_distribution function"""

    def setup_method(self):
        """Set up test data"""
        self.config = {
            "unit_control": {
                "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None},
                "B": {"max_pct_A": 0.10, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": 0.10},
                "C": {"max_pct_A": 0.05, "max_pct_B": 0.20, "max_pct_C": 0.60, "min_pct_D": 0.15},
                "D": {"max_pct_A": 0.05, "max_pct_B": 0.10, "max_pct_C": 0.65, "min_pct_D": 0.20},
            }
        }

    def test_valid_distribution(self):
        """Test valid distribution passes with no violations"""
        counts = {"A": 2, "B": 3, "C": 4, "D": 1}  # Total: 10, A=20%, B=30%, C=40%, D=10%
        violations = validate_unit_distribution(self.config, "A", counts)
        assert len(violations) == 0

    def test_violation_max_pct_a(self):
        """TC-4: unit_type A, N=10, actual A_count=3 -> pct_A=0.3 -> violates max_pct_A=0.20"""
        counts = {"A": 3, "B": 3, "C": 3, "D": 1}  # Total: 10, A=30%
        violations = validate_unit_distribution(self.config, "A", counts)
        assert len(violations) == 1
        assert violations[0]["grade"] == "A"
        assert violations[0]["limit_type"] == "max_pct_A"
        assert violations[0]["actual_value"] == 0.3

    def test_violation_min_pct_d(self):
        """Test violation when min_pct_D is not met"""
        counts = {"A": 0, "B": 5, "C": 8, "D": 1}  # Total: 14, D=7% < 10% required, B=36% > 30%, C=57% > 50%
        violations = validate_unit_distribution(self.config, "B", counts)
        # Check that D violation is detected
        d_violations = [v for v in violations if v["grade"] == "D"]
        assert len(d_violations) == 1
        assert d_violations[0]["limit_type"] == "min_pct_D"

    def test_multiple_violations(self):
        """Test multiple violations detected"""
        counts = {"A": 3, "B": 7, "C": 0, "D": 0}  # Total: 10, A=30%, B=70%
        violations = validate_unit_distribution(self.config, "A", counts)
        assert len(violations) >= 2  # A exceeds, B exceeds

    def test_no_control_for_unit_type(self):
        """Test no violations when unit type not in control"""
        counts = {"A": 10, "B": 0, "C": 0, "D": 0}
        violations = validate_unit_distribution(self.config, "Z", counts)
        assert len(violations) == 0

    def test_empty_counts(self):
        """Test empty counts returns no violations"""
        counts = {}
        violations = validate_unit_distribution(self.config, "A", counts)
        assert len(violations) == 0

    def test_min_pct_d_null(self):
        """Test that min_pct_D=null is not validated"""
        counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        violations = validate_unit_distribution(self.config, "A", counts)
        # No violation for D since min_pct_D is None for unit type A
        assert all(v["grade"] != "D" for v in violations)


class TestValidateKPIConfigStructure:
    """Test cases for validate_kpi_config_structure function"""

    def test_valid_config(self):
        """Test that valid config returns no errors"""
        config = {
            "name": "Test Config",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"]},
                {"min": 60, "max": 90, "possible_codes": ["C"]},
            ],
            "unit_control": {
                "A": {"max_pct_A": 0.2, "max_pct_B": 0.3, "max_pct_C": 0.5, "min_pct_D": 0.1}
            },
        }
        errors = validate_kpi_config_structure(config)
        assert len(errors) == 0

    def test_missing_name(self):
        """Test error when name is missing"""
        config = {
            "ambiguous_assignment": "manual",
            "grade_thresholds": [],
            "unit_control": {},
        }
        errors = validate_kpi_config_structure(config)
        assert any("name" in err.lower() for err in errors)

    def test_invalid_ambiguous_assignment(self):
        """Test error for invalid ambiguous_assignment value"""
        config = {
            "name": "Test",
            "ambiguous_assignment": "invalid_policy",
            "grade_thresholds": [],
            "unit_control": {},
        }
        errors = validate_kpi_config_structure(config)
        assert any("ambiguous_assignment" in err for err in errors)

    def test_default_code_not_in_possible_codes(self):
        """TC-5: default_code không thuộc possible_codes -> validation fail"""
        config = {
            "name": "Test",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "default_code": "C"}  # Invalid!
            ],
            "unit_control": {},
        }
        errors = validate_kpi_config_structure(config)
        assert any("default_code" in err for err in errors)

    def test_min_greater_than_max(self):
        """Test error when min >= max"""
        config = {
            "name": "Test",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 60, "max": 60, "possible_codes": ["D"]}  # min == max, invalid
            ],
            "unit_control": {},
        }
        errors = validate_kpi_config_structure(config)
        assert any("min" in err and "max" in err for err in errors)

    def test_empty_possible_codes(self):
        """Test error when possible_codes is empty"""
        config = {
            "name": "Test",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [{"min": 0, "max": 60, "possible_codes": []}],
            "unit_control": {},
        }
        errors = validate_kpi_config_structure(config)
        assert any("possible_codes" in err and "non-empty" in err for err in errors)

    def test_invalid_percentage_value(self):
        """Test error when percentage values are out of range"""
        config = {
            "name": "Test",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [{"min": 0, "max": 60, "possible_codes": ["D"]}],
            "unit_control": {
                "A": {"max_pct_A": 1.5, "max_pct_B": 0.3, "max_pct_C": 0.5}  # 1.5 > 1, invalid
            },
        }
        errors = validate_kpi_config_structure(config)
        assert any("max_pct_A" in err for err in errors)
