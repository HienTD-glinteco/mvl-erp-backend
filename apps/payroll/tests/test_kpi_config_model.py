import pytest
from django.test import TestCase

from apps.payroll.models import KPIConfig


@pytest.mark.django_db
class KPIConfigModelTest(TestCase):
    """Test cases for KPIConfig model"""

    def setUp(self):
        """Set up test data"""
        self.valid_config = {
            "name": "Default KPI Config",
            "description": "Standard grading scale and unit control",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {
                    "min": 60,
                    "max": 70,
                    "possible_codes": ["C", "D"],
                    "default_code": "C",
                    "label": "Average or Poor",
                },
                {
                    "min": 70,
                    "max": 90,
                    "possible_codes": ["B", "C"],
                    "default_code": "B",
                    "label": "Good or Average",
                },
                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
            ],
            "unit_control": {
                "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None},
                "B": {"max_pct_A": 0.10, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": 0.10},
                "C": {"max_pct_A": 0.05, "max_pct_B": 0.20, "max_pct_C": 0.60, "min_pct_D": 0.15},
                "D": {"max_pct_A": 0.05, "max_pct_B": 0.10, "max_pct_C": 0.65, "min_pct_D": 0.20},
            },
            "meta": {},
        }

    def test_create_kpi_config(self):
        """Test creating a KPI configuration"""
        config = KPIConfig.objects.create(config=self.valid_config)

        self.assertIsNotNone(config.id)
        self.assertEqual(config.version, 1)
        self.assertEqual(config.config, self.valid_config)

    def test_auto_increment_version(self):
        """Test that version is auto-incremented"""
        config1 = KPIConfig.objects.create(config=self.valid_config)
        self.assertEqual(config1.version, 1)

        config2 = KPIConfig.objects.create(config=self.valid_config)
        self.assertEqual(config2.version, 2)

        config3 = KPIConfig.objects.create(config=self.valid_config)
        self.assertEqual(config3.version, 3)

    def test_str_representation(self):
        """Test string representation of KPIConfig"""
        config = KPIConfig.objects.create(config=self.valid_config)
        self.assertEqual(str(config), f"KPIConfig v{config.version}")

    def test_ordering(self):
        """Test that configs are ordered by version descending"""
        config1 = KPIConfig.objects.create(config=self.valid_config)
        config2 = KPIConfig.objects.create(config=self.valid_config)
        config3 = KPIConfig.objects.create(config=self.valid_config)

        configs = list(KPIConfig.objects.all())
        self.assertEqual(configs[0].version, 3)
        self.assertEqual(configs[1].version, 2)
        self.assertEqual(configs[2].version, 1)

    def test_get_latest_config(self):
        """Test getting the latest (first) configuration"""
        KPIConfig.objects.create(config=self.valid_config)
        KPIConfig.objects.create(config=self.valid_config)
        latest = KPIConfig.objects.create(config=self.valid_config)

        retrieved = KPIConfig.objects.first()
        self.assertEqual(retrieved.id, latest.id)
        self.assertEqual(retrieved.version, 3)

    def test_config_json_field(self):
        """Test that config field stores and retrieves JSON correctly"""
        config = KPIConfig.objects.create(config=self.valid_config)
        retrieved = KPIConfig.objects.get(id=config.id)

        self.assertEqual(retrieved.config["name"], "Default KPI Config")
        self.assertEqual(retrieved.config["ambiguous_assignment"], "manual")
        self.assertEqual(len(retrieved.config["grade_thresholds"]), 4)
        self.assertEqual(len(retrieved.config["unit_control"]), 4)
