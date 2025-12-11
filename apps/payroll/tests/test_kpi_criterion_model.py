from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import User
from apps.payroll.models import KPICriterion


@pytest.mark.django_db
class KPICriterionModelTest(TestCase):
    """Test cases for KPICriterion model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_create_kpi_criterion(self):
        """Test creating a KPI criterion with valid data"""
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

        self.assertIsNotNone(criterion.id)
        self.assertEqual(criterion.target, "sales")
        self.assertEqual(criterion.evaluation_type, "job_performance")
        self.assertEqual(criterion.name, "Revenue Achievement")
        self.assertEqual(criterion.component_total_score, Decimal("70.00"))
        self.assertEqual(criterion.ordering, 1)
        self.assertTrue(criterion.active)
        self.assertEqual(criterion.created_by, self.user)
        self.assertIsNotNone(criterion.created_at)
        self.assertIsNotNone(criterion.updated_at)

    def test_str_representation(self):
        """Test string representation of KPICriterion"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )
        expected_str = "sales - job_performance - Revenue Achievement"
        self.assertEqual(str(criterion), expected_str)

    def test_default_values(self):
        """Test that default values are set correctly"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Test Criterion",
            component_total_score=Decimal("50.00"),
        )
        self.assertEqual(criterion.ordering, 0)
        self.assertTrue(criterion.active)
        self.assertEqual(criterion.description, "")

    def test_unique_together_constraint(self):
        """Test that (target, evaluation_type, name) must be unique"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            KPICriterion.objects.create(
                target="sales",
                evaluation_type="job_performance",
                name="Revenue Achievement",
                component_total_score=Decimal("80.00"),
            )

    def test_unique_constraint_allows_different_target(self):
        """Test that same name is allowed for different target"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )

        # Should succeed with different target
        criterion2 = KPICriterion.objects.create(
            target="backoffice",
            evaluation_type="job_performance",
            name="Revenue Achievement",
            component_total_score=Decimal("70.00"),
        )
        self.assertIsNotNone(criterion2.id)

    def test_unique_constraint_allows_different_evaluation_type(self):
        """Test that same name is allowed for different evaluation_type"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Attendance",
            component_total_score=Decimal("30.00"),
        )

        # Should succeed with different evaluation_type
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            name="Attendance",
            component_total_score=Decimal("30.00"),
        )
        self.assertIsNotNone(criterion2.id)

    def test_component_total_score_validation_min(self):
        """Test that component_total_score cannot be less than 0"""
        criterion = KPICriterion(
            target="sales",
            evaluation_type="job_performance",
            name="Test",
            component_total_score=Decimal("-10.00"),
        )
        with self.assertRaises(DjangoValidationError):
            criterion.full_clean()

    def test_component_total_score_validation_max(self):
        """Test that component_total_score cannot be greater than 100"""
        criterion = KPICriterion(
            target="sales",
            evaluation_type="job_performance",
            name="Test",
            component_total_score=Decimal("150.00"),
        )
        with self.assertRaises(DjangoValidationError):
            criterion.full_clean()

    def test_component_total_score_validation_boundary_values(self):
        """Test boundary values for component_total_score"""
        # Test 0.00 (minimum valid)
        criterion1 = KPICriterion(
            target="sales",
            evaluation_type="job_performance",
            name="Test Min",
            component_total_score=Decimal("0.00"),
        )
        criterion1.full_clean()  # Should not raise
        criterion1.save()
        self.assertEqual(criterion1.component_total_score, Decimal("0.00"))

        # Test 100.00 (maximum valid)
        criterion2 = KPICriterion(
            target="sales",
            evaluation_type="job_performance",
            name="Test Max",
            component_total_score=Decimal("100.00"),
        )
        criterion2.full_clean()  # Should not raise
        criterion2.save()
        self.assertEqual(criterion2.component_total_score, Decimal("100.00"))

    def test_ordering_field(self):
        """Test that criteria can be ordered"""
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="First",
            component_total_score=Decimal("50.00"),
            ordering=2,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Second",
            component_total_score=Decimal("50.00"),
            ordering=1,
        )

        # Default ordering should be by target, evaluation_type, ordering, name
        criteria = list(KPICriterion.objects.all())
        self.assertEqual(criteria[0].id, criterion2.id)
        self.assertEqual(criteria[1].id, criterion1.id)

    def test_active_flag_for_soft_delete(self):
        """Test that active flag can be used for soft-delete"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Test",
            component_total_score=Decimal("50.00"),
            active=True,
        )
        self.assertTrue(criterion.active)

        # Soft-delete by setting active=False
        criterion.active = False
        criterion.save()
        self.assertFalse(criterion.active)

    def test_created_by_and_updated_by_tracking(self):
        """Test that created_by and updated_by are tracked correctly"""
        user1 = User.objects.create_user(username="creator", email="creator@example.com")
        user2 = User.objects.create_user(username="updater", email="updater@example.com")

        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Test",
            component_total_score=Decimal("50.00"),
            created_by=user1,
        )
        self.assertEqual(criterion.created_by, user1)
        self.assertIsNone(criterion.updated_by)

        # Update with different user
        criterion.name = "Updated Test"
        criterion.updated_by = user2
        criterion.save()
        self.assertEqual(criterion.created_by, user1)
        self.assertEqual(criterion.updated_by, user2)

    def test_foreign_key_on_delete_set_null(self):
        """Test that user deletion doesn't cascade to criteria"""
        user = User.objects.create_user(username="tempuser", email="temp@example.com")
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Test",
            component_total_score=Decimal("50.00"),
            created_by=user,
        )
        self.assertEqual(criterion.created_by, user)

        # Delete user
        user.delete()

        # Criterion should still exist with created_by=None
        criterion.refresh_from_db()
        self.assertIsNone(criterion.created_by)

    def test_decimal_precision(self):
        """Test that decimal values are stored with correct precision"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Test",
            component_total_score=Decimal("75.50"),
        )
        criterion.refresh_from_db()
        self.assertEqual(criterion.component_total_score, Decimal("75.50"))

    def test_multiple_criteria_same_target(self):
        """Test creating multiple criteria for same target"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="job_performance",
            name="Revenue",
            component_total_score=Decimal("70.00"),
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            name="Attendance",
            component_total_score=Decimal("30.00"),
        )

        sales_criteria = KPICriterion.objects.filter(target="sales")
        self.assertEqual(sales_criteria.count(), 2)

    def test_db_indexes(self):
        """Test that database indexes are created"""
        # This test verifies the model meta configuration
        meta = KPICriterion._meta
        indexes = meta.indexes
        self.assertEqual(len(indexes), 2)

        # Check index fields
        index_fields = [tuple(idx.fields) for idx in indexes]
        self.assertIn(("target", "evaluation_type"), index_fields)
        self.assertIn(("active",), index_fields)
