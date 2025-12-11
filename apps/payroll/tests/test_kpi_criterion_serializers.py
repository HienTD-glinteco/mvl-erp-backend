from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.core.models import User
from apps.payroll.api.serializers import KPICriterionSerializer
from apps.payroll.models import KPICriterion


@pytest.mark.django_db
class TestKPICriterionSerializer:
    """Test cases for KPICriterionSerializer"""

    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.valid_data = {
            "target": "sales",
            "evaluation_type": "job_performance",
            "name": "Revenue Achievement",
            "description": "Monthly revenue target achievement",
            "component_total_score": "70.00",
            "ordering": 1,
            "active": True,
        }

    def test_serialize_kpi_criterion(self):
        """Test serializing a KPICriterion instance"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            description="Monthly revenue target achievement",
            component_total_score=Decimal("70.00"),
            ordering=1,
            active=True,
            created_by=self.user,
        )
        serializer = KPICriterionSerializer(criterion)

        assert serializer.data["id"] == criterion.id
        assert serializer.data["target"] == "sales"
        assert serializer.data["evaluation_type"] == "job_performance"
        assert serializer.data["name"] == "Revenue Achievement"
        assert serializer.data["description"] == "Monthly revenue target achievement"
        assert serializer.data["component_total_score"] == "70.00"
        assert serializer.data["ordering"] == 1
        assert serializer.data["active"] is True
        assert serializer.data["created_by"] == self.user.id
        assert "created_at" in serializer.data
        assert "updated_at" in serializer.data

    def test_deserialize_valid_data(self):
        """Test deserializing valid data"""
        serializer = KPICriterionSerializer(data=self.valid_data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["target"] == "sales"
        assert serializer.validated_data["component_total_score"] == Decimal("70.00")

    def test_create_with_valid_data(self):
        """Test creating a criterion through serializer"""
        serializer = KPICriterionSerializer(data=self.valid_data)
        assert serializer.is_valid(), serializer.errors

        criterion = serializer.save(created_by=self.user)
        assert criterion.id is not None
        assert criterion.target == "sales"
        assert criterion.created_by == self.user

    def test_read_only_fields(self):
        """Test that certain fields are read-only"""
        serializer = KPICriterionSerializer()
        read_only_fields = serializer.Meta.read_only_fields

        assert "id" in read_only_fields
        assert "created_by" in read_only_fields
        assert "updated_by" in read_only_fields
        assert "created_at" in read_only_fields
        assert "updated_at" in read_only_fields

    def test_validate_component_total_score_valid_values(self):
        """Test that valid component_total_score values are accepted"""
        valid_scores = ["0.00", "50.00", "75.50", "100.00"]
        for score in valid_scores:
            data = self.valid_data.copy()
            data["component_total_score"] = score
            serializer = KPICriterionSerializer(data=data)
            assert serializer.is_valid(), f"Score {score} should be valid but got errors: {serializer.errors}"

    def test_validate_component_total_score_too_low(self):
        """Test that component_total_score below 0 is rejected"""
        data = self.valid_data.copy()
        data["component_total_score"] = "-10.00"
        serializer = KPICriterionSerializer(data=data)
        assert not serializer.is_valid()
        assert "component_total_score" in serializer.errors

    def test_validate_component_total_score_too_high(self):
        """Test that component_total_score above 100 is rejected"""
        data = self.valid_data.copy()
        data["component_total_score"] = "150.00"
        serializer = KPICriterionSerializer(data=data)
        assert not serializer.is_valid()
        assert "component_total_score" in serializer.errors

    def test_required_fields(self):
        """Test that required fields are validated"""
        required_fields = ["target", "evaluation_type", "name", "component_total_score"]
        for field in required_fields:
            data = self.valid_data.copy()
            del data[field]
            serializer = KPICriterionSerializer(data=data)
            assert not serializer.is_valid()
            assert field in serializer.errors, f"Field {field} should be required"

    def test_optional_fields(self):
        """Test that optional fields can be omitted"""
        data = {
            "target": "sales",
            "evaluation_type": "job_performance",
            "name": "Revenue Achievement",
            "component_total_score": "70.00",
        }
        serializer = KPICriterionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        criterion = serializer.save(created_by=self.user)
        assert criterion.description == ""
        assert criterion.ordering == 0
        assert criterion.active is True

    def test_unique_constraint_validation_on_create(self):
        """Test that unique constraint is validated on create"""
        # Create first criterion
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )

        # Try to create duplicate
        serializer = KPICriterionSerializer(data=self.valid_data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_unique_constraint_validation_on_update(self):
        """Test that unique constraint is validated on update"""
        # Create two criteria
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Customer Satisfaction",
            component_total_score=Decimal("30.00"),
        )

        # Try to update criterion1 to have same name as criterion2
        data = {"name": "Customer Satisfaction"}
        serializer = KPICriterionSerializer(criterion1, data=data, partial=True)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_update_criterion(self):
        """Test updating a criterion through serializer"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            created_by=self.user,
        )

        update_data = {
            "description": "Updated description",
            "component_total_score": "75.00",
        }
        serializer = KPICriterionSerializer(criterion, data=update_data, partial=True)
        assert serializer.is_valid(), serializer.errors

        updated_criterion = serializer.save(updated_by=self.user)
        assert updated_criterion.description == "Updated description"
        assert updated_criterion.component_total_score == Decimal("75.00")
        assert updated_criterion.updated_by == self.user

    def test_partial_update(self):
        """Test partial update (PATCH)"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )

        data = {"active": False}
        serializer = KPICriterionSerializer(criterion, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

        updated_criterion = serializer.save()
        assert updated_criterion.active is False
        # Other fields should remain unchanged
        assert updated_criterion.target == "sales"
        assert updated_criterion.component_total_score == Decimal("70.00")

    def test_full_update(self):
        """Test full update (PUT)"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )

        new_data = {
            "target": "backoffice",
            "evaluation_type": "discipline",
            "name": "Attendance",
            "description": "Monthly attendance",
            "component_total_score": "30.00",
            "ordering": 2,
            "active": True,
        }
        serializer = KPICriterionSerializer(criterion, data=new_data)
        assert serializer.is_valid(), serializer.errors

        updated_criterion = serializer.save()
        assert updated_criterion.target == "backoffice"
        assert updated_criterion.evaluation_type == "discipline"
        assert updated_criterion.name == "Attendance"
        assert updated_criterion.component_total_score == Decimal("30.00")

    def test_unique_constraint_allows_same_name_different_target(self):
        """Test that same name is allowed for different target"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )

        data = self.valid_data.copy()
        data["target"] = "backoffice"
        serializer = KPICriterionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_unique_constraint_allows_same_name_different_evaluation_type(self):
        """Test that same name is allowed for different evaluation_type"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Attendance",
            component_total_score=Decimal("70.00"),
        )

        data = self.valid_data.copy()
        data["name"] = "Attendance"
        data["evaluation_type"] = "discipline"
        serializer = KPICriterionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_decimal_precision(self):
        """Test that decimal values maintain precision"""
        data = self.valid_data.copy()
        data["component_total_score"] = "75.50"
        serializer = KPICriterionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        criterion = serializer.save(created_by=self.user)
        assert criterion.component_total_score == Decimal("75.50")

    def test_empty_description(self):
        """Test that empty description is allowed"""
        data = self.valid_data.copy()
        data["description"] = ""
        serializer = KPICriterionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_long_text_fields(self):
        """Test that long text is accepted for text fields"""
        data = self.valid_data.copy()
        data["description"] = "A" * 1000
        serializer = KPICriterionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        criterion = serializer.save(created_by=self.user)
        assert len(criterion.description) == 1000
