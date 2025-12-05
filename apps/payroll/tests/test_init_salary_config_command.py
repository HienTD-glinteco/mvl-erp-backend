import pytest
from django.core.management import call_command
from django.test import TestCase

from apps.payroll.models import SalaryConfig


@pytest.mark.django_db
class InitSalaryConfigCommandTest(TestCase):
    """Test cases for init_salary_config management command"""

    def test_command_creates_config(self):
        """Test that the command creates a salary configuration"""
        # Ensure no configs exist
        SalaryConfig.objects.all().delete()

        # Run the command
        call_command("init_salary_config")

        # Check that a config was created
        self.assertEqual(SalaryConfig.objects.count(), 1)

        config = SalaryConfig.objects.first()
        self.assertEqual(config.version, 1)
        self.assertIsNotNone(config.config)

        # Verify structure
        self.assertIn("insurance_contributions", config.config)
        self.assertIn("personal_income_tax", config.config)
        self.assertIn("kpi_salary", config.config)
        self.assertIn("business_progressive_salary", config.config)

    def test_command_with_reset(self):
        """Test that the command with --reset deletes existing configs"""
        # Create some existing configs
        SalaryConfig.objects.create(config={"test": "data"})
        SalaryConfig.objects.create(config={"test": "data2"})

        initial_count = SalaryConfig.objects.count()
        self.assertEqual(initial_count, 2)

        # Run the command with reset
        call_command("init_salary_config", reset=True)

        # Check that old configs were deleted and new one created
        self.assertEqual(SalaryConfig.objects.count(), 1)

        config = SalaryConfig.objects.first()
        # After reset, version should be 1 again
        self.assertEqual(config.version, 1)

    def test_command_without_reset(self):
        """Test that the command without --reset keeps existing configs"""
        # Create an existing config
        SalaryConfig.objects.create(config={"test": "data"})

        initial_count = SalaryConfig.objects.count()
        self.assertEqual(initial_count, 1)

        # Run the command without reset
        call_command("init_salary_config")

        # Check that a new config was added
        self.assertEqual(SalaryConfig.objects.count(), 2)

        configs = list(SalaryConfig.objects.all())
        # Latest should have version 2
        self.assertEqual(configs[0].version, 2)
        self.assertEqual(configs[1].version, 1)

    def test_config_structure_complete(self):
        """Test that the created config has all required fields"""
        SalaryConfig.objects.all().delete()
        call_command("init_salary_config")

        config = SalaryConfig.objects.first().config

        # Validate insurance contributions
        self.assertIn("accident_occupational_insurance", config["insurance_contributions"])
        self.assertEqual(len(config["insurance_contributions"]), 5)

        # Validate KPI tiers
        self.assertIn("tiers", config["kpi_salary"])
        self.assertEqual(len(config["kpi_salary"]["tiers"]), 4)

        # Validate business commission tiers
        self.assertIn("tiers", config["business_progressive_salary"])
        self.assertEqual(len(config["business_progressive_salary"]["tiers"]), 5)

        # Validate M0 has criteria
        m0_tier = next((t for t in config["business_progressive_salary"]["tiers"] if t["code"] == "M0"), None)
        self.assertIsNotNone(m0_tier)
        self.assertEqual(len(m0_tier["criteria"]), 2)
