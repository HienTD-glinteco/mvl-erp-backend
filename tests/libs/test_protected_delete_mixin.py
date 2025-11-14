"""
Tests for ProtectedDeleteMixin.

This module tests the functionality of the ProtectedDeleteMixin which validates
protected related objects before deletion in Django REST Framework ViewSets.
"""

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import translation
from rest_framework import status, viewsets
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Branch
from libs.drf.mixin.protected_delete import ProtectedDeleteMixin

User = get_user_model()


# Test ViewSet using the ProtectedDeleteMixin
class TestProvinceViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    """Test ViewSet for Province model using ProtectedDeleteMixin."""

    queryset = Province.objects.all()


class ProtectedDeleteMixinTest(TransactionTestCase):
    """Test cases for ProtectedDeleteMixin."""

    def setUp(self):
        """Set up test data."""
        # Clear existing data
        Branch.objects.all().delete()
        AdministrativeUnit.objects.all().delete()
        Province.objects.all().delete()
        User.objects.all().delete()

        self.factory = APIRequestFactory()
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")

        # Create test province
        self.province = Province.objects.create(name="Test Province", code="TP01")

    def tearDown(self):
        """Clean up test data."""
        Branch.objects.all().delete()
        AdministrativeUnit.objects.all().delete()
        Province.objects.all().delete()
        User.objects.all().delete()

    def test_delete_without_protected_objects_succeeds(self):
        """Test that deletion succeeds when there are no protected related objects."""
        # Arrange
        viewset = TestProvinceViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(f"/provinces/{self.province.pk}/")
        force_authenticate(request, user=self.user)

        # Act
        response = viewset(request, pk=self.province.pk)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Province.objects.filter(pk=self.province.pk).exists())

    def test_delete_with_protected_objects_fails(self):
        """Test that deletion fails with proper error when protected objects exist."""
        # Arrange
        # Create another administrative unit that references the province (needed for Branch)
        admin_unit = AdministrativeUnit.objects.create(
            name="District 1",
            code="D1",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Create branches that reference the province with PROTECT
        branch1 = Branch.objects.create(name="Branch 1", province=self.province, administrative_unit=admin_unit)
        branch2 = Branch.objects.create(name="Branch 2", province=self.province, administrative_unit=admin_unit)

        viewset = TestProvinceViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(f"/provinces/{self.province.pk}/")
        force_authenticate(request, user=self.user)

        # Act
        with translation.override("en"):
            response = viewset(request, pk=self.province.pk)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertIn("protected_objects", response.data)

        # Verify error message mentions the protected objects
        detail = response.data["detail"]
        self.assertIn("Province", detail)
        self.assertIn("2", detail)
        self.assertIn("Branches", detail)

        # Verify protected objects structure
        protected_objects = response.data["protected_objects"]
        self.assertEqual(len(protected_objects), 1)
        self.assertEqual(protected_objects[0]["count"], 2)
        self.assertEqual(protected_objects[0]["name"], "Branches")
        self.assertIn("protected_object_ids", protected_objects[0])
        self.assertEqual(len(protected_objects[0]["protected_object_ids"]), 2)

        # Verify province still exists
        self.assertTrue(Province.objects.filter(pk=self.province.pk).exists())

    def test_error_message_format(self):
        """Test that error messages are formatted correctly."""
        # Arrange
        admin_unit = AdministrativeUnit.objects.create(
            name="District 1",
            code="D1",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        branch = Branch.objects.create(name="Branch 1", province=self.province, administrative_unit=admin_unit)

        viewset = TestProvinceViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(f"/provinces/{self.province.pk}/")
        force_authenticate(request, user=self.user)

        # Act
        with translation.override("en"):
            response = viewset(request, pk=self.province.pk)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify the error message follows the expected format
        detail = response.data["detail"]
        self.assertIn("Cannot delete this Province because it is referenced by:", detail)
        self.assertIn("1 Branches", detail)

    def test_protected_objects_count(self):
        """Test that the count of protected objects is accurate."""
        # Arrange
        # Create administrative unit that is needed for branches
        admin_unit = AdministrativeUnit.objects.create(
            name="District 1",
            code="D1",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Create 5 branches that reference the province
        for i in range(5):
            Branch.objects.create(
                name=f"Branch {i}",
                province=self.province,
                administrative_unit=admin_unit,
            )

        viewset = TestProvinceViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete(f"/provinces/{self.province.pk}/")
        force_authenticate(request, user=self.user)

        # Act
        with translation.override("en"):
            response = viewset(request, pk=self.province.pk)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify count
        protected_objects = response.data["protected_objects"]
        self.assertEqual(len(protected_objects), 1)
        self.assertEqual(protected_objects[0]["count"], 5)

        # Verify error message
        detail = response.data["detail"]
        self.assertIn("5 Branches", detail)
