"""
Example Usage of Salary Configuration System

This script demonstrates how to use the SalaryConfig model and API
in payroll calculations.
"""

from apps.payroll.models import SalaryConfig


def get_current_config():
    """Get the current salary configuration."""
    return SalaryConfig.objects.first()


def calculate_social_insurance(base_salary):
    """Calculate social insurance contribution.

    Args:
        base_salary: Employee's base salary

    Returns:
        Tuple of (employee_contribution, employer_contribution)
    """
    config = get_current_config()
    if not config:
        raise ValueError("No salary configuration found")

    insurance = config.config["insurance_contributions"]["social_insurance"]

    # Apply salary ceiling
    taxable_salary = min(base_salary, insurance["salary_ceiling"])

    employee_contribution = taxable_salary * insurance["employee_rate"]
    employer_contribution = taxable_salary * insurance["employer_rate"]

    return employee_contribution, employer_contribution


def calculate_personal_income_tax(taxable_income):
    """Calculate personal income tax using progressive rates.

    Args:
        taxable_income: Income after deductions

    Returns:
        Tax amount
    """
    config = get_current_config()
    if not config:
        raise ValueError("No salary configuration found")

    levels = config.config["personal_income_tax"]["progressive_levels"]

    tax = 0
    previous_threshold = 0

    for level in levels:
        threshold = level["up_to"]
        rate = level["rate"]

        if threshold is None:
            # Last bracket - unlimited
            tax += (taxable_income - previous_threshold) * rate
            break
        elif taxable_income <= threshold:
            # Income falls in this bracket
            tax += (taxable_income - previous_threshold) * rate
            break
        else:
            # Income exceeds this bracket
            tax += (threshold - previous_threshold) * rate
            previous_threshold = threshold

    return tax


def apply_kpi_bonus(base_salary, kpi_grade):
    """Apply KPI grade bonus to salary.

    Args:
        base_salary: Employee's base salary
        kpi_grade: KPI grade (A, B, C, or D)

    Returns:
        Bonus amount
    """
    config = get_current_config()
    if not config:
        raise ValueError("No salary configuration found")

    kpi_config = config.config["kpi_salary"]
    tiers = kpi_config["tiers"]

    # Find the tier for the given grade
    tier = next((t for t in tiers if t["code"] == kpi_grade), None)

    if not tier:
        raise ValueError(f"Invalid KPI grade: {kpi_grade}")

    percentage = tier["percentage"]
    return base_salary * percentage


def get_business_salary_level(level_code):
    """Get business progressive salary for a specific level.

    Args:
        level_code: Level code (M0, M1, M2, M3, M4, etc.)

    Returns:
        Salary amount
    """
    config = get_current_config()
    if not config:
        raise ValueError("No salary configuration found")

    business_config = config.config["business_progressive_salary"]
    tiers = business_config["tiers"]

    # Find the tier for the given level code
    tier = next((t for t in tiers if t["code"] == level_code), None)

    if not tier:
        raise ValueError(f"Invalid level: {level_code}")

    return tier["amount"]


def check_business_commission_eligibility(employee_data, level_code):
    """Check if employee meets criteria for a specific commission level.

    Args:
        employee_data: Dict with employee performance data
        level_code: Level code to check (M0, M1, M2, etc.)

    Returns:
        Tuple of (eligible: bool, missing_criteria: list)
    """
    config = get_current_config()
    if not config:
        raise ValueError("No salary configuration found")

    business_config = config.config["business_progressive_salary"]
    tiers = business_config["tiers"]

    # Find the tier for the given level code
    tier = next((t for t in tiers if t["code"] == level_code), None)

    if not tier:
        raise ValueError(f"Invalid level: {level_code}")

    criteria = tier["criteria"]
    missing = []

    # Check each criterion
    for criterion in criteria:
        criterion_name = criterion["name"]
        min_value = criterion["min"]

        actual_value = employee_data.get(criterion_name, 0)

        if actual_value < min_value:
            missing.append(
                {
                    "name": criterion_name,
                    "required": min_value,
                    "actual": actual_value,
                }
            )

    eligible = len(missing) == 0
    return eligible, missing


# Example usage
if __name__ == "__main__":
    # Example: Calculate total compensation for an employee
    base_salary = 20000000  # 20 million VND
    kpi_grade = "A"
    number_of_dependents = 2

    # Get current config
    config = get_current_config()

    if config:
        print(f"Using Salary Config Version: {config.version}")
        print("-" * 50)

        # 1. Calculate insurance contributions
        emp_insurance, empr_insurance = calculate_social_insurance(base_salary)
        print(f"Base Salary: {base_salary:,} VND")
        print(f"Employee Insurance: {emp_insurance:,.0f} VND")
        print(f"Employer Insurance: {empr_insurance:,.0f} VND")

        # 2. Calculate taxable income
        tax_config = config.config["personal_income_tax"]
        standard_deduction = tax_config["standard_deduction"]
        dependent_deduction = tax_config["dependent_deduction"]

        total_deduction = standard_deduction + (dependent_deduction * number_of_dependents)
        taxable_income = base_salary - emp_insurance - total_deduction

        print("\nDeductions:")
        print(f"  Standard: {standard_deduction:,} VND")
        print(f"  Dependents ({number_of_dependents}): {dependent_deduction * number_of_dependents:,} VND")
        print(f"  Insurance: {emp_insurance:,.0f} VND")
        print(f"Taxable Income: {taxable_income:,.0f} VND")

        # 3. Calculate tax
        tax = calculate_personal_income_tax(taxable_income)
        print(f"Personal Income Tax: {tax:,.0f} VND")

        # 4. Calculate KPI bonus
        kpi_bonus = apply_kpi_bonus(base_salary, kpi_grade)
        print(f"\nKPI Grade {kpi_grade} Bonus: {kpi_bonus:,.0f} VND")

        # 5. Calculate net salary
        net_salary = base_salary + kpi_bonus - emp_insurance - tax
        print(f"\n{'=' * 50}")
        print(f"NET SALARY: {net_salary:,.0f} VND")
        print(f"{'=' * 50}")

        # 6. Show business commission levels
        print("\nBusiness Commission Levels:")
        business_config = config.config["business_progressive_salary"]
        for tier in business_config["tiers"]:
            code = tier["code"]
            amount = tier["amount"]
            criteria = tier["criteria"]

            print(f"  {code}: {amount:,} VND")
            if criteria:
                print("    Criteria:")
                for criterion in criteria:
                    print(f"      - {criterion['name']}: min {criterion['min']:,}")

        # 7. Check commission eligibility (example)
        print("\nCommission Eligibility Check:")
        employee_performance = {
            "transaction_count": 75,
            "revenue": 120000000,
        }

        for tier in business_config["tiers"]:
            if tier["criteria"]:  # Skip M0 which has no criteria
                eligible, missing = check_business_commission_eligibility(employee_performance, tier["code"])
                status = "✓ ELIGIBLE" if eligible else "✗ NOT ELIGIBLE"
                print(f"  {tier['code']}: {status}")
                if missing:
                    for m in missing:
                        print(f"    Missing: {m['name']} (has {m['actual']:,}, needs {m['required']:,})")
    else:
        print("ERROR: No salary configuration found!")
        print("Please create a salary configuration in Django Admin first.")
