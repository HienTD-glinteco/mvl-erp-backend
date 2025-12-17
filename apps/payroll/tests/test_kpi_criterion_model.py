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
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            description="Monthly revenue target achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
            active=True,
            created_by=self.user,
        )

        self.assertIsNotNone(criterion.id)
        self.assertEqual(criterion.target, "sales")
        self.assertEqual(criterion.evaluation_type, "work_performance")
        self.assertEqual(criterion.criterion, "Revenue Achievement")
        self.assertEqual(criterion.component_total_score, Decimal("70.00"))
        self.assertEqual(criterion.group_number, 1)
        self.assertEqual(criterion.order, 1)
        self.assertTrue(criterion.active)
        self.assertEqual(criterion.created_by, self.user)
        self.assertIsNotNone(criterion.created_at)
        self.assertIsNotNone(criterion.updated_at)

    def test_str_representation(self):
        """Test string representation of KPICriterion"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        expected_str = "sales - work_performance - Revenue Achievement"
        self.assertEqual(str(criterion), expected_str)

    def test_default_values(self):
        """Test that default values are set correctly"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test Criterion",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        self.assertTrue(criterion.active)
        self.assertEqual(criterion.description, "")
        self.assertIsNone(criterion.sub_criterion)

    def test_unique_together_constraint(self):
        """Test that (target, evaluation_type, criterion, sub_criterion) must be unique

        Note: In SQLite, NULL values are not considered equal in unique constraints,
        so we test with non-NULL sub_criterion values.
        """
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            sub_criterion="Monthly target",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )

        # Try to create duplicate (same target, evaluation_type, criterion, and sub_criterion)
        from django.db import transaction

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                KPICriterion.objects.create(
                    target="sales",
                    evaluation_type="work_performance",
                    criterion="Revenue Achievement",
                    sub_criterion="Monthly target",
                    component_total_score=Decimal("80.00"),
                    group_number=1,
                    order=2,
                )

    def test_unique_constraint_allows_different_target(self):
        """Test that same criterion name is allowed for different target"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )

        # Should succeed with different target
        criterion2 = KPICriterion.objects.create(
            target="backoffice",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        self.assertIsNotNone(criterion2.id)

    def test_unique_constraint_allows_different_evaluation_type(self):
        """Test that same criterion name is allowed for different evaluation_type"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Attendance",
            component_total_score=Decimal("30.00"),
            group_number=1,
            order=1,
        )

        # Should succeed with different evaluation_type
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Attendance",
            component_total_score=Decimal("30.00"),
            group_number=2,
            order=1,
        )
        self.assertIsNotNone(criterion2.id)

    def test_component_total_score_validation_min(self):
        """Test that component_total_score cannot be less than 0"""
        criterion = KPICriterion(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("-10.00"),
            group_number=1,
            order=1,
        )
        with self.assertRaises(DjangoValidationError):
            criterion.full_clean()

    def test_component_total_score_validation_max(self):
        """Test that component_total_score cannot be greater than 100"""
        criterion = KPICriterion(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("150.00"),
            group_number=1,
            order=1,
        )
        with self.assertRaises(DjangoValidationError):
            criterion.full_clean()

    def test_component_total_score_validation_boundary_values(self):
        """Test boundary values for component_total_score"""
        # Test 0.00 (minimum valid)
        criterion1 = KPICriterion(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test Min",
            component_total_score=Decimal("0.00"),
            group_number=1,
            order=1,
        )
        criterion1.full_clean()  # Should not raise
        criterion1.save()
        self.assertEqual(criterion1.component_total_score, Decimal("0.00"))

        # Test 100.00 (maximum valid)
        criterion2 = KPICriterion(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test Max",
            component_total_score=Decimal("100.00"),
            group_number=1,
            order=2,
        )
        criterion2.full_clean()  # Should not raise
        criterion2.save()
        self.assertEqual(criterion2.component_total_score, Decimal("100.00"))

    def test_ordering_field(self):
        """Test that criteria can be ordered"""
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="First",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=2,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Second",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )

        # Default ordering should be by evaluation_type, order
        criteria = list(KPICriterion.objects.all())
        self.assertEqual(criteria[0].id, criterion2.id)
        self.assertEqual(criteria[1].id, criterion1.id)

    def test_active_flag_for_soft_delete(self):
        """Test that active flag can be used for soft-delete"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
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
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
            created_by=user1,
        )
        self.assertEqual(criterion.created_by, user1)
        self.assertIsNone(criterion.updated_by)

        # Update with different user
        criterion.criterion = "Updated Test"
        criterion.updated_by = user2
        criterion.save()
        self.assertEqual(criterion.created_by, user1)
        self.assertEqual(criterion.updated_by, user2)

    def test_foreign_key_on_delete_set_null(self):
        """Test that user deletion doesn't cascade to criteria"""
        user = User.objects.create_user(username="tempuser", email="temp@example.com")
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
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
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("75.50"),
            group_number=1,
            order=1,
        )
        criterion.refresh_from_db()
        self.assertEqual(criterion.component_total_score, Decimal("75.50"))

    def test_multiple_criteria_same_target(self):
        """Test creating multiple criteria for same target"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Attendance",
            component_total_score=Decimal("30.00"),
            group_number=2,
            order=1,
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

    def test_evaluation_type_choices(self):
        """Test that evaluation_type accepts only valid choices"""
        # Test valid choices
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test Work Performance",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        self.assertEqual(criterion1.evaluation_type, "work_performance")

        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Test Discipline",
            component_total_score=Decimal("50.00"),
            group_number=2,
            order=1,
        )
        self.assertEqual(criterion2.evaluation_type, "discipline")

    def test_ordering_by_evaluation_type_then_order(self):
        """Test that criteria are ordered by evaluation_type first, then by order"""
        # Create criteria with different evaluation types and orders
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Discipline 1",
            component_total_score=Decimal("25.00"),
            group_number=1,
            order=1,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Work 2",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=2,
        )
        criterion3 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Work 1",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        criterion4 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Discipline 2",
            component_total_score=Decimal("25.00"),
            group_number=1,
            order=2,
        )

        # Get all criteria in default order
        criteria = list(KPICriterion.objects.all())

        # discipline comes before work_performance alphabetically
        # Within each type, order should be ascending
        self.assertEqual(criteria[0].id, criterion1.id)  # discipline, order 1
        self.assertEqual(criteria[1].id, criterion4.id)  # discipline, order 2
        self.assertEqual(criteria[2].id, criterion3.id)  # work_performance, order 1
        self.assertEqual(criteria[3].id, criterion2.id)  # work_performance, order 2

    def test_sub_criterion_field(self):
        """Test that sub_criterion field works correctly"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            sub_criterion="Monthly target",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        self.assertEqual(criterion.sub_criterion, "Monthly target")

        # Test nullable sub_criterion
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Attendance",
            component_total_score=Decimal("30.00"),
            group_number=2,
            order=1,
        )
        self.assertIsNone(criterion2.sub_criterion)

    def test_group_number_field(self):
        """Test that group_number field works correctly"""
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Customer Satisfaction",
            component_total_score=Decimal("30.00"),
            group_number=1,
            order=2,
        )
        criterion3 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Attendance",
            component_total_score=Decimal("20.00"),
            group_number=2,
            order=1,
        )

        # Criteria with the same group_number
        group1_criteria = KPICriterion.objects.filter(group_number=1)
        self.assertEqual(group1_criteria.count(), 2)

        group2_criteria = KPICriterion.objects.filter(group_number=2)
        self.assertEqual(group2_criteria.count(), 1)
