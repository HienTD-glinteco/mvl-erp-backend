import json
from datetime import date

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
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)
from libs import ColorVariant

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


class RecruitmentCandidateAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentCandidate API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        RecruitmentCandidate.objects.all().delete()
        RecruitmentRequest.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        JobDescription.objects.all().delete()
        RecruitmentSource.objects.all().delete()
        RecruitmentChannel.objects.all().delete()
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

        # Create employee
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            phone="0123456789",
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="emp.personal@example.com",
            start_date="2024-01-01",
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create recruitment request
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

        # Create recruitment source and channel
        self.recruitment_source = RecruitmentSource.objects.create(
            name="LinkedIn",
            description="Professional networking platform",
        )

        self.recruitment_channel = RecruitmentChannel.objects.create(
            name="Job Website",
            belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE,
            description="Online job posting platform",
        )

    def test_list_candidates(self):
        """Test listing recruitment candidates"""
        # Create test candidates
        candidate1 = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        candidate2 = RecruitmentCandidate.objects.create(
            name="Tran Thi C",
            citizen_id="123456789013",
            email="tranthic@example.com",
            phone="0987654321",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
        )

        url = reverse("hrm:recruitment-candidate-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_create_candidate(self):
        """Test creating a new recruitment candidate"""
        url = reverse("hrm:recruitment-candidate-list")
        data = {
            "name": "Nguyen Van B",
            "citizen_id": "123456789012",
            "email": "nguyenvanb@example.com",
            "phone": "0123456789",
            "recruitment_request_id": self.recruitment_request.id,
            "recruitment_source_id": self.recruitment_source.id,
            "recruitment_channel_id": self.recruitment_channel.id,
            "years_of_experience": 5,
            "submitted_date": "2025-10-15",
            "status": "CONTACTED",
            "note": "Strong Python skills",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], "Nguyen Van B")
        self.assertEqual(response_data["citizen_id"], "123456789012")
        self.assertEqual(response_data["email"], "nguyenvanb@example.com")

        # Verify candidate was created in database
        candidate = RecruitmentCandidate.objects.get(email="nguyenvanb@example.com")
        self.assertEqual(candidate.name, "Nguyen Van B")
        self.assertEqual(candidate.branch, self.recruitment_request.branch)
        self.assertEqual(candidate.block, self.recruitment_request.block)
        self.assertEqual(candidate.department, self.recruitment_request.department)

    def test_create_candidate_invalid_citizen_id(self):
        """Test creating candidate with invalid citizen ID"""
        url = reverse("hrm:recruitment-candidate-list")
        data = {
            "name": "Nguyen Van B",
            "citizen_id": "12345",  # Too short
            "email": "nguyenvanb@example.com",
            "phone": "0123456789",
            "recruitment_request_id": self.recruitment_request.id,
            "recruitment_source_id": self.recruitment_source.id,
            "recruitment_channel_id": self.recruitment_channel.id,
            "years_of_experience": 5,
            "submitted_date": "2025-10-15",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_candidate_hired_without_onboard_date(self):
        """Test creating hired candidate without onboard_date"""
        url = reverse("hrm:recruitment-candidate-list")
        data = {
            "name": "Nguyen Van B",
            "citizen_id": "123456789012",
            "email": "nguyenvanb@example.com",
            "phone": "0123456789",
            "recruitment_request_id": self.recruitment_request.id,
            "recruitment_source_id": self.recruitment_source.id,
            "recruitment_channel_id": self.recruitment_channel.id,
            "years_of_experience": 5,
            "submitted_date": "2025-10-15",
            "status": "HIRED",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_candidate_hired_with_onboard_date(self):
        """Test creating hired candidate with onboard_date"""
        url = reverse("hrm:recruitment-candidate-list")
        data = {
            "name": "Nguyen Van B",
            "citizen_id": "123456789012",
            "email": "nguyenvanb@example.com",
            "phone": "0123456789",
            "recruitment_request_id": self.recruitment_request.id,
            "recruitment_source_id": self.recruitment_source.id,
            "recruitment_channel_id": self.recruitment_channel.id,
            "years_of_experience": 5,
            "submitted_date": "2025-10-15",
            "status": "HIRED",
            "onboard_date": "2025-11-01",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["colored_status"]["value"], "HIRED")
        self.assertEqual(response_data["onboard_date"], "2025-11-01")

    def test_retrieve_candidate(self):
        """Test retrieving a specific candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], "Nguyen Van B")
        self.assertEqual(response_data["citizen_id"], "123456789012")

    def test_update_candidate(self):
        """Test updating a candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        data = {
            "name": "Nguyen Van B Updated",
            "citizen_id": "123456789012",
            "email": "nguyenvanb@example.com",
            "phone": "0123456789",
            "recruitment_request_id": self.recruitment_request.id,
            "recruitment_source_id": self.recruitment_source.id,
            "recruitment_channel_id": self.recruitment_channel.id,
            "years_of_experience": 6,
            "submitted_date": "2025-10-15",
            "status": "INTERVIEWED_1",
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], "Nguyen Van B Updated")
        self.assertEqual(response_data["years_of_experience"], 6)
        self.assertEqual(response_data["colored_status"]["value"], "INTERVIEWED_1")

    def test_partial_update_candidate(self):
        """Test partially updating a candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        data = {
            "status": "HIRED",
            "onboard_date": "2025-11-01",
        }

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["colored_status"]["value"], "HIRED")
        self.assertEqual(response_data["onboard_date"], "2025-11-01")

    def test_delete_candidate(self):
        """Test deleting a candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify candidate was deleted
        self.assertFalse(RecruitmentCandidate.objects.filter(id=candidate.id).exists())

    def test_update_referrer_action(self):
        """Test updating referrer using custom action"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-update-referrer", kwargs={"pk": candidate.id})
        data = {"referrer_id": self.employee.id}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertIsNotNone(response_data["referrer"])
        self.assertEqual(response_data["referrer"]["id"], self.employee.id)
        self.assertEqual(response_data["referrer"]["code"], self.employee.code)

        # Verify department is included as nested serializer
        self.assertIn("department", response_data["referrer"])
        self.assertIsNotNone(response_data["referrer"]["department"])
        self.assertEqual(response_data["referrer"]["department"]["id"], self.department.id)
        self.assertEqual(response_data["referrer"]["department"]["code"], self.department.code)

        # Verify in database
        candidate.refresh_from_db()
        self.assertEqual(candidate.referrer, self.employee)

    def test_filter_by_status(self):
        """Test filtering candidates by status"""
        RecruitmentCandidate.objects.create(
            name="Candidate 1",
            citizen_id="123456789012",
            email="candidate1@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        RecruitmentCandidate.objects.create(
            name="Candidate 2",
            citizen_id="123456789013",
            email="candidate2@example.com",
            phone="0987654321",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        url = reverse("hrm:recruitment-candidate-list")
        response = self.client.get(url, {"status": "HIRED"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["colored_status"]["value"], "HIRED")

    def test_search_candidates(self):
        """Test searching candidates by name, email, or code"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-list")
        response = self.client.get(url, {"search": "Nguyen Van B"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertGreaterEqual(len(data), 1)
        self.assertTrue(any(item["name"] == "Nguyen Van B" for item in data))

    def test_colored_status_in_response(self):
        """Test that colored_status field is included in API response"""
        # Create candidate
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        # Retrieve the candidate
        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Check colored_status is present and has correct structure
        self.assertIn("colored_status", response_data)
        colored_status = response_data["colored_status"]
        self.assertIn("value", colored_status)
        self.assertIn("variant", colored_status)
        self.assertEqual(colored_status["value"], "CONTACTED")
        self.assertEqual(colored_status["variant"], ColorVariant.GREY)

    def test_colored_status_variants_for_all_statuses(self):
        """Test that all status values return correct color variants"""
        test_cases = [
            ("CONTACTED", ColorVariant.GREY),
            ("INTERVIEW_SCHEDULED_1", ColorVariant.YELLOW),
            ("INTERVIEWED_1", ColorVariant.ORANGE),
            ("INTERVIEW_SCHEDULED_2", ColorVariant.PURPLE),
            ("INTERVIEWED_2", ColorVariant.BLUE),
            ("HIRED", ColorVariant.GREEN),
            ("REJECTED", ColorVariant.RED),
        ]

        for idx, (status_value, expected_variant) in enumerate(test_cases):
            # Create candidate with specific status
            candidate = RecruitmentCandidate.objects.create(
                name=f"Candidate {status_value}",
                citizen_id=f"{123456789000 + idx:012d}",
                email=f"{status_value.lower()}@example.com",
                phone="0123456789",
                recruitment_request=self.recruitment_request,
                recruitment_source=self.recruitment_source,
                recruitment_channel=self.recruitment_channel,
                years_of_experience=5,
                submitted_date=date(2025, 10, 15),
                status=status_value,
                onboard_date=date(2025, 11, 1) if status_value == "HIRED" else None,
            )

            # Retrieve the candidate
            url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
            response = self.client.get(url)

            response_data = self.get_response_data(response)
            colored_status = response_data["colored_status"]
            self.assertEqual(colored_status["value"], status_value)
            self.assertEqual(colored_status["variant"], expected_variant)

    def test_filter_by_multiple_statuses(self):
        """Test filtering candidates by multiple status values"""
        # Create candidates with different statuses
        RecruitmentCandidate.objects.create(
            name="Candidate 1",
            citizen_id="123456789012",
            email="candidate1@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        RecruitmentCandidate.objects.create(
            name="Candidate 2",
            citizen_id="123456789013",
            email="candidate2@example.com",
            phone="0987654321",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        RecruitmentCandidate.objects.create(
            name="Candidate 3",
            citizen_id="123456789014",
            email="candidate3@example.com",
            phone="0912345678",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=4,
            submitted_date=date(2025, 10, 17),
            status=RecruitmentCandidate.Status.REJECTED,
        )

        url = reverse("hrm:recruitment-candidate-list")
        # Filter by multiple statuses: HIRED and REJECTED
        response = self.client.get(url, {"status": ["HIRED", "REJECTED"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        statuses = [item["colored_status"]["value"] for item in data]
        self.assertIn("HIRED", statuses)
        self.assertIn("REJECTED", statuses)
        self.assertNotIn("CONTACTED", statuses)

    def test_filter_by_multiple_recruitment_requests(self):
        """Test filtering candidates by multiple recruitment_request values"""
        # Create a second recruitment request
        recruitment_request_2 = RecruitmentRequest.objects.create(
            name="Frontend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="1500-2500 USD",
            number_of_positions=1,
        )

        # Create candidates for different recruitment requests
        candidate1 = RecruitmentCandidate.objects.create(
            name="Backend Candidate",
            citizen_id="123456789012",
            email="backend@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        candidate2 = RecruitmentCandidate.objects.create(
            name="Frontend Candidate",
            citizen_id="123456789013",
            email="frontend@example.com",
            phone="0987654321",
            recruitment_request=recruitment_request_2,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        # Create a third recruitment request for testing
        recruitment_request_3 = RecruitmentRequest.objects.create(
            name="DevOps Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2500-3500 USD",
            number_of_positions=1,
        )

        candidate3 = RecruitmentCandidate.objects.create(
            name="DevOps Candidate",
            citizen_id="123456789014",
            email="devops@example.com",
            phone="0912345678",
            recruitment_request=recruitment_request_3,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=4,
            submitted_date=date(2025, 10, 17),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        url = reverse("hrm:recruitment-candidate-list")
        # Filter by multiple recruitment requests using comma-separated values
        response = self.client.get(
            url, {"recruitment_request": f"{self.recruitment_request.id},{recruitment_request_2.id}"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        emails = [item["email"] for item in data]
        self.assertIn("backend@example.com", emails)
        self.assertIn("frontend@example.com", emails)
        self.assertNotIn("devops@example.com", emails)
