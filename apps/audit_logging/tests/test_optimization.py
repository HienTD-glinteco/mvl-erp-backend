"""
Tests for audit logging optimization features.

This module tests the performance optimization features for audit logging:
- m2m_fields_to_track: Controls which M2M fields are tracked
- reverse_fk_fields_to_track: Controls which reverse FK relationships are tracked
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.audit_logging.producer import _collect_related_changes


@override_settings(AUDIT_LOG_DISABLED=False)
def test_m2m_fields_to_track_empty_list():
    """Test that setting m2m_fields_to_track=[] skips all M2M field tracking."""
    # Create mock M2M field
    mock_m2m_field = MagicMock()
    mock_m2m_field.name = "tags"

    # Create mock objects with M2M field but m2m_fields_to_track=[]
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = [mock_m2m_field]
    original._meta.related_objects = []
    original.pk = 1

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = [mock_m2m_field]
    modified._meta.related_objects = []
    modified.pk = 1
    modified.m2m_fields_to_track = []  # Empty list means no M2M tracking

    # Mock the related managers to simulate changes
    original_manager = MagicMock()
    original_manager.values_list = MagicMock(return_value=[1, 2])
    original.tags = original_manager

    modified_manager = MagicMock()
    modified_manager.values_list = MagicMock(return_value=[1, 2, 3])
    modified.tags = modified_manager

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should return empty list since m2m_fields_to_track=[]
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0

    # Verify that the managers were NOT queried (optimization working)
    original_manager.values_list.assert_not_called()
    modified_manager.values_list.assert_not_called()


@override_settings(AUDIT_LOG_DISABLED=False)
def test_m2m_fields_to_track_specific_fields():
    """Test that m2m_fields_to_track=['field_name'] only tracks specified M2M fields."""
    # Create two mock M2M fields
    mock_m2m_field1 = MagicMock()
    mock_m2m_field1.name = "tags"
    mock_m2m_field1.related_model = MagicMock()
    mock_m2m_field1.related_model._meta = MagicMock()
    mock_m2m_field1.related_model._meta.model_name = "tag"
    mock_m2m_field1.related_model.objects = MagicMock()

    mock_m2m_field2 = MagicMock()
    mock_m2m_field2.name = "categories"

    # Create mock objects with two M2M fields but only track one
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = [mock_m2m_field1, mock_m2m_field2]
    original._meta.related_objects = []
    original.pk = 1

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = [mock_m2m_field1, mock_m2m_field2]
    modified._meta.related_objects = []
    modified.pk = 1
    modified.m2m_fields_to_track = ["tags"]  # Only track tags

    # Mock the related managers
    # tags: changed (should be tracked)
    original_tags = MagicMock()
    original_tags.values_list = MagicMock(return_value=[1])
    original.tags = original_tags

    modified_tags = MagicMock()
    modified_tags.values_list = MagicMock(return_value=[1, 2])
    modified.tags = modified_tags

    # categories: changed (should NOT be tracked due to m2m_fields_to_track)
    original_categories = MagicMock()
    original_categories.values_list = MagicMock(return_value=[10])
    original.categories = original_categories

    modified_categories = MagicMock()
    modified_categories.values_list = MagicMock(return_value=[10, 20])
    modified.categories = modified_categories

    # Mock the Tag model for added items
    mock_tag = MagicMock()
    mock_tag.pk = 2
    mock_tag.__str__ = MagicMock(return_value="New Tag")
    mock_m2m_field1.related_model.objects.filter = MagicMock(return_value=[mock_tag])

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should only track tags, not categories
    assert len(related_changes) == 1
    assert related_changes[0]["field_name"] == "tags"
    assert related_changes[0]["relation_type"] == "many_to_many"
    assert len(related_changes[0]["changes"]) == 1
    assert related_changes[0]["changes"][0]["action"] == "added"

    # Verify that categories manager was NOT queried
    original_categories.values_list.assert_not_called()
    modified_categories.values_list.assert_not_called()


@override_settings(AUDIT_LOG_DISABLED=False)
def test_m2m_fields_to_track_none_tracks_all():
    """Test that m2m_fields_to_track=None (default) tracks all M2M fields."""
    # Create mock M2M field
    mock_m2m_field = MagicMock()
    mock_m2m_field.name = "tags"
    mock_m2m_field.related_model = MagicMock()
    mock_m2m_field.related_model._meta = MagicMock()
    mock_m2m_field.related_model._meta.model_name = "tag"
    mock_m2m_field.related_model.objects = MagicMock()

    # Create mock objects WITHOUT m2m_fields_to_track (None by default)
    original = MagicMock(spec=['_meta', 'pk', 'tags'])  # spec limits attributes to simulate real object
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = [mock_m2m_field]
    original._meta.related_objects = []
    original.pk = 1

    modified = MagicMock(spec=['_meta', 'pk', 'tags'])  # spec limits attributes to simulate real object
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = [mock_m2m_field]
    modified._meta.related_objects = []
    modified.pk = 1
    # Note: m2m_fields_to_track not set (None), so should track all

    # Mock the related managers to simulate changes
    original_manager = MagicMock()
    original_manager.values_list = MagicMock(return_value=[1])
    original.tags = original_manager

    modified_manager = MagicMock()
    modified_manager.values_list = MagicMock(return_value=[1, 2])
    modified.tags = modified_manager

    # Mock the Tag model for added items
    mock_tag = MagicMock()
    mock_tag.pk = 2
    mock_tag.__str__ = MagicMock(return_value="New Tag")
    mock_m2m_field.related_model.objects.filter = MagicMock(return_value=[mock_tag])

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should track the M2M field since m2m_fields_to_track is None
    assert len(related_changes) == 1
    assert related_changes[0]["field_name"] == "tags"
    assert related_changes[0]["relation_type"] == "many_to_many"


@override_settings(AUDIT_LOG_DISABLED=False)
def test_reverse_fk_fields_to_track_empty_list():
    """Test that setting reverse_fk_fields_to_track=[] skips all reverse FK tracking."""
    # Create mock related object descriptor
    mock_related_object = MagicMock()
    mock_related_object.get_accessor_name = MagicMock(return_value="comments")

    # Create mock objects with reverse FK but reverse_fk_fields_to_track=[]
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = []
    original._meta.related_objects = [mock_related_object]
    original.pk = 1

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = []
    modified._meta.related_objects = [mock_related_object]
    modified.pk = 1
    modified.reverse_fk_fields_to_track = []  # Empty list means no reverse FK tracking

    # Mock the related manager
    original_comments = MagicMock()
    original_comments.all = MagicMock(return_value=[])
    original.comments = original_comments

    modified_comments = MagicMock()
    modified_comments.all = MagicMock(return_value=[])
    modified.comments = modified_comments

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should return empty list since reverse_fk_fields_to_track=[]
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0

    # Verify that the managers were NOT queried (optimization working)
    original_comments.all.assert_not_called()
    modified_comments.all.assert_not_called()


@override_settings(AUDIT_LOG_DISABLED=False)
def test_reverse_fk_fields_to_track_specific_fields():
    """Test that reverse_fk_fields_to_track=['field_name'] only tracks specified reverse FKs."""
    # Create two mock related object descriptors
    mock_related_object1 = MagicMock()
    mock_related_object1.get_accessor_name = MagicMock(return_value="comments")
    mock_related_object1.related_model = MagicMock()
    mock_related_object1.related_model._meta = MagicMock()
    mock_related_object1.related_model._meta.model_name = "comment"

    mock_related_object2 = MagicMock()
    mock_related_object2.get_accessor_name = MagicMock(return_value="attachments")

    # Create mock objects with two reverse FKs but only track one
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = []
    original._meta.related_objects = [mock_related_object1, mock_related_object2]
    original.pk = 1

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = []
    modified._meta.related_objects = [mock_related_object1, mock_related_object2]
    modified.pk = 1
    modified.reverse_fk_fields_to_track = ["comments"]  # Only track comments

    # Mock comment (should be tracked)
    mock_comment = MagicMock()
    mock_comment.pk = 100
    mock_comment.__str__ = MagicMock(return_value="New Comment")

    original_comments = MagicMock()
    original_comments.all = MagicMock(return_value=[])
    original.comments = original_comments

    modified_comments = MagicMock()
    modified_comments.all = MagicMock(return_value=[mock_comment])
    modified.comments = modified_comments

    # Mock attachments (should NOT be tracked)
    original_attachments = MagicMock()
    original_attachments.all = MagicMock(return_value=[])
    original.attachments = original_attachments

    modified_attachments = MagicMock()
    modified_attachments.all = MagicMock(return_value=[MagicMock(pk=200)])
    modified.attachments = modified_attachments

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should only track comments, not attachments
    assert len(related_changes) == 1
    assert related_changes[0]["field_name"] == "comments"
    assert related_changes[0]["relation_type"] == "reverse_foreign_key"
    assert len(related_changes[0]["changes"]) == 1
    assert related_changes[0]["changes"][0]["action"] == "added"

    # Verify that attachments manager was NOT queried
    original_attachments.all.assert_not_called()
    modified_attachments.all.assert_not_called()


@override_settings(AUDIT_LOG_DISABLED=False)
def test_reverse_fk_fields_to_track_none_tracks_all():
    """Test that reverse_fk_fields_to_track=None (default) tracks all reverse FKs."""
    # Create mock related object descriptor
    mock_related_object = MagicMock()
    mock_related_object.get_accessor_name = MagicMock(return_value="comments")
    mock_related_object.related_model = MagicMock()
    mock_related_object.related_model._meta = MagicMock()
    mock_related_object.related_model._meta.model_name = "comment"

    # Create mock objects WITHOUT reverse_fk_fields_to_track (None by default)
    original = MagicMock(spec=['_meta', 'pk', 'comments'])  # spec limits attributes to simulate real object
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = []
    original._meta.related_objects = [mock_related_object]
    original.pk = 1

    modified = MagicMock(spec=['_meta', 'pk', 'comments'])  # spec limits attributes to simulate real object
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = []
    modified._meta.related_objects = [mock_related_object]
    modified.pk = 1
    # Note: reverse_fk_fields_to_track not set (None), so should track all

    # Mock comment
    mock_comment = MagicMock()
    mock_comment.pk = 100
    mock_comment.__str__ = MagicMock(return_value="New Comment")

    original_comments = MagicMock()
    original_comments.all = MagicMock(return_value=[])
    original.comments = original_comments

    modified_comments = MagicMock()
    modified_comments.all = MagicMock(return_value=[mock_comment])
    modified.comments = modified_comments

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should track the reverse FK since reverse_fk_fields_to_track is None
    assert len(related_changes) == 1
    assert related_changes[0]["field_name"] == "comments"
    assert related_changes[0]["relation_type"] == "reverse_foreign_key"


@override_settings(AUDIT_LOG_DISABLED=False)
def test_combined_optimization():
    """Test that both m2m_fields_to_track and reverse_fk_fields_to_track work together."""
    # Create mock M2M field
    mock_m2m_field = MagicMock()
    mock_m2m_field.name = "tags"

    # Create mock related object descriptor
    mock_related_object = MagicMock()
    mock_related_object.get_accessor_name = MagicMock(return_value="comments")

    # Create mock objects with both set to empty lists
    original = MagicMock()
    original._meta = MagicMock()
    original._meta.fields = []
    original._meta.many_to_many = [mock_m2m_field]
    original._meta.related_objects = [mock_related_object]
    original.pk = 1

    modified = MagicMock()
    modified._meta = MagicMock()
    modified._meta.fields = []
    modified._meta.many_to_many = [mock_m2m_field]
    modified._meta.related_objects = [mock_related_object]
    modified.pk = 1
    modified.m2m_fields_to_track = []  # No M2M tracking
    modified.reverse_fk_fields_to_track = []  # No reverse FK tracking

    # Mock the related managers
    original_tags = MagicMock()
    original_tags.values_list = MagicMock(return_value=[1])
    original.tags = original_tags

    modified_tags = MagicMock()
    modified_tags.values_list = MagicMock(return_value=[1, 2])
    modified.tags = modified_tags

    original_comments = MagicMock()
    original_comments.all = MagicMock(return_value=[])
    original.comments = original_comments

    modified_comments = MagicMock()
    modified_comments.all = MagicMock(return_value=[MagicMock(pk=100)])
    modified.comments = modified_comments

    # Call _collect_related_changes
    related_changes = _collect_related_changes(original, modified)

    # Should return empty list since both are set to []
    assert isinstance(related_changes, list)
    assert len(related_changes) == 0

    # Verify that neither manager was queried
    original_tags.values_list.assert_not_called()
    modified_tags.values_list.assert_not_called()
    original_comments.all.assert_not_called()
    modified_comments.all.assert_not_called()


@pytest.mark.django_db
@override_settings(AUDIT_LOG_DISABLED=False)
@patch("apps.audit_logging.producer._audit_producer.log_event")
def test_employee_model_optimization(mock_log_event):
    """Test that Employee model uses the optimization correctly."""
    from apps.hrm.models import Employee

    # Verify that Employee has the optimization attributes set
    assert hasattr(Employee, "m2m_fields_to_track")
    assert hasattr(Employee, "reverse_fk_fields_to_track")

    # Verify they are set to empty lists for optimization
    assert Employee.m2m_fields_to_track == []
    assert Employee.reverse_fk_fields_to_track == []
