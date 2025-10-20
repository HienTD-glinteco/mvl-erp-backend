"""
Tests for automatic audit logging functionality.

This module tests the decorator, middleware, and refactored log_audit_event function.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.test import RequestFactory, TestCase, override_settings

from apps.audit_logging import LogAction, audit_logging_register, log_audit_event
from apps.audit_logging.middleware import audit_context, get_current_request, get_current_user, set_current_request
from libs.models import create_dummy_model

User = get_user_model()


@override_settings(AUDIT_LOG_DISABLED=False)
class TestLogAuditEvent(TestCase):
    """Test cases for the refactored log_audit_event function."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.TestModel = create_dummy_model(
            base_name="TestLogAuditEventModel",
            fields={
                "name": models.CharField(max_length=100),
                "value": models.IntegerField(default=0),
            },
        )

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.factory = RequestFactory()

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_log_audit_event_with_all_parameters(self, mock_log_event):
        """Test log_audit_event with all parameters provided."""

        # Create a test object
        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1  # Simulate saved object

        # Create a mock request
        request = self.factory.get("/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "Test User Agent"

        # Call log_audit_event
        log_audit_event(
            action=LogAction.ADD,
            original_object=None,
            modified_object=test_obj,
            user=self.user,
            request=request,
        )

        # Verify log_event was called
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Verify the logged data
        self.assertEqual(call_args["action"], LogAction.ADD)
        self.assertEqual(call_args["object_type"], self.TestModel._meta.model_name)
        self.assertEqual(call_args["object_id"], "1")
        self.assertEqual(call_args["object_repr"], str(test_obj))
        self.assertEqual(call_args["user_id"], str(self.user.pk))
        self.assertEqual(call_args["username"], self.user.username)
        self.assertEqual(call_args["ip_address"], "192.168.1.1")
        self.assertEqual(call_args["user_agent"], "Test User Agent")
        self.assertIn("change_message", call_args)

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_log_audit_event_with_employee_info(self, mock_log_event):
        """Test that employee department and position info is captured."""
        from datetime import date

        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department, Employee, OrganizationChart, Position

        # Create organizational structure
        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Admin Unit",
            code="TAU",
            parent_province=province,
            level="district",
        )
        branch = Branch.objects.create(
            name="Test Branch",
            code="TB01",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            name="Test Block",
            code="BL01",
            block_type="support",
            branch=branch,
        )
        department = Department.objects.create(
            name="Test Department",
            code="TD01",
            branch=branch,
            block=block,
        )

        # Create employee
        employee = Employee.objects.create(
            code="MV001",
            fullname="Test User Full Name",
            username="testuser_emp",
            email="testuser_emp@example.com",
            department=department,
        )
        employee.user = self.user
        employee.save()

        # Create position
        position = Position.objects.create(
            name="Test Position",
            code="TP01",
        )

        # Create organization chart entry
        OrganizationChart.objects.create(
            employee=self.user,
            position=position,
            department=department,
            start_date=date.today(),
            is_primary=True,
            is_active=True,
        )

        # Create a test object
        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1

        # Create a mock request
        request = self.factory.get("/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Call log_audit_event
        log_audit_event(
            action=LogAction.ADD,
            original_object=None,
            modified_object=test_obj,
            user=self.user,
            request=request,
        )

        # Verify log_event was called with department and position info
        # The last call should be for our test object
        self.assertTrue(mock_log_event.called)
        call_args = mock_log_event.call_args[1]

        # Verify employee fields
        self.assertEqual(call_args["employee_code"], "MV001")
        self.assertEqual(call_args["full_name"], "Test User Full Name")

        # Verify department fields
        self.assertEqual(call_args["department_id"], str(department.pk))
        self.assertEqual(call_args["department_name"], "Test Department")

        # Verify position fields
        self.assertEqual(call_args["position_id"], str(position.pk))
        self.assertEqual(call_args["position_name"], "Test Position")

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_log_audit_event_without_request(self, mock_log_event):
        """Test log_audit_event without request context."""

        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1

        log_audit_event(
            action=LogAction.CHANGE,
            original_object=test_obj,
            modified_object=test_obj,
            user=self.user,
            request=None,
        )

        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Verify basic data is present
        self.assertEqual(call_args["action"], LogAction.CHANGE)
        self.assertEqual(call_args["user_id"], str(self.user.pk))

        # Verify request-specific data is not present
        self.assertNotIn("ip_address", call_args)
        self.assertNotIn("user_agent", call_args)

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_log_audit_event_delete_action(self, mock_log_event):
        """Test log_audit_event for DELETE action."""

        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1

        log_audit_event(
            action=LogAction.DELETE,
            original_object=test_obj,
            modified_object=None,
            user=self.user,
            request=None,
        )

        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        self.assertEqual(call_args["action"], LogAction.DELETE)
        self.assertEqual(call_args["change_message"], "Deleted object")

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_log_audit_event_with_x_forwarded_for(self, mock_log_event):
        """Test IP address extraction with X-Forwarded-For header."""

        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1

        request = self.factory.get("/")
        request.user = self.user
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 192.168.1.1"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        log_audit_event(
            action=LogAction.ADD,
            original_object=None,
            modified_object=test_obj,
            user=self.user,
            request=request,
        )

        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Should extract the first IP from X-Forwarded-For
        self.assertEqual(call_args["ip_address"], "10.0.0.1")

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_log_audit_event_with_extra_kwargs(self, mock_log_event):
        """Test log_audit_event with additional custom fields."""

        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1

        log_audit_event(
            action=LogAction.IMPORT,
            original_object=None,
            modified_object=test_obj,
            user=self.user,
            request=None,
            custom_field="custom_value",
            import_source="excel_file.xlsx",
        )

        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        # Verify extra kwargs are included
        self.assertEqual(call_args["custom_field"], "custom_value")
        self.assertEqual(call_args["import_source"], "excel_file.xlsx")


@override_settings(AUDIT_LOG_DISABLED=False)
class TestAuditContext(TestCase):
    """Test cases for the audit context functionality."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

    def test_context_manager_stores_request(self):
        """Test that context manager stores request in thread-local storage."""
        request = self.factory.get("/")
        request.user = self.user

        with audit_context(request):
            # Verify request is available
            current_request = get_current_request()
            self.assertIsNotNone(current_request)
            self.assertEqual(current_request, request)

            # Verify user is available
            current_user = get_current_user()
            self.assertIsNotNone(current_user)
            self.assertEqual(current_user, self.user)

        # Verify request is cleaned up after context
        current_request = get_current_request()
        self.assertIsNone(current_request)

    def test_context_manager_cleans_up_on_exception(self):
        """Test that context manager cleans up request on exception."""
        request = self.factory.get("/")
        request.user = self.user

        try:
            with audit_context(request):
                # Verify request is available
                current_request = get_current_request()
                self.assertIsNotNone(current_request)

                # Raise exception
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify request is cleaned up even after exception
        current_request = get_current_request()
        self.assertIsNone(current_request)

    def test_set_current_request_directly(self):
        """Test setting request directly using set_current_request."""
        request = self.factory.get("/")
        request.user = self.user

        set_current_request(request)

        # Verify request is available
        current_request = get_current_request()
        self.assertIsNotNone(current_request)
        self.assertEqual(current_request, request)

    def test_get_current_user_without_request(self):
        """Test get_current_user when no request is available."""
        current_user = get_current_user()
        self.assertIsNone(current_user)

    def test_get_current_user_without_user_attribute(self):
        """Test get_current_user when request has no user."""
        request = self.factory.get("/")
        # Don't set request.user

        with audit_context(request):
            current_user = get_current_user()
            self.assertIsNone(current_user)


@override_settings(AUDIT_LOG_DISABLED=False)
class TestAuditLoggingDecorator(TestCase):
    """Test cases for the @audit_logging decorator."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.factory = RequestFactory()

        self.DecoratedModel = create_dummy_model(
            base_name="TestAuditLoggingDecoratorModel",
            fields={"name": models.CharField(max_length=100)},
        )
        self.DecoratedModel = audit_logging_register(self.DecoratedModel)

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_decorator_logs_create(self, mock_log_event):
        """Test that decorator logs object creation."""

        # Set up request context using context manager
        request = self.factory.post("/")
        request.user = self.user

        instance = self.DecoratedModel(name="Test")
        instance.pk = 1

        # Manually trigger post_save signal
        post_save.send(sender=self.DecoratedModel, instance=instance, created=True)

        # Verify log_event was called
        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args[1]

        self.assertEqual(call_args["action"], LogAction.ADD)

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_decorator_logs_update(self, mock_log_event):
        """Test that decorator logs object updates."""

        # Set up request context using context manager
        request = self.factory.post("/")
        request.user = self.user

        with audit_context(request):
            # Create instances
            instance = self.DecoratedModel(name="Updated")
            instance.pk = 1

            # Manually trigger post_save signal with created=False
            post_save.send(sender=self.DecoratedModel, instance=instance, created=False)

            # Verify log_event was called
            mock_log_event.assert_called_once()
            call_args = mock_log_event.call_args[1]

            self.assertEqual(call_args["action"], LogAction.CHANGE)

    @patch("apps.audit_logging.producer._audit_producer.log_event")
    def test_decorator_logs_delete(self, mock_log_event):
        """Test that decorator logs object deletion."""

        # Set up request context using context manager
        request = self.factory.post("/")
        request.user = self.user

        with audit_context(request):
            # Create instance
            instance = self.DecoratedModel(name="Test")
            instance.pk = 1

            # Manually trigger post_delete signal
            post_delete.send(sender=self.DecoratedModel, instance=instance)

            # Verify log_event was called
            mock_log_event.assert_called_once()
            call_args = mock_log_event.call_args[1]

            self.assertEqual(call_args["action"], LogAction.DELETE)


@override_settings(AUDIT_LOG_DISABLED=False)
class TestLogActionEnum(TestCase):
    """Test cases for the LogAction enum."""

    def test_log_action_values(self):
        """Test that LogAction enum has all required values."""
        self.assertEqual(LogAction.ADD, "ADD")
        self.assertEqual(LogAction.CHANGE, "CHANGE")
        self.assertEqual(LogAction.DELETE, "DELETE")
        self.assertEqual(LogAction.IMPORT, "IMPORT")
        self.assertEqual(LogAction.EXPORT, "EXPORT")

    def test_log_action_labels(self):
        """Test that LogAction enum has proper labels."""
        self.assertIsNotNone(LogAction.ADD.label)
        self.assertIsNotNone(LogAction.CHANGE.label)
        self.assertIsNotNone(LogAction.DELETE.label)
        self.assertIsNotNone(LogAction.IMPORT.label)
        self.assertIsNotNone(LogAction.EXPORT.label)

    def test_log_action_choices(self):
        """Test that LogAction can be used as choices in a model field."""
        choices = LogAction.choices
        self.assertEqual(len(choices), 8)
        self.assertIn(("ADD", LogAction.ADD.label), choices)


@override_settings(AUDIT_LOG_DISABLED=True)
class TestAuditLogDisabled(TestCase):
    """Test cases for AUDIT_LOG_DISABLED setting."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.TestModel = create_dummy_model(
            base_name="TestAuditLogDisabledModel",
            fields={
                "name": models.CharField(max_length=100),
                "value": models.IntegerField(default=0),
            },
        )

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.factory = RequestFactory()

    @patch("asyncio.run")
    def test_log_event_writes_to_file_but_not_rabbitmq_when_disabled(self, mock_asyncio_run):
        """Test that when AUDIT_LOG_DISABLED=True, logs are written to file but not sent to RabbitMQ."""
        test_obj = self.TestModel(name="Test", value=42)
        test_obj.pk = 1

        # Call log_audit_event
        log_audit_event(
            action=LogAction.ADD,
            original_object=None,
            modified_object=test_obj,
            user=self.user,
        )

        # Verify asyncio.run was NOT called (RabbitMQ send should not happen when disabled)
        mock_asyncio_run.assert_not_called()

    @patch("asyncio.run")
    def test_log_event_directly_respects_disabled_setting(self, mock_asyncio_run):
        """Test that AuditStreamProducer.log_event respects AUDIT_LOG_DISABLED setting."""
        from apps.audit_logging.producer import _audit_producer

        # Call log_event directly
        _audit_producer.log_event(
            action=LogAction.ADD,
            object_type="test_model",
            object_id="1",
            object_repr="Test Object",
        )

        # Verify asyncio.run was NOT called (RabbitMQ send should not happen when disabled)
        mock_asyncio_run.assert_not_called()
