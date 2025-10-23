import json
from datetime import datetime, timezone

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
    InterviewCandidate,
    InterviewSchedule,
    JobDescription,
    RecruitmentCandidate,
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


class InterviewScheduleAPITest(TransactionTestCase, APITestMixin):
    """Test cases for InterviewSchedule API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        InterviewSchedule.objects.all().delete()
        InterviewCandidate.objects.all().delete()
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

        # Create employees
        self.employee1 = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            phone="0123456789",
            attendance_code="NGUYENVANA",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
        )

        self.employee2 = Employee.objects.create(
            fullname="Le Thi D",
            username="lethid",
            email="lethid@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            phone="0123456789",
            attendance_code="LETHID",
            date_of_birth="1990-01-01",
            personal_email="lethid.personal@example.com",
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
            proposer=self.employee1,
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

        # Create recruitment candidates
        self.candidate1 = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date="2025-10-15",
        )

        self.candidate2 = RecruitmentCandidate.objects.create(
            name="Tran Thi C",
            citizen_id="123456789013",
            email="tranthic@example.com",
            phone="0987654321",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date="2025-10-16",
        )

    def test_create_interview_schedule(self):
        """Test creating a new interview schedule"""
        url = reverse("hrm:interview-schedule-list")
        data = {
            "title": "First Round Interview",
            "recruitment_request_id": self.recruitment_request.id,
            "interview_type": "IN_PERSON",
            "location": "Office Meeting Room A",
            "time": "2025-10-25T10:00:00Z",
            "note": "Please bring portfolio",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["title"], "First Round Interview")
        self.assertEqual(response_data["interview_type"], "IN_PERSON")
        self.assertEqual(response_data["location"], "Office Meeting Room A")
        self.assertEqual(response_data["number_of_candidates"], 0)

    def test_update_interviewers(self):
        """Test updating interviewers in interview schedule"""
        schedule = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        url = reverse("hrm:interview-schedule-update-interviewers", args=[schedule.id])
        data = {
            "interviewer_ids": [self.employee1.id, self.employee2.id],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data["interviewers"]), 2)

        # Verify database was updated
        schedule.refresh_from_db()
        self.assertEqual(schedule.interviewers.count(), 2)


class InterviewCandidateAPITest(TransactionTestCase, APITestMixin):
    """Test cases for InterviewCandidate API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Clear all existing data for clean tests
        InterviewCandidate.objects.all().delete()
        InterviewSchedule.objects.all().delete()
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
            attendance_code="NGUYENVANA",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
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
            submitted_date="2025-10-15",
        )

        # Create interview schedule
        self.interview_schedule = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

    def test_create_interview_candidate(self):
        """Test creating a new interview candidate"""
        url = reverse("hrm:interview-candidate-list")
        data = {
            "recruitment_candidate_id": self.candidate.id,
            "interview_schedule_id": self.interview_schedule.id,
            "interview_time": "2025-10-25T10:00:00Z",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["recruitment_candidate"]["name"], "Nguyen Van B")
        self.assertEqual(response_data["interview_schedule"]["title"], "First Round Interview")

    def test_list_interview_candidates(self):
        """Test listing interview candidates"""
        InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate,
            interview_schedule=self.interview_schedule,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm:interview-candidate-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["recruitment_candidate"]["email"], "nguyenvanb@example.com")
