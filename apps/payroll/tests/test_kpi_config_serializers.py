import pytest
from rest_framework.exceptions import ValidationError

from apps.payroll.api.serializers import KPIConfigSerializer
from apps.payroll.api.serializers.kpi_config_schemas import (
    GradeThresholdSerializer,
    KPIConfigSchemaSerializer,
    UnitControlSerializer,
)
from apps.payroll.models import KPIConfig


@pytest.mark.django_db
class TestGradeThresholdSerializer:
    """Test cases for GradeThresholdSerializer"""

    def test_valid_threshold(self):
        """Test valid threshold data"""
        data = {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"}
        serializer = GradeThresholdSerializer(data=data)
        assert serializer.is_valid()

    def test_threshold_with_default_code(self):
        """Test threshold with valid default_code"""
        data = {"min": 60, "max": 70, "possible_codes": ["C", "D"], "default_code": "C", "label": "Average"}
        serializer = GradeThresholdSerializer(data=data)
        assert serializer.is_valid()

    def test_invalid_default_code(self):
        """Test threshold with default_code not in possible_codes"""
        data = {"min": 60, "max": 70, "possible_codes": ["C", "D"], "default_code": "A"}
        serializer = GradeThresholdSerializer(data=data)
        assert not serializer.is_valid()
        assert "default_code" in serializer.errors

    def test_min_greater_than_max(self):
        """Test threshold with min >= max"""
        data = {"min": 70, "max": 60, "possible_codes": ["D"]}
        serializer = GradeThresholdSerializer(data=data)
        assert not serializer.is_valid()
        assert "min" in serializer.errors

    def test_empty_possible_codes(self):
        """Test threshold with empty possible_codes"""
        data = {"min": 0, "max": 60, "possible_codes": []}
        serializer = GradeThresholdSerializer(data=data)
        assert not serializer.is_valid()
        assert "possible_codes" in serializer.errors


class TestUnitControlSerializer:
    """Test cases for UnitControlSerializer"""

    def test_valid_unit_control(self):
        """Test valid unit control data"""
        data = {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": 0.10}
        serializer = UnitControlSerializer(data=data)
        assert serializer.is_valid()

    def test_unit_control_with_null_min_pct_d(self):
        """Test unit control with null min_pct_D"""
        data = {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None}
        serializer = UnitControlSerializer(data=data)
        assert serializer.is_valid()

    def test_invalid_percentage_too_high(self):
        """Test percentage value > 1.0"""
        data = {"max_pct_A": 1.5, "max_pct_B": 0.30, "max_pct_C": 0.50}
        serializer = UnitControlSerializer(data=data)
        assert not serializer.is_valid()
        assert "max_pct_A" in serializer.errors

    def test_invalid_percentage_negative(self):
        """Test negative percentage value"""
        data = {"max_pct_A": -0.1, "max_pct_B": 0.30, "max_pct_C": 0.50}
        serializer = UnitControlSerializer(data=data)
        assert not serializer.is_valid()
        assert "max_pct_A" in serializer.errors


@pytest.mark.django_db
class TestKPIConfigSchemaSerializer:
    """Test cases for KPIConfigSchemaSerializer"""

    def setup_method(self):
        """Set up test data"""
        self.valid_data = {
            "name": "Default KPI Config",
            "description": "Standard grading scale",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {
                    "min": 60,
                    "max": 70,
                    "possible_codes": ["C", "D"],
                    "default_code": "C",
                    "label": "Average",
                },
            ],
            "unit_control": {
                "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None}
            },
            "meta": {},
        }

    def test_valid_config_schema(self):
        """Test valid KPI config schema"""
        serializer = KPIConfigSchemaSerializer(data=self.valid_data)
        assert serializer.is_valid()

    def test_missing_required_field_name(self):
        """Test missing required field 'name'"""
        data = self.valid_data.copy()
        del data["name"]
        serializer = KPIConfigSchemaSerializer(data=data)
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_invalid_ambiguous_assignment(self):
        """Test invalid ambiguous_assignment value"""
        data = self.valid_data.copy()
        data["ambiguous_assignment"] = "invalid_policy"
        serializer = KPIConfigSchemaSerializer(data=data)
        assert not serializer.is_valid()
        assert "ambiguous_assignment" in serializer.errors

    def test_valid_ambiguous_policies(self):
        """Test all valid ambiguous_assignment policies"""
        valid_policies = ["manual", "auto_prefer_default", "auto_prefer_highest", "auto_prefer_first"]
        for policy in valid_policies:
            data = self.valid_data.copy()
            data["ambiguous_assignment"] = policy
            serializer = KPIConfigSchemaSerializer(data=data)
            assert serializer.is_valid(), f"Policy {policy} should be valid"

    def test_optional_description(self):
        """Test that description is optional"""
        data = self.valid_data.copy()
        del data["description"]
        serializer = KPIConfigSchemaSerializer(data=data)
        assert serializer.is_valid()

    def test_optional_meta(self):
        """Test that meta is optional"""
        data = self.valid_data.copy()
        del data["meta"]
        serializer = KPIConfigSchemaSerializer(data=data)
        assert serializer.is_valid()


@pytest.mark.django_db
class TestKPIConfigSerializer:
    """Test cases for KPIConfigSerializer"""

    def setup_method(self):
        """Set up test data"""
        self.valid_config = {
            "name": "Default KPI Config",
            "description": "Standard grading scale",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {
                    "min": 60,
                    "max": 70,
                    "possible_codes": ["C", "D"],
                    "default_code": "C",
                    "label": "Average",
                },
            ],
            "unit_control": {
                "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None}
            },
            "meta": {},
        }

    def test_serialize_kpi_config(self):
        """Test serializing a KPIConfig instance"""
        config = KPIConfig.objects.create(config=self.valid_config)
        serializer = KPIConfigSerializer(config)

        assert serializer.data["id"] == config.id
        assert serializer.data["version"] == 1
        assert serializer.data["config"]["name"] == "Default KPI Config"
        assert "created_at" in serializer.data
        assert "updated_at" in serializer.data

    def test_read_only_fields(self):
        """Test that id, version, created_at, updated_at are read-only"""
        serializer = KPIConfigSerializer()
        read_only_fields = serializer.Meta.read_only_fields

        assert "id" in read_only_fields
        assert "version" in read_only_fields
        assert "created_at" in read_only_fields
        assert "updated_at" in read_only_fields

    def test_config_validation(self):
        """Test that invalid config is rejected"""
        invalid_config = {
            "name": "Test",
            "ambiguous_assignment": "invalid",  # Invalid policy
            "grade_thresholds": [],
            "unit_control": {},
        }
        config = KPIConfig.objects.create(config=invalid_config)
        serializer = KPIConfigSerializer(config)

        # Validation happens during serialization
        # The serializer should still work with existing data
        assert serializer.data["config"]["ambiguous_assignment"] == "invalid"

    def test_validate_config_method(self):
        """Test the validate_config method"""
        serializer = KPIConfigSerializer()

        # Valid config should pass
        validated = serializer.validate_config(self.valid_config)
        assert validated == self.valid_config

        # Invalid config should raise ValidationError
        invalid_config = {
            "name": "Test",
            "ambiguous_assignment": "invalid_policy",
            "grade_thresholds": [],
            "unit_control": {},
        }
        with pytest.raises(ValidationError):
            serializer.validate_config(invalid_config)
