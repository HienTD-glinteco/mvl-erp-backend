"""
Tests for PermissionSchemaMixin and x-permissions OpenAPI extension.

These tests verify that x-permissions is automatically generated for ViewSet
CRUD actions based on the permission_prefix configuration, aligned with
PermissionRegistrationMixin.get_registered_permissions().
"""

import pytest

from libs.drf.spectacular.permission_schema import PermissionSchemaMixin


class MockViewSet(PermissionSchemaMixin):
    """Mock ViewSet for testing with STANDARD_ACTIONS like PermissionRegistrationMixin."""

    permission_prefix = "project"
    action = None

    # Simulate STANDARD_ACTIONS from PermissionRegistrationMixin
    STANDARD_ACTIONS: dict[str, dict] = {
        "list": {},
        "retrieve": {},
        "create": {},
        "update": {},
        "partial_update": {},
        "destroy": {},
        "export": {},
        "histories": {},
        "history_detail": {},
    }

    PERMISSION_REGISTERED_ACTIONS: dict[str, dict] = {}


class TestPermissionSchemaMixin:
    """Test cases for PermissionSchemaMixin."""

    @pytest.fixture
    def viewset(self):
        """Create a mock viewset for testing."""
        return MockViewSet()

    def test_list_action_generates_permission(self, viewset):
        """Test that list action generates correct permission code."""
        viewset.action = "list"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.list"]

    def test_retrieve_action_generates_permission(self, viewset):
        """Test that retrieve action generates correct permission code."""
        viewset.action = "retrieve"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.retrieve"]

    def test_create_action_generates_permission(self, viewset):
        """Test that create action generates correct permission code."""
        viewset.action = "create"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.create"]

    def test_update_action_generates_permission(self, viewset):
        """Test that update action generates correct permission code."""
        viewset.action = "update"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.update"]

    def test_partial_update_action_generates_permission(self, viewset):
        """Test that partial_update action generates correct permission code."""
        viewset.action = "partial_update"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.partial_update"]

    def test_destroy_action_generates_permission(self, viewset):
        """Test that destroy action generates correct permission code."""
        viewset.action = "destroy"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.destroy"]

    def test_export_action_generates_permission(self, viewset):
        """Test that export action (standard) generates correct permission code."""
        viewset.action = "export"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.export"]

    def test_histories_action_generates_permission(self, viewset):
        """Test that histories action generates correct permission code."""
        viewset.action = "histories"
        extensions = viewset.get_schema_operation_extensions()

        assert "x-permissions" in extensions
        assert extensions["x-permissions"] == ["project.histories"]

    def test_custom_action_returns_empty_extensions(self, viewset):
        """Test that custom actions not in STANDARD_ACTIONS return empty extensions."""
        viewset.action = "custom_action"
        extensions = viewset.get_schema_operation_extensions()

        assert extensions == {}

    def test_no_action_returns_empty_extensions(self, viewset):
        """Test that no action returns empty extensions."""
        viewset.action = None
        extensions = viewset.get_schema_operation_extensions()

        assert extensions == {}

    def test_no_permission_prefix_returns_empty_extensions(self, viewset):
        """Test that no permission_prefix returns empty extensions."""
        viewset.action = "list"
        viewset.permission_prefix = ""
        extensions = viewset.get_schema_operation_extensions()

        assert extensions == {}

    def test_registered_action_generates_permission(self):
        """Test that registered custom actions generate permission codes."""

        class ViewSetWithRegisteredActions(PermissionSchemaMixin):
            permission_prefix = "employee"
            action = "approve"
            STANDARD_ACTIONS = {"list": {}, "retrieve": {}}
            PERMISSION_REGISTERED_ACTIONS = {
                "approve": {"name_template": "Approve", "description_template": "Approve employee"},
                "reject": {"name_template": "Reject", "description_template": "Reject employee"},
            }

        viewset = ViewSetWithRegisteredActions()
        extensions = viewset.get_schema_operation_extensions()

        assert extensions["x-permissions"] == ["employee.approve"]

    def test_permission_format_follows_rbac_pattern(self):
        """Test that permission format follows {permission_prefix}.{action} pattern."""

        class EmployeeViewSet(PermissionSchemaMixin):
            permission_prefix = "hrm_employee"
            STANDARD_ACTIONS = {
                "list": {},
                "retrieve": {},
                "create": {},
                "update": {},
                "partial_update": {},
                "destroy": {},
            }
            PERMISSION_REGISTERED_ACTIONS = {}

        viewset = EmployeeViewSet()

        # Test all CRUD actions follow the pattern
        expected_permissions = {
            "list": "hrm_employee.list",
            "retrieve": "hrm_employee.retrieve",
            "create": "hrm_employee.create",
            "update": "hrm_employee.update",
            "partial_update": "hrm_employee.partial_update",
            "destroy": "hrm_employee.destroy",
        }

        for action, expected_permission in expected_permissions.items():
            viewset.action = action
            extensions = viewset.get_schema_operation_extensions()
            assert extensions["x-permissions"] == [expected_permission], f"Failed for action: {action}"


class TestPermissionSchemaMixinWithoutStandardActions:
    """Test cases for PermissionSchemaMixin when STANDARD_ACTIONS is not defined."""

    def test_without_standard_actions_returns_empty(self):
        """Test that viewset without STANDARD_ACTIONS returns empty for standard actions."""

        class ViewSetWithoutStandardActions(PermissionSchemaMixin):
            permission_prefix = "test"
            action = "list"
            # No STANDARD_ACTIONS defined

        viewset = ViewSetWithoutStandardActions()
        extensions = viewset.get_schema_operation_extensions()

        # Without STANDARD_ACTIONS, even "list" is not recognized
        assert extensions == {}

    def test_with_only_registered_actions(self):
        """Test that viewset with only registered actions works."""

        class ViewSetWithOnlyRegistered(PermissionSchemaMixin):
            permission_prefix = "custom"
            action = "special_action"
            STANDARD_ACTIONS = {}
            PERMISSION_REGISTERED_ACTIONS = {"special_action": {}}

        viewset = ViewSetWithOnlyRegistered()
        extensions = viewset.get_schema_operation_extensions()

        assert extensions["x-permissions"] == ["custom.special_action"]
