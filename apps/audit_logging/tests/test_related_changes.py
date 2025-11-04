"""
Tests for tracking related object changes in audit logs.

This module tests the functionality that captures changes to related objects
(ForeignKey, ManyToMany, reverse ForeignKey) when the main object changes.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.audit_logging import LogAction, log_audit_event
from apps.audit_logging.producer import _collect_related_changes, _prepare_change_messages

User = get_user_model()


@pytest.mark.django_db
@override_settings(AUDIT_LOG_DISABLED=False)
@patch("apps.audit_logging.producer._audit_producer.log_event")
def test_related_changes_no_longer_collected(mock_log_event):
    """Test that related_changes are no longer automatically collected (refactored behavior)."""
    # Create mock objects with _meta
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = []
    original._meta.related_objects = []
    original.pk = 1
    original.__str__ = MagicMock(return_value="Test Object")

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = []
    modified._meta.related_objects = []
    modified.pk = 1
    modified.__str__ = MagicMock(return_value="Test Object")
    modified.__class__ = original.__class__

    # Create user
    user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

    # Log the change
    log_audit_event(
        action=LogAction.CHANGE,
        original_object=original,
        modified_object=modified,
        user=user,
    )

    # Verify log was created
    mock_log_event.assert_called_once()
    call_args = mock_log_event.call_args[1]

    # related_changes should NOT be present (new refactored behavior)
    assert "related_changes" not in call_args


@pytest.mark.django_db
@override_settings(AUDIT_LOG_DISABLED=False)
@patch("apps.audit_logging.producer._audit_producer.log_event")
def test_backward_compatibility_with_add_action(mock_log_event):
    """Test that ADD action works without related_changes (backward compatibility)."""
    # Create mock object
    article = MagicMock()
    article.pk = 1
    article.__str__ = MagicMock(return_value="New Article")
    article.__class__ = MagicMock()
    article.__class__.__name__ = "Article"

    # Create user
    user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

    # Log creation
    log_audit_event(
        action=LogAction.ADD,
        original_object=None,
        modified_object=article,
        user=user,
    )

    # Verify log was created
    mock_log_event.assert_called_once()
    call_args = mock_log_event.call_args[1]

    # Check basic fields are present
    assert call_args["action"] == LogAction.ADD
    assert call_args["change_message"] == "Created new object"

    # related_changes should not be present for ADD action
    assert "related_changes" not in call_args


@pytest.mark.django_db
@override_settings(AUDIT_LOG_DISABLED=False)
@patch("apps.audit_logging.producer._audit_producer.log_event")
def test_backward_compatibility_with_delete_action(mock_log_event):
    """Test that DELETE action works without related_changes (backward compatibility)."""
    # Create mock object
    article = MagicMock()
    article.pk = 1
    article.__str__ = MagicMock(return_value="Article to Delete")
    article.__class__ = MagicMock()
    article.__class__.__name__ = "Article"

    # Create user
    user = User.objects.create_user(username="testuser2", email="test2@example.com", password="testpass123")

    # Log deletion
    log_audit_event(
        action=LogAction.DELETE,
        original_object=article,
        modified_object=None,
        user=user,
    )

    # Verify log was created
    mock_log_event.assert_called_once()
    call_args = mock_log_event.call_args[1]

    # Check basic fields are present
    assert call_args["action"] == LogAction.DELETE
    assert call_args["change_message"] == "Deleted object"

    # related_changes should not be present for DELETE action
    assert "related_changes" not in call_args


@override_settings(AUDIT_LOG_DISABLED=False)
def test_collect_related_changes_returns_empty():
    """Test that _collect_related_changes returns empty list (refactored behavior)."""
    # Create objects without _meta attribute
    original = MagicMock(spec=[])
    modified = MagicMock(spec=[])

    # Call the utility function
    related_changes = _collect_related_changes(original, modified)

    # Should always return empty list (new simplified behavior)
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0


@override_settings(AUDIT_LOG_DISABLED=False)
def test_collect_related_changes_always_returns_empty():
    """Test that _collect_related_changes always returns empty (simplified behavior)."""
    # Create mock objects with _meta but no relationships
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.many_to_many = []
    original._meta.related_objects = []

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.many_to_many = []
    modified._meta.related_objects = []

    # Call the utility function
    related_changes = _collect_related_changes(original, modified)

    # Should always return empty list (simplified - no longer collects related changes)
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0


@override_settings(AUDIT_LOG_DISABLED=False)
def test_prepare_change_messages_no_related_changes():
    """Test that _prepare_change_messages no longer adds related_changes field."""
    # Create mock objects with relationships
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = []
    original._meta.related_objects = []

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = []
    modified._meta.related_objects = []

    # Create log_data dict
    log_data = {}

    # Call _prepare_change_messages
    _prepare_change_messages(log_data, LogAction.CHANGE, original, modified)

    # Check that change_message was added (should be "Object modified" for no field changes)
    assert "change_message" in log_data
    assert log_data["change_message"] == "Object modified"

    # related_changes should NOT be added (new refactored behavior)
    assert "related_changes" not in log_data


@override_settings(AUDIT_LOG_DISABLED=False)
def test_prepare_change_messages_with_field_changes():
    """Test that _prepare_change_messages creates structured format for field changes."""
    # Create mock field with verbose_name
    mock_field = MagicMock()
    mock_field.name = "expiration_date"
    mock_field.verbose_name = "Expiration date"

    # Create mock objects with field changes
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = [mock_field]
    original._meta.many_to_many = []
    original._meta.related_objects = []
    original.expiration_date = "21/09/2025"

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = [mock_field]
    modified._meta.many_to_many = []
    modified._meta.related_objects = []
    modified.expiration_date = "10/09/2025"

    # Create log_data dict
    log_data = {}

    # Call _prepare_change_messages
    _prepare_change_messages(log_data, LogAction.CHANGE, original, modified)

    # Check that change_message has structured format
    assert "change_message" in log_data
    assert isinstance(log_data["change_message"], dict)
    assert "headers" in log_data["change_message"]
    assert "rows" in log_data["change_message"]

    # Verify headers
    assert log_data["change_message"]["headers"] == ["field", "old_value", "new_value"]

    # Verify rows
    rows = log_data["change_message"]["rows"]
    assert len(rows) == 1
    assert rows[0]["field"] == "Expiration date"
    assert rows[0]["old_value"] == "21/09/2025"
    assert rows[0]["new_value"] == "10/09/2025"


@override_settings(AUDIT_LOG_DISABLED=False)
def test_prepare_change_messages_with_multiple_field_changes():
    """Test that _prepare_change_messages handles multiple field changes."""
    # Create mock fields
    mock_field1 = MagicMock()
    mock_field1.name = "name"
    mock_field1.verbose_name = "Name"

    mock_field2 = MagicMock()
    mock_field2.name = "email"
    mock_field2.verbose_name = "Email address"

    # Create mock objects
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = [mock_field1, mock_field2]
    original._meta.many_to_many = []
    original._meta.related_objects = []
    original.name = "John Doe"
    original.email = "john@example.com"

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = [mock_field1, mock_field2]
    modified._meta.many_to_many = []
    modified._meta.related_objects = []
    modified.name = "Jane Doe"
    modified.email = "jane@example.com"

    # Create log_data dict
    log_data = {}

    # Call _prepare_change_messages
    _prepare_change_messages(log_data, LogAction.CHANGE, original, modified)

    # Check that change_message has structured format
    assert "change_message" in log_data
    assert isinstance(log_data["change_message"], dict)

    # Verify rows
    rows = log_data["change_message"]["rows"]
    assert len(rows) == 2

    # Check first change
    assert rows[0]["field"] == "Name"
    assert rows[0]["old_value"] == "John Doe"
    assert rows[0]["new_value"] == "Jane Doe"

    # Check second change
    assert rows[1]["field"] == "Email address"
    assert rows[1]["old_value"] == "john@example.com"
    assert rows[1]["new_value"] == "jane@example.com"


@override_settings(AUDIT_LOG_DISABLED=False)
def test_prepare_change_messages_with_null_values():
    """Test that _prepare_change_messages handles None values correctly."""
    # Create mock field
    mock_field = MagicMock()
    mock_field.name = "description"
    mock_field.verbose_name = "Description"

    # Create mock objects where value changes to None
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = [mock_field]
    original._meta.many_to_many = []
    original._meta.related_objects = []
    original.description = "Some description"

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = [mock_field]
    modified._meta.many_to_many = []
    modified._meta.related_objects = []
    modified.description = None

    # Create log_data dict
    log_data = {}

    # Call _prepare_change_messages
    _prepare_change_messages(log_data, LogAction.CHANGE, original, modified)

    # Check that change_message has structured format
    assert "change_message" in log_data
    assert isinstance(log_data["change_message"], dict)

    # Verify rows
    rows = log_data["change_message"]["rows"]
    assert len(rows) == 1
    assert rows[0]["field"] == "Description"
    assert rows[0]["old_value"] == "Some description"
    assert rows[0]["new_value"] is None


@override_settings(AUDIT_LOG_DISABLED=False)
def test_prepare_change_messages_with_list_values():
    """Test that _prepare_change_messages handles list values correctly."""
    # Create mock field
    mock_field = MagicMock()
    mock_field.name = "tags"
    mock_field.verbose_name = "Tags"

    # Create mock objects where value is a list
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = [mock_field]
    original._meta.many_to_many = []
    original._meta.related_objects = []
    original.tags = ["tag1", "tag2"]

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = [mock_field]
    modified._meta.many_to_many = []
    modified._meta.related_objects = []
    modified.tags = ["tag3", "tag4", "tag5"]

    # Create log_data dict
    log_data = {}

    # Call _prepare_change_messages
    _prepare_change_messages(log_data, LogAction.CHANGE, original, modified)

    # Check that change_message has structured format
    assert "change_message" in log_data
    assert isinstance(log_data["change_message"], dict)

    # Verify rows
    rows = log_data["change_message"]["rows"]
    assert len(rows) == 1
    assert rows[0]["field"] == "Tags"
    # List values should remain as lists with string representations
    assert rows[0]["old_value"] == ["tag1", "tag2"]
    assert rows[0]["new_value"] == ["tag3", "tag4", "tag5"]


@override_settings(AUDIT_LOG_DISABLED=False)
def test_prepare_change_messages_with_choice_field():
    """Test that _prepare_change_messages handles choice fields correctly using get_FOO_display()."""
    # Create mock field with choices
    mock_field = MagicMock()
    mock_field.name = "status"
    mock_field.verbose_name = "Status"
    mock_field.choices = [("A", "Active"), ("I", "Inactive")]

    # Create mock objects with choice field
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = [mock_field]
    original._meta.many_to_many = []
    original._meta.related_objects = []
    original.status = "A"
    original.get_status_display = MagicMock(return_value="Active")

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = [mock_field]
    modified._meta.many_to_many = []
    modified._meta.related_objects = []
    modified.status = "I"
    modified.get_status_display = MagicMock(return_value="Inactive")

    # Create log_data dict
    log_data = {}

    # Call _prepare_change_messages
    _prepare_change_messages(log_data, LogAction.CHANGE, original, modified)

    # Check that change_message has structured format
    assert "change_message" in log_data
    assert isinstance(log_data["change_message"], dict)

    # Verify rows
    rows = log_data["change_message"]["rows"]
    assert len(rows) == 1
    assert rows[0]["field"] == "Status"
    # Choice field values should show human-readable labels
    assert rows[0]["old_value"] == "Active"
    assert rows[0]["new_value"] == "Inactive"

    # Verify that get_status_display was called
    original.get_status_display.assert_called_once()
    modified.get_status_display.assert_called_once()


@override_settings(AUDIT_LOG_DISABLED=False)
def test_collect_related_changes_no_longer_tracks_reverse_fk():
    """Test that _collect_related_changes no longer tracks reverse FK changes (refactored)."""
    # Create mock field with choices for related objects
    mock_field = MagicMock()
    mock_field.name = "priority"
    mock_field.verbose_name = "Priority"
    mock_field.choices = [("H", "High"), ("M", "Medium"), ("L", "Low")]

    # Create main objects (parent)
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = []
    original.pk = 1

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = []
    modified.pk = 1

    # Create related object mock
    related_object_mock = MagicMock()
    related_object_mock.related_model = MagicMock()
    related_object_mock.related_model._meta = MagicMock()
    related_object_mock.related_model._meta.model_name = "task"
    related_object_mock.get_accessor_name = MagicMock(return_value="tasks")

    # Create original related object with choice field
    original_task = MagicMock()
    original_task._meta = MagicMock()
    original_task._meta.fields = [mock_field]
    original_task.pk = 101
    original_task.priority = "H"
    original_task.get_priority_display = MagicMock(return_value="High")
    original_task.__str__ = MagicMock(return_value="Task 101")

    # Create modified related object with choice field
    modified_task = MagicMock()
    modified_task._meta = MagicMock()
    modified_task._meta.fields = [mock_field]
    modified_task.pk = 101
    modified_task.priority = "L"
    modified_task.get_priority_display = MagicMock(return_value="Low")
    modified_task.__str__ = MagicMock(return_value="Task 101")

    # Set up the related objects on the main objects
    original_tasks = MagicMock()
    original_tasks.all = MagicMock(return_value=[original_task])
    original.tasks = original_tasks

    modified_tasks = MagicMock()
    modified_tasks.all = MagicMock(return_value=[modified_task])
    modified.tasks = modified_tasks

    # Add the related object descriptor to meta
    original._meta.related_objects = [related_object_mock]
    modified._meta.related_objects = [related_object_mock]

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Verify that NO related changes are collected (new refactored behavior)
    assert len(related_changes) == 0
    # Related object changes should now be logged through audit_log_target
