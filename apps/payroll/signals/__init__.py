"""Signals package for payroll app.

This package contains all signal handlers organized by their purpose.
Signals are automatically registered when the app is initialized.

Signal Files:
- model_lifecycle: All model post_save/delete handlers (CONSOLIDATED)
- kpi_assessment: KPI-specific business logic
- employee_lifecycle: Employee onboarding/offboarding
- deadline_validation: Pre-save validations
- code_generation: Auto-code generation
- period_protection: CRUD protection for completed periods

DEPRECATED (Phase 2 - DO NOT USE):
- payroll_recalculation: Merged into model_lifecycle
- statistics_update: Merged into model_lifecycle
- dashboard_cache: Merged into model_lifecycle
"""

# Import all signal modules to ensure they are registered
from apps.payroll.signals import (
    code_generation,
    deadline_validation,
    employee_lifecycle,
    kpi_assessment,
    model_lifecycle,
    period_protection,
)

# DEPRECATED - These are kept for backward compatibility but will be removed
# All functionality has been moved to model_lifecycle.py
# from apps.payroll.signals import dashboard_cache, payroll_recalculation, statistics_update

__all__ = [
    "code_generation",
    "deadline_validation",
    "employee_lifecycle",
    "kpi_assessment",
    "model_lifecycle",
    "period_protection",
    # Deprecated - do not use:
    # "dashboard_cache",
    # "payroll_recalculation",
    # "statistics_update",
]
