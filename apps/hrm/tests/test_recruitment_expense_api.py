import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class RecruitmentExpenseAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentExpense API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        RecruitmentExpense.objects.all().delete()
        RecruitmentRequest.objects.all().delete()
        RecruitmentSource.objects.all().delete()
        RecruitmentChannel.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        JobDescription.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

        # Create employees
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            phone="0123456789",
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        self.referee = Employee.objects.create(
            fullname="Tran Van B",
            username="tranvanb",
            email="tranvanb@example.com",
            phone="0123456788",
            attendance_code="EMP002",
            date_of_birth="1991-01-01",
            personal_email="tranvanb.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        self.referrer = Employee.objects.create(
            fullname="Le Thi C",
            username="lethic",
            email="lethic@example.com",
            phone="0123456787",
            attendance_code="EMP003",
            date_of_birth="1992-01-01",
            personal_email="lethic.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create recruitment request with OPEN status
        self.recruitment_request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
            number_of_positions=2,
        )

        # Create recruitment sources (with and without referral)
        self.source_no_referral = RecruitmentSource.objects.create(
            name="LinkedIn",
            allow_referral=False,
        )

        self.source_with_referral = RecruitmentSource.objects.create(
            name="Employee Referral",
            allow_referral=True,
        )

        # Create recruitment channels
        self.channel = RecruitmentChannel.objects.create(
            name="Online Advertising",
        )

        self.expense_data = {
            "date": "2025-10-15",
            "recruitment_source_id": self.source_no_referral.id,
            "recruitment_channel_id": self.channel.id,
            "recruitment_request_id": self.recruitment_request.id,
            "num_candidates_participated": 10,
            "total_cost": "5000.00",
            "num_candidates_hired": 2,
            "activity": "Posted job ad on LinkedIn for 30 days",
            "note": "Good response rate",
        }

    def test_create_recruitment_expense_without_referral(self):
        """Test creating a recruitment expense without referral"""
        url = reverse("hrm:recruitment-expense-list")
        response = self.client.post(url, self.expense_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RecruitmentExpense.objects.count(), 1)

        expense = RecruitmentExpense.objects.first()
        self.assertEqual(str(expense.date), self.expense_data["date"])
        self.assertEqual(expense.recruitment_source_id, self.expense_data["recruitment_source_id"])
        self.assertEqual(expense.recruitment_channel_id, self.expense_data["recruitment_channel_id"])
        self.assertEqual(expense.recruitment_request_id, self.expense_data["recruitment_request_id"])
        self.assertEqual(expense.num_candidates_participated, self.expense_data["num_candidates_participated"])
        self.assertEqual(str(expense.total_cost), self.expense_data["total_cost"])
        self.assertEqual(expense.num_candidates_hired, self.expense_data["num_candidates_hired"])
        self.assertEqual(expense.activity, self.expense_data["activity"])
        self.assertEqual(expense.note, self.expense_data["note"])
        self.assertIsNone(expense.referee)
        self.assertIsNone(expense.referrer)

        # Verify avg_cost is calculated correctly
        self.assertEqual(expense.avg_cost, Decimal("2500.00"))

    def test_create_recruitment_expense_with_referral(self):
        """Test creating a recruitment expense with referral"""
        url = reverse("hrm:recruitment-expense-list")
        data = {
            "date": "2025-10-15",
            "recruitment_source_id": self.source_with_referral.id,
            "recruitment_channel_id": self.channel.id,
            "recruitment_request_id": self.recruitment_request.id,
            "num_candidates_participated": 3,
            "total_cost": "1000.00",
            "num_candidates_hired": 1,
            "referee_id": self.referee.id,
            "referrer_id": self.referrer.id,
            "activity": "Employee referral program",
            "note": "High quality candidates",
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = RecruitmentExpense.objects.first()
        self.assertEqual(expense.referee_id, self.referee.id)
        self.assertEqual(expense.referrer_id, self.referrer.id)

    def test_create_with_referral_source_missing_referee(self):
        """Test that creating expense with referral source requires referee"""
        url = reverse("hrm:recruitment-expense-list")
        data = self.expense_data.copy()
        data["recruitment_source_id"] = self.source_with_referral.id
        # Missing referee_id and referrer_id

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        print(f"content: {content}")
        self.assertIn("error", content)
        error = content["error"]
        print(f"error: {error}")
        self.assertIn("Referee is required when recruitment source allows referral.", str(error))
        self.assertIn("Referrer is required when recruitment source allows referral.", str(error))

    def test_create_with_non_referral_source_and_referee(self):
        """Test that creating expense with non-referral source rejects referee"""
        url = reverse("hrm:recruitment-expense-list")
        data = self.expense_data.copy()
        data["referee_id"] = self.referee.id
        data["referrer_id"] = self.referrer.id

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_create_with_same_referee_and_referrer(self):
        """Test that referee and referrer cannot be the same person"""
        url = reverse("hrm:recruitment-expense-list")
        data = {
            "date": "2025-10-15",
            "recruitment_source_id": self.source_with_referral.id,
            "recruitment_channel_id": self.channel.id,
            "recruitment_request_id": self.recruitment_request.id,
            "num_candidates_participated": 3,
            "total_cost": "1000.00",
            "num_candidates_hired": 1,
            "referee_id": self.referee.id,
            "referrer_id": self.referee.id,  # Same as referee
            "activity": "Employee referral program",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_create_with_draft_recruitment_request_fails(self):
        """Test that expense cannot be created for DRAFT recruitment request"""
        # Create a DRAFT recruitment request
        draft_request = RecruitmentRequest.objects.create(
            name="Draft Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="2000-3000 USD",
        )

        url = reverse("hrm:recruitment-expense-list")
        data = self.expense_data.copy()
        data["recruitment_request_id"] = draft_request.id

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_list_recruitment_expenses(self):
        """Test listing recruitment expenses via API"""
        url = reverse("hrm:recruitment-expense-list")
        self.client.post(url, self.expense_data, format="json")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)

        # Check nested objects are returned
        expense = response_data[0]
        self.assertIn("recruitment_source", expense)
        self.assertIn("recruitment_channel", expense)
        self.assertIn("recruitment_request", expense)
        self.assertIn("avg_cost", expense)
        self.assertEqual(expense["avg_cost"], "2500.00")

    def test_retrieve_recruitment_expense(self):
        """Test retrieving a recruitment expense via API"""
        url = reverse("hrm:recruitment-expense-list")
        create_response = self.client.post(url, self.expense_data, format="json")
        expense_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-expense-detail", kwargs={"pk": expense_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["activity"], self.expense_data["activity"])
        self.assertEqual(response_data["total_cost"], self.expense_data["total_cost"])

    def test_update_recruitment_expense(self):
        """Test updating a recruitment expense via API"""
        url = reverse("hrm:recruitment-expense-list")
        create_response = self.client.post(url, self.expense_data, format="json")
        expense_id = self.get_response_data(create_response)["id"]

        update_data = {
            "date": "2025-10-15",
            "recruitment_source_id": self.source_no_referral.id,
            "recruitment_channel_id": self.channel.id,
            "recruitment_request_id": self.recruitment_request.id,
            "num_candidates_participated": 12,
            "total_cost": "6000.00",
            "num_candidates_hired": 3,
            "activity": "Extended job ad on LinkedIn for 45 days",
            "note": "Increased budget for better reach",
        }

        url = reverse("hrm:recruitment-expense-detail", kwargs={"pk": expense_id})
        response = self.client.put(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["num_candidates_participated"], update_data["num_candidates_participated"])
        self.assertEqual(response_data["total_cost"], update_data["total_cost"])
        self.assertEqual(response_data["num_candidates_hired"], update_data["num_candidates_hired"])
        self.assertEqual(response_data["avg_cost"], "2000.00")

    def test_partial_update_recruitment_expense(self):
        """Test partially updating a recruitment expense via API"""
        url = reverse("hrm:recruitment-expense-list")
        create_response = self.client.post(url, self.expense_data, format="json")
        expense_id = self.get_response_data(create_response)["id"]

        partial_data = {
            "num_candidates_hired": 3,
            "note": "Additional candidate hired",
        }

        url = reverse("hrm:recruitment-expense-detail", kwargs={"pk": expense_id})
        response = self.client.patch(url, partial_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["num_candidates_hired"], partial_data["num_candidates_hired"])
        self.assertEqual(response_data["note"], partial_data["note"])
        # Other fields should remain unchanged
        self.assertEqual(response_data["activity"], self.expense_data["activity"])
        # avg_cost should be recalculated
        self.assertEqual(response_data["avg_cost"], "1666.67")

    def test_delete_recruitment_expense(self):
        """Test deleting a recruitment expense"""
        url = reverse("hrm:recruitment-expense-list")
        create_response = self.client.post(url, self.expense_data, format="json")
        expense_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-expense-detail", kwargs={"pk": expense_id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RecruitmentExpense.objects.count(), 0)

    def test_avg_cost_calculation_zero_hires(self):
        """Test avg_cost is 0.00 when no candidates hired"""
        url = reverse("hrm:recruitment-expense-list")
        data = self.expense_data.copy()
        data["num_candidates_hired"] = 0
        create_response = self.client.post(url, data, format="json")

        response_data = self.get_response_data(create_response)
        self.assertEqual(response_data["avg_cost"], "0.00")

    def test_ordering_by_date(self):
        """Test ordering recruitment expenses by date"""
        url = reverse("hrm:recruitment-expense-list")

        # Create multiple expenses
        data1 = self.expense_data.copy()
        data1["date"] = "2025-10-10"
        data1["activity"] = "Expense 1"
        self.client.post(url, data1, format="json")

        data2 = self.expense_data.copy()
        data2["date"] = "2025-10-20"
        data2["activity"] = "Expense 2"
        self.client.post(url, data2, format="json")

        # Order by date ascending
        response = self.client.get(url, {"ordering": "date"})
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]["date"], "2025-10-10")
        self.assertEqual(response_data[1]["date"], "2025-10-20")

    def test_ordering_by_total_cost(self):
        """Test ordering recruitment expenses by total_cost"""
        url = reverse("hrm:recruitment-expense-list")

        # Create multiple expenses
        data1 = self.expense_data.copy()
        data1["total_cost"] = "3000.00"
        data1["date"] = "2025-10-10"
        self.client.post(url, data1, format="json")

        data2 = self.expense_data.copy()
        data2["total_cost"] = "8000.00"
        data2["date"] = "2025-10-20"
        self.client.post(url, data2, format="json")

        # Order by total_cost descending
        response = self.client.get(url, {"ordering": "-total_cost"})
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]["total_cost"], "8000.00")
        self.assertEqual(response_data[1]["total_cost"], "3000.00")

    def test_required_fields(self):
        """Test that required fields are validated"""
        url = reverse("hrm:recruitment-expense-list")

        # Test without date
        data = self.expense_data.copy()
        del data["date"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without recruitment_source_id
        data = self.expense_data.copy()
        del data["recruitment_source_id"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without recruitment_channel_id
        data = self.expense_data.copy()
        del data["recruitment_channel_id"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without recruitment_request_id
        data = self.expense_data.copy()
        del data["recruitment_request_id"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test without total_cost
        data = self.expense_data.copy()
        del data["total_cost"]
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nested_objects_in_response(self):
        """Test that nested objects are included in API response"""
        url = reverse("hrm:recruitment-expense-list")
        create_response = self.client.post(url, self.expense_data, format="json")
        expense_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-expense-detail", kwargs={"pk": expense_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Check recruitment_source nested object
        self.assertIn("recruitment_source", response_data)
        source = response_data["recruitment_source"]
        self.assertIn("id", source)
        self.assertIn("code", source)
        self.assertIn("name", source)
        self.assertIn("allow_referral", source)
        self.assertEqual(source["allow_referral"], False)

        # Check recruitment_channel nested object
        self.assertIn("recruitment_channel", response_data)
        channel = response_data["recruitment_channel"]
        self.assertIn("id", channel)
        self.assertIn("code", channel)
        self.assertIn("name", channel)

        # Check recruitment_request nested object
        self.assertIn("recruitment_request", response_data)
        request = response_data["recruitment_request"]
        self.assertIn("id", request)
        self.assertIn("code", request)
        self.assertIn("name", request)

    def test_referral_nested_objects(self):
        """Test that referee and referrer nested objects are included"""
        url = reverse("hrm:recruitment-expense-list")
        data = {
            "date": "2025-10-15",
            "recruitment_source_id": self.source_with_referral.id,
            "recruitment_channel_id": self.channel.id,
            "recruitment_request_id": self.recruitment_request.id,
            "num_candidates_participated": 3,
            "total_cost": "1000.00",
            "num_candidates_hired": 1,
            "referee_id": self.referee.id,
            "referrer_id": self.referrer.id,
            "activity": "Employee referral program",
        }
        create_response = self.client.post(url, data, format="json")
        expense_id = self.get_response_data(create_response)["id"]

        url = reverse("hrm:recruitment-expense-detail", kwargs={"pk": expense_id})
        response = self.client.get(url)

        response_data = self.get_response_data(response)

        # Check referee nested object
        self.assertIn("referee", response_data)
        referee = response_data["referee"]
        self.assertIn("id", referee)
        self.assertIn("code", referee)
        self.assertIn("fullname", referee)
        self.assertEqual(referee["id"], self.referee.id)

        # Check referrer nested object
        self.assertIn("referrer", response_data)
        referrer = response_data["referrer"]
        self.assertIn("id", referrer)
        self.assertIn("code", referrer)
        self.assertIn("fullname", referrer)
        self.assertEqual(referrer["id"], self.referrer.id)

    def test_search_by_activity(self):
        """Test searching expenses by activity field"""
        url = reverse("hrm:recruitment-expense-list")

        # Create expenses with different activities
        data1 = self.expense_data.copy()
        data1["activity"] = "LinkedIn advertising campaign"
        data1["date"] = "2025-10-10"
        self.client.post(url, data1, format="json")

        data2 = self.expense_data.copy()
        data2["activity"] = "Employee referral program"
        data2["date"] = "2025-10-15"
        self.client.post(url, data2, format="json")

        # Search for "LinkedIn"
        response = self.client.get(url, {"search": "LinkedIn"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertIn("LinkedIn", response_data[0]["activity"])

    def test_search_by_note(self):
        """Test searching expenses by note field"""
        url = reverse("hrm:recruitment-expense-list")

        # Create expenses with different notes
        data1 = self.expense_data.copy()
        data1["note"] = "High quality candidates"
        data1["date"] = "2025-10-10"
        self.client.post(url, data1, format="json")

        data2 = self.expense_data.copy()
        data2["note"] = "Low response rate"
        data2["date"] = "2025-10-15"
        self.client.post(url, data2, format="json")

        # Search for "quality"
        response = self.client.get(url, {"search": "quality"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertIn("quality", response_data[0]["note"])

    def test_export_recruitment_expense_direct(self):
        """Test exporting recruitment expenses with direct delivery"""
        url = reverse("hrm:recruitment-expense-list")

        # Create test expenses
        self.client.post(url, self.expense_data, format="json")
        expense_data_2 = self.expense_data.copy()
        expense_data_2["date"] = "2025-10-16"
        expense_data_2["total_cost"] = "3000.00"
        expense_data_2["num_candidates_hired"] = 1
        self.client.post(url, expense_data_2, format="json")

        # Export with direct delivery
        export_url = reverse("hrm:recruitment-expense-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])

    def test_export_recruitment_expense_fields(self):
        """Test that export includes correct fields"""
        url = reverse("hrm:recruitment-expense-list")

        # Create a test expense
        response = self.client.post(url, self.expense_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Export with direct delivery to check fields
        export_url = reverse("hrm:recruitment-expense-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        # File should be generated and downloadable
        self.assertTrue(len(response.content) > 0)

    def test_export_recruitment_expense_filtered(self):
        """Test exporting filtered recruitment expenses"""
        url = reverse("hrm:recruitment-expense-list")

        # Create expenses with different dates
        self.client.post(url, self.expense_data, format="json")
        expense_data_2 = self.expense_data.copy()
        expense_data_2["date"] = "2025-11-15"
        self.client.post(url, expense_data_2, format="json")

        # Export with date filter
        export_url = reverse("hrm:recruitment-expense-export")
        response = self.client.get(export_url, {"delivery": "direct", "date": "2025-10-15"})

        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertTrue(len(response.content) > 0)
