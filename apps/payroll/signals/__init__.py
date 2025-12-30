"""Signals package for payroll app.

This package contains all signal handlers organized by their purpose.
Signals are automatically registered when the app is initialized.
"""

# Import all signal modules to ensure they are registered
from apps.payroll.signals import (
    code_generation,
    deadline_validation,
    kpi_assessment,
    payroll_recalculation,
    statistics_update,
)

__all__ = [
    "code_generation",
    "deadline_validation",
    "kpi_assessment",
    "payroll_recalculation",
    "statistics_update",
]
