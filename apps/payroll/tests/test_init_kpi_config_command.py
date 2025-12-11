import pytest
from django.core.management import call_command
from django.test import TestCase

from apps.payroll.models import KPIConfig


@pytest.mark.django_db
class InitKPIConfigCommandTest(TestCase):
    """Test cases for init_kpi_config management command"""

    def test_command_creates_config(self):
        """Test that the command creates a KPI configuration"""
        # Ensure no configs exist
        KPIConfig.objects.all().delete()

        # Run the command
        call_command("init_kpi_config")

        # Check that a config was created
        self.assertEqual(KPIConfig.objects.count(), 1)

        config = KPIConfig.objects.first()
        self.assertEqual(config.version, 1)
        self.assertIsNotNone(config.config)

        # Verify structure
        self.assertIn("name", config.config)
        self.assertIn("ambiguous_assignment", config.config)
        self.assertIn("grade_thresholds", config.config)
        self.assertIn("unit_control", config.config)

    def test_command_with_reset(self):
        """Test that the command with --reset deletes existing configs"""
        # Create some existing configs
        KPIConfig.objects.create(config={"name": "test", "ambiguous_assignment": "manual"})
        KPIConfig.objects.create(config={"name": "test2", "ambiguous_assignment": "manual"})

        initial_count = KPIConfig.objects.count()
        self.assertEqual(initial_count, 2)

        # Run the command with reset
        call_command("init_kpi_config", reset=True)

        # Check that old configs were deleted and new one created
        self.assertEqual(KPIConfig.objects.count(), 1)

        config = KPIConfig.objects.first()
        # After reset, version should be 1 again
        self.assertEqual(config.version, 1)

    def test_command_without_reset(self):
        """Test that the command without --reset keeps existing configs"""
        # Create an existing config
        KPIConfig.objects.create(config={"name": "test", "ambiguous_assignment": "manual"})

        initial_count = KPIConfig.objects.count()
        self.assertEqual(initial_count, 1)

        # Run the command without reset
        call_command("init_kpi_config")

        # Check that a new config was added
        self.assertEqual(KPIConfig.objects.count(), 2)

        configs = list(KPIConfig.objects.all())
        # Latest should have version 2
        self.assertEqual(configs[0].version, 2)
        self.assertEqual(configs[1].version, 1)

    def test_config_structure_complete(self):
        """Test that the created config has all required fields"""
        KPIConfig.objects.all().delete()
        call_command("init_kpi_config")

        config = KPIConfig.objects.first().config

        # Validate name
        self.assertEqual(config["name"], "Default KPI Config")

        # Validate ambiguous_assignment
        self.assertIn(config["ambiguous_assignment"], ["manual", "auto_prefer_default", "auto_prefer_highest", "auto_prefer_first"])

        # Validate grade_thresholds
        self.assertIn("grade_thresholds", config)
        self.assertEqual(len(config["grade_thresholds"]), 4)

        # Each threshold should have required fields
        for threshold in config["grade_thresholds"]:
            self.assertIn("min", threshold)
            self.assertIn("max", threshold)
            self.assertIn("possible_codes", threshold)
            self.assertGreater(len(threshold["possible_codes"]), 0)

        # Validate unit_control
        self.assertIn("unit_control", config)
        self.assertEqual(len(config["unit_control"]), 4)

        # Each unit control should have required fields
        for unit_type, control in config["unit_control"].items():
            self.assertIn("max_pct_A", control)
            self.assertIn("max_pct_B", control)
            self.assertIn("max_pct_C", control)
            # min_pct_D can be null
            self.assertIn("min_pct_D", control)

    def test_config_validates_correctly(self):
        """Test that the created config passes validation"""
        KPIConfig.objects.all().delete()
        call_command("init_kpi_config")

        config = KPIConfig.objects.first()

        # Import validation function
        from apps.payroll.utils.kpi_helpers import validate_kpi_config_structure

        errors = validate_kpi_config_structure(config.config)
        self.assertEqual(len(errors), 0, f"Config validation failed with errors: {errors}")
