import pytest
from django.test import TestCase

from apps.payroll.models import SalaryConfig


@pytest.mark.django_db
class SalaryConfigModelTest(TestCase):
    """Test cases for SalaryConfig model"""

    def setUp(self):
        """Set up test data"""
        self.valid_config = {
            "insurance_contributions": {
                "social_insurance": {"employee_rate": 0.08, "employer_rate": 0.17, "salary_ceiling": 46800000},
                "health_insurance": {"employee_rate": 0.015, "employer_rate": 0.03, "salary_ceiling": 46800000},
                "unemployment_insurance": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
                "union_fee": {"employee_rate": 0.01, "employer_rate": 0.01, "salary_ceiling": 46800000},
                "accident_occupational_insurance": {
                    "employee_rate": 0.0,
                    "employer_rate": 0.005,
                    "salary_ceiling": 46800000,
                },
            },
            "personal_income_tax": {
                "standard_deduction": 11000000,
                "dependent_deduction": 4400000,
                "progressive_levels": [
                    {"up_to": 5000000, "rate": 0.05},
                    {"up_to": 10000000, "rate": 0.10},
                    {"up_to": 18000000, "rate": 0.15},
                    {"up_to": 32000000, "rate": 0.20},
                    {"up_to": 52000000, "rate": 0.25},
                    {"up_to": 80000000, "rate": 0.30},
                    {"up_to": None, "rate": 0.35},
                ],
            },
            "kpi_salary": {
                "apply_on": "base_salary",
                "tiers": [
                    {"code": "A", "percentage": 0.10, "description": "Excellent"},
                    {"code": "B", "percentage": 0.05, "description": "Good"},
                    {"code": "C", "percentage": 0.00, "description": "Average"},
                    {"code": "D", "percentage": -0.05, "description": "Below Average"},
                ],
            },
            "overtime_multipliers": {
                "saturday_inweek": 1.5,
                "sunday": 2.0,
                "holiday": 3.0,
            },
            "business_progressive_salary": {
                "apply_on": "base_salary",
                "tiers": [
                    {"code": "M0", "amount": 0, "criteria": []},
                    {
                        "code": "M1",
                        "amount": 7000000,
                        "criteria": [
                            {"name": "transaction_count", "min": 50},
                            {"name": "revenue", "min": 100000000},
                        ],
                    },
                    {
                        "code": "M2",
                        "amount": 9000000,
                        "criteria": [
                            {"name": "transaction_count", "min": 80},
                            {"name": "revenue", "min": 150000000},
                        ],
                    },
                    {
                        "code": "M3",
                        "amount": 11000000,
                        "criteria": [
                            {"name": "transaction_count", "min": 120},
                            {"name": "revenue", "min": 200000000},
                        ],
                    },
                    {
                        "code": "M4",
                        "amount": 13000000,
                        "criteria": [
                            {"name": "transaction_count", "min": 150},
                            {"name": "revenue", "min": 250000000},
                        ],
                    },
                ],
            },
        }

    def test_create_salary_config(self):
        """Test creating a salary configuration"""
        config = SalaryConfig.objects.create(config=self.valid_config)

        self.assertIsNotNone(config.id)
        self.assertEqual(config.version, 1)
        self.assertEqual(config.config, self.valid_config)

    def test_auto_increment_version(self):
        """Test that version is auto-incremented"""
        config1 = SalaryConfig.objects.create(config=self.valid_config)
        self.assertEqual(config1.version, 1)

        config2 = SalaryConfig.objects.create(config=self.valid_config)
        self.assertEqual(config2.version, 2)

        config3 = SalaryConfig.objects.create(config=self.valid_config)
        self.assertEqual(config3.version, 3)

    def test_str_representation(self):
        """Test string representation of SalaryConfig"""
        config = SalaryConfig.objects.create(config=self.valid_config)
        self.assertEqual(str(config), f"SalaryConfig v{config.version}")

    def test_ordering(self):
        """Test that configs are ordered by version descending"""
        config1 = SalaryConfig.objects.create(config=self.valid_config)
        config2 = SalaryConfig.objects.create(config=self.valid_config)
        config3 = SalaryConfig.objects.create(config=self.valid_config)

        configs = list(SalaryConfig.objects.all())
        self.assertEqual(configs[0].version, 3)
        self.assertEqual(configs[1].version, 2)
        self.assertEqual(configs[2].version, 1)

    def test_get_latest_config(self):
        """Test getting the latest (first) configuration"""
        SalaryConfig.objects.create(config=self.valid_config)
        SalaryConfig.objects.create(config=self.valid_config)
        latest = SalaryConfig.objects.create(config=self.valid_config)

        retrieved = SalaryConfig.objects.first()
        self.assertEqual(retrieved.id, latest.id)
        self.assertEqual(retrieved.version, 3)
