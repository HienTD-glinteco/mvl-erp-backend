import pytest
from django.test import TestCase

from apps.payroll.api.serializers import SalaryConfigSchemaSerializer, SalaryConfigSerializer
from apps.payroll.models import SalaryConfig


@pytest.mark.django_db
class SalaryConfigSerializerTest(TestCase):
    """Test cases for SalaryConfig serializers"""

    def setUp(self):
        """Set up test data"""
        self.valid_config_data = {
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
                ],
            },
        }

    def test_valid_config_schema_serialization(self):
        """Test that valid config data passes schema validation"""
        serializer = SalaryConfigSchemaSerializer(data=self.valid_config_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_config_missing_insurance(self):
        """Test validation fails when insurance_contributions is missing"""
        invalid_data = self.valid_config_data.copy()
        del invalid_data["insurance_contributions"]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("insurance_contributions", serializer.errors)

    def test_invalid_config_missing_tax(self):
        """Test validation fails when personal_income_tax is missing"""
        invalid_data = self.valid_config_data.copy()
        del invalid_data["personal_income_tax"]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("personal_income_tax", serializer.errors)

    def test_invalid_config_missing_kpi(self):
        """Test validation fails when kpi_salary is missing"""
        invalid_data = self.valid_config_data.copy()
        del invalid_data["kpi_salary"]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("kpi_salary", serializer.errors)

    def test_invalid_config_missing_business_salary(self):
        """Test validation fails when business_progressive_salary is missing"""
        invalid_data = self.valid_config_data.copy()
        del invalid_data["business_progressive_salary"]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("business_progressive_salary", serializer.errors)

    def test_invalid_insurance_rate(self):
        """Test validation fails with invalid insurance rates"""
        invalid_data = self.valid_config_data.copy()
        invalid_data["insurance_contributions"]["social_insurance"]["employee_rate"] = "invalid"

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())

    def test_salary_config_serializer_with_model(self):
        """Test SalaryConfigSerializer with model instance"""
        config = SalaryConfig.objects.create(config=self.valid_config_data)
        serializer = SalaryConfigSerializer(config)

        data = serializer.data
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["config"], self.valid_config_data)
        self.assertIn("id", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_progressive_tax_levels_validation(self):
        """Test that progressive tax levels are validated correctly"""
        invalid_data = self.valid_config_data.copy()
        invalid_data["personal_income_tax"]["progressive_levels"] = [
            {"up_to": 5000000}  # Missing rate
        ]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())

    def test_kpi_tiers_validation(self):
        """Test that KPI tiers are validated correctly"""
        invalid_data = self.valid_config_data.copy()
        invalid_data["kpi_salary"]["tiers"] = [
            {"code": "A", "percentage": 0.10}  # Missing description
        ]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())

    def test_business_tiers_validation(self):
        """Test that business commission tiers are validated correctly"""
        invalid_data = self.valid_config_data.copy()
        invalid_data["business_progressive_salary"]["tiers"] = [
            {"code": "M0", "amount": 0}  # Missing criteria
        ]

        serializer = SalaryConfigSchemaSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
