from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.hrm.models import AttendanceGeolocation
from apps.realestate.models import Project

User = get_user_model()


class AttendanceGeolocationModelTest(TestCase):
    """Test cases for AttendanceGeolocation model."""

    def setUp(self):
        """Set up test data."""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.project = Project.objects.create(name="Test Project", code="DA001", status="active")

    def test_create_geolocation_with_required_fields(self):
        """Test creating a geolocation with all required fields."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Test Geofence",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=100,
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertIsNotNone(geolocation.id)
        self.assertEqual(geolocation.name, "Test Geofence")
        self.assertEqual(geolocation.project, self.project)
        self.assertTrue(geolocation.code.startswith("DV"))

    def test_code_auto_generation(self):
        """Test that code is auto-generated with DV prefix."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Auto Code Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=100,
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertIsNotNone(geolocation.code)
        self.assertTrue(geolocation.code.startswith("DV"))

    def test_code_uniqueness(self):
        """Test that codes are unique."""
        geo1 = AttendanceGeolocation.objects.create(
            name="Geo 1",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=100,
            created_by=self.user,
            updated_by=self.user,
        )
        geo2 = AttendanceGeolocation.objects.create(
            name="Geo 2",
            project=self.project,
            latitude="10.7800000",
            longitude="106.7100000",
            radius_m=100,
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertNotEqual(geo1.code, geo2.code)

    def test_default_radius(self):
        """Test that default radius is 100 meters."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Default Radius Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(geolocation.radius_m, 100)

    def test_default_status(self):
        """Test that default status is 'active'."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Default Status Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(geolocation.status, "active")

    def test_invalid_radius_validation(self):
        """Test that radius must be at least 1 meter."""
        geolocation = AttendanceGeolocation(
            name="Invalid Radius Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=0,  # Invalid
            created_by=self.user,
            updated_by=self.user,
        )

        with self.assertRaises(ValidationError):
            geolocation.full_clean()

    def test_soft_delete(self):
        """Test soft delete functionality."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Soft Delete Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            created_by=self.user,
            updated_by=self.user,
        )

        # Perform soft delete
        geolocation.delete()

        # Verify soft delete flags are set
        geolocation.refresh_from_db()
        self.assertTrue(geolocation.deleted)
        self.assertIsNotNone(geolocation.deleted_at)

        # Verify it still exists in database
        self.assertTrue(AttendanceGeolocation.objects.filter(id=geolocation.id).exists())

        # Verify it's excluded from default queryset
        default_queryset = AttendanceGeolocation.objects.filter(deleted=False)
        self.assertFalse(default_queryset.filter(id=geolocation.id).exists())

    def test_string_representation(self):
        """Test __str__ method."""
        geolocation = AttendanceGeolocation.objects.create(
            name="String Test Geofence",
            code="DV123",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            created_by=self.user,
            updated_by=self.user,
        )

        expected_str = f"{geolocation.code} - {geolocation.name}"
        self.assertEqual(str(geolocation), expected_str)

    def test_optional_fields(self):
        """Test that optional fields (address, notes) can be blank."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Optional Fields Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            created_by=self.user,
            updated_by=self.user,
            # address and notes not provided
        )

        self.assertEqual(geolocation.address, "")
        self.assertEqual(geolocation.notes, "")

    def test_audit_fields(self):
        """Test that audit fields are properly set."""
        geolocation = AttendanceGeolocation.objects.create(
            name="Audit Fields Test",
            project=self.project,
            latitude="10.7769000",
            longitude="106.7009000",
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(geolocation.created_by, self.user)
        self.assertEqual(geolocation.updated_by, self.user)
        self.assertIsNotNone(geolocation.created_at)
        self.assertIsNotNone(geolocation.updated_at)


class ProjectModelTest(TestCase):
    """Test cases for Project model."""

    def test_create_project(self):
        """Test creating a project."""
        project = Project.objects.create(name="Test Project", code="DA001", status="active")

        self.assertIsNotNone(project.id)
        self.assertEqual(project.name, "Test Project")
        self.assertTrue(project.code.startswith("DA"))

    def test_code_auto_generation(self):
        """Test that code is auto-generated with DA prefix."""
        project = Project.objects.create(name="Auto Code Test", status="active")

        self.assertIsNotNone(project.code)
        self.assertTrue(project.code.startswith("DA"))

    def test_default_status(self):
        """Test that default status is 'active'."""
        project = Project.objects.create(name="Default Status Test")

        self.assertEqual(project.status, "active")

    def test_default_is_active(self):
        """Test that default is_active is True."""
        project = Project.objects.create(name="Default Active Test")

        self.assertTrue(project.is_active)

    def test_string_representation(self):
        """Test __str__ method."""
        project = Project.objects.create(name="String Test Project", code="DA123")

        expected_str = f"{project.code} - {project.name}"
        self.assertEqual(str(project), expected_str)
