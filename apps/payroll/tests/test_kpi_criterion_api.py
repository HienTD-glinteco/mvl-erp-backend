import json
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.models import User
from apps.payroll.models import KPICriterion


@pytest.mark.django_db
class KPICriterionAPITest(APITestCase):
    """Test cases for KPICriterion API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create a superuser to bypass permissions for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.valid_data = {
            "target": "sales",
            "evaluation_type": "work_performance",
            "criterion": "Revenue Achievement",
            "description": "Monthly revenue target achievement",
            "component_total_score": "70.00",
            "group_number": 1,
            "order": 1,
            "active": True,
        }

    def test_list_criteria_empty(self):
        """Test listing criteria when none exist"""
        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        self.assertEqual(response_data["data"]["count"], 0)
        self.assertEqual(response_data["data"]["results"], [])

    def test_list_criteria_success(self):
        """Test listing criteria successfully"""
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Attendance",
            component_total_score=Decimal("30.00"),
            group_number=2,
            order=1,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        self.assertEqual(response_data["data"]["count"], 2)
        self.assertEqual(len(response_data["data"]["results"]), 2)

    def test_retrieve_criterion_success(self):
        """Test retrieving a single criterion"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            description="Monthly revenue target achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
            active=True,
        )

        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": criterion.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        data = response_data["data"]
        self.assertEqual(data["id"], criterion.id)
        self.assertEqual(data["target"], "sales")
        self.assertEqual(data["evaluation_type"], "work_performance")
        self.assertEqual(data["criterion"], "Revenue Achievement")
        self.assertEqual(data["component_total_score"], "70.00")

    def test_retrieve_criterion_not_found(self):
        """Test retrieving non-existent criterion"""
        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": 9999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertIsNotNone(response_data["error"])

    def test_create_criterion_success(self):
        """Test creating a criterion successfully"""
        url = reverse("payroll:kpi-criteria-list")
        response = self.client.post(url, data=self.valid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        data = response_data["data"]
        self.assertIsNotNone(data["id"])
        self.assertEqual(data["target"], "sales")
        self.assertEqual(data["created_by"], self.user.id)

        # Verify in database
        criterion = KPICriterion.objects.get(id=data["id"])
        self.assertEqual(criterion.target, "sales")
        self.assertEqual(criterion.created_by, self.user)

    def test_create_criterion_missing_required_field(self):
        """Test creating criterion with missing required field"""
        data = self.valid_data.copy()
        del data["evaluation_type"]

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        # Error format: {type: 'validation_error', errors: [{attr: 'field', ...}]}
        error = response_data["error"]
        self.assertEqual(error["type"], "validation_error")
        error_attrs = [e["attr"] for e in error["errors"]]
        self.assertIn("evaluation_type", error_attrs)

    def test_create_criterion_invalid_score(self):
        """Test creating criterion with invalid score"""
        data = self.valid_data.copy()
        data["component_total_score"] = "150.00"

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        # Error format: {type: 'validation_error', errors: [{attr: 'field', ...}]}
        error = response_data["error"]
        self.assertEqual(error["type"], "validation_error")
        error_attrs = [e["attr"] for e in error["errors"]]
        self.assertIn("component_total_score", error_attrs)

    def test_create_criterion_duplicate(self):
        """Test creating duplicate criterion"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.post(url, data=self.valid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        # Error format: {type: 'validation_error', errors: [{attr: 'field', ...}]}
        error = response_data["error"]
        self.assertEqual(error["type"], "validation_error")
        error_attrs = [e["attr"] for e in error["errors"]]
        self.assertIn("non_field_errors", error_attrs)

    def test_update_criterion_success(self):
        """Test updating a criterion (PUT)"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
            created_by=self.user,
        )

        update_data = {
            "target": "sales",
            "evaluation_type": "work_performance",
            "criterion": "Revenue Achievement",
            "description": "Updated description",
            "component_total_score": "75.00",
            "group_number": 1,
            "order": 2,
            "active": True,
        }

        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": criterion.pk})
        response = self.client.put(url, data=update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(data["description"], "Updated description")
        self.assertEqual(data["component_total_score"], "75.00")
        self.assertEqual(data["updated_by"], self.user.id)

        # Verify in database
        criterion.refresh_from_db()
        self.assertEqual(criterion.description, "Updated description")
        self.assertEqual(criterion.updated_by, self.user)

    def test_partial_update_criterion_success(self):
        """Test partially updating a criterion (PATCH)"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
            active=True,
        )

        update_data = {"active": False}

        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": criterion.pk})
        response = self.client.patch(url, data=update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertFalse(data["active"])

        # Other fields should remain unchanged
        self.assertEqual(data["target"], "sales")
        self.assertEqual(data["component_total_score"], "70.00")

    def test_delete_criterion_success(self):
        """Test deleting a criterion"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )

        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": criterion.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        self.assertFalse(KPICriterion.objects.filter(id=criterion.id).exists())

    def test_delete_criterion_not_found(self):
        """Test deleting non-existent criterion"""
        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": 9999})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_by_target(self):
        """Test filtering criteria by target"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        KPICriterion.objects.create(
            target="backoffice",
            evaluation_type="work_performance",
            criterion="Efficiency",
            component_total_score=Decimal("60.00"),
            group_number=1,
            order=1,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"target": "sales"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["count"], 1)
        self.assertEqual(response_data["data"]["results"][0]["target"], "sales")

    def test_filter_by_evaluation_type(self):
        """Test filtering criteria by evaluation_type"""
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

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"evaluation_type": "discipline"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["count"], 1)
        self.assertEqual(response_data["data"]["results"][0]["evaluation_type"], "discipline")

    def test_filter_by_active(self):
        """Test filtering criteria by active status"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Active Criterion",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
            active=True,
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Inactive Criterion",
            component_total_score=Decimal("30.00"),
            group_number=1,
            order=2,
            active=False,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"active": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["count"], 1)
        self.assertTrue(response_data["data"]["results"][0]["active"])

    def test_search_by_name(self):
        """Test searching criteria by criterion name"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Revenue Achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Customer Satisfaction",
            component_total_score=Decimal("30.00"),
            group_number=1,
            order=2,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"search": "Revenue"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["count"], 1)
        self.assertIn("Revenue", response_data["data"]["results"][0]["criterion"])

    def test_search_by_description(self):
        """Test searching criteria by description"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Criterion 1",
            description="Monthly target achievement",
            component_total_score=Decimal("70.00"),
            group_number=1,
            order=1,
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Criterion 2",
            description="Daily attendance record",
            component_total_score=Decimal("30.00"),
            group_number=1,
            order=2,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"search": "attendance"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["count"], 1)

    def test_ordering_by_name(self):
        """Test ordering criteria by criterion name"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="B Criterion",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="A Criterion",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=2,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"ordering": "criterion"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        results = response_data["data"]["results"]
        self.assertEqual(results[0]["criterion"], "A Criterion")
        self.assertEqual(results[1]["criterion"], "B Criterion")

    def test_ordering_descending(self):
        """Test ordering criteria in descending order"""
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="First",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Second",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=2,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"ordering": "-created_at"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        results = response_data["data"]["results"]
        self.assertEqual(results[0]["id"], criterion2.id)

    def test_pagination(self):
        """Test pagination of criteria list"""
        # Create multiple criteria
        for i in range(15):
            KPICriterion.objects.create(
                target="sales",
                evaluation_type="work_performance",
                criterion=f"Criterion {i}",
                component_total_score=Decimal("50.00"),
                group_number=1,
                order=i,
            )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url, {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertEqual(response_data["data"]["count"], 15)
        self.assertEqual(len(response_data["data"]["results"]), 10)
        self.assertIsNotNone(response_data["data"]["next"])

    def test_response_envelope_format(self):
        """Test that responses follow the envelope format"""
        criterion = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )

        url = reverse("payroll:kpi-criteria-detail", kwargs={"pk": criterion.pk})
        response = self.client.get(url)

        response_data = json.loads(response.content)

        # Check envelope structure
        self.assertIn("success", response_data)
        self.assertIn("data", response_data)
        self.assertIn("error", response_data)

        # For success response
        self.assertTrue(response_data["success"])
        self.assertIsNotNone(response_data["data"])
        self.assertIsNone(response_data["error"])

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected"""
        KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Test",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )

        # Create a new client without authentication
        unauthenticated_client = APIClient()
        url = reverse("payroll:kpi-criteria-list")
        response = unauthenticated_client.get(url)

        # Should be 401 or 403 depending on permission configuration
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_default_ordering_by_evaluation_type_and_order(self):
        """Test that default ordering is by evaluation_type (discipline first, then work_performance) and order"""
        # Create criteria with different evaluation types and orders
        criterion1 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Work 1",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=1,
        )
        criterion2 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Discipline 1",
            component_total_score=Decimal("25.00"),
            group_number=2,
            order=1,
        )
        criterion3 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="work_performance",
            criterion="Work 2",
            component_total_score=Decimal("50.00"),
            group_number=1,
            order=2,
        )
        criterion4 = KPICriterion.objects.create(
            target="sales",
            evaluation_type="discipline",
            criterion="Discipline 2",
            component_total_score=Decimal("25.00"),
            group_number=2,
            order=2,
        )

        url = reverse("payroll:kpi-criteria-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        results = response_data["data"]["results"]

        # discipline comes before work_performance alphabetically
        # Within each type, order should be ascending
        self.assertEqual(results[0]["id"], criterion2.id)  # discipline, order 1
        self.assertEqual(results[1]["id"], criterion4.id)  # discipline, order 2
        self.assertEqual(results[2]["id"], criterion1.id)  # work_performance, order 1
        self.assertEqual(results[3]["id"], criterion3.id)  # work_performance, order 2
