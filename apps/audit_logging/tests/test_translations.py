
import pytest
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.audit_logging.registry import AuditLogRegistry
from apps.audit_logging.translations import (
    get_action_display,
    get_field_display,
    get_object_type_display,
    translate_change_message,
)


# Mock models for testing
class TestModel(models.Model):
    name = models.CharField(max_length=100, verbose_name="Full Name")
    age = models.IntegerField(verbose_name="Age")

    class Meta:
        app_label = "audit_logging"
        verbose_name = "Test Object"
        verbose_name_plural = "Test Objects"


@pytest.fixture
def mock_registry():
    # Store original registry state
    original_registry = AuditLogRegistry._registry.copy()
    AuditLogRegistry._registry.clear()

    # Register test model manually
    AuditLogRegistry.register(TestModel)

    yield

    # Restore registry
    AuditLogRegistry._registry = original_registry


class TestTranslations:
    def test_get_object_type_display(self, mock_registry):
        """Test translating object type using model verbose_name."""
        # Registered model
        assert get_object_type_display("testmodel") == "Test Object"
        assert get_object_type_display("TestModel") == "Test Object"

        # Unregistered model (fallback)
        assert get_object_type_display("unknown_model") == "Unknown Model"
        assert get_object_type_display("some_other_model") == "Some Other Model"

    def test_get_field_display(self, mock_registry):
        """Test translating field name using model field verbose_name."""
        # Registered model field
        assert get_field_display("name", "TestModel") == "Full Name"
        assert get_field_display("age", "TestModel") == "Age"

        # Unregistered field (fallback)
        assert get_field_display("unknown_field", "TestModel") == "Unknown Field"

        # Unregistered model (fallback)
        assert get_field_display("name", "UnknownModel") == "Name"

        # No object type
        assert get_field_display("phone_number") == "Phone Number"

    def test_get_action_display(self):
        """Test translating actions."""
        # Using simple string check as actual translation might depend on locale
        # but we can check if it returns a lazy object or string that matches expected logic
        assert str(get_action_display("CREATE")) == "Create"
        assert str(get_action_display("UPDATE")) == "Update"
        assert str(get_action_display("DELETE")) == "Delete"

        # Unknown action
        assert get_action_display("CUSTOM") == "Custom"

    def test_translate_change_message(self, mock_registry):
        """Test translating the entire change message structure."""
        change_message = {
            "headers": ["field", "old_value", "new_value"],
            "rows": [
                {
                    "field": "name",
                    "old_value": "Old Name",
                    "new_value": "New Name"
                },
                {
                    "field": "age",
                    "old_value": 20,
                    "new_value": 21
                }
            ]
        }

        translated = translate_change_message(change_message, "TestModel")

        assert translated["headers"] == ["Field", "Old value", "New value"]
        assert len(translated["rows"]) == 2

        assert translated["rows"][0]["field"] == "Full Name"
        assert translated["rows"][0]["old_value"] == "Old Name"
        assert translated["rows"][0]["new_value"] == "New Name"

        assert translated["rows"][1]["field"] == "Age"
        assert translated["rows"][1]["old_value"] == 20
        assert translated["rows"][1]["new_value"] == 21

    def test_translate_change_message_empty_or_invalid(self):
        """Test change message handling for empty or invalid inputs."""
        assert translate_change_message(None) is None
        assert translate_change_message("string message") == "string message"
        assert translate_change_message({}) == {}

        empty_rows = {"rows": []}
        assert translate_change_message(empty_rows) == empty_rows
