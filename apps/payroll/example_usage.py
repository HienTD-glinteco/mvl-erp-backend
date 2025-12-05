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
    
    grades = config.config["kpi_salary"]["grades"]
    
    if kpi_grade not in grades:
        raise ValueError(f"Invalid KPI grade: {kpi_grade}")
    
    multiplier = grades[kpi_grade]
    return base_salary * multiplier


def get_business_salary_level(level):
    """Get business progressive salary for a specific level.
    
    Args:
        level: Level code (M0, M1, M2, M3, M4)
        
    Returns:
        Salary amount or 'base_salary' for M0
    """
    config = get_current_config()
    if not config:
        raise ValueError("No salary configuration found")
    
    levels = config.config["business_progressive_salary"]["levels"]
    
    if level not in levels:
        raise ValueError(f"Invalid level: {level}")
    
    return levels[level]


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
        
        print(f"\nDeductions:")
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
        print(f"\n{'='*50}")
        print(f"NET SALARY: {net_salary:,.0f} VND")
        print(f"{'='*50}")
        
        # 6. Show business levels
        print(f"\nBusiness Salary Levels:")
        for level in ["M0", "M1", "M2", "M3", "M4"]:
            amount = get_business_salary_level(level)
            if isinstance(amount, str):
                print(f"  {level}: {amount}")
            else:
                print(f"  {level}: {amount:,} VND")
    else:
        print("ERROR: No salary configuration found!")
        print("Please create a salary configuration in Django Admin first.")
