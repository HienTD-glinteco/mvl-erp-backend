"""
Tests for AUDIT_LOG_TARGET functionality and cascade delete handling.

This module tests the new refactored audit logging system that includes:
- AUDIT_LOG_TARGET attribute for dependent models
- Cascade delete detection to avoid duplicate logs
- Logging dependent model changes under target models
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase, override_settings

from apps.audit_logging import LogAction, audit_logging_register
from apps.audit_logging.decorators import _clear_delete_context
from apps.audit_logging.registry import AuditLogRegistry
from libs.models import BaseModel, create_dummy_model

User = get_user_model()


@override_settings(AUDIT_LOG_DISABLED=False)
class TestAuditLogTarget(TestCase):
    """Test cases for AUDIT_LOG_TARGET functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a main model (parent)
        cls.MainModel = create_dummy_model(
            base_name="MainModel",
            base_class=BaseModel,
            fields={
                "name": models.CharField(max_length=100),
            },
        )

        # Create a dependent model with AUDIT_LOG_TARGET
        cls.DependentModel = create_dummy_model(
            base_name="DependentModel",
            base_class=BaseModel,
            fields={
                "description": models.CharField(max_length=200),
                "main_object": models.ForeignKey(
                    cls.MainModel,
                    on_delete=models.CASCADE,
                    related_name="dependents",
                ),
            },
        )

        # Set AUDIT_LOG_TARGET on the dependent model
        cls.DependentModel.AUDIT_LOG_TARGET = cls.MainModel

        # Register both models
        audit_logging_register(cls.MainModel)
        audit_logging_register(cls.DependentModel)

        # Create database tables for the dynamic models
        from django.db import connection
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
        
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.MainModel)
            schema_editor.create_model(cls.DependentModel)
        
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')

    @classmethod
    def tearDownClass(cls):
        # Drop the tables after tests
        from django.db import connection
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
        
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.DependentModel)
            schema_editor.delete_model(cls.MainModel)
        
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')
        
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        _clear_delete_context()

    def tearDown(self):
        _clear_delete_context()

    def test_audit_log_target_registration(self):
        """Test that AUDIT_LOG_TARGET is properly registered."""
        target = AuditLogRegistry.get_audit_log_target(self.DependentModel)
        self.assertEqual(target, self.MainModel)

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_dependent_create_logs_under_target(self, mock_log_event):
        """Test that creating a dependent object logs under the target model."""
        # Create main object
        main_obj = self.MainModel.objects.create(name="Main Object")
        mock_log_event.reset_mock()

        # Create dependent object
        dependent = self.DependentModel.objects.create(
            description="Dependent Description",
            main_object=main_obj,
        )

        # Verify log was created
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Should log as CHANGE to main object (not ADD to dependent)
        self.assertEqual(call_args["action"], LogAction.CHANGE)

        # Should include source metadata
        self.assertIn("source_model", call_args)
        self.assertEqual(call_args["source_model"], self.DependentModel._meta.model_name)
        self.assertIn("source_pk", call_args)
        self.assertEqual(call_args["source_pk"], str(dependent.pk))
        self.assertIn("source_repr", call_args)

        # Change message should mention the dependent
        self.assertIn("change_message", call_args)
        self.assertIn("Added", call_args["change_message"])

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_dependent_update_logs_under_target(self, mock_log_event):
        """Test that updating a dependent object logs under the target model."""
        # Create main object and dependent
        main_obj = self.MainModel.objects.create(name="Main Object")
        dependent = self.DependentModel.objects.create(
            description="Original Description",
            main_object=main_obj,
        )
        mock_log_event.reset_mock()

        # Update dependent
        dependent.description = "Updated Description"
        dependent.save()

        # Verify log was created
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Should log as CHANGE to main object
        self.assertEqual(call_args["action"], LogAction.CHANGE)
        self.assertIn("source_model", call_args)
        self.assertIn("Modified", call_args["change_message"])

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_dependent_delete_logs_under_target(self, mock_log_event):
        """Test that deleting a dependent object logs under the target model."""
        # Create main object and dependent
        main_obj = self.MainModel.objects.create(name="Main Object")
        dependent = self.DependentModel.objects.create(
            description="Description",
            main_object=main_obj,
        )
        mock_log_event.reset_mock()

        # Delete dependent
        dependent.delete()

        # Verify log was created
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Should log as CHANGE to main object (not DELETE)
        self.assertEqual(call_args["action"], LogAction.CHANGE)
        self.assertIn("source_model", call_args)
        self.assertIn("Deleted", call_args["change_message"])

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_cascade_delete_prevents_duplicate_logs(self, mock_log_event):
        """Test that cascade deleting main object doesn't log dependent deletes."""
        # Create main object with dependent
        main_obj = self.MainModel.objects.create(name="Main Object")
        dependent = self.DependentModel.objects.create(
            description="Description",
            main_object=main_obj,
        )
        mock_log_event.reset_mock()

        # Delete main object (should cascade to dependent)
        main_obj.delete()

        # Should only have ONE log call (for main object delete)
        # The dependent's delete should be skipped as cascade
        self.assertEqual(mock_log_event.call_count, 1)

        call_args = mock_log_event.call_args[1]
        # The single log should be for the main object deletion
        self.assertEqual(call_args["action"], LogAction.DELETE)
        # Should not have source_model (this is the main object, not dependent)
        self.assertNotIn("source_model", call_args)


@override_settings(AUDIT_LOG_DISABLED=False)
class TestAuditLogTargetStringReference(TestCase):
    """Test AUDIT_LOG_TARGET with string references."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ParentModel = create_dummy_model(
            base_name="ParentModel",
            base_class=BaseModel,
            fields={
                "title": models.CharField(max_length=100),
            },
        )

        cls.ChildModel = create_dummy_model(
            base_name="ChildModel",
            base_class=BaseModel,
            fields={
                "note": models.CharField(max_length=200),
                "parent": models.ForeignKey(
                    cls.ParentModel,
                    on_delete=models.CASCADE,
                ),
            },
        )

        cls.ChildModel.AUDIT_LOG_TARGET = cls.ParentModel

        audit_logging_register(cls.ParentModel)
        audit_logging_register(cls.ChildModel)

        # Create database tables for the dynamic models
        from django.db import connection
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
        
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.ParentModel)
            schema_editor.create_model(cls.ChildModel)
        
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')

    @classmethod
    def tearDownClass(cls):
        # Drop the tables after tests
        from django.db import connection
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
        
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.ChildModel)
            schema_editor.delete_model(cls.ParentModel)
        
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')
        
        super().tearDownClass()

    def test_string_reference_resolved(self):
        """Test that string reference to AUDIT_LOG_TARGET is resolved."""
        target = AuditLogRegistry.get_audit_log_target(self.ChildModel)
        self.assertEqual(target, self.ParentModel)


@override_settings(AUDIT_LOG_DISABLED=False)
class TestSimplifiedRelatedChanges(TestCase):
    """Test that related changes are no longer automatically collected."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ArticleModel = create_dummy_model(
            base_name="ArticleModel",
            base_class=BaseModel,
            fields={
                "title": models.CharField(max_length=100),
            },
        )

        cls.TagModel = create_dummy_model(
            base_name="TagModel",
            base_class=BaseModel,
            fields={
                "name": models.CharField(max_length=50),
            },
        )

        # Add M2M relationship
        cls.ArticleModel.add_to_class(
            "tags",
            models.ManyToManyField(cls.TagModel, related_name="articles"),
        )

        # Register models
        audit_logging_register(cls.ArticleModel)
        audit_logging_register(cls.TagModel)

        # Create database tables for the dynamic models
        from django.db import connection
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
        
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.ArticleModel)
            schema_editor.create_model(cls.TagModel)
            # Create M2M table
            for field in cls.ArticleModel._meta.get_fields():
                if field.many_to_many and not field.remote_field.through._meta.auto_created:
                    continue
                if field.many_to_many:
                    schema_editor.create_model(field.remote_field.through)
        
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')

    @classmethod
    def tearDownClass(cls):
        # Drop the tables after tests
        from django.db import connection
        
        # Disable foreign key checks for SQLite
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
        
        with connection.schema_editor() as schema_editor:
            # Drop M2M table
            for field in cls.ArticleModel._meta.get_fields():
                if field.many_to_many:
                    schema_editor.delete_model(field.remote_field.through)
            schema_editor.delete_model(cls.TagModel)
            schema_editor.delete_model(cls.ArticleModel)
        
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')
        
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_m2m_changes_not_automatically_logged(self, mock_log_event):
        """Test that M2M changes are NOT automatically logged in related_changes."""
        # Create article and tags
        article = self.ArticleModel.objects.create(title="Test Article")
        tag1 = self.TagModel.objects.create(name="Tag1")
        tag2 = self.TagModel.objects.create(name="Tag2")

        # Add tags to article
        article.tags.add(tag1, tag2)

        # Get the article again to have original vs modified state
        original = self.ArticleModel.objects.get(pk=article.pk)
        original.tags.add(tag1)  # Simulate having tag1 originally

        modified = self.ArticleModel.objects.get(pk=article.pk)
        modified.tags.add(tag1, tag2)  # Now has both tags

        mock_log_event.reset_mock()

        # Update article directly
        modified.title = "Updated Title"
        modified.save()

        # Verify log was created
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Should NOT have related_changes field
        self.assertNotIn("related_changes", call_args)

        # Change message should only contain direct field changes
        self.assertIn("change_message", call_args)
        change_msg = call_args["change_message"]
        if isinstance(change_msg, dict):
            # If it's structured, should only have title change
            rows = change_msg.get("rows", [])
            field_names = [row["field"] for row in rows]
            self.assertIn("title", [f.lower() for f in field_names])
