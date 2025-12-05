# Payroll Module

This module manages salary structure configuration for the MVL Backend ERP system.

## Features

### Salary Configuration Management

The system stores all salary-related rules and parameters in a single JSON configuration:
- Insurance contribution rates (Social, Health, Unemployment, Union)
- Personal income tax progressive levels
- KPI salary grades  
- Business progressive salary levels

### Key Components

#### Model: SalaryConfig

Stores the salary configuration as a JSON field with auto-versioning support.

**Fields:**
- `config` (JSONField): Complete salary configuration structure
- `version` (PositiveIntegerField): Auto-incremented version number
- `created_at`, `updated_at`: Standard timestamp fields

#### API Endpoint

**GET `/api/payroll/salary-config/current/`**

Returns the current active salary configuration. This endpoint is read-only.

**Response Format:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "version": 1,
    "config": {
      "insurance_contributions": { ... },
      "personal_income_tax": { ... },
      "kpi_salary": { ... },
      "business_progressive_salary": { ... }
    },
    "created_at": "2025-12-04T10:00:00Z",
    "updated_at": "2025-12-04T10:00:00Z"
  },
  "error": null
}
```

#### Configuration Schema

The config JSON must follow this structure:

```json
{
  "insurance_contributions": {
    "social_insurance": {
      "employee_rate": 0.08,
      "employer_rate": 0.17,
      "salary_ceiling": 46800000
    },
    "health_insurance": {
      "employee_rate": 0.015,
      "employer_rate": 0.03,
      "salary_ceiling": 46800000
    },
    "unemployment_insurance": {
      "employee_rate": 0.01,
      "employer_rate": 0.01,
      "salary_ceiling": 46800000
    },
    "union_fee": {
      "employee_rate": 0.01,
      "employer_rate": 0.01,
      "salary_ceiling": 46800000
    },
    "accident_occupational_insurance": {
      "employee_rate": 0.0,
      "employer_rate": 0.005,
      "salary_ceiling": 46800000
    }
  },
  "personal_income_tax": {
    "standard_deduction": 11000000,
    "dependent_deduction": 4400000,
    "progressive_levels": [
      { "up_to": 5000000, "rate": 0.05 },
      { "up_to": 10000000, "rate": 0.10 },
      { "up_to": 18000000, "rate": 0.15 },
      { "up_to": 32000000, "rate": 0.20 },
      { "up_to": 52000000, "rate": 0.25 },
      { "up_to": 80000000, "rate": 0.30 },
      { "up_to": null, "rate": 0.35 }
    ]
  },
  "kpi_salary": {
    "apply_on": "base_salary",
    "tiers": [
      { "code": "A", "percentage": 0.10, "description": "Excellent" },
      { "code": "B", "percentage": 0.05, "description": "Good" },
      { "code": "C", "percentage": 0.00, "description": "Average" },
      { "code": "D", "percentage": -0.05, "description": "Below Average" }
    ]
  },
  "business_progressive_salary": {
    "apply_on": "base_salary",
    "tiers": [
      {
        "code": "M0",
        "amount": 0,
        "criteria": []
      },
      {
        "code": "M1",
        "amount": 7000000,
        "criteria": [
          { "name": "transaction_count", "min": 50 },
          { "name": "revenue", "min": 100000000 }
        ]
      },
      {
        "code": "M2",
        "amount": 9000000,
        "criteria": [
          { "name": "transaction_count", "min": 80 },
          { "name": "revenue", "min": 150000000 }
        ]
      }
    ]
  }
}
```

### Django Admin

Configuration can be edited through Django Admin at `/admin/payroll/salaryconfig/`.

**Features:**
- Version field is read-only and auto-incremented
- JSON editor for config field
- Delete protection to maintain history

### Usage in Payroll Calculation

When calculating payroll:

1. Retrieve the current configuration:
```python
from apps.payroll.models import SalaryConfig

config = SalaryConfig.objects.first().config
```

2. Use the config data in calculations:
```python
# Get insurance rates
social_insurance_employee = config['insurance_contributions']['social_insurance']['employee_rate']

# Get tax progressive levels
tax_levels = config['personal_income_tax']['progressive_levels']

# Get KPI tier by code
kpi_tiers = config['kpi_salary']['tiers']
kpi_tier_a = next((t for t in kpi_tiers if t['code'] == 'A'), None)
kpi_percentage = kpi_tier_a['percentage']

# Get business commission tier by code
business_tiers = config['business_progressive_salary']['tiers']
m1_tier = next((t for t in business_tiers if t['code'] == 'M1'), None)
m1_amount = m1_tier['amount']
m1_criteria = m1_tier['criteria']
```

3. Save config snapshot with payroll record:
```python
payroll.config_snapshot = SalaryConfig.objects.first().config
payroll.save()
```

### Testing

The module includes comprehensive tests covering:
- Model functionality and version auto-increment
- API endpoint responses and error handling
- Serializer validation
- All edge cases

Run tests:
```bash
ENVIRONMENT=test poetry run pytest apps/payroll/tests/ -v
```

### Future Enhancements

Potential future additions:
- API endpoints for POST/PUT/PATCH with schema validation
- Configuration history tracking and rollback
- Frontend JSON editor UI with schema validation
- Comparison tool for different versions
