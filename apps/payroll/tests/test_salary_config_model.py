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
            "kpi_salary": {"grades": {"A": 0.10, "B": 0.05, "C": 0.00, "D": -0.05}},
            "business_progressive_salary": {
                "levels": {"M0": "base_salary", "M1": 7000000, "M2": 9000000, "M3": 11000000, "M4": 13000000}
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
