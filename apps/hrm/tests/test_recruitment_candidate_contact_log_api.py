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
    RecruitmentCandidateContactLog,
    RecruitmentChannel,
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


class RecruitmentCandidateContactLogAPITest(TransactionTestCase, APITestMixin):
    """Test cases for RecruitmentCandidateContactLog API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        RecruitmentCandidateContactLog.objects.all().delete()
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

        # Create recruitment candidate
        self.candidate = RecruitmentCandidate.objects.create(
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

    def test_list_contact_logs(self):
        """Test listing contact logs"""
        # Create test logs
        log1 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        log2 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Second contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_create_contact_log(self):
        """Test creating a new contact log"""
        url = reverse("hrm:recruitment-candidate-contact-log-list")
        data = {
            "employee_id": self.employee.id,
            "date": "2025-10-16",
            "method": "PHONE",
            "note": "Contacted to schedule first interview",
            "recruitment_candidate_id": self.candidate.id,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["method"], "PHONE")
        self.assertEqual(response_data["note"], "Contacted to schedule first interview")

        # Verify log was created in database
        log = RecruitmentCandidateContactLog.objects.get(note="Contacted to schedule first interview")
        self.assertEqual(log.employee, self.employee)
        self.assertEqual(log.recruitment_candidate, self.candidate)

    def test_retrieve_contact_log(self):
        """Test retrieving a specific contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["method"], "PHONE")
        self.assertEqual(response_data["note"], "First contact")

    def test_update_contact_log(self):
        """Test updating a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        data = {
            "employee_id": self.employee.id,
            "date": "2025-10-16",
            "method": "EMAIL",
            "note": "Updated contact method to email",
            "recruitment_candidate_id": self.candidate.id,
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["method"], "EMAIL")
        self.assertEqual(response_data["note"], "Updated contact method to email")

    def test_partial_update_contact_log(self):
        """Test partially updating a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        data = {
            "note": "Candidate confirmed interview time",
        }

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["note"], "Candidate confirmed interview time")
        self.assertEqual(response_data["method"], "PHONE")  # Should remain unchanged

    def test_delete_contact_log(self):
        """Test deleting a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify log was deleted
        self.assertFalse(RecruitmentCandidateContactLog.objects.filter(id=log.id).exists())

    def test_filter_by_method(self):
        """Test filtering contact logs by method"""
        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Phone contact",
            recruitment_candidate=self.candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Email contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"method": "PHONE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["method"], "PHONE")

    def test_filter_by_candidate(self):
        """Test filtering contact logs by recruitment candidate"""
        # Create another candidate
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

        # Create logs for both candidates
        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contact for candidate 1",
            recruitment_candidate=self.candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Contact for candidate 2",
            recruitment_candidate=candidate2,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"recruitment_candidate": self.candidate.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["recruitment_candidate"]["id"], self.candidate.id)

    def test_filter_by_date_range(self):
        """Test filtering contact logs by date range"""
        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 15),
            method="PHONE",
            note="Early contact",
            recruitment_candidate=self.candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Later contact",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"date_from": "2025-10-16", "date_to": "2025-10-18"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["note"], "Later contact")

    def test_search_contact_logs(self):
        """Test searching contact logs"""
        RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contacted to schedule first interview",
            recruitment_candidate=self.candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"search": "first interview"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertGreaterEqual(len(data), 1)
        self.assertTrue(any("first interview" in item["note"] for item in data))
