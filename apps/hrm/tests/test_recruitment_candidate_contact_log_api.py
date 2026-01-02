from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import RecruitmentCandidate, RecruitmentCandidateContactLog


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestRecruitmentCandidateContactLogAPI(APITestMixin):
    """Test cases for RecruitmentCandidateContactLog API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    def test_list_contact_logs(self, recruitment_candidate, employee):
        """Test listing contact logs"""
        # Create test logs
        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=recruitment_candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Second contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_create_contact_log(self, recruitment_candidate, employee):
        """Test creating a new contact log"""
        url = reverse("hrm:recruitment-candidate-contact-log-list")
        data = {
            "employee_id": employee.id,
            "date": "2025-10-16",
            "method": "PHONE",
            "note": "Contacted to schedule first interview",
            "recruitment_candidate_id": recruitment_candidate.id,
        }

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["method"] == "PHONE"
        assert response_data["note"] == "Contacted to schedule first interview"

        # Verify log was created in database
        log = RecruitmentCandidateContactLog.objects.get(note="Contacted to schedule first interview")
        assert log.employee == employee
        assert log.recruitment_candidate == recruitment_candidate

    def test_retrieve_contact_log(self, recruitment_candidate, employee):
        """Test retrieving a specific contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["method"] == "PHONE"
        assert response_data["note"] == "First contact"

    def test_update_contact_log(self, recruitment_candidate, employee):
        """Test updating a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        data = {
            "employee_id": employee.id,
            "date": "2025-10-16",
            "method": "EMAIL",
            "note": "Updated contact method to email",
            "recruitment_candidate_id": recruitment_candidate.id,
        }

        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["method"] == "EMAIL"
        assert response_data["note"] == "Updated contact method to email"

    def test_partial_update_contact_log(self, recruitment_candidate, employee):
        """Test partially updating a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        data = {
            "note": "Candidate confirmed interview time",
        }

        response = self.client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["note"] == "Candidate confirmed interview time"
        assert response_data["method"] == "PHONE"  # Should remain unchanged

    def test_delete_contact_log(self, recruitment_candidate, employee):
        """Test deleting a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-detail", kwargs={"pk": log.id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify log was deleted
        assert not RecruitmentCandidateContactLog.objects.filter(id=log.id).exists()

    def test_filter_by_method(self, recruitment_candidate, employee):
        """Test filtering contact logs by method"""
        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Phone contact",
            recruitment_candidate=recruitment_candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Email contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"method": "PHONE"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["method"] == "PHONE"

    def test_filter_by_candidate(
        self, recruitment_candidate, recruitment_request, recruitment_source, recruitment_channel, employee
    ):
        """Test filtering contact logs by recruitment candidate"""
        # Create another candidate
        candidate2 = RecruitmentCandidate.objects.create(
            name="Tran Thi C",
            citizen_id="123456789013",
            email="tranthic@example.com",
            phone="0987654321",
            recruitment_request=recruitment_request,
            recruitment_source=recruitment_source,
            recruitment_channel=recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
        )

        # Create logs for both candidates
        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contact for candidate 1",
            recruitment_candidate=recruitment_candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Contact for candidate 2",
            recruitment_candidate=candidate2,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"recruitment_candidate": recruitment_candidate.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["recruitment_candidate"]["id"] == recruitment_candidate.id

    def test_filter_by_date_range(self, recruitment_candidate, employee):
        """Test filtering contact logs by date range"""
        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 15),
            method="PHONE",
            note="Early contact",
            recruitment_candidate=recruitment_candidate,
        )

        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Later contact",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"date_from": "2025-10-16", "date_to": "2025-10-18"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["note"] == "Later contact"

    def test_search_contact_logs(self, recruitment_candidate, employee):
        """Test searching contact logs"""
        RecruitmentCandidateContactLog.objects.create(
            employee=employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contacted to schedule first interview",
            recruitment_candidate=recruitment_candidate,
        )

        url = reverse("hrm:recruitment-candidate-contact-log-list")
        response = self.client.get(url, {"search": "first interview"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) >= 1
        assert any("first interview" in item["note"] for item in data)
