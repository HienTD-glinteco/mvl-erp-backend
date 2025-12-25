"""Payroll calculation utilities."""

from decimal import Decimal
from typing import Tuple


def calculate_business_progressive_salary(
    revenue: int,
    transaction_count: int,
    tiers: list
) -> Tuple[str, Decimal]:
    """Calculate business progressive salary based on revenue and transaction count.
    
    Args:
        revenue: Total sales revenue
        transaction_count: Number of transactions
        tiers: List of tier definitions from SalaryConfig
        
    Returns:
        tuple: (grade, amount) - e.g., ("M3", Decimal("10000000"))
    """
    # Sort tiers by amount descending to get highest matching tier
    sorted_tiers = sorted(tiers, key=lambda t: t['amount'], reverse=True)
    
    for tier in sorted_tiers:
        criteria = tier['criteria']
        meets_all = True
        
        for criterion in criteria:
            if criterion['name'] == 'revenue':
                if revenue < criterion['min']:
                    meets_all = False
                    break
            elif criterion['name'] == 'transaction_count':
                if transaction_count < criterion['min']:
                    meets_all = False
                    break
        
        if meets_all:
            return tier['code'], Decimal(str(tier['amount']))
    
    # Default to M0 with 0 amount
    return 'M0', Decimal('0')
