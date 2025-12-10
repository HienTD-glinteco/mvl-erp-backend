"""Helper functions for KPI configuration and grade calculations."""

from typing import Any


def calc_grade_from_percent(config_json: dict[str, Any], percent: float) -> dict[str, Any]:
    """Calculate grade from KPI percentage based on configuration.

    Args:
        config_json: The KPI configuration JSON
        percent: The KPI percentage value

    Returns:
        Dictionary with grade resolution result:
        - If single grade: {"grade": "A", "ambiguous": False}
        - If ambiguous: {"ambiguous": True, "possible_codes": ["B", "C"], "suggested": "B" or None}
        - If no match: {"grade": None, "ambiguous": False}

    The function follows these rules:
    1. Find first threshold where min <= percent < max
    2. If no match found, return None
    3. If single possible_code, return that grade
    4. If multiple possible_codes, apply ambiguous_assignment policy:
       - "manual": return ambiguous result with possible_codes
       - "auto_prefer_default": use default_code if available, else first
       - "auto_prefer_highest": choose best grade (A > B > C > D)
       - "auto_prefer_first": use first in possible_codes list
    """
    grade_thresholds = config_json.get("grade_thresholds", [])
    ambiguous_assignment = config_json.get("ambiguous_assignment", "manual")

    # Find matching threshold
    matched_threshold = None
    for threshold in grade_thresholds:
        min_val = threshold.get("min", 0)
        max_val = threshold.get("max", float("inf"))
        if min_val <= percent < max_val:
            matched_threshold = threshold
            break

    # No match found
    if not matched_threshold:
        return {"grade": None, "ambiguous": False}

    possible_codes = matched_threshold.get("possible_codes", [])

    # Single grade - no ambiguity
    if len(possible_codes) == 1:
        return {"grade": possible_codes[0], "ambiguous": False}

    # Multiple possible grades - handle based on policy
    default_code = matched_threshold.get("default_code")

    if ambiguous_assignment == "manual":
        return {
            "ambiguous": True,
            "possible_codes": possible_codes,
            "suggested": default_code if default_code in possible_codes else None,
        }

    if ambiguous_assignment == "auto_prefer_default":
        if default_code and default_code in possible_codes:
            return {"grade": default_code, "ambiguous": False}
        # Fallback to first
        return {"grade": possible_codes[0], "ambiguous": False}

    if ambiguous_assignment == "auto_prefer_highest":
        # A > B > C > D
        grade_priority = {"A": 4, "B": 3, "C": 2, "D": 1}
        best_grade = max(possible_codes, key=lambda g: grade_priority.get(g, 0))
        return {"grade": best_grade, "ambiguous": False}

    if ambiguous_assignment == "auto_prefer_first":
        return {"grade": possible_codes[0], "ambiguous": False}

    # Default fallback
    return {"grade": possible_codes[0], "ambiguous": False}


def validate_unit_distribution(  # noqa: C901
    config_json: dict[str, Any], unit_type: str, counts_per_grade: dict[str, int]
) -> list[dict[str, Any]]:
    """Validate grade distribution for a unit against configured limits.

    Args:
        config_json: The KPI configuration JSON
        unit_type: The unit type (e.g., 'A', 'B', 'C', 'D')
        counts_per_grade: Dictionary with grade counts, e.g., {'A': 2, 'B': 3, 'C': 4, 'D': 1}

    Returns:
        List of violations. Each violation is a dict:
        {
            "grade": "A",
            "limit_type": "max_pct_A",
            "limit_value": 0.20,
            "actual_value": 0.30,
            "message": "Grade A exceeds maximum allowed percentage (30.0% > 20.0%)"
        }
        Empty list if no violations.
    """
    unit_control = config_json.get("unit_control", {})

    if unit_type not in unit_control:
        # No control defined for this unit type
        return []

    control = unit_control[unit_type]

    # Calculate total count
    total = sum(counts_per_grade.values())
    if total == 0:
        return []

    violations = []

    # Check max_pct_A
    max_pct_a = control.get("max_pct_A")
    if max_pct_a is not None:
        actual_a = counts_per_grade.get("A", 0)
        actual_pct_a = actual_a / total
        if actual_pct_a > max_pct_a:
            violations.append(
                {
                    "grade": "A",
                    "limit_type": "max_pct_A",
                    "limit_value": max_pct_a,
                    "actual_value": actual_pct_a,
                    "message": f"Grade A exceeds maximum allowed percentage ({actual_pct_a:.1%} > {max_pct_a:.1%})",
                }
            )

    # Check max_pct_B
    max_pct_b = control.get("max_pct_B")
    if max_pct_b is not None:
        actual_b = counts_per_grade.get("B", 0)
        actual_pct_b = actual_b / total
        if actual_pct_b > max_pct_b:
            violations.append(
                {
                    "grade": "B",
                    "limit_type": "max_pct_B",
                    "limit_value": max_pct_b,
                    "actual_value": actual_pct_b,
                    "message": f"Grade B exceeds maximum allowed percentage ({actual_pct_b:.1%} > {max_pct_b:.1%})",
                }
            )

    # Check max_pct_C
    max_pct_c = control.get("max_pct_C")
    if max_pct_c is not None:
        actual_c = counts_per_grade.get("C", 0)
        actual_pct_c = actual_c / total
        if actual_pct_c > max_pct_c:
            violations.append(
                {
                    "grade": "C",
                    "limit_type": "max_pct_C",
                    "limit_value": max_pct_c,
                    "actual_value": actual_pct_c,
                    "message": f"Grade C exceeds maximum allowed percentage ({actual_pct_c:.1%} > {max_pct_c:.1%})",
                }
            )

    # Check min_pct_D
    min_pct_d = control.get("min_pct_D")
    if min_pct_d is not None:
        actual_d = counts_per_grade.get("D", 0)
        actual_pct_d = actual_d / total
        if actual_pct_d < min_pct_d:
            violations.append(
                {
                    "grade": "D",
                    "limit_type": "min_pct_D",
                    "limit_value": min_pct_d,
                    "actual_value": actual_pct_d,
                    "message": f"Grade D below minimum required percentage ({actual_pct_d:.1%} < {min_pct_d:.1%})",
                }
            )

    return violations


def validate_kpi_config_structure(config_json: dict[str, Any]) -> list[str]:  # noqa: C901
    """Validate the structure of KPI configuration JSON.

    Args:
        config_json: The KPI configuration JSON to validate

    Returns:
        List of error messages. Empty list if valid.
    """
    errors = []

    # Check required fields
    if "name" not in config_json:
        errors.append("Missing required field: 'name'")

    if "ambiguous_assignment" not in config_json:
        errors.append("Missing required field: 'ambiguous_assignment'")
    else:
        valid_policies = ["manual", "auto_prefer_default", "auto_prefer_highest", "auto_prefer_first"]
        if config_json["ambiguous_assignment"] not in valid_policies:
            errors.append(f"Invalid ambiguous_assignment value. Must be one of: {', '.join(valid_policies)}")

    if "grade_thresholds" not in config_json:
        errors.append("Missing required field: 'grade_thresholds'")
    else:
        thresholds = config_json["grade_thresholds"]
        if not isinstance(thresholds, list):
            errors.append("'grade_thresholds' must be a list")
        else:
            for i, threshold in enumerate(thresholds):
                # Check required fields
                if "min" not in threshold:
                    errors.append(f"grade_thresholds[{i}]: missing 'min' field")
                if "max" not in threshold:
                    errors.append(f"grade_thresholds[{i}]: missing 'max' field")
                if "possible_codes" not in threshold:
                    errors.append(f"grade_thresholds[{i}]: missing 'possible_codes' field")
                else:
                    codes = threshold["possible_codes"]
                    if not isinstance(codes, list) or len(codes) == 0:
                        errors.append(f"grade_thresholds[{i}]: 'possible_codes' must be non-empty list")

                # Validate min < max
                if "min" in threshold and "max" in threshold:
                    if threshold["min"] >= threshold["max"]:
                        errors.append(
                            f"grade_thresholds[{i}]: 'min' must be less than 'max' "
                            f"({threshold['min']} >= {threshold['max']})"
                        )

                # Validate default_code
                if "default_code" in threshold:
                    default = threshold["default_code"]
                    codes = threshold.get("possible_codes", [])
                    if default not in codes:
                        errors.append(
                            f"grade_thresholds[{i}]: 'default_code' ({default}) "
                            f"must be in 'possible_codes' {codes}"
                        )

    if "unit_control" not in config_json:
        errors.append("Missing required field: 'unit_control'")
    else:
        unit_control = config_json["unit_control"]
        if not isinstance(unit_control, dict):
            errors.append("'unit_control' must be an object/dict")
        else:
            for unit_type, control in unit_control.items():
                # Validate percentage values
                for key in ["max_pct_A", "max_pct_B", "max_pct_C"]:
                    if key in control:
                        val = control[key]
                        if not isinstance(val, (int, float)) or val < 0 or val > 1:
                            errors.append(f"unit_control[{unit_type}][{key}]: must be a number between 0 and 1")

                if "min_pct_D" in control and control["min_pct_D"] is not None:
                    val = control["min_pct_D"]
                    if not isinstance(val, (int, float)) or val < 0 or val > 1:
                        errors.append(
                            f"unit_control[{unit_type}][min_pct_D]: must be a number between 0 and 1"
                        )

    return errors
