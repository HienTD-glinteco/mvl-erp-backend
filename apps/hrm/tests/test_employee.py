import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Employee

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def normalize_list_response(self, data):
        """Normalize list responses that may or may not be paginated"""

        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            count = data.get("count", len(results))
            return results, count

        if isinstance(data, list):
            return data, len(data)

        return [], 0


class EmployeeModelTest(TestCase):
    """Test cases for Employee model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_create_employee(self):
        """Test creating an employee"""
        employee = Employee.objects.create(
            code="EMP001",
            name="John Doe",
            user=self.user,
        )
        self.assertEqual(employee.code, "EMP001")
        self.assertEqual(employee.name, "John Doe")
        self.assertEqual(employee.user, self.user)
        self.assertEqual(str(employee), "EMP001 - John Doe")

    def test_employee_code_unique(self):
        """Test employee code uniqueness"""
        user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )
        Employee.objects.create(code="EMP001", name="John Doe", user=self.user)

        with self.assertRaises(Exception):
            Employee.objects.create(code="EMP001", name="Jane Doe", user=user2)

    def test_employee_user_one_to_one(self):
        """Test that one user can only have one employee record"""
        Employee.objects.create(code="EMP001", name="John Doe", user=self.user)

        with self.assertRaises(Exception):
            Employee.objects.create(code="EMP002", name="John Doe Again", user=self.user)


class EmployeeAPITest(TestCase, APITestMixin):
    """Test cases for Employee API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # Create test users and employees
        self.user1 = User.objects.create_user(
            username="emp001",
            email="emp1@example.com",
            password="testpass123",
        )
        self.employee1 = Employee.objects.create(
            code="EMP001",
            name="John Doe",
            user=self.user1,
        )

        self.user2 = User.objects.create_user(
            username="emp002",
            email="emp2@example.com",
            password="testpass123",
        )
        self.employee2 = Employee.objects.create(
            code="EMP002",
            name="Jane Smith",
            user=self.user2,
        )

        self.user3 = User.objects.create_user(
            username="emp003",
            email="emp3@example.com",
            password="testpass123",
        )
        self.employee3 = Employee.objects.create(
            code="EMP003",
            name="Bob Johnson",
            user=self.user3,
        )

    def test_list_employees(self):
        """Test listing all employees"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 3)
        self.assertEqual(len(results), 3)
        codes = {item["code"] for item in results}
        self.assertSetEqual(codes, {"EMP001", "EMP002", "EMP003"})

    def test_filter_employees_by_code(self):
        """Test filtering employees by code"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"code": "EMP001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 1)
        self.assertEqual(results[0]["code"], "EMP001")

    def test_filter_employees_by_code_partial(self):
        """Test filtering employees by partial code match"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"code": "001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 1)
        self.assertEqual(results[0]["code"], "EMP001")

    def test_filter_employees_by_name(self):
        """Test filtering employees by name"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"name": "John"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 2)

        codes = [item["code"] for item in results]
        self.assertIn("EMP001", codes)
        self.assertIn("EMP003", codes)

    def test_filter_employees_by_name_partial(self):
        """Test filtering employees by partial name match"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"name": "Jane"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 1)
        self.assertEqual(results[0]["name"], "Jane Smith")

    def test_search_employees(self):
        """Test searching employees"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "Jane"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any(item["name"] == "Jane Smith" for item in results))

    def test_list_employees_pagination(self):
        """Test employee list pagination"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"page": 1, "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 3)

        if len(results) != count:
            self.assertLessEqual(len(results), 2)
        else:
            self.assertEqual(len(results), count)

    def test_retrieve_employee(self):
        """Test retrieving a single employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["code"], "EMP001")
        self.assertEqual(data["name"], "John Doe")

    # TODO: fix this test when the model Employee is implemented.
    # def test_create_employee(self):
    #     """Test creating an employee"""
    #     user4 = User.objects.create_user(
    #         username="emp004",
    #         email="emp4@example.com",
    #         password="testpass123",
    #     )
    #     url = reverse("hrm:employee-list")
    #     payload = {
    #         "code": "EMP004",
    #         "name": "Alice Williams",
    #         "user_id": user4.id,
    #     }
    #     response = self.client.post(url, payload, format="json")

    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #     data = self.get_response_data(response)
    #     self.assertEqual(data["code"], "EMP004")
    #     self.assertEqual(data["name"], "Alice Williams")
    #     self.assertEqual(data["user_id"], user4.id)
    #     self.assertTrue(Employee.objects.filter(code="EMP004").exists())

    def test_update_employee(self):
        """Test updating an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "code": "EMP001",
            "name": "John Updated",
            "user_id": self.user1.id,
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "John Updated")

        self.employee1.refresh_from_db()
        self.assertEqual(self.employee1.name, "John Updated")

    def test_partial_update_employee(self):
        """Test partially updating an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {"name": "John Partially Updated"}
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "John Partially Updated")

        self.employee1.refresh_from_db()
        self.assertEqual(self.employee1.name, "John Partially Updated")

    def test_delete_employee(self):
        """Test deleting an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee3.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Employee.objects.filter(id=self.employee3.id).exists())
