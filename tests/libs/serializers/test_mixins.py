"""
Tests for serializer mixins.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.core.models import Role
from libs.drf.serializers.mixins import FieldFilteringSerializerMixin

User = get_user_model()


class TestSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Test serializer with field filtering mixin."""

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class TestSerializerWithDefaults(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Test serializer with default_fields attribute."""

    default_fields = ["id", "name"]

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "created_at", "updated_at"]


class FieldFilteringSerializerMixinTests(TestCase):
    """Test cases for FieldFilteringSerializerMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.role = Role.objects.create(code="TEST01", name="Test Role", description="Test Description")

    def test_no_filtering_when_no_request(self):
        """Test that all fields are included when no request in context."""
        serializer = TestSerializer(self.role)
        fields = set(serializer.fields.keys())
        expected_fields = {"id", "code", "name", "description", "created_at", "updated_at"}
        self.assertEqual(fields, expected_fields)

    def test_no_filtering_when_no_fields_param(self):
        """Test that all fields are included when fields parameter is not provided."""
        request = self.factory.get("/api/test/")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"id", "code", "name", "description", "created_at", "updated_at"}
        self.assertEqual(fields, expected_fields)

    def test_field_filtering_with_valid_fields(self):
        """Test that only requested fields are included."""
        request = self.factory.get("/api/test/?fields=id,name,code")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"id", "name", "code"}
        self.assertEqual(fields, expected_fields)

    def test_field_filtering_with_single_field(self):
        """Test filtering with a single field."""
        request = self.factory.get("/api/test/?fields=name")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"name"}
        self.assertEqual(fields, expected_fields)

    def test_field_filtering_ignores_invalid_fields(self):
        """Test that invalid field names are ignored."""
        request = self.factory.get("/api/test/?fields=id,name,invalid_field")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        # Only valid fields should be included
        expected_fields = {"id", "name"}
        self.assertEqual(fields, expected_fields)

    def test_field_filtering_with_spaces(self):
        """Test that spaces in fields parameter are handled correctly."""
        request = self.factory.get("/api/test/?fields=id, name, code")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"id", "name", "code"}
        self.assertEqual(fields, expected_fields)

    def test_field_filtering_with_empty_string(self):
        """Test that empty fields parameter returns all fields."""
        request = self.factory.get("/api/test/?fields=")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"id", "code", "name", "description", "created_at", "updated_at"}
        self.assertEqual(fields, expected_fields)

    def test_default_fields_when_no_fields_param(self):
        """Test that default_fields are used when fields parameter is not provided."""
        request = self.factory.get("/api/test/")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializerWithDefaults(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"id", "name"}
        self.assertEqual(fields, expected_fields)

    def test_fields_param_overrides_default_fields(self):
        """Test that fields parameter overrides default_fields."""
        request = self.factory.get("/api/test/?fields=code,description")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializerWithDefaults(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        expected_fields = {"code", "description"}
        self.assertEqual(fields, expected_fields)

    def test_serialization_with_filtered_fields(self):
        """Test that serialization works correctly with filtered fields."""
        request = self.factory.get("/api/test/?fields=id,name")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        data = serializer.data

        self.assertEqual(len(data), 2)
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertEqual(data["name"], "Test Role")
        self.assertNotIn("description", data)
        self.assertNotIn("code", data)

    def test_many_serializers_with_filtering(self):
        """Test that field filtering works with many=True."""
        Role.objects.create(code="TEST02", name="Test Role 2")
        Role.objects.create(code="TEST03", name="Test Role 3")

        request = self.factory.get("/api/test/?fields=id,name")
        request.user = self.user
        drf_request = Request(request)

        roles = Role.objects.filter(code__startswith="TEST")
        serializer = TestSerializer(roles, many=True, context={"request": drf_request})
        data = serializer.data

        self.assertEqual(len(data), 3)
        for item in data:
            self.assertEqual(len(item), 2)
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertNotIn("code", item)
            self.assertNotIn("description", item)

    def test_field_filtering_case_sensitive(self):
        """Test that field names are case-sensitive."""
        request = self.factory.get("/api/test/?fields=ID,NAME")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        # No fields should match (case mismatch)
        self.assertEqual(len(fields), 0)

    def test_no_crash_with_all_invalid_fields(self):
        """Test that serializer doesn't crash when all requested fields are invalid."""
        request = self.factory.get("/api/test/?fields=invalid1,invalid2")
        request.user = self.user
        drf_request = Request(request)

        serializer = TestSerializer(self.role, context={"request": drf_request})
        fields = set(serializer.fields.keys())
        # No fields should be included
        self.assertEqual(len(fields), 0)
        # Serialization should work (empty dict)
        data = serializer.data
        self.assertEqual(data, {})
