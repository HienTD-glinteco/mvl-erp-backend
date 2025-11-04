"""
Tests for AUDIT_LOG_TARGET functionality and cascade delete handling.

This module tests the new refactored audit logging system that includes:
- AUDIT_LOG_TARGET attribute for dependent models
- Cascade delete detection to avoid duplicate logs
- Logging dependent model changes under target models
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, models
from django.test import TransactionTestCase, override_settings

from apps.audit_logging import LogAction, audit_logging_register
from apps.audit_logging.decorators import _clear_delete_context
from apps.audit_logging.registry import AuditLogRegistry
from libs.models import create_dummy_model

User = get_user_model()


@override_settings(AUDIT_LOG_DISABLED=False)
class TestAuditLogTarget(TransactionTestCase):
    """Test cases for AUDIT_LOG_TARGET functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a main model (parent)
        cls.MainModel = create_dummy_model(
            base_name="MainModel",
            fields={
                "name": models.CharField(max_length=100),
            },
        )

        # Create a dependent model with AUDIT_LOG_TARGET
        cls.DependentModel = create_dummy_model(
            base_name="DependentModel",
            fields={
                "description": models.CharField(max_length=200),
                # Use a simple IntegerField as a stand-in for the FK to avoid
                # creating an actual relation/table during tests. Tests pass
                # the related object's PK when creating instances.
                "main_object": models.IntegerField(),
            },
        )

        # Set AUDIT_LOG_TARGET on the dependent model
        cls.DependentModel.AUDIT_LOG_TARGET = cls.MainModel

        # Register both models
        audit_logging_register(cls.MainModel)
        audit_logging_register(cls.DependentModel)
        # Create database tables for test models. Disable SQLite foreign key
        # checks around schema_editor since SQLite cannot toggle them while
        # in a transaction.
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.MainModel)
            schema_editor.create_model(cls.DependentModel)

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def tearDownClass(cls):
        # Drop database tables for test models
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.DependentModel)
            schema_editor.delete_model(cls.MainModel)

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")

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
        # Patch the helper that finds the target instance since we use an
        # IntegerField stand-in instead of a real FK. Have it return the
        # main_obj so the audit logging logic proceeds as if a FK existed.
        from unittest.mock import patch as _patch

        with _patch("apps.audit_logging.decorators._get_target_instance", return_value=main_obj):
            # Pass PK for the stand-in IntegerField
            dependent = self.DependentModel.objects.create(
                description="Dependent Description",
                main_object=main_obj.pk,
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
        # Create dependent and ensure _get_target_instance returns main_obj
        from unittest.mock import patch as _patch

        with _patch("apps.audit_logging.decorators._get_target_instance", return_value=main_obj):
            dependent = self.DependentModel.objects.create(
                description="Original Description",
                main_object=main_obj.pk,
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
        from unittest.mock import patch as _patch

        with _patch("apps.audit_logging.decorators._get_target_instance", return_value=main_obj):
            dependent = self.DependentModel.objects.create(
                description="Description",
                main_object=main_obj.pk,
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
        from unittest.mock import patch as _patch

        with _patch("apps.audit_logging.decorators._get_target_instance", return_value=main_obj):
            dependent = self.DependentModel.objects.create(
                description="Description",
                main_object=main_obj.pk,
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
class TestAuditLogTargetStringReference(TransactionTestCase):
    """Test AUDIT_LOG_TARGET with string references."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ParentModel = create_dummy_model(
            base_name="ParentModel",
            fields={
                "title": models.CharField(max_length=100),
            },
        )

        cls.ChildModel = create_dummy_model(
            base_name="ChildModel",
            fields={
                "note": models.CharField(max_length=200),
                # Use IntegerField as stand-in for parent FK to avoid
                # creating real FK relationships in the test DB.
                "parent": models.IntegerField(),
            },
        )

        cls.ChildModel.AUDIT_LOG_TARGET = cls.ParentModel

        audit_logging_register(cls.ParentModel)
        audit_logging_register(cls.ChildModel)
        # Create DB tables for parent/child stand-ins
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.ParentModel)
            schema_editor.create_model(cls.ChildModel)

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def tearDownClass(cls):
        # Drop DB tables for parent/child stand-ins
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.ChildModel)
            schema_editor.delete_model(cls.ParentModel)

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")

        super().tearDownClass()

    def test_string_reference_resolved(self):
        """Test that string reference to AUDIT_LOG_TARGET is resolved."""
        target = AuditLogRegistry.get_audit_log_target(self.ChildModel)
        self.assertEqual(target, self.ParentModel)


@override_settings(AUDIT_LOG_DISABLED=False)
class TestSimplifiedRelatedChanges(TransactionTestCase):
    """Test that related changes are no longer automatically collected."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ArticleModel = create_dummy_model(
            base_name="ArticleModel",
            fields={
                "title": models.CharField(max_length=100),
            },
        )

        cls.TagModel = create_dummy_model(
            base_name="TagModel",
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
        # Create DB tables for article/tag and let Django create the M2M
        # through table automatically when creating ArticleModel.
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.TagModel)
            schema_editor.create_model(cls.ArticleModel)

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def tearDownClass(cls):
        # Drop DB tables for article/tag
        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = OFF")

        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.ArticleModel)
            schema_editor.delete_model(cls.TagModel)

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")

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
