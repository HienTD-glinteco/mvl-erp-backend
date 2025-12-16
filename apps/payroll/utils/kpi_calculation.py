"""Business logic utilities for KPI assessment calculations.

This module provides functions for:
- Grade resolution with ambiguous handling
- Unit control validation
- Department auto-assignment algorithms
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


def calculate_grade_from_percent(  # noqa: C901
    percent: Decimal,
    grade_thresholds: List[Dict[str, Any]],
    ambiguous_assignment: str = "manual",
) -> Tuple[Optional[str], List[str]]:
    """Calculate grade from percentage using grade thresholds.

    Args:
        percent: Total percentage achieved
        grade_thresholds: List of threshold dicts with min, max, possible_codes, default_code
        ambiguous_assignment: Policy for ambiguous ranges (manual/auto_prefer_default/auto_prefer_highest/auto_prefer_first)

    Returns:
        Tuple of (assigned_grade, possible_codes)

    Example:
        >>> calculate_grade_from_percent(
        ...     Decimal("85"),
        ...     [{"min": 70, "max": 90, "possible_codes": ["B", "C"], "default_code": "B"}],
        ...     "manual"
        ... )
        ("B", ["B", "C"])
    """
    if percent is None:
        return (None, [])

    # Find matching threshold
    matching_threshold = None
    for threshold in grade_thresholds:
        min_val = Decimal(str(threshold.get("min", 0)))
        max_val = Decimal(str(threshold.get("max", 110)))
        if min_val <= percent < max_val:
            matching_threshold = threshold
            break

    if not matching_threshold:
        return (None, [])

    possible_codes = matching_threshold.get("possible_codes", [])
    default_code = matching_threshold.get("default_code")

    # If single code, no ambiguity
    if len(possible_codes) == 1:
        return (possible_codes[0], possible_codes)

    # Multiple possible codes - handle based on policy
    if len(possible_codes) > 1:
        if ambiguous_assignment == "manual":
            return (default_code, possible_codes)
        elif ambiguous_assignment == "auto_prefer_default":
            return (default_code if default_code else possible_codes[0], possible_codes)
        elif ambiguous_assignment == "auto_prefer_highest":
            # Rank: A > B > C > D
            grade_rank = {"A": 0, "B": 1, "C": 2, "D": 3}
            sorted_codes = sorted(possible_codes, key=lambda x: grade_rank.get(x, 99))
            return (sorted_codes[0], possible_codes)
        elif ambiguous_assignment == "auto_prefer_first":
            return (possible_codes[0], possible_codes)

    return (None, possible_codes)


def validate_unit_control(
    department_unit_type: str,
    grade_counts: Dict[str, int],
    total_employees: int,
    unit_control: Dict[str, Dict[str, Optional[float]]],
) -> Tuple[bool, List[str]]:
    """Validate grade distribution against unit control rules.

    Args:
        department_unit_type: Type of unit (A/B/C/D) for the department
        grade_counts: Dict mapping grade (A/B/C/D) to count
        total_employees: Total number of employees considered
        unit_control: Unit control rules dict

    Returns:
        Tuple of (is_valid, list of violation messages)

    Example:
        >>> validate_unit_control(
        ...     "A",
        ...     {"A": 3, "B": 5, "C": 2, "D": 0},
        ...     10,
        ...     {"A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None}}
        ... )
        (False, ["Grade A exceeds maximum: 30.00% > 20.00%"])
    """
    if total_employees == 0:
        return (True, [])

    rules = unit_control.get(department_unit_type)
    if not rules:
        return (True, [])

    violations = []

    # Check max percentages
    for grade in ["A", "B", "C"]:
        max_key = f"max_pct_{grade}"
        max_pct = rules.get(max_key)
        if max_pct is not None:
            count = grade_counts.get(grade, 0)
            actual_pct = count / total_employees
            if actual_pct > max_pct:
                violations.append(f"Grade {grade} exceeds maximum: {actual_pct * 100:.2f}% > {max_pct * 100:.2f}%")

    # Check min percentage for D
    min_pct_d = rules.get("min_pct_D")
    if min_pct_d is not None:
        count_d = grade_counts.get("D", 0)
        actual_pct_d = count_d / total_employees
        if actual_pct_d < min_pct_d:
            violations.append(f"Grade D below minimum: {actual_pct_d * 100:.2f}% < {min_pct_d * 100:.2f}%")

    return (len(violations) == 0, violations)


def allocate_grades_by_quota(  # noqa: C901
    employees_data: List[Dict[str, Any]],
    department_unit_type: str,
    unit_control: Dict[str, Dict[str, Optional[float]]],
) -> Tuple[Dict[int, str], List[str]]:
    """Allocate grades to employees based on quota and ranking.

    This implements the department auto-assignment algorithm:
    1. Calculate quotas from unit_control
    2. Rank employees by total_manager_percent (descending)
    3. Assign grades: top N_A get A, next N_B get B, etc.
    4. Respect manager overrides (don't reassign if grade_manager_overridden is set)

    Args:
        employees_data: List of dicts with keys: employee_id, total_manager_percent, grade_manager_overridden
        department_unit_type: Unit type (A/B/C/D)
        unit_control: Unit control rules

    Returns:
        Tuple of (assignment_dict {employee_id: grade}, list of warnings/violations)

    Example:
        >>> allocate_grades_by_quota(
        ...     [
        ...         {"employee_id": 1, "total_manager_percent": Decimal("95"), "grade_manager_overridden": None},
        ...         {"employee_id": 2, "total_manager_percent": Decimal("85"), "grade_manager_overridden": None},
        ...     ],
        ...     "A",
        ...     {"A": {"max_pct_A": 0.50, "max_pct_B": 0.50, "max_pct_C": 0.0, "min_pct_D": None}}
        ... )
        ({1: 'A', 2: 'B'}, [])
    """
    if not employees_data:
        return ({}, [])

    rules = unit_control.get(department_unit_type)
    if not rules:
        return ({}, ["No unit control rules found for unit type"])

    # Separate overridden and non-overridden employees
    overridden = [e for e in employees_data if e.get("grade_manager_overridden")]
    non_overridden = [e for e in employees_data if not e.get("grade_manager_overridden")]

    # Sort non-overridden by total_manager_percent descending
    # Use employee_id as tiebreaker for deterministic results
    non_overridden.sort(
        key=lambda x: (x.get("total_manager_percent") or Decimal("-999"), -x.get("employee_id", 0)), reverse=True
    )

    N = len(non_overridden)
    if N == 0:
        # All are overridden, nothing to assign
        return ({}, [])

    # Calculate quotas
    import math

    max_a = math.floor((rules.get("max_pct_A") or 0) * N)
    max_b = math.floor((rules.get("max_pct_B") or 0) * N)
    max_c = math.floor((rules.get("max_pct_C") or 0) * N)
    min_d_pct = rules.get("min_pct_D")
    min_d = math.ceil(min_d_pct * N) if min_d_pct is not None else 0

    # Assign grades
    assignments = {}
    warnings = []
    idx = 0

    # Assign A
    for i in range(min(max_a, N)):
        if idx < len(non_overridden):
            assignments[non_overridden[idx]["employee_id"]] = "A"
            idx += 1

    # Assign B
    for i in range(min(max_b, N - idx)):
        if idx < len(non_overridden):
            assignments[non_overridden[idx]["employee_id"]] = "B"
            idx += 1

    # Assign C
    for i in range(min(max_c, N - idx)):
        if idx < len(non_overridden):
            assignments[non_overridden[idx]["employee_id"]] = "C"
            idx += 1

    # Remaining get D
    while idx < len(non_overridden):
        assignments[non_overridden[idx]["employee_id"]] = "D"
        idx += 1

    # Check if min_d is satisfied
    count_d = sum(1 for g in assignments.values() if g == "D")
    if count_d < min_d:
        # Need to convert some C to D
        needed = min_d - count_d
        # Find employees with C from bottom
        c_employees = [emp_id for emp_id, grade in assignments.items() if grade == "C"]
        # Sort by original order (lowest performing first)
        c_employees_sorted = []
        for emp in non_overridden:
            if emp["employee_id"] in c_employees:
                c_employees_sorted.append(emp["employee_id"])
        c_employees_sorted.reverse()  # Start from lowest

        converted = 0
        for emp_id in c_employees_sorted:
            if converted < needed:
                assignments[emp_id] = "D"
                converted += 1

        if converted < needed:
            warnings.append(f"Could not satisfy min_pct_D requirement: needed {min_d}, got {count_d + converted}")

    return (assignments, warnings)
