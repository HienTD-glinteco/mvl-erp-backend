"""Tests for domain-specific email actions (Employee and Interview Schedule)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
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


class EmployeeEmailActionTests(TestCase):
    """Test cases for Employee email actions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.staff_user = User.objects.create_superuser(
            username="staffuser",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )

        # Create organizational hierarchy
        self.province = Province.objects.create(
            code="test", name="test", english_name="test", level="province", decree="", enabled=True
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="test",
            name="test",
            english_name="test",
            parent_province=self.province,
            level="district",
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Test Branch", code="TB", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block = Block.objects.create(name="Test Block", code="TBK", branch=self.branch, block_type="business")
        self.department = Department.objects.create(
            name="Test Department", code="TD", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(name="Test Position", code="TP")

        # Create a real employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            email="john.doe@example.com",
            username="johndoe",
            start_date=timezone.now().date(),
            is_onboarding_email_sent=False,
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
        )

    def test_welcome_email_preview(self):
        """Test preview welcome email for employee."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        response = self.client.post(f"/api/hrm/employees/{self.employee.id}/welcome_email/preview/", {}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("html", data)
        self.assertIn("text", data)
        self.assertIn("John Doe", data["html"])

    @patch("apps.mailtemplates.views.send_email_job_task.delay")
    def test_welcome_email_send(self, mock_task):
        """Test send welcome email for employee."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Provide recipients data matching the template variables schema
        request_data = {
            "recipients": [
                {
                    "email": self.employee.email,
                    "data": {
                        "employee_fullname": self.employee.fullname,
                        "employee_email": self.employee.email,
                        "employee_username": self.employee.username,
                        "employee_start_date": self.employee.start_date.isoformat(),
                        "employee_code": self.employee.code
                        if hasattr(self.employee, "code") and self.employee.code
                        else "MVL001",
                        "employee_department_name": self.employee.department.name if self.employee.department else "",
                        "new_password": "TestPass123",
                        "logo_image_url": "/static/img/email_logo.png",
                    },
                }
            ],
        }

        # Act
        response = self.client.post(
            f"/api/hrm/employees/{self.employee.id}/welcome_email/send/", request_data, format="json"
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        mock_task.assert_called_once_with(data["job_id"])

    def test_welcome_email_preview_with_custom_data(self):
        """Test preview with custom data override."""
        # Arrange
        self.client.force_authenticate(user=self.staff_user)

        # Act
        custom_data = {
            "data": {
                "employee_fullname": "Custom Name",
                "employee_email": "custom@example.com",
                "employee_username": "custom",
                "employee_start_date": "2026-01-01",
                "employee_code": "MVL999",
                "employee_department_name": "Custom Dept",
                "new_password": "CustomPass123",
                "logo_image_url": "/static/img/email_logo.png",
            }
        }
        response = self.client.post(
            f"/api/hrm/employees/{self.employee.id}/welcome_email/preview/", custom_data, format="json"
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        # Should use custom data, not employee data
        self.assertIn("Custom Name", data["html"])
        self.assertNotIn("John Doe", data["html"])

    def test_welcome_email_requires_authentication(self):
        """Test welcome email actions require authentication."""
        # Act - No authentication
        response = self.client.post(f"/api/hrm/employees/{self.employee.id}/welcome_email/preview/", {}, format="json")

        # Assert
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )  # RoleBasedPermission returns 403 for unauthenticated


class InterviewScheduleEmailActionTests(TestCase):
    """Test cases for InterviewSchedule email actions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.province = Province.objects.create(
            code="test", name="test", english_name="test", level="province", decree="", enabled=True
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="test",
            name="test",
            english_name="test",
            parent_province=self.province,
            level="district",
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Test Branch", code="TB", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block = Block.objects.create(name="Test Block", code="TBK", branch=self.branch, block_type="business")
        self.department = Department.objects.create(
            name="Test Department", code="TD", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(name="Senior Developer", code="SD")

        # Create proposer (HR employee)
        self.proposer = Employee.objects.create(
            fullname="HR Manager",
            email="hr@example.com",
            username="hrmanager",
            start_date=timezone.now().date(),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            code="JD001",
            title="Senior Developer",
            position_title="Senior Developer",
            responsibility="Development tasks",
            requirement="5 years experience",
            benefit="Competitive salary",
            proposed_salary="Negotiable",
        )

        # Create recruitment request
        self.recruitment_request = RecruitmentRequest.objects.create(
            code="RR001",
            name="Senior Developer Recruitment",
            job_description=self.job_description,
            branch=self.branch,
            proposer=self.proposer,
        )

        # Create interview schedule
        interview_time = timezone.now() + timezone.timedelta(days=7)

        self.interview_schedule = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=self.recruitment_request,
            interview_type="IN_PERSON",
            location="Office Meeting Room A",
            time=interview_time,
            note="Please bring portfolio",
        )

        # Create recruitment channel and source
        self.recruitment_channel = RecruitmentChannel.objects.create(
            code="CH001",
            name="Job Website",
        )
        self.recruitment_source = RecruitmentSource.objects.create(
            code="RS001",
            name="LinkedIn",
        )

        # Create candidates
        submitted_date = timezone.now().date()
        self.candidate1 = RecruitmentCandidate.objects.create(
            name="Candidate One",
            email="candidate1@example.com",
            phone="0123456789",
            citizen_id="123456789012",
            recruitment_request=self.recruitment_request,
            recruitment_channel=self.recruitment_channel,
            recruitment_source=self.recruitment_source,
            submitted_date=submitted_date,
        )
        self.candidate2 = RecruitmentCandidate.objects.create(
            name="Candidate Two",
            email="candidate2@example.com",
            phone="0987654321",
            citizen_id="210987654321",
            recruitment_request=self.recruitment_request,
            recruitment_channel=self.recruitment_channel,
            recruitment_source=self.recruitment_source,
            submitted_date=submitted_date,
        )
        self.candidate3 = RecruitmentCandidate.objects.create(
            name="Candidate Three",
            email="candidate3@example.com",
            phone="0111222333",
            citizen_id="333222111000",
            recruitment_request=self.recruitment_request,
            recruitment_channel=self.recruitment_channel,
            recruitment_source=self.recruitment_source,
            submitted_date=submitted_date,
        )

        # Link candidates to interview schedule
        self.interview_candidate1 = InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate1,
            interview_schedule=self.interview_schedule,
            interview_time=interview_time,
        )
        self.interview_candidate2 = InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate2,
            interview_schedule=self.interview_schedule,
            interview_time=interview_time + timezone.timedelta(hours=1),
        )
        self.interview_candidate3 = InterviewCandidate.objects.create(
            recruitment_candidate=self.candidate3,
            interview_schedule=self.interview_schedule,
            interview_time=interview_time + timezone.timedelta(hours=2),
        )

    def test_interview_invite_preview(self):
        """Test preview interview invitation email for schedule."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.post(
            f"/api/hrm/interview-schedules/{self.interview_schedule.id}/interview_invite/preview/",
            {},
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("html", data)
        self.assertIn("text", data)
        self.assertIn("subject", data)
        # Preview uses sample data by default
        self.assertIn("Interview Invitation", data["subject"])

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_interview_invite_send_all_candidates(self, mock_task):
        """Test send interview invitation to all candidates in schedule."""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.post(
            f"/api/hrm/interview-schedules/{self.interview_schedule.id}/interview_invite/send/",
            {},
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        self.assertEqual(data["total_recipients"], 3)  # All 3 candidates
        mock_task.delay.assert_called_once()

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_interview_invite_send_filtered_candidates(self, mock_task):
        """Test send interview invitation to specific candidates only."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        request_data = {
            "candidate_ids": [self.interview_candidate1.id, self.interview_candidate2.id]  # Only 2 candidates
        }

        # Act
        response = self.client.post(
            f"/api/hrm/interview-schedules/{self.interview_schedule.id}/interview_invite/send/",
            request_data,
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()["data"]
        self.assertIn("job_id", data)
        self.assertEqual(data["total_recipients"], 2)  # Only 2 candidates
        mock_task.delay.assert_called_once()

    def test_interview_invite_preview_with_custom_data(self):
        """Test preview with custom data override."""
        # Arrange
        self.client.force_authenticate(user=self.user)
        custom_data = {
            "data": {
                "candidate_name": "Custom Candidate",
                "position": "Custom Position",
                "interview_date": "2025-12-01",
                "interview_time": "14:00",
                "location": "Custom Location",
            }
        }

        # Act
        response = self.client.post(
            f"/api/hrm/interview-schedules/{self.interview_schedule.id}/interview_invite/preview/",
            custom_data,
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("Custom Candidate", data["html"])
        self.assertIn("Custom Position", data["html"])

    def test_interview_invite_requires_authentication(self):
        """Test interview invitation actions require authentication."""
        # Act - No authentication
        response = self.client.post(
            f"/api/hrm/interview-schedules/{self.interview_schedule.id}/interview_invite/preview/",
            {},
            format="json",
        )

        # Assert
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )  # RoleBasedPermission returns 403 for unauthenticated
