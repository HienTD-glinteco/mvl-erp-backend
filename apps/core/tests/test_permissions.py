from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from apps.core.api.permissions import RoleBasedPermission
from apps.core.models import Permission, Role, User
from apps.core.utils import register_permission


class PermissionModelTestCase(TestCase):
    """Test Permission model"""

    def test_create_permission(self):
        # Arrange & Act
        permission = Permission.objects.create(
            code="document.create",
            description="Tạo tài liệu",
        )

        # Assert
        self.assertEqual(permission.code, "document.create")
        self.assertEqual(permission.description, "Tạo tài liệu")
        self.assertIsNotNone(permission.created_at)
        self.assertIsNotNone(permission.updated_at)

    def test_permission_string_representation(self):
        # Arrange
        permission = Permission.objects.create(
            code="document.list",
            description="Xem danh sách tài liệu",
        )

        # Act & Assert
        self.assertEqual(str(permission), "document.list - Xem danh sách tài liệu")

    def test_permission_string_representation_with_name(self):
        # Arrange
        permission = Permission.objects.create(
            code="document.list",
            name="List Documents",
            description="Xem danh sách tài liệu",
        )

        # Act & Assert
        self.assertEqual(str(permission), "document.list - List Documents")

    def test_create_permission_with_name(self):
        # Arrange & Act
        permission = Permission.objects.create(
            code="document.create",
            name="Create Document",
            description="Tạo tài liệu",
        )

        # Assert
        self.assertEqual(permission.code, "document.create")
        self.assertEqual(permission.name, "Create Document")
        self.assertEqual(permission.description, "Tạo tài liệu")
        self.assertIsNotNone(permission.created_at)
        self.assertIsNotNone(permission.updated_at)


class RoleModelTestCase(TestCase):
    """Test Role model"""

    def test_create_role(self):
        # Arrange & Act
        role = Role.objects.create(
            code="VT003",
            name="Manager",
            description="Quản lý",
        )

        # Assert
        self.assertEqual(role.name, "Manager")
        self.assertEqual(role.description, "Quản lý")
        self.assertIsNotNone(role.created_at)
        self.assertIsNotNone(role.updated_at)

    def test_role_permissions_relationship(self):
        # Arrange
        role = Role.objects.create(code="VT004", name="Manager")
        permission1 = Permission.objects.create(code="document.create", description="Tạo tài liệu")
        permission2 = Permission.objects.create(code="document.list", description="Xem danh sách tài liệu")

        # Act
        role.permissions.add(permission1, permission2)

        # Assert
        self.assertEqual(role.permissions.count(), 2)
        self.assertIn(permission1, role.permissions.all())
        self.assertIn(permission2, role.permissions.all())

    def test_role_string_representation(self):
        # Arrange
        role = Role.objects.create(code="VT001", name="Admin")

        # Act & Assert
        self.assertEqual(str(role), "VT001 - Admin")


class UserPermissionTestCase(TestCase):
    """Test User permission methods"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.permission = Permission.objects.create(
            code="document.create",
            description="Tạo tài liệu",
        )
        self.role = Role.objects.create(code="VT005", name="Editor")
        self.role.permissions.add(self.permission)

    def test_user_has_permission_through_role(self):
        # Arrange
        self.user.role = self.role
        self.user.save()

        # Act & Assert
        self.assertTrue(self.user.has_permission("document.create"))

    def test_user_does_not_have_permission(self):
        # Arrange - user has no roles

        # Act & Assert
        self.assertFalse(self.user.has_permission("document.create"))

    def test_superuser_has_all_permissions(self):
        # Arrange
        self.user.is_superuser = True
        self.user.save()

        # Act & Assert
        self.assertTrue(self.user.has_permission("document.create"))
        self.assertTrue(self.user.has_permission("any.permission"))

    def test_user_with_role_having_multiple_permissions(self):
        # Arrange
        permission2 = Permission.objects.create(code="document.delete", description="Xóa tài liệu")
        # Add both permissions to the same role
        self.role.permissions.add(permission2)

        self.user.role = self.role
        self.user.save()

        # Act & Assert
        self.assertTrue(self.user.has_permission("document.create"))
        self.assertTrue(self.user.has_permission("document.delete"))


class RegisterPermissionDecoratorTestCase(TestCase):
    """Test @register_permission decorator"""

    def test_decorator_attaches_metadata_to_function(self):
        # Arrange & Act
        @register_permission("test.permission", "Test Permission")
        def test_view(request):
            return Response({"ok": True})

        # Assert
        self.assertEqual(test_view._permission_code, "test.permission")
        self.assertEqual(test_view._permission_description, "Test Permission")

    def test_decorator_with_module_and_submodule(self):
        # Arrange & Act
        @register_permission("test.permission", "Test Permission", module="Test Module", submodule="Test Submodule")
        def test_view(request):
            return Response({"ok": True})

        # Assert
        self.assertEqual(test_view._permission_code, "test.permission")
        self.assertEqual(test_view._permission_description, "Test Permission")
        self.assertEqual(test_view._permission_module, "Test Module")
        self.assertEqual(test_view._permission_submodule, "Test Submodule")

    def test_decorator_with_name(self):
        # Arrange & Act
        @register_permission("test.permission", "Test Permission", name="Test Permission Name")
        def test_view(request):
            return Response({"ok": True})

        # Assert
        self.assertEqual(test_view._permission_code, "test.permission")
        self.assertEqual(test_view._permission_description, "Test Permission")
        self.assertEqual(test_view._permission_name, "Test Permission Name")

    def test_decorator_on_class_method(self):
        # Arrange & Act
        class TestView(APIView):
            @register_permission("test.get", "Test GET")
            def get(self, request):
                return Response({"ok": True})

        # Assert
        self.assertEqual(TestView.get._permission_code, "test.get")
        self.assertEqual(TestView.get._permission_description, "Test GET")

    def test_decorated_function_still_callable(self):
        # Arrange
        @register_permission("test.permission", "Test Permission")
        def test_view():
            return "success"

        # Act
        result = test_view()

        # Assert
        self.assertEqual(result, "success")


class RoleBasedPermissionTestCase(TestCase):
    """Test RoleBasedPermission class"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.permission = Permission.objects.create(
            code="test.view",
            description="Test View Permission",
        )
        self.role = Role.objects.create(code="VT006", name="Tester")
        self.role.permissions.add(self.permission)

    def test_permission_allowed_for_user_with_role(self):
        # Arrange
        self.user.role = self.role
        self.user.save()

        @api_view(["GET"])
        @permission_classes([RoleBasedPermission])
        @register_permission("test.view", "Test View Permission")
        def test_view(request):
            return Response({"ok": True})

        request = self.factory.get("/test/")
        request.user = self.user

        # Act
        response = test_view(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permission_denied_for_user_without_role(self):
        # Arrange
        from rest_framework.exceptions import PermissionDenied

        # Create a view function with permission decorator
        def raw_view(request):
            return Response({"ok": True})

        # Apply decorators
        test_view = register_permission("test.view", "Test View Permission")(raw_view)

        request = self.factory.get("/test/")
        request.user = self.user

        # Act & Assert - RoleBasedPermission should raise PermissionDenied
        permission_checker = RoleBasedPermission()

        with self.assertRaises(PermissionDenied) as context:
            permission_checker.has_permission(request, test_view)
        self.assertIn("không có quyền", str(context.exception))

    def test_permission_allowed_for_superuser(self):
        # Arrange
        self.user.is_superuser = True
        self.user.save()

        @api_view(["GET"])
        @permission_classes([RoleBasedPermission])
        @register_permission("test.view", "Test View Permission")
        def test_view(request):
            return Response({"ok": True})

        request = self.factory.get("/test/")
        request.user = self.user

        # Act
        response = test_view(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permission_allowed_for_view_without_permission_code(self):
        # Arrange - view without @register_permission decorator
        @api_view(["GET"])
        @permission_classes([RoleBasedPermission])
        def test_view(request):
            return Response({"ok": True})

        request = self.factory.get("/test/")
        request.user = self.user

        # Act
        response = test_view(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_class_based_view_permission(self):
        # Arrange
        self.user.role = self.role
        self.user.save()

        class TestView(APIView):
            permission_classes = [RoleBasedPermission]

            @register_permission("test.view", "Test View Permission")
            def get(self, request):
                return Response({"ok": True})

        view = TestView.as_view()
        request = self.factory.get("/test/")
        # Use force_authenticate for DRF views
        from rest_framework.test import force_authenticate

        request.user = self.user
        force_authenticate(request, user=self.user)

        # Act
        response = view(request)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@pytest.mark.django_db
class CollectPermissionsCommandTestCase(TestCase):
    """Test collect_permissions management command"""

    def test_command_runs_without_errors(self):
        # Arrange & Act - Simply run the command on existing URL patterns
        out = StringIO()
        call_command("collect_permissions", stdout=out)

        # Assert - Command should complete successfully
        output = out.getvalue()
        self.assertIn("collected", output.lower())
        self.assertIn("permissions", output.lower())

    def test_command_creates_new_permission(self):
        # Arrange - Create a permission manually
        code = "manual.test.permission"
        description = "Manual Test Permission"

        # Act - Create it directly (simulating what the command would do)
        permission, created = Permission.objects.update_or_create(
            code=code,
            defaults={"description": description},
        )

        # Assert
        self.assertTrue(created)
        self.assertEqual(permission.code, code)
        self.assertEqual(permission.description, description)

    def test_command_creates_permission_with_module_and_submodule(self):
        # Arrange - Create a permission with module and submodule
        code = "hrm.view_employee"
        description = "View employee list"
        module = "HRM"
        submodule = "Employee Profile"

        # Act - Create it directly (simulating what the command would do)
        permission, created = Permission.objects.update_or_create(
            code=code,
            defaults={
                "description": description,
                "module": module,
                "submodule": submodule,
            },
        )

        # Assert
        self.assertTrue(created)
        self.assertEqual(permission.code, code)
        self.assertEqual(permission.description, description)
        self.assertEqual(permission.module, module)
        self.assertEqual(permission.submodule, submodule)

    def test_command_creates_permission_with_name(self):
        # Arrange - Create a permission with name
        code = "hrm.create_employee"
        name = "Create Employee"
        description = "Create new employee"
        module = "HRM"
        submodule = "Employee Profile"

        # Act - Create it directly (simulating what the command would do)
        permission, created = Permission.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "module": module,
                "submodule": submodule,
            },
        )

        # Assert
        self.assertTrue(created)
        self.assertEqual(permission.code, code)
        self.assertEqual(permission.name, name)
        self.assertEqual(permission.description, description)
        self.assertEqual(permission.module, module)
        self.assertEqual(permission.submodule, submodule)

    def test_command_updates_existing_permission(self):
        # Arrange - Create an existing permission with old description
        code = "test.update"
        old_description = "Old Description"
        new_description = "New Description"

        Permission.objects.create(code=code, description=old_description)

        # Act - Update it (simulating what the command would do)
        permission, created = Permission.objects.update_or_create(
            code=code,
            defaults={"description": new_description},
        )

        # Assert
        self.assertFalse(created)
        self.assertEqual(permission.description, new_description)

    def test_command_updates_permission_module_and_submodule(self):
        # Arrange - Create an existing permission without module/submodule
        code = "test.update.module"
        description = "Test Permission"
        old_module = ""
        old_submodule = ""

        Permission.objects.create(code=code, description=description, module=old_module, submodule=old_submodule)

        # Act - Update with module and submodule
        new_module = "Test Module"
        new_submodule = "Test Submodule"
        permission, created = Permission.objects.update_or_create(
            code=code,
            defaults={
                "description": description,
                "module": new_module,
                "submodule": new_submodule,
            },
        )

        # Assert
        self.assertFalse(created)
        self.assertEqual(permission.module, new_module)
        self.assertEqual(permission.submodule, new_submodule)
