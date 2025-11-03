"""
Tests for FileConfirmSerializerMixin schema generation with drf-spectacular.

This test verifies that the FileConfirmSerializerMixin correctly generates
structured OpenAPI schema for file upload fields when file_confirm_fields
is explicitly declared.
"""

import pytest
from django.test import TestCase
from drf_spectacular.openapi import AutoSchema
from rest_framework import serializers, viewsets
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.hrm.models import EmployeeCertificate
from libs.drf.serializers.mixins import FileConfirmSerializerMixin


class TestCertificateSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Test serializer with explicit file_confirm_fields."""

    file_confirm_fields = ["attachment", "document"]

    class Meta:
        model = EmployeeCertificate
        fields = ["id", "certificate_name", "attachment"]


class TestCertificateSerializerNoFields(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Test serializer without file_confirm_fields (fallback to auto-detection)."""

    class Meta:
        model = EmployeeCertificate
        fields = ["id", "certificate_name", "attachment"]


class TestCertificateViewSet(viewsets.ModelViewSet):
    """Test viewset for schema generation."""

    queryset = EmployeeCertificate.objects.all()
    serializer_class = TestCertificateSerializer


@pytest.mark.django_db
class TestFileConfirmMixinSchemaGeneration:
    """Tests for FileConfirmSerializerMixin schema generation."""

    def test_declared_files_field_exists_at_class_level(self):
        """Test that files field is declared at class level when file_confirm_fields is set."""
        # The serializer class should have _file_fields_serializer_class set
        assert hasattr(TestCertificateSerializer, "_file_fields_serializer_class")
        assert TestCertificateSerializer._file_fields_serializer_class is not None

        # Instantiate and check that files field is in fields
        serializer = TestCertificateSerializer()
        assert "files" in serializer.fields

    def test_files_field_is_nested_serializer(self):
        """Test that files field is a nested serializer, not a DictField."""
        serializer = TestCertificateSerializer()
        files_field = serializer.fields["files"]

        # Should be a serializer instance
        assert isinstance(files_field, serializers.Serializer)
        assert not isinstance(files_field, serializers.DictField)

    def test_files_field_contains_specific_fields(self):
        """Test that files field contains fields from file_confirm_fields."""
        serializer = TestCertificateSerializer()
        files_field = serializer.fields["files"]

        # Check that it has the expected child fields
        assert "attachment" in files_field.fields
        assert "document" in files_field.fields

        # Verify field types
        assert isinstance(files_field.fields["attachment"], serializers.CharField)
        assert isinstance(files_field.fields["document"], serializers.CharField)

    def test_files_field_properties(self):
        """Test that files field has correct properties."""
        serializer = TestCertificateSerializer()
        files_field = serializer.fields["files"]

        # Check properties
        assert files_field.required is False
        assert files_field.write_only is True

    def test_schema_generation_with_declared_fields(self):
        """Test that drf-spectacular generates correct schema for declared files field."""
        # Create a request
        factory = APIRequestFactory()
        django_request = factory.post("/api/test/")
        drf_request = Request(django_request)

        view_instance = TestCertificateViewSet()
        view_instance.action = "create"
        view_instance.request = drf_request
        view_instance.format_kwarg = None
        view_instance.kwargs = {}

        # Generate schema
        schema = AutoSchema()
        schema.view = view_instance
        schema.path = "/api/test/"
        schema.method = "POST"

        # Get request body schema
        request_body = schema.get_request_serializer()
        if request_body is not None:
            # drf-spectacular may return either a serializer class or instance
            # depending on configuration. Instantiate if it's a class.
            serializer_instance = request_body() if isinstance(request_body, type) else request_body

            assert "files" in serializer_instance.fields
            files_field = serializer_instance.fields["files"]

            # Verify it's a nested serializer
            assert isinstance(files_field, serializers.Serializer)
            assert "attachment" in files_field.fields
            assert "document" in files_field.fields

    def test_auto_detection_without_explicit_fields(self):
        """Test that auto-detection still works when file_confirm_fields is not set."""
        serializer = TestCertificateSerializerNoFields()

        # Should have files field
        assert "files" in serializer.fields

        # Check that auto-detection found the attachment field
        files_field = serializer.fields["files"]
        if isinstance(files_field, serializers.Serializer):
            # Auto-detected and created nested serializer
            assert "attachment" in files_field.fields
        else:
            # Fallback to DictField is also acceptable
            assert isinstance(files_field, serializers.DictField)

    def test_multiple_serializers_dont_interfere(self):
        """Test that multiple serializers with different file_confirm_fields don't interfere."""

        class SerializerA(FileConfirmSerializerMixin, serializers.ModelSerializer):
            file_confirm_fields = ["attachment"]

            class Meta:
                model = EmployeeCertificate
                fields = ["id", "attachment"]

        class SerializerB(FileConfirmSerializerMixin, serializers.ModelSerializer):
            file_confirm_fields = ["document", "photo"]

            class Meta:
                model = EmployeeCertificate
                fields = ["id", "attachment"]

        # Create instances
        serializer_a = SerializerA()
        serializer_b = SerializerB()

        # Check A has only attachment
        assert "files" in serializer_a.fields
        files_field_a = serializer_a.fields["files"]
        assert isinstance(files_field_a, serializers.Serializer)
        assert "attachment" in files_field_a.fields
        assert "document" not in files_field_a.fields

        # Check B has document and photo
        assert "files" in serializer_b.fields
        files_field_b = serializer_b.fields["files"]
        assert isinstance(files_field_b, serializers.Serializer)
        assert "document" in files_field_b.fields
        assert "photo" in files_field_b.fields
        assert "attachment" not in files_field_b.fields


class TestFileConfirmMixinSchemaGenerationWithDjango(TestCase):
    """Django TestCase for FileConfirmSerializerMixin schema generation."""

    def test_files_field_write_only(self):
        """Test that files field is write_only."""
        serializer = TestCertificateSerializer()
        files_field = serializer.fields["files"]

        assert files_field.write_only is True

    def test_files_field_optional(self):
        """Test that files field is optional (required=False)."""
        serializer = TestCertificateSerializer()
        files_field = serializer.fields["files"]

        assert files_field.required is False

    def test_serialization_excludes_files_field(self):
        """Test that files field is not included in serialized output (write_only)."""
        from datetime import date

        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.constants import CertificateType
        from apps.hrm.models import Block, Branch, Department, Employee

        # Create test data
        province = Province.objects.create(code="01", name="Test Province")
        admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=province,
            administrative_unit=admin_unit,
        )

        block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )

        department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=branch,
            block=block,
        )

        employee = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            branch=branch,
            block=block,
            department=department,
            start_date=date(2020, 1, 1),
        )

        certificate = EmployeeCertificate.objects.create(
            employee=employee,
            certificate_type=CertificateType.FOREIGN_LANGUAGE,
            certificate_name="Test Certificate",
        )

        serializer = TestCertificateSerializer(certificate)
        data = serializer.data

        # files field should not be in serialized output
        assert "files" not in data
        assert "id" in data
        assert "certificate_name" in data
