"""Tests for EmployeeKPIAssessment and related models.

This module tests:
- Model creation and constraints
- Snapshot behavior (criteria changes don't affect existing assessments)
- Score calculation logic
- Grade resolution with ambiguous handling
- Resync functionality
- Unit control validation
- Department auto-assignment
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.hrm.models import Branch, Employee
from apps.payroll.models import (
    EmployeeKPIAssessment,
    EmployeeKPIItem,
    KPIConfig,
    KPICriterion,
)
from apps.payroll.utils import (
    calculate_grade_from_percent,
    create_assessment_items_from_criteria,
    resync_assessment_add_missing,
)

User = get_user_model()


class EmployeeKPIAssessmentModelTest(TestCase):
    """Test cases for EmployeeKPIAssessment model."""
    
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee
    
    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        
        # Create KPI config
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                    {
                        "min": 60,
                        "max": 70,
                        "possible_codes": ["C", "D"],
                        "default_code": "C",
                        "label": "Average or Poor",
                    },
                    {
                        "min": 70,
                        "max": 90,
                        "possible_codes": ["B", "C"],
                        "default_code": "B",
                        "label": "Good or Average",
                    },
                    {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
                ],
                "ambiguous_assignment": "manual",
                "unit_control": {
                    "A": {"max_pct_A": 0.20, "max_pct_B": 0.30, "max_pct_C": 0.50, "min_pct_D": None},
                },
            }
        )
        # Create assessment period
        from apps.payroll.models import KPIAssessmentPeriod
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )
        # Create test criteria
        self.criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
            active=True,
        )
        self.criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Attendance",
            component_total_score=Decimal("30.00"),
            group_number=2,
            order=1,
            active=True,
        )
    def test_create_assessment(self):
        """Test creating an employee KPI assessment."""
        assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
        )
        self.assertIsNotNone(assessment.id)
        self.assertEqual(assessment.employee, self.employee)
        self.assertEqual(assessment.period, self.period)
        self.assertFalse(assessment.finalized)
    def test_unique_constraint(self):
        """Test that employee+period combination is unique."""
        EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
        )
        # Attempting to create duplicate should raise error
        with self.assertRaises(Exception):
            EmployeeKPIAssessment.objects.create(
                employee=self.employee,
                period=self.period,
            )
    def test_create_items_from_criteria(self):
        """Test creating assessment items from criteria snapshots."""
        assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
        )
        criteria = KPICriterion.objects.filter(active=True)
        items = create_assessment_items_from_criteria(assessment, list(criteria))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].criterion, "Revenue Achievement")
        self.assertEqual(items[0].component_total_score, Decimal("70.00"))
        self.assertEqual(items[1].criterion, "Attendance")
        self.assertEqual(items[1].component_total_score, Decimal("30.00"))
    def test_snapshot_preserved_after_criterion_change(self):
        """Test that assessment item snapshots are preserved when criteria change."""
        assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
        )
        criteria = KPICriterion.objects.filter(active=True)
        items = create_assessment_items_from_criteria(assessment, list(criteria))
        # Modify the original criterion
        self.criterion1.component_total_score = Decimal("80.00")
        self.criterion1.criterion = "Updated Revenue Achievement"
        self.criterion1.save()
        # Reload item and check snapshot is unchanged
        item = EmployeeKPIItem.objects.get(id=items[0].id)
        self.assertEqual(item.criterion, "Revenue Achievement")  # Original name
        self.assertEqual(item.component_total_score, Decimal("70.00"))  # Original score
    def test_snapshot_preserved_after_criterion_deletion(self):
        """Test that assessment item snapshots are preserved when criteria are deleted."""
        assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
        )
        criteria = KPICriterion.objects.filter(active=True)
        items = create_assessment_items_from_criteria(assessment, list(criteria))
        # Delete the original criterion
        criterion_id = self.criterion1.id
        self.criterion1.delete()
        # Reload item and check snapshot is preserved, criterion_id is NULL
        item = EmployeeKPIItem.objects.get(id=items[0].id)
        self.assertIsNone(item.criterion_id)
        self.assertEqual(item.criterion, "Revenue Achievement")
        self.assertEqual(item.component_total_score, Decimal("70.00"))
