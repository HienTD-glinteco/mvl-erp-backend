import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import (
    Employee,
    InterviewCandidate,
    InterviewSchedule,
    Position,
    RecruitmentCandidate,
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


@pytest.mark.django_db
class TestInterviewScheduleAPI(APITestMixin):
    """Test cases for InterviewSchedule API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser

    def test_create_interview_schedule(self, recruitment_request):
        """Test creating a new interview schedule"""
        url = reverse("hrm:interview-schedule-list")
        data = {
            "title": "First Round Interview",
            "recruitment_request_id": recruitment_request.id,
            "interview_type": "IN_PERSON",
            "location": "Office Meeting Room A",
            "time": "2025-10-25T10:00:00Z",
            "note": "Please bring portfolio",
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["title"] == "First Round Interview"
        assert response_data["interview_type"] == "IN_PERSON"
        assert response_data["location"] == "Office Meeting Room A"
        assert response_data["number_of_candidates"] == 0

        # Verify position_title field is included
        assert "recruitment_request" in response_data
        assert "position_title" in response_data["recruitment_request"]
        # In conftest.py, job_description.title is "Senior Python Developer"
        assert response_data["recruitment_request"]["position_title"] == "Senior Python Developer"

    def test_update_interviewers(self, recruitment_request, employee):
        """Test updating interviewers in interview schedule"""
        # Create a second employee for testing multiple interviewers
        employee2 = Employee.objects.create(
            fullname="Le Thi D",
            username="lethid",
            email="lethid@example.com",
            personal_email="lethid.personal@example.com",
            branch=employee.branch,
            block=employee.block,
            department=employee.department,
            position=employee.position,
            phone="0547872843",
            attendance_code="LETHID",
            citizen_id="000000020026",
            start_date="2024-01-01",
        )

        schedule = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        url = reverse("hrm:interview-schedule-update-interviewers", args=[schedule.id])
        data = {
            "interviewer_ids": [employee.id, employee2.id],
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data["interviewers"]) == 2

        # Verify position_name field is included
        for interviewer in response_data["interviewers"]:
            assert "position_name" in interviewer
            # In conftest.py, position.name is "Test Position"
            assert interviewer["position_name"] == "Test Position"

        # Verify database was updated
        schedule.refresh_from_db()
        assert schedule.interviewers.count() == 2

    def test_export_interview_schedules(self, recruitment_request):
        """Test exporting interview schedules to Excel"""
        # Create interview schedules
        schedule1 = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        schedule2 = InterviewSchedule.objects.create(
            title="Second Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.ONLINE,
            location="Zoom Meeting",
            time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
            note="Technical interview",
        )

        url = reverse("hrm:interview-schedule-export")

        # Test direct download
        response = self.client.get(url, {"delivery": "direct"})
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]
        assert "filename" in response["Content-Disposition"]

        # Verify the exported data contains the correct fields
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active

        # Verify headers
        headers = [cell.value for cell in sheet[1]]
        expected_headers = [
            "Interview Schedule",
            "Recruitment Request",
            "Interview Position Title",
            "Number of positions",
            "Time interview",
        ]
        assert headers == expected_headers

        # Verify data rows (2 schedules created)
        assert sheet.max_row == 3  # 1 header + 2 data rows

        # Verify first schedule data (ordered by time descending, so Second Round comes first)
        row2 = [cell.value for cell in sheet[2]]
        assert row2[0] == "Second Round Interview"
        assert row2[1] == "Backend Developer Position"
        assert row2[2] == "Senior Python Developer"
        assert row2[3] == 2

        # Verify second schedule data
        row3 = [cell.value for cell in sheet[3]]
        assert row3[0] == "First Round Interview"
        assert row3[1] == "Backend Developer Position"
        assert row3[2] == "Senior Python Developer"
        assert row3[3] == 2

    def test_filter_interview_schedules_by_recruitment_candidate(self, recruitment_request, recruitment_candidate):
        """Test filtering interview schedules by recruitment_candidate_id"""
        # Create another candidate
        candidate2 = RecruitmentCandidate.objects.create(
            name="Tran Thi C",
            citizen_id="123456789013",
            email="tranthic@example.com",
            phone="0987654321",
            recruitment_request=recruitment_request,
            recruitment_source=recruitment_candidate.recruitment_source,
            recruitment_channel=recruitment_candidate.recruitment_channel,
            years_of_experience=3,
            submitted_date="2025-10-16",
        )

        # Create interview schedules
        schedule1 = InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        schedule2 = InterviewSchedule.objects.create(
            title="Second Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.ONLINE,
            location="Zoom Meeting",
            time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
            note="Technical interview",
        )

        schedule3 = InterviewSchedule.objects.create(
            title="Third Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room B",
            time=datetime(2025, 10, 27, 15, 0, 0, tzinfo=timezone.utc),
            note="Final interview",
        )

        # Add recruitment_candidate (from fixture) to schedule1 and schedule2
        InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=schedule1,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )
        InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=schedule2,
            interview_time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
        )

        # Add candidate2 to schedule2 and schedule3
        InterviewCandidate.objects.create(
            recruitment_candidate=candidate2,
            interview_schedule=schedule2,
            interview_time=datetime(2025, 10, 26, 14, 0, 0, tzinfo=timezone.utc),
        )
        InterviewCandidate.objects.create(
            recruitment_candidate=candidate2,
            interview_schedule=schedule3,
            interview_time=datetime(2025, 10, 27, 15, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm:interview-schedule-list")

        # Filter by recruitment_candidate - should return schedule1 and schedule2
        response = self.client.get(url, {"recruitment_candidate_id": recruitment_candidate.id})
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2
        schedule_ids = [item["id"] for item in data]
        assert schedule1.id in schedule_ids
        assert schedule2.id in schedule_ids
        assert schedule3.id not in schedule_ids

        # Filter by candidate2 - should return schedule2 and schedule3
        response = self.client.get(url, {"recruitment_candidate_id": candidate2.id})
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2
        schedule_ids = [item["id"] for item in data]
        assert schedule1.id not in schedule_ids
        assert schedule2.id in schedule_ids
        assert schedule3.id in schedule_ids

        # Filter by non-existent candidate - should return empty list
        response = self.client.get(url, {"recruitment_candidate_id": 99999})
        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 0

    def test_delete_interview_schedule_prevented_when_candidate_emailed(
        self, recruitment_request, recruitment_candidate
    ):
        """Test deleting interview schedule is prevented when candidate has been emailed"""
        schedule = InterviewSchedule.objects.create(
            title="Interview to Delete (Emailed)",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Room B",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        # Create candidate with email sent
        InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=schedule,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            email_sent_at=datetime(2025, 10, 24, 10, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm:interview-schedule-detail", args=[schedule.id])
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        import json

        response_json = json.loads(response.content.decode())
        assert response_json["success"] is False
        assert InterviewSchedule.objects.filter(id=schedule.id).exists()

    def test_delete_interview_schedule_success_when_candidate_not_emailed(
        self, recruitment_request, recruitment_candidate
    ):
        """Test deleting interview schedule is successful when candidate has NOT been emailed"""
        schedule = InterviewSchedule.objects.create(
            title="Interview to Delete (No Email)",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Room B",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

        # Create candidate with NO email sent
        InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=schedule,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            email_sent_at=None,
        )

        url = reverse("hrm:interview-schedule-detail", args=[schedule.id])
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not InterviewSchedule.objects.filter(id=schedule.id).exists()

    def test_delete_interview_schedule_success_when_no_candidates(self, recruitment_request):
        """Test deleting interview schedule is successful when there are no candidates"""
        schedule = InterviewSchedule.objects.create(
            title="Empty Interview to Delete",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Room C",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm:interview-schedule-detail", args=[schedule.id])
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not InterviewSchedule.objects.filter(id=schedule.id).exists()


@pytest.mark.django_db
class TestInterviewCandidateAPI(APITestMixin):
    """Test cases for InterviewCandidate API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser):
        """Set up test client and user"""
        self.client = api_client
        self.user = superuser

    @pytest.fixture
    def interview_schedule(self, recruitment_request):
        """Create an interview schedule for testing"""
        return InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

    def test_create_interview_candidate(self, recruitment_candidate, interview_schedule):
        """Test creating a new interview candidate"""
        url = reverse("hrm:interview-candidate-list")
        data = {
            "recruitment_candidate_id": recruitment_candidate.id,
            "interview_schedule_id": interview_schedule.id,
            "interview_time": "2025-10-25T10:00:00Z",
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["recruitment_candidate"]["name"] == "Nguyen Van B"
        assert response_data["interview_schedule"]["title"] == "First Round Interview"

    def test_list_interview_candidates(self, recruitment_candidate, interview_schedule):
        """Test listing interview candidates"""
        InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=interview_schedule,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm:interview-candidate-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["recruitment_candidate"]["email"] == "nguyenvanb@example.com"


@pytest.mark.django_db
class TestInterviewScheduleEmailTemplate(APITestMixin):
    """Test cases for InterviewSchedule email template actions (preview and send)"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, superuser, employee):
        """Set up test client and user linked to employee"""
        self.client = api_client
        self.user = superuser
        # The employee fixture in conftest.py already links to the user
        self.employee = employee
        # Customize employee position for some tests
        position = Position.objects.get_or_create(name="HR Manager", code="HRM001")[0]
        self.employee.position = position
        self.employee.save()

    @pytest.fixture
    def interview_schedule(self, recruitment_request):
        """Create an interview schedule for testing"""
        return InterviewSchedule.objects.create(
            title="First Round Interview",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office Meeting Room A",
            time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
            note="Please bring portfolio",
        )

    @pytest.fixture
    def interview_candidates(self, recruitment_candidate, interview_schedule, recruitment_request):
        """Create test interview candidates"""
        # Create second candidate
        candidate2 = RecruitmentCandidate.objects.create(
            name="Tran Thi C",
            citizen_id="123456789013",
            email="tranthic@example.com",
            phone="0987654321",
            recruitment_request=recruitment_request,
            recruitment_source=recruitment_candidate.recruitment_source,
            recruitment_channel=recruitment_candidate.recruitment_channel,
            years_of_experience=3,
            submitted_date="2025-10-16",
        )

        # Create candidate with no email
        candidate_no_email = RecruitmentCandidate.objects.create(
            name="Le Van D",
            citizen_id="123456789014",
            email="",  # No email
            phone="0111111111",
            recruitment_request=recruitment_request,
            recruitment_source=recruitment_candidate.recruitment_source,
            recruitment_channel=recruitment_candidate.recruitment_channel,
            years_of_experience=2,
            submitted_date="2025-10-17",
        )

        ic1 = InterviewCandidate.objects.create(
            recruitment_candidate=recruitment_candidate,
            interview_schedule=interview_schedule,
            interview_time=datetime(2025, 10, 25, 10, 0, 0, tzinfo=timezone.utc),
        )

        ic2 = InterviewCandidate.objects.create(
            recruitment_candidate=candidate2,
            interview_schedule=interview_schedule,
            interview_time=datetime(2025, 10, 25, 11, 0, 0, tzinfo=timezone.utc),
        )

        ic_no_email = InterviewCandidate.objects.create(
            recruitment_candidate=candidate_no_email,
            interview_schedule=interview_schedule,
            interview_time=datetime(2025, 10, 25, 12, 0, 0, tzinfo=timezone.utc),
        )

        return ic1, ic2, ic_no_email

    def test_get_recipients_returns_all_candidates_with_email(self, interview_schedule, interview_candidates):
        """Test get_recipients returns all candidates with email addresses"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {}
        request.user = self.user

        recipients = viewset.get_recipients(request, interview_schedule)

        # Should return 2 recipients (exclude candidate without email)
        assert len(recipients) == 2
        emails = [r["email"] for r in recipients]
        assert "nguyenvanb@example.com" in emails
        assert "tranthic@example.com" in emails

    def test_get_recipients_filters_by_candidate_ids(self, interview_schedule, interview_candidates):
        """Test get_recipients filters by candidate_ids when provided"""
        ic1, _, _ = interview_candidates
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {"candidate_ids": [ic1.id]}
        request.user = self.user

        recipients = viewset.get_recipients(request, interview_schedule)

        # Should return only 1 recipient
        assert len(recipients) == 1
        assert recipients[0]["email"] == "nguyenvanb@example.com"

    def test_get_recipients_includes_already_sent_candidates(self, interview_schedule, interview_candidates):
        """Test get_recipients includes candidates who already received email"""
        ic1, ic2, _ = interview_candidates
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        # Mark candidate1 as email sent
        ic1.email_sent_at = datetime.now(timezone.utc)
        ic1.save()

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {"candidate_ids": [ic1.id, ic2.id]}
        request.user = self.user

        recipients = viewset.get_recipients(request, interview_schedule)

        # Should return only candidate2 (candidate1 already sent)
        assert len(recipients) == 2

    def test_get_recipients_raises_error_when_no_candidates(self, recruitment_request):
        """Test get_recipients raises error when no candidates found"""
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet
        from apps.mailtemplates.services import TemplateValidationError

        # Create empty schedule
        empty_schedule = InterviewSchedule.objects.create(
            title="Empty Schedule",
            recruitment_request=recruitment_request,
            interview_type=InterviewSchedule.InterviewType.IN_PERSON,
            location="Office",
            time=datetime(2025, 10, 30, 10, 0, 0, tzinfo=timezone.utc),
        )

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.data = {}
        request.user = self.user

        with pytest.raises(TemplateValidationError) as context:
            viewset.get_recipients(request, empty_schedule)

        assert "No candidates found" in str(context.value)

    def test_get_recipient_for_interview_candidate_returns_correct_data(self, interview_candidates):
        """Test get_recipient_for_interview_candidate returns correctly structured data"""
        ic1, _, _ = interview_candidates
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = self.user

        recipient = viewset.get_recipient_for_interview_candidate(request, ic1)

        # Verify basic structure
        assert recipient is not None
        assert recipient["email"] == "nguyenvanb@example.com"

        # Verify data fields
        data = recipient["data"]
        assert data["candidate_name"] == "Nguyen Van B"
        assert data["position"] == "Senior Python Developer"
        assert data["interview_date"] == "2025-10-25"
        assert data["interview_time"] == "10:00"
        assert data["location"] == "Office Meeting Room A"
        assert "logo_image_url" in data

        # Verify callback_data
        assert recipient["callback_data"]["interview_candidate_id"] == ic1.id

    def test_get_recipient_for_interview_candidate_includes_contact_info(self, interview_candidates):
        """Test get_recipient_for_interview_candidate includes contact info from user employee"""
        ic1, _, _ = interview_candidates
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = self.user

        recipient = viewset.get_recipient_for_interview_candidate(request, ic1)

        # Verify contact info from employee
        assert recipient["contact_fullname"] == "Test Employee"
        assert recipient["contact_phone"] == "0123456789"
        assert recipient["contact_position"] == "HR Manager"

    def test_get_recipient_for_interview_candidate_skips_candidate_without_email(self, interview_candidates):
        """Test get_recipient_for_interview_candidate returns None for candidate without email"""
        _, _, ic_no_email = interview_candidates
        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = self.user

        recipient = viewset.get_recipient_for_interview_candidate(request, ic_no_email)

        assert recipient is None

    def test_get_recipient_for_interview_candidate_handles_user_without_employee(self, interview_candidates):
        """Test get_recipient_for_interview_candidate handles user without employee"""
        ic1, _, _ = interview_candidates
        # Create user without employee
        from django.contrib.auth import get_user_model

        from apps.hrm.api.views.interview_schedule import InterviewScheduleViewSet

        User = get_user_model()
        user_no_employee = User.objects.create_superuser(
            username="noemployee",
            email="noemployee@example.com",
            password="testpass123",
        )

        viewset = InterviewScheduleViewSet()
        request = MagicMock()
        request.user = user_no_employee

        recipient = viewset.get_recipient_for_interview_candidate(request, ic1)

        # Should return recipient without contact info
        assert recipient is not None
        assert "contact_fullname" not in recipient
        assert "contact_phone" not in recipient
        assert "contact_position" not in recipient

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_interview_invite_send_action(self, mock_task, interview_schedule, interview_candidates):
        """Test interview_invite_send action creates email job"""
        url = reverse("hrm:interview-schedule-interview-invite-send", args=[interview_schedule.id])
        data = {"subject": "Interview Invitation"}

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        result = self.get_response_data(response)
        assert "job_id" in result
        assert result["total_recipients"] == 2  # 2 candidates with email

    @patch("apps.mailtemplates.view_mixins.send_email_job_task")
    def test_interview_invite_send_with_candidate_ids_filter(
        self, mock_task, interview_schedule, interview_candidates
    ):
        """Test interview_invite_send action filters by candidate_ids"""
        ic1, _, _ = interview_candidates
        url = reverse("hrm:interview-schedule-interview-invite-send", args=[interview_schedule.id])
        data = {
            "subject": "Interview Invitation",
            "candidate_ids": [ic1.id],
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        result = self.get_response_data(response)
        assert "job_id" in result
        assert result["total_recipients"] == 1  # Only 1 candidate

    def test_interview_invite_preview_action(self, interview_schedule, interview_candidates):
        """Test interview_invite_preview action returns preview"""
        url = reverse("hrm:interview-schedule-interview-invite-preview", args=[interview_schedule.id])
        data = {}

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        result = self.get_response_data(response)
        assert "html" in result
        assert "subject" in result
