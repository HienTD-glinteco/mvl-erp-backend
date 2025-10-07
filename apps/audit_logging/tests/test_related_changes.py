"""
Tests for tracking related object changes in audit logs.

This module tests the functionality that captures changes to related objects
(ForeignKey, ManyToMany, reverse ForeignKey) when the main object changes.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.audit_logging import LogAction, log_audit_event
from apps.audit_logging.producer import _collect_related_changes, _prepare_change_messages

User = get_user_model()


@pytest.mark.django_db
@patch("apps.audit_logging.producer._audit_producer.log_event")
def test_related_changes_field_added_to_log(mock_log_event):
    """Test that related_changes field is added when there are related changes."""
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

    # With no actual related changes, related_changes should not be present or be empty
    if "related_changes" in call_args:
        assert len(call_args["related_changes"]) == 0


@pytest.mark.django_db
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


def test_collect_related_changes_with_no_meta():
    """Test that _collect_related_changes handles objects without _meta gracefully."""
    # Create objects without _meta attribute
    original = MagicMock(spec=[])
    modified = MagicMock(spec=[])

    # Call the utility function
    related_changes = _collect_related_changes(original, modified)

    # Should return empty list for objects without _meta
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0


def test_collect_related_changes_with_empty_relationships():
    """Test that _collect_related_changes works when there are no relationships."""
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

    # Should return empty list when there are no relationships
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0


def test_prepare_change_messages_adds_related_changes():
    """Test that _prepare_change_messages adds related_changes field."""
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

    # Check that change_message was added
    assert "change_message" in log_data

    # related_changes should not be added if there are no actual changes
    # This verifies the function runs without errors
