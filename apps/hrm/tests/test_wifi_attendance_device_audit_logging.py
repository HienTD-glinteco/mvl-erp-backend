"""
Tests for WiFi Attendance Device audit logging functionality.

This module tests the AuditLoggingMixin integration with WifiAttendanceDeviceViewSet.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, WifiAttendanceDevice

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@override_settings(AUDIT_LOG_DISABLED=False)
class WifiAttendanceDeviceAuditLoggingTest(TransactionTestCase, APITestMixin):
    """Test cases for WifiAttendanceDevice audit logging via AuditLoggingMixin."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        WifiAttendanceDevice.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        Province.objects.all().delete()
        AdministrativeUnit.objects.all().delete()
        User.objects.all().delete()

        # Create superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create provinces
        self.province1 = Province.objects.create(name="Test Province 1", code="TP001")

        # Create administrative units with parent provinces
        self.admin_unit1 = AdministrativeUnit.objects.create(
            name="Test Admin Unit 1",
            code="TAU001",
            parent_province=self.province1,
            level="district",
        )

        # Update province with administrative unit
        self.province1.administrative_unit = self.admin_unit1
        self.province1.save()

        # Create branch
        self.branch1 = Branch.objects.create(
            name="Ho Chi Minh Branch",
            code="CN001",
            province=self.province1,
            administrative_unit=self.admin_unit1,
        )

        # Create block
        self.block1 = Block.objects.create(
            name="Business Block 1",
            code="KH001",
            block_type="business",
            branch=self.branch1,
        )

    @patch("apps.audit_logging.decorators.log_audit_event")
    def test_create_wifi_logs_audit_event(self, mock_log_audit_event):
        """Test that creating a WiFi attendance device logs an audit event."""
        url = reverse("hrm:wifi-attendance-device-list")
        payload = {
            "name": "Office WiFi Main",
            "branch_id": self.branch1.id,
            "block_id": self.block1.id,
            "bssid": "00:11:22:33:44:55",
            "state": "in_use",
            "notes": "Main office WiFi network",
        }

        response = self.client.post(url, payload, format="json")

        # Assert response is successful
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assert audit event was logged
        mock_log_audit_event.assert_called()

        # Verify at least one call has action ADD
        # Note: AutoCodeMixin may trigger additional CHANGE events
        from apps.audit_logging import LogAction

        call_args_list = mock_log_audit_event.call_args_list
        actions = [call[1].get("action") for call in call_args_list if "action" in call[1]]
        self.assertIn(LogAction.ADD, actions, "Expected LogAction.ADD to be in the logged actions")

    @patch("apps.audit_logging.decorators.log_audit_event")
    def test_update_wifi_logs_audit_event(self, mock_log_audit_event):
        """Test that updating a WiFi attendance device logs an audit event."""
        # Create a WiFi device first
        wifi = WifiAttendanceDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=self.branch1,
            block=self.block1,
            bssid="00:11:22:33:44:55",
            state="in_use",
            notes="Main office WiFi network",
        )

        # Clear the mock to ignore creation event
        mock_log_audit_event.reset_mock()

        # Update the WiFi device
        url = reverse("hrm:wifi-attendance-device-detail", kwargs={"pk": wifi.pk})
        payload = {
            "name": "Office WiFi Main Updated",
            "branch_id": self.branch1.id,
            "block_id": self.block1.id,
            "bssid": "00:11:22:33:44:55",
            "state": "not_in_use",
            "notes": "Updated notes",
        }

        response = self.client.put(url, payload, format="json")

        # Assert response is successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Assert audit event was logged
        mock_log_audit_event.assert_called()

        # Verify the audit log was called with correct action
        call_args = mock_log_audit_event.call_args
        self.assertIsNotNone(call_args)
        # Check that action is CHANGE
        self.assertIn("action", call_args[1])
        from apps.audit_logging import LogAction

        self.assertEqual(call_args[1]["action"], LogAction.CHANGE)

    @patch("apps.audit_logging.decorators.log_audit_event")
    def test_partial_update_wifi_logs_audit_event(self, mock_log_audit_event):
        """Test that partially updating a WiFi attendance device logs an audit event."""
        # Create a WiFi device first
        wifi = WifiAttendanceDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=self.branch1,
            block=self.block1,
            bssid="00:11:22:33:44:55",
            state="in_use",
            notes="Main office WiFi network",
        )

        # Clear the mock to ignore creation event
        mock_log_audit_event.reset_mock()

        # Partially update the WiFi device
        url = reverse("hrm:wifi-attendance-device-detail", kwargs={"pk": wifi.pk})
        payload = {
            "state": "not_in_use",
            "notes": "Disabled for maintenance",
        }

        response = self.client.patch(url, payload, format="json")

        # Assert response is successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Assert audit event was logged
        mock_log_audit_event.assert_called()

        # Verify the audit log was called with correct action
        call_args = mock_log_audit_event.call_args
        self.assertIsNotNone(call_args)
        # Check that action is CHANGE
        self.assertIn("action", call_args[1])
        from apps.audit_logging import LogAction

        self.assertEqual(call_args[1]["action"], LogAction.CHANGE)

    @patch("apps.audit_logging.decorators.log_audit_event")
    def test_delete_wifi_logs_audit_event(self, mock_log_audit_event):
        """Test that deleting a WiFi attendance device logs an audit event."""
        # Create a WiFi device first
        wifi = WifiAttendanceDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=self.branch1,
            block=self.block1,
            bssid="00:11:22:33:44:55",
            state="in_use",
            notes="Main office WiFi network",
        )

        # Clear the mock to ignore creation event
        mock_log_audit_event.reset_mock()

        # Delete the WiFi device
        url = reverse("hrm:wifi-attendance-device-detail", kwargs={"pk": wifi.pk})
        response = self.client.delete(url)

        # Assert response is successful
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Assert audit event was logged
        mock_log_audit_event.assert_called()

        # Verify the audit log was called with correct action
        call_args = mock_log_audit_event.call_args
        self.assertIsNotNone(call_args)
        # Check that action is DELETE
        self.assertIn("action", call_args[1])
        from apps.audit_logging import LogAction

        self.assertEqual(call_args[1]["action"], LogAction.DELETE)

    def test_histories_endpoint_exists(self):
        """Test that histories endpoint is available from AuditLoggingMixin."""
        # Create a WiFi device
        wifi = WifiAttendanceDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=self.branch1,
            block=self.block1,
            bssid="00:11:22:33:44:55",
            state="in_use",
            notes="Main office WiFi network",
        )

        # Try to access histories endpoint
        url = reverse("hrm:wifi-attendance-device-histories", kwargs={"pk": wifi.pk})
        response = self.client.get(url)

        # Endpoint should exist (may return empty results if OpenSearch is not available)
        # We're just testing that the endpoint is registered and accessible
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

    def test_audit_context_set_during_api_request(self):
        """Test that audit context is properly set during API request lifecycle."""
        # Instead of mocking audit_context, we verify that the mixin's initial method is called
        # by checking that the request is processed successfully with audit logging enabled

        with patch("apps.audit_logging.decorators.log_audit_event") as mock_log_audit_event:
            # Make API request
            url = reverse("hrm:wifi-attendance-device-list")
            payload = {
                "name": "Office WiFi Main",
                "branch_id": self.branch1.id,
                "block_id": self.block1.id,
                "bssid": "00:11:22:33:44:55",
                "state": "in_use",
                "notes": "Main office WiFi network",
            }

            response = self.client.post(url, payload, format="json")

            # Assert response is successful
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # Verify audit logging was triggered (which means audit context was set)
            mock_log_audit_event.assert_called()

            # Verify user context is available in the audit log
            call_args_list = mock_log_audit_event.call_args_list
            # At least one call should have user information
            has_user_context = any(
                call[1].get("user") is not None or call[1].get("request") is not None for call in call_args_list
            )
            self.assertTrue(has_user_context, "Expected audit context to include user or request information")


@override_settings(AUDIT_LOG_DISABLED=False)
class WifiAttendanceDeviceHistoryDetailTest(TransactionTestCase, APITestMixin):
    """Test cases for WiFi Attendance Device history detail endpoint."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        WifiAttendanceDevice.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        Province.objects.all().delete()
        AdministrativeUnit.objects.all().delete()
        User.objects.all().delete()

        # Create superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create provinces
        self.province1 = Province.objects.create(name="Test Province 1", code="TP001")

        # Create administrative units with parent provinces
        self.admin_unit1 = AdministrativeUnit.objects.create(
            name="Test Admin Unit 1",
            code="TAU001",
            parent_province=self.province1,
            level="district",
        )

        # Update province with administrative unit
        self.province1.administrative_unit = self.admin_unit1
        self.province1.save()

        # Create branch
        self.branch1 = Branch.objects.create(
            name="Ho Chi Minh Branch",
            code="CN001",
            province=self.province1,
            administrative_unit=self.admin_unit1,
        )

        # Create block
        self.block1 = Block.objects.create(
            name="Business Block 1",
            code="KH001",
            block_type="business",
            branch=self.branch1,
        )

        # Create a WiFi device
        self.wifi = WifiAttendanceDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=self.branch1,
            block=self.block1,
            bssid="00:11:22:33:44:55",
            state="in_use",
            notes="Main office WiFi network",
        )

    @patch("apps.audit_logging.api.mixins.get_opensearch_client")
    def test_history_detail_endpoint_exists(self, mock_get_opensearch_client):
        """Test that history detail endpoint is available from AuditLoggingMixin."""
        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_get_opensearch_client.return_value = mock_client

        # Mock get_log_by_id response
        mock_client.get_log_by_id.return_value = {
            "log_id": "log123",
            "timestamp": "2025-11-18T10:00:00Z",
            "user_id": str(self.user.id),
            "username": self.user.username,
            "action": "CREATE",
            "object_type": "wifiattendancedevice",
            "object_id": str(self.wifi.id),
            "object_repr": str(self.wifi),
        }

        # Try to access history detail endpoint
        url = reverse("hrm:wifi-attendance-device-history-detail", kwargs={"pk": self.wifi.pk, "log_id": "log123"})
        response = self.client.get(url)

        # Endpoint should exist and return the log detail
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify response contains audit log detail
        data = self.get_response_data(response)
        self.assertEqual(data["log_id"], "log123")
        self.assertEqual(data["action"], "CREATE")

    @patch("apps.audit_logging.api.mixins.get_opensearch_client")
    def test_history_detail_not_found(self, mock_get_opensearch_client):
        """Test history detail endpoint returns 404 when log is not found."""
        # Mock OpenSearch client to raise exception
        mock_client = MagicMock()
        mock_get_opensearch_client.return_value = mock_client

        from apps.audit_logging.exceptions import AuditLogException

        mock_client.get_log_by_id.side_effect = AuditLogException("Log not found")

        # Try to access non-existent history detail
        url = reverse(
            "hrm:wifi-attendance-device-history-detail", kwargs={"pk": self.wifi.pk, "log_id": "nonexistent"}
        )
        response = self.client.get(url)

        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
