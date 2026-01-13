import pytest
from apps.audit_logging.api.serializers import AuditLogSerializer
from apps.audit_logging.registry import AuditLogRegistry
from django.db import models


# Mock model for testing
class ApiTestModel(models.Model):
    name = models.CharField(max_length=100, verbose_name="Full Name")

    class Meta:
        app_label = "audit_logging"
        verbose_name = "API Test Object"


@pytest.fixture
def mock_registry():
    original_registry = AuditLogRegistry._registry.copy()
    AuditLogRegistry._registry.clear()
    AuditLogRegistry.register(ApiTestModel)
    yield
    AuditLogRegistry._registry = original_registry


@pytest.mark.django_db
class TestAuditLogSerializerTranslation:

    def test_serializer_translation_fields(self, mock_registry):
        """Test that serializer includes translated fields directly in main fields."""
        data = {
            "log_id": "test-id",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": "user123",
            "username": "user@example.com",
            "action": "CREATE",
            "object_type": "ApiTestModel",
            "object_id": "1",
            "change_message": {
                "headers": ["field", "old_value", "new_value"],
                "rows": [
                    {
                        "field": "name",
                        "old_value": "Old",
                        "new_value": "New"
                    }
                ]
            }
        }

        serializer = AuditLogSerializer(data)
        result = serializer.data

        # Check translated fields are returned in place of raw keys
        assert result["object_type"] == "API Test Object"
        assert result["action"] == "Create"

        change_msg = result["change_message"]
        assert change_msg["headers"] == ["Field", "Old value", "New value"]
        assert change_msg["rows"][0]["field"] == "Full Name"

    def test_is_system_action(self):
        """Test is_system_action logic."""
        # User action
        user_data = {
            "log_id": "1",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": "user123",
            "username": "john.doe"
        }
        assert AuditLogSerializer(user_data).data["is_system_action"] is False

        # System action (no user_id)
        system_no_user = {
            "log_id": "2",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": None,
            "username": None
        }
        assert AuditLogSerializer(system_no_user).data["is_system_action"] is True

        # System action (system username)
        system_user = {
            "log_id": "3",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": "sys123",
            "username": "system"
        }
        assert AuditLogSerializer(system_user).data["is_system_action"] is True

        # Celery user
        celery_user = {
            "log_id": "4",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": "celery123",
            "username": "celery"
        }
        assert AuditLogSerializer(celery_user).data["is_system_action"] is True
