import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import openpyxl
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
    Position,
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

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
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

        # Create position
        self.position = Position.objects.create(
            name="Senior Developer",
            code="SD001",
            description="Senior software developer position",
        )

        # Create employees
        self.employee1 = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            phone="0123456789",
            attendance_code="NGUYENVANA",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020025",
        )

        self.employee2 = Employee.objects.create(
            fullname="Le Thi D",
            username="lethid",
            email="lethid@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            phone="0123456789",
            attendance_code="LETHID",
            date_of_birth="1990-01-01",
            personal_email="lethid.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020026",
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            position_title="Senior Python Developer",
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

        # Verify position_title field is included
        self.assertIn("recruitment_request", response_data)
        self.assertIn("position_title", response_data["recruitment_request"])
        self.assertEqual(response_data["recruitment_request"]["position_title"], "Senior Python Developer")

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

        # Verify position_name field is included
        for interviewer in response_data["interviewers"]:
            self.assertIn("position_name", interviewer)
            self.assertEqual(interviewer["position_name"], "Senior Developer")

        # Verify database was updated
        schedule.refresh_from_db()
        self.assertEqual(schedule.interviewers.count(), 2)

    def test_export_interview_schedules(self):
        """Test exporting interview schedules to Excel"""
        # Create interview schedules
        schedule1 = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        schedule2 = InterviewSchedule.objects.create(
            title="Second Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.ONLINE,
            location="Zoom Meeting",
            time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
            note="Technical interview",
        )

        url = reverse("hrm:interview-schedule-export")

        # Test direct download
        response = self.client.get(url, {"delivery": "direct"})
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("filename", response["Content-Disposition"])

        # Verify the exported data contains the correct fields
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active

        # Verify headers
        headers = [cell.value for cell in sheet[1]]
        expected_headers = [
            "Title",
            "Recruitment Request",
            "Position Title",
            "Number of Positions",
            "Interview Time",
        ]
        self.assertEqual(headers, expected_headers)

        # Verify data rows (2 schedules created)
        self.assertEqual(sheet.max_row, 3)  # 1 header + 2 data rows

        # Verify first schedule data (ordered by time descending, so Second Round comes first)
        row2 = [cell.value for cell in sheet[2]]
        self.assertEqual(row2[0], "Second Round Interview")
        self.assertEqual(row2[1], "Backend Developer Position")
        self.assertEqual(row2[2], "Senior Python Developer")
        self.assertEqual(row2[3], 2)

        # Verify second schedule data
        row3 = [cell.value for cell in sheet[3]]
        self.assertEqual(row3[0], "First Round Interview")
        self.assertEqual(row3[1], "Backend Developer Position")
        self.assertEqual(row3[2], "Senior Python Developer")
        self.assertEqual(row3[3], 2)

    def test_filter_interview_schedules_by_recruitment_candidate(self):
        """Test filtering interview schedules by recruitment_candidate_id"""
        # Create interview schedules
        schedule1 = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        schedule2 = InterviewSchedule.objects.create(
            title="Second Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.ONLINE,
            location="Zoom Meeting",
            time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
            note="Technical interview",
        )

        schedule3 = InterviewSchedule.objects.create(
            title="Third Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room B",
            time=datetime(2025, 10, 27, 15, 0, 0, tzinfo=timezone.utc),
            note="Final interview",
        )

        # Add candidate1 to schedule1 and schedule2
        InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate1,
            interview_schedule=schedule1,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )
        InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate1,
            interview_schedule=schedule2,
            interview_time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
        )

        # Add candidate2 to schedule2 and schedule3
        InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate2,
            interview_schedule=schedule2,
            interview_time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
        )
        InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate2,
            interview_schedule=schedule3,
            interview_time=datetime(2025, 10, 27, 15, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm:interview-schedule-list")

        # Filter by candidate1 - should return schedule1 and schedule2
        response = self.client.get(url, {"recruitment_candidate_id": self.candidate1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        schedule_ids = [item["id"] for item in data]
        self.assertIn(schedule1.id, schedule_ids)
        self.assertIn(schedule2.id, schedule_ids)
        self.assertNotIn(schedule3.id, schedule_ids)

        # Filter by candidate2 - should return schedule2 and schedule3
        response = self.client.get(url, {"recruitment_candidate_id": self.candidate2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)
        schedule_ids = [item["id"] for item in data]
        self.assertNotIn(schedule1.id, schedule_ids)
        self.assertIn(schedule2.id, schedule_ids)
        self.assertIn(schedule3.id, schedule_ids)

        # Filter by non-existent candidate - should return empty list
        response = self.client.get(url, {"recruitment_candidate_id": 99999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 0)


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

        self.user = User.objects.create_superuser(
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

        # Create position
        self.position = Position.objects.create(
            name="Senior Developer",
            code="SD001",
            description="Senior software developer position",
        )

        # Create employee
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            phone="0123456789",
            attendance_code="NGUYENVANA",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020027",
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            position_title="Senior Python Developer",
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


class InterviewScheduleEmailTemplateTest(TransactionTestCase, APITestMixin):
    """Test cases for InterviewSchedule email template actions (preview and send)"""

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

        # Create superuser with employee for contact info tests
        self.user = User.objects.create_superuser(
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

        # Create position
        self.position = Position.objects.create(
            name="HR Manager",
            code="HRM001",
            description="Human Resources Manager",
        )

        # Create employee and link to user
        self.employee = Employee.objects.create(
            fullname="Nguyen Van HR",
            username="nguyenvanhr",
            email="nguyenvanhr@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            phone="0123456789",
            attendance_code="NGUYENVANHR",
            date_of_birth="1990-01-01",
            personal_email="nguyenvanhr.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020030",
            user=self.user,
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            position_title="Senior Python Developer",
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

        self.candidate_no_email = RecruitmentCandidate.objects.create(
            name="Le Van D",
            citizen_id="123456789014",
            email="",  # No email
            phone="0111111111",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=2,
            submitted_date="2025-10-17",
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

        # Create interview candidates
        self.interview_candidate1 = InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate1,
            interview_schedule=self.interview_schedule,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )

        self.interview_candidate2 = InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate2,
            interview_schedule=self.interview_schedule,
            interview_time=datetime(2025, 10, 25, 11, 0, 0, tzinfo=timezone.utc),
        )

        self.interview_candidate_no_email = InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate_no_email,
            interview_schedule=self.interview_schedule,
            interview_time=datetime(2025, 10, 25, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_get_recipients_returns_all_candidates_with_email(self):
        """Test get_recipients returns all candidates with email addresses"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {}
        request.user = self.user

        recipients = viewset.get_recipients(request, self.interview_schedule)

        # Should return 2 recipients (exclude candidate without email)
        self.assertEqual(len(recipients), 2)
        emails = [r["email"] for r in recipients]
        self.assertIn("nguyenvanb@example.com", emails)
        self.assertIn("tranthic@example.com", emails)

    def test_get_recipients_filters_by_candidate_ids(self):
        """Test get_recipients filters by candidate_ids when provided"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {"candidate_ids": [self.interview_candidate1.id]}
        request.user = self.user

        recipients = viewset.get_recipients(request, self.interview_schedule)

        # Should return only 1 recipient
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]["email"], "nguyenvanb@example.com")

    def test_get_recipients_excludes_already_sent_candidates(self):
        """Test get_recipients excludes candidates who already received email"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        # Mark candidate1 as email sent
        self.interview_candidate1.email_sent_at = datetime.now(timezone.utc)
        self.interview_candidate1.save()

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {"candidate_ids": [self.interview_candidate1.id, self.interview_candidate2.id]}
        request.user = self.user

        recipients = viewset.get_recipients(request, self.interview_schedule)

        # Should return only candidate2 (candidate1 already sent)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]["email"], "tranthic@example.com")

    def test_get_recipients_raises_error_when_no_candidates(self):
        """Test get_recipients raises error when no candidates found"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet
        from apps.mailtemplates.services import TemplateValidationError

        # Create empty schedule
        empty_schedule = InterviewSchedule.objects.create(
            title="Empty Schedule",
            recruitment_request=self.recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office",
            time=datetime(2025, 10, 30, 10, 0, 0, tzinfo=timezone.utc),
        )

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {}
        request.user = self.user

        with self.assertRaises(TemplateValidationError) as context:
            viewset.get_recipients(request, empty_schedule)

        self.assertIn("No candidates found", str(context.exception))

    def test_get_recipient_for_interview_candidate_returns_correct_data(self):
        """Test get_recipient_for_interview_candidate returns correctly structured data"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = self.user

        recipient = viewset.get_recipient_for_interview_candidate(request, self.interview_candidate1)

        # Verify basic structure
        self.assertIsNotNone(recipient)
        self.assertEqual(recipient["email"], "nguyenvanb@example.com")

        # Verify data fields
        data = recipient["data"]
        self.assertEqual(data["candidate_name"], "Nguyen Van B")
        self.assertEqual(data["position"], "Senior Python Developer")
        self.assertEqual(data["interview_date"], "2025-10-25")
        self.assertEqual(data["interview_time"], "10:00")
        self.assertEqual(data["location"], "Office Meeting Room A")
        self.assertIn("logo_image_url", data)

        # Verify callback_data
        self.assertEqual(recipient["callback_data"]["interview_candidate_id"], self.interview_candidate1.id)

    def test_get_recipient_for_interview_candidate_includes_contact_info(self):
        """Test get_recipient_for_interview_candidate includes contact info from user employee"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = self.user

        recipient = viewset.get_recipient_for_interview_candidate(request, self.interview_candidate1)

        # Verify contact info from employee
        self.assertEqual(recipient["contact_fullname"], "Nguyen Van HR")
        self.assertEqual(recipient["contact_phone"], "0123456789")
        self.assertEqual(recipient["contact_position"], "HR Manager")

    def test_get_recipient_for_interview_candidate_skips_candidate_without_email(self):
        """Test get_recipient_for_interview_candidate returns None for candidate without email"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = self.user

        recipient = viewset.get_recipient_for_interview_candidate(request, self.interview_candidate_no_email)

        self.assertIsNone(recipient)

    def test_get_recipient_for_interview_candidate_handles_user_without_employee(self):
        """Test get_recipient_for_interview_candidate handles user without employee"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        # Create user without employee
        user_no_employee = User.objects.create_superuser(
            username="noemployee",
            email="noemployee@example.com",
            password="testpass123",
        )

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = user_no_employee

        recipient = viewset.get_recipient_for_interview_candidate(request, self.interview_candidate1)

        # Should return recipient without contact info
        self.assertIsNotNone(recipient)
        self.assertNotIn("contact_fullname", recipient)
        self.assertNotIn("contact_phone", recipient)
        self.assertNotIn("contact_position", recipient)

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_interview_invite_send_action(self, mock_task):
        """Test interview_invite_send action creates email job"""
        url = reverse("hrm:interview-schedule-interview-invite-send", args=[self.interview_schedule.id])
        data = {"subject": "Interview Invitation"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = self.get_response_data(response)
        self.assertIn("job_id", result)
        self.assertEqual(result["total_recipients"], 2)  # 2 candidates with email

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_interview_invite_send_with_candidate_ids_filter(self, mock_task):
        """Test interview_invite_send action filters by candidate_ids"""
        url = reverse("hrm:interview-schedule-interview-invite-send", args=[self.interview_schedule.id])
        data = {
            "subject": "Interview Invitation",
            "candidate_ids": [self.interview_candidate1.id],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        result = self.get_response_data(response)
        self.assertIn("job_id", result)
        self.assertEqual(result["total_recipients"], 1)  # Only 1 candidate

    def test_interview_invite_preview_action(self):
        """Test interview_invite_preview action returns preview"""
        url = reverse("hrm:interview-schedule-interview-invite-preview", args=[self.interview_schedule.id])
        data = {}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = self.get_response_data(response)
        self.assertIn("html", result)
        self.assertIn("subject", result)
