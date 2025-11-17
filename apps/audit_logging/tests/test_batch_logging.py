"""
Tests for batch audit logging functionality.

This module tests the batch_audit_context and related utilities for
efficient logging of bulk operations.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import models
from django.test import RequestFactory, TestCase, override_settings

from apps.audit_logging import AuditLogRegistry, LogAction, audit_logging_register, batch_audit_context
from libs.models import create_dummy_model

User = get_user_model()


@override_settings(AUDIT_LOG_DISABLED=False)
class TestBatchAuditContext(TestCase):
    """Test cases for the batch_audit_context context manager."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.TestBatchModel = create_dummy_model(
            base_name="TestBatchModel",
            fields={
                "name": models.CharField(max_length=100),
                "value": models.IntegerField(default=0),
            },
        )
        AuditLogRegistry.register(cls.TestBatchModel)

    def setUp(self):
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.factory = RequestFactory()

    def test_batch_context_provides_metadata(self):
        """Test that batch context provides metadata for individual logs."""
        request = self.factory.post("/api/import/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "Test User Agent"

        with batch_audit_context(
            action=LogAction.IMPORT,
            model_class=self.TestBatchModel,
            user=self.user,
            request=request,
            import_source="test.xlsx",
        ) as batch:
            # Get the metadata that would be attached to individual logs
            metadata = batch.get_metadata()

            # Verify metadata contains batch information
            self.assertIn("batch_id", metadata)
            self.assertEqual(metadata["batch_action"], LogAction.IMPORT)
            self.assertEqual(metadata["import_source"], "test.xlsx")

            # Verify batch_id is a valid UUID
            self.assertEqual(len(batch.batch_id), 36)  # UUID format

    @patch("apps.audit_logging.batch._audit_producer.log_event")
    def test_batch_context_with_errors_logs_summary(self, mock_log_event):
        """Test that batch context logs a summary when there are errors."""
        with batch_audit_context(
            action=LogAction.IMPORT,
            model_class=self.TestBatchModel,
            user=self.user,
            request=None,
        ) as batch:
            # Track processed objects
            for i in range(3):
                batch.increment_count()

            # Add some errors
            batch.add_error("Failed to parse row 5")
            batch.add_error("Duplicate entry at row 7")

        # Verify summary log was created (only when there are errors)
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        self.assertEqual(call_args["action"], LogAction.IMPORT)
        self.assertTrue(call_args.get("batch_summary"))
        self.assertEqual(call_args["total_processed"], 3)
        self.assertEqual(call_args["error_count"], 2)
        self.assertIn("with 2 error(s)", call_args["change_message"])
        self.assertEqual(len(call_args["errors"]), 2)

    def test_batch_context_export_action_metadata(self):
        """Test batch context with EXPORT action provides correct metadata."""
        request = self.factory.get("/api/export/")
        request.user = self.user

        with batch_audit_context(
            action=LogAction.EXPORT,
            model_class=self.TestBatchModel,
            user=self.user,
            request=request,
            export_format="xlsx",
            export_filters={"active": True},
        ) as batch:
            metadata = batch.get_metadata()

            self.assertEqual(metadata["batch_action"], LogAction.EXPORT)
            self.assertEqual(metadata["export_format"], "xlsx")
            self.assertEqual(metadata["export_filters"], {"active": True})
            self.assertIn("batch_id", metadata)

    def test_batch_context_without_errors_no_summary(self):
        """Test batch context without errors doesn't log a summary."""
        with patch("apps.audit_logging.batch._audit_producer.log_event") as mock_log_event:
            with batch_audit_context(
                action=LogAction.IMPORT,
                model_class=self.TestBatchModel,
                user=self.user,
                request=None,
            ) as batch:
                # Process some objects but no errors
                for i in range(5):
                    batch.increment_count()

            # No summary log should be created when there are no errors
            mock_log_event.assert_not_called()

    @patch("apps.audit_logging.batch._audit_producer.log_event")
    def test_batch_context_limits_errors_in_summary(self, mock_log_event):
        """Test that batch context limits the number of errors in summary log."""
        with batch_audit_context(
            action=LogAction.IMPORT,
            model_class=self.TestBatchModel,
            user=self.user,
            request=None,
        ) as batch:
            # Add more than 20 errors
            for i in range(25):
                batch.add_error(f"Error {i}")

        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Verify error count is correct but logged errors are limited
        self.assertEqual(call_args["error_count"], 25)
        self.assertEqual(len(call_args["errors"]), 20)  # Limited to first 20


@override_settings(AUDIT_LOG_DISABLED=False)
class TestBatchWithDecorator(TestCase):
    """Test that batch context works with the @audit_logging decorator."""

    def setUp(self):
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.factory = RequestFactory()

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_batch_context_creates_individual_logs_with_metadata(self, mock_log_event):
        """Test that individual logs ARE created with batch metadata attached."""

        from django.db.models.signals import post_save

        from apps.audit_logging.middleware import audit_context

        # Create and register a decorated model
        BatchDecoratedModel = create_dummy_model(
            base_name="BatchDecoratedModel",
            fields={"name": models.CharField(max_length=100)},
        )
        BatchDecoratedModel = audit_logging_register(BatchDecoratedModel)

        request = self.factory.post("/api/import/")
        request.user = self.user

        with audit_context(request):
            with batch_audit_context(
                action=LogAction.IMPORT,
                model_class=BatchDecoratedModel,
                user=self.user,
                request=request,
                import_source="test.xlsx",
            ) as batch:
                # Simulate saving objects (trigger signals)
                for i in range(3):
                    instance = BatchDecoratedModel(name=f"Test {i}")
                    instance.pk = i + 1

                    # Manually trigger signal
                    post_save.send(sender=BatchDecoratedModel, instance=instance, created=True)

        # Verify individual logs WERE created (3 objects = 3 logs)
        self.assertEqual(mock_log_event.call_count, 3)

        # Verify each log has batch metadata
        for call in mock_log_event.call_args_list:
            call_args = call[1]
            self.assertIn("batch_id", call_args)
            self.assertEqual(call_args["batch_action"], LogAction.IMPORT)
            self.assertEqual(call_args["import_source"], "test.xlsx")
