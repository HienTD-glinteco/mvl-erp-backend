"""
Tests for BaseModelViewSet automatic permission registration.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from rest_framework import viewsets
from rest_framework.decorators import action

from apps.core.models import Permission
from libs.base_viewset import BaseModelViewSet


# Test fixtures - Mock ViewSets for testing
class MockModel:
    """Mock model for testing"""

    class _meta:
        verbose_name = "Test Item"
        verbose_name_plural = "Test Items"


class SimpleTestViewSet(BaseModelViewSet):
    """Simple test viewset with all standard actions"""

    class MockQuerySet:
        model = MockModel

    queryset = MockQuerySet()
    module = "Test Module"
    submodule = "Test Submodule"
    permission_prefix = "test_item"


class ViewSetWithCustomActions(BaseModelViewSet):
    """Test viewset with custom actions"""

    class MockQuerySet:
        model = MockModel

    queryset = MockQuerySet()
    module = "Test Module"
    submodule = "Custom Actions"
    permission_prefix = "custom_test"

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Custom approve action"""
        pass

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Custom statistics action"""
        pass


class ViewSetWithoutPrefix(BaseModelViewSet):
    """Test viewset without permission_prefix - should not generate permissions"""

    class MockQuerySet:
        model = MockModel

    queryset = MockQuerySet()
    module = "Test Module"
    submodule = "No Prefix"
    # No permission_prefix - should be skipped


class BaseModelViewSetTestCase(TestCase):
    """Test BaseModelViewSet permission generation"""

    def test_get_model_name(self):
        """Test get_model_name returns correct model name"""
        # Act
        model_name = SimpleTestViewSet.get_model_name()

        # Assert
        self.assertEqual(model_name, "Test Item")

    def test_get_model_name_plural(self):
        """Test get_model_name_plural returns correct plural name"""
        # Act
        model_name_plural = SimpleTestViewSet.get_model_name_plural()

        # Assert
        self.assertEqual(model_name_plural, "Test Items")

    def test_get_custom_actions(self):
        """Test get_custom_actions returns all custom actions"""
        # Act
        custom_actions = ViewSetWithCustomActions.get_custom_actions()

        # Assert
        self.assertIn("approve", custom_actions)
        self.assertIn("statistics", custom_actions)
        # Standard actions should not be included
        self.assertNotIn("list", custom_actions)
        self.assertNotIn("create", custom_actions)

    def test_get_registered_permissions_standard_actions(self):
        """Test get_registered_permissions generates permissions for standard actions"""
        # Act
        permissions = SimpleTestViewSet.get_registered_permissions()

        # Assert
        self.assertEqual(len(permissions), 6)  # 6 standard actions

        # Extract permission codes
        codes = [p["code"] for p in permissions]
        self.assertIn("test_item.list", codes)
        self.assertIn("test_item.retrieve", codes)
        self.assertIn("test_item.create", codes)
        self.assertIn("test_item.update", codes)
        self.assertIn("test_item.partial_update", codes)
        self.assertIn("test_item.destroy", codes)

    def test_permission_metadata_structure(self):
        """Test permission metadata has correct structure"""
        # Act
        permissions = SimpleTestViewSet.get_registered_permissions()

        # Assert
        for perm in permissions:
            self.assertIn("code", perm)
            self.assertIn("name", perm)
            self.assertIn("description", perm)
            self.assertIn("module", perm)
            self.assertIn("submodule", perm)

    def test_permission_metadata_values(self):
        """Test permission metadata contains correct values"""
        # Act
        permissions = SimpleTestViewSet.get_registered_permissions()
        list_perm = next(p for p in permissions if p["code"] == "test_item.list")

        # Assert
        self.assertEqual(list_perm["module"], "Test Module")
        self.assertEqual(list_perm["submodule"], "Test Submodule")
        self.assertIn("List", list_perm["name"])
        self.assertIn("Test Items", list_perm["name"])  # Should use plural

    def test_custom_actions_generate_permissions(self):
        """Test custom actions generate permissions"""
        # Act
        permissions = ViewSetWithCustomActions.get_registered_permissions()

        # Assert
        codes = [p["code"] for p in permissions]
        self.assertIn("custom_test.approve", codes)
        self.assertIn("custom_test.statistics", codes)

        # Check custom action permission metadata
        approve_perm = next(p for p in permissions if p["code"] == "custom_test.approve")
        self.assertIn("Approve", approve_perm["name"])
        self.assertEqual(approve_perm["module"], "Test Module")
        self.assertEqual(approve_perm["submodule"], "Custom Actions")

    def test_viewset_without_prefix_returns_empty(self):
        """Test viewset without permission_prefix returns empty list"""
        # Act
        permissions = ViewSetWithoutPrefix.get_registered_permissions()

        # Assert
        self.assertEqual(len(permissions), 0)

    def test_list_action_uses_plural_name(self):
        """Test that list action uses plural model name"""
        # Act
        permissions = SimpleTestViewSet.get_registered_permissions()
        list_perm = next(p for p in permissions if p["code"] == "test_item.list")

        # Assert
        self.assertIn("Test Items", list_perm["name"])  # Plural

    def test_other_actions_use_singular_name(self):
        """Test that non-list actions use singular model name"""
        # Act
        permissions = SimpleTestViewSet.get_registered_permissions()
        create_perm = next(p for p in permissions if p["code"] == "test_item.create")

        # Assert
        self.assertIn("Test Item", create_perm["name"])  # Singular


@pytest.mark.django_db
class CollectPermissionsWithBaseViewSetTestCase(TestCase):
    """Test collect_permissions command with BaseModelViewSet"""

    def test_command_collects_from_base_viewset(self):
        """Test that collect_permissions command finds BaseModelViewSet permissions"""
        # Arrange - Clear existing permissions
        Permission.objects.all().delete()

        # Act - Run the command
        out = StringIO()
        call_command("collect_permissions", stdout=out)

        # Assert - Command should complete successfully
        output = out.getvalue()
        self.assertIn("collected", output.lower())
        self.assertIn("permissions", output.lower())

    def test_command_creates_permissions_in_database(self):
        """Test that permissions are actually created in the database"""
        # Arrange - Clear existing permissions
        Permission.objects.all().delete()

        # Act - Run the command
        call_command("collect_permissions", stdout=StringIO())

        # Assert - Check that role permissions were created
        role_permissions = Permission.objects.filter(code__startswith="role.")
        self.assertGreater(role_permissions.count(), 0)

        # Check specific permissions
        list_perm = Permission.objects.filter(code="role.list").first()
        self.assertIsNotNone(list_perm)
        self.assertEqual(list_perm.module, "Core")
        self.assertEqual(list_perm.submodule, "Role Management")
        self.assertIn("Role", list_perm.name)

    def test_command_updates_existing_permissions(self):
        """Test that command updates existing permissions"""
        # Arrange - Create an existing permission with old data
        Permission.objects.create(
            code="role.list",
            name="Old Name",
            description="Old Description",
            module="Old Module",
            submodule="Old Submodule",
        )

        # Act - Run the command
        call_command("collect_permissions", stdout=StringIO())

        # Assert - Permission should be updated
        perm = Permission.objects.get(code="role.list")
        self.assertNotEqual(perm.name, "Old Name")
        self.assertNotEqual(perm.module, "Old Module")
        self.assertEqual(perm.module, "Core")

    def test_command_handles_duplicates(self):
        """Test that command handles duplicate permissions correctly"""
        # Arrange - Clear existing permissions
        Permission.objects.all().delete()

        # Act - Run the command twice
        call_command("collect_permissions", stdout=StringIO())
        initial_count = Permission.objects.count()
        call_command("collect_permissions", stdout=StringIO())
        final_count = Permission.objects.count()

        # Assert - Count should remain the same
        self.assertEqual(initial_count, final_count)

    def test_command_output_shows_base_viewset_scan(self):
        """Test that command output mentions BaseModelViewSet scanning"""
        # Act
        out = StringIO()
        call_command("collect_permissions", stdout=out)
        output = out.getvalue()

        # Assert
        self.assertIn("BaseModelViewSet", output)


class BaseModelViewSetIntegrationTestCase(TestCase):
    """Integration tests for BaseModelViewSet with real models"""

    def test_role_viewset_generates_permissions(self):
        """Test that RoleViewSet generates correct permissions"""
        # Import the actual RoleViewSet
        from apps.core.api.views import RoleViewSet

        # Act
        permissions = RoleViewSet.get_registered_permissions()

        # Assert
        self.assertGreater(len(permissions), 0)
        codes = [p["code"] for p in permissions]
        self.assertIn("role.list", codes)
        self.assertIn("role.create", codes)
        self.assertIn("role.update", codes)
        self.assertIn("role.destroy", codes)

        # Check metadata
        list_perm = next(p for p in permissions if p["code"] == "role.list")
        self.assertEqual(list_perm["module"], "Core")
        self.assertEqual(list_perm["submodule"], "Role Management")
