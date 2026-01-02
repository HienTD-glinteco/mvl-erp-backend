from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import (
    Employee,
    RecruitmentCandidate,
    RecruitmentRequest,
)
from libs import ColorVariant


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
class TestRecruitmentCandidateAPI(APITestMixin):
    """Test cases for RecruitmentCandidate API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_method(
        self, api_client, user, employee, recruitment_request, recruitment_source, recruitment_channel, department
    ):
        self.client = api_client
        self.user = user
        self.employee = employee
        self.recruitment_request = recruitment_request
        self.recruitment_source = recruitment_source
        self.recruitment_channel = recruitment_channel
        self.department = department

        # Branch and block from recruitment_request (which come from fixtures)
        self.branch = recruitment_request.branch
        self.block = recruitment_request.block

        self.candidate_data = {
            "name": "Nguyen Van B",
            "citizen_id": "123456789012",
            "email": "nguyenvanb@example.com",
            "phone": "0123456789",
            "recruitment_request_id": self.recruitment_request.id,
            "recruitment_source_id": self.recruitment_source.id,
            "recruitment_channel_id": self.recruitment_channel.id,
            "years_of_experience": RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            "submitted_date": "2025-10-15",
            "status": "CONTACTED",
            "note": "Strong Python skills",
        }

    def test_list_candidates(self):
        """Test listing recruitment candidates"""
        # Create test candidates
        RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        RecruitmentCandidate.objects.create(
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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_create_candidate(self):
        """Test creating a new recruitment candidate"""
        url = reverse("hrm:recruitment-candidate-list")
        data = self.candidate_data.copy()

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["name"] == "Nguyen Van B"
        assert response_data["citizen_id"] == "123456789012"
        assert response_data["email"] == "nguyenvanb@example.com"

        # Verify candidate was created in database
        candidate = RecruitmentCandidate.objects.get(email="nguyenvanb@example.com")
        assert candidate.name == "Nguyen Van B"
        assert candidate.branch == self.recruitment_request.branch
        assert candidate.block == self.recruitment_request.block
        assert candidate.department == self.recruitment_request.department

    def test_create_candidate_invalid_citizen_id(self):
        """Test creating candidate with invalid citizen ID"""
        url = reverse("hrm:recruitment-candidate-list")
        data = self.candidate_data.copy()
        data["citizen_id"] = "12345"  # Too short

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_candidate_hired_without_onboard_date(self):
        """Test creating hired candidate without onboard_date"""
        url = reverse("hrm:recruitment-candidate-list")
        data = self.candidate_data.copy()
        data["status"] = "HIRED"

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_candidate_hired_with_onboard_date(self):
        """Test creating hired candidate with onboard_date"""
        url = reverse("hrm:recruitment-candidate-list")
        data = self.candidate_data.copy()
        data["status"] = "HIRED"
        data["onboard_date"] = "2025-11-01"

        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["colored_status"]["value"] == "HIRED"
        assert response_data["onboard_date"] == "2025-11-01"

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == "Nguyen Van B"
        assert response_data["citizen_id"] == "123456789012"

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
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
            "years_of_experience": "THREE_TO_FIVE_YEARS",
            "submitted_date": "2025-10-15",
            "status": "INTERVIEWED_1",
        }

        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == "Nguyen Van B Updated"
        assert response_data["years_of_experience"] == RecruitmentCandidate.YearsOfExperience.THREE_TO_FIVE_YEARS
        assert response_data["colored_status"]["value"] == "INTERVIEWED_1"

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        data = {
            "status": "HIRED",
            "onboard_date": "2025-11-01",
        }

        response = self.client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["colored_status"]["value"] == "HIRED"
        assert response_data["onboard_date"] == "2025-11-01"

    def test_delete_candidate_success(self):
        """Test deleting a candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.REJECTED,
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify candidate was deleted
        assert not RecruitmentCandidate.objects.filter(id=candidate.id).exists()

    def test_delete_candidate_failed(self):
        """Test deleting a candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify candidate was NOT deleted
        assert RecruitmentCandidate.objects.filter(id=candidate.id).exists()

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-update-referrer", kwargs={"pk": candidate.id})
        data = {"referrer_id": self.employee.id}

        response = self.client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["referrer"] is not None
        assert response_data["referrer"]["id"] == self.employee.id
        assert response_data["referrer"]["code"] == self.employee.code

        # Verify department is included as nested serializer
        assert "department" in response_data["referrer"]
        assert response_data["referrer"]["department"] is not None
        assert response_data["referrer"]["department"]["id"] == self.department.id
        assert response_data["referrer"]["department"]["code"] == self.department.code

        # Verify in database
        candidate.refresh_from_db()
        assert candidate.referrer == self.employee

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["colored_status"]["value"] == "HIRED"

    def test_search_candidates(self):
        """Test searching candidates by name, email, or code"""
        RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        url = reverse("hrm:recruitment-candidate-list")
        response = self.client.get(url, {"search": "Nguyen Van B"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) >= 1
        assert any(item["name"] == "Nguyen Van B" for item in data)

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
        )

        # Retrieve the candidate
        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Check colored_status is present and has correct structure
        assert "colored_status" in response_data
        colored_status = response_data["colored_status"]
        assert "value" in colored_status
        assert "variant" in colored_status
        assert colored_status["value"] == "CONTACTED"
        assert colored_status["variant"] == ColorVariant.GREY

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
                years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
                submitted_date=date(2025, 10, 15),
                status=status_value,
                onboard_date=date(2025, 11, 1) if status_value == "HIRED" else None,
            )

            # Retrieve the candidate
            url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.id})
            response = self.client.get(url)

            response_data = self.get_response_data(response)
            colored_status = response_data["colored_status"]
            assert colored_status["value"] == status_value
            assert colored_status["variant"] == expected_variant

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
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2
        statuses = [item["colored_status"]["value"] for item in data]
        assert "HIRED" in statuses
        assert "REJECTED" in statuses
        assert "CONTACTED" not in statuses

    def test_filter_by_multiple_recruitment_requests(self):
        """Test filtering candidates by multiple recruitment_request values"""
        # Create a second recruitment request
        recruitment_request_2 = RecruitmentRequest.objects.create(
            name="Frontend Developer Position",
            job_description=self.recruitment_request.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="1500-2500 USD",
            number_of_positions=1,
        )

        # Create candidates for different recruitment requests
        RecruitmentCandidate.objects.create(
            name="Backend Candidate",
            citizen_id="123456789012",
            email="backend@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        RecruitmentCandidate.objects.create(
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
            job_description=self.recruitment_request.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2500-3500 USD",
            number_of_positions=1,
        )

        RecruitmentCandidate.objects.create(
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

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2
        emails = [item["email"] for item in data]
        assert "backend@example.com" in emails
        assert "frontend@example.com" in emails
        assert "devops@example.com" not in emails

    def test_export_recruitment_candidate_direct(self):
        """Test exporting recruitment candidates with direct delivery"""
        url = reverse("hrm:recruitment-candidate-list")

        # Create test candidates
        self.client.post(url, self.candidate_data, format="json")

        candidate_data_2 = self.candidate_data.copy()
        candidate_data_2["name"] = "Tran Van B"
        candidate_data_2["citizen_id"] = "123456789013"
        candidate_data_2["email"] = "tranvanb@example.com"
        candidate_data_2["phone"] = "0987654322"
        candidate_data_2["status"] = "INTERVIEWED_1"
        self.client.post(url, candidate_data_2, format="json")

        # Export with direct delivery
        export_url = reverse("hrm:recruitment-candidate-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]

    def test_export_recruitment_candidate_fields(self):
        """Test that export includes correct fields"""
        url = reverse("hrm:recruitment-candidate-list")

        # Create a test candidate
        response = self.client.post(url, self.candidate_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Export with direct delivery to check fields
        export_url = reverse("hrm:recruitment-candidate-export")
        response = self.client.get(export_url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        # File should be generated and downloadable
        assert len(response.content) > 0

    def test_export_recruitment_candidate_filtered(self):
        """Test exporting filtered recruitment candidates"""
        url = reverse("hrm:recruitment-candidate-list")

        # Create candidates with different statuses
        self.client.post(url, self.candidate_data, format="json")

        candidate_data_2 = self.candidate_data.copy()
        candidate_data_2["name"] = "Tran Van B"
        candidate_data_2["citizen_id"] = "123456789013"
        candidate_data_2["email"] = "tranvanb@example.com"
        candidate_data_2["phone"] = "0987654322"
        candidate_data_2["status"] = "HIRED"
        candidate_data_2["onboard_date"] = "2025-11-01"
        self.client.post(url, candidate_data_2, format="json")

        # Export with status filter
        export_url = reverse("hrm:recruitment-candidate-export")
        response = self.client.get(export_url, {"delivery": "direct", "status": "HIRED"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 0

    def test_convert_candidate_to_employee_success(self):
        """Test successfully converting a recruitment candidate to employee"""
        # Create a candidate
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van D",
            citizen_id="123456789014",
            email="nguyenvand@example.com",
            phone="0123456790",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.THREE_TO_FIVE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response = self.client.post(url, {"code_type": "MV"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify employee was created with correct data
        assert response_data["fullname"] == "Nguyen Van D"
        assert response_data["username"] == "nguyenvand@example.com"
        assert response_data["email"] == "nguyenvand@example.com"
        assert response_data["citizen_id"] == "123456789014"
        assert response_data["phone"] == "0123456790"
        assert response_data["start_date"] == str(date.today())
        assert response_data["attendance_code"] is not None
        assert len(response_data["attendance_code"]) == 6
        assert response_data["is_onboarding_email_sent"] is False

        # Verify department, branch, block were copied
        assert response_data["department"]["id"] == self.department.id
        assert response_data["branch"]["id"] == self.branch.id
        assert response_data["block"]["id"] == self.block.id

        # Verify employee exists in database with correct status
        employee = Employee.objects.get(email="nguyenvand@example.com")
        assert employee.fullname == "Nguyen Van D"
        assert employee.username == "nguyenvand@example.com"
        assert employee.citizen_id == "123456789014"
        assert employee.phone == "0123456790"
        assert employee.status == Employee.Status.ONBOARDING

        # Verify candidate is linked to employee
        candidate.refresh_from_db()
        assert candidate.employee == employee

    def test_convert_candidate_to_employee_requires_code_type(self):
        """Test converting candidate without code_type returns error"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van E",
            citizen_id="123456789018",
            email="nguyenvane@example.com",
            phone="0123456796",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response = self.client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "code_type" in response_data["error"]

    def test_convert_candidate_to_employee_with_ctv_code_type(self):
        """Test converting candidate with CTV code type"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van CTV",
            citizen_id="123456789019",
            email="nguyenvanctv@example.com",
            phone="0123456797",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response = self.client.post(url, {"code_type": "CTV"}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["colored_code_type"]["value"] == "CTV"

    def test_convert_candidate_already_converted(self):
        """Test converting candidate that is already converted returns error"""
        # Create a candidate and an employee
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van Already",
            citizen_id="123456789020",
            email="nguyenvanalready@example.com",
            phone="0123456798",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        # First conversion should succeed
        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response1 = self.client.post(url, {"code_type": "MV"}, format="json")
        assert response1.status_code == status.HTTP_201_CREATED

        # Second conversion should fail
        response2 = self.client.post(url, {"code_type": "MV"}, format="json")
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response2.json()
        assert "non_field_errors" in response_data["error"]

    def test_convert_candidate_to_employee_requires_hired_status(self):
        """Test converting candidate without HIRED status returns error"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van Not Hired",
            citizen_id="123456789099",
            email="nguyenvannothired@example.com",
            phone="0123456700",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.INTERVIEWED_1,  # Not HIRED status
        )

        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response = self.client.post(url, {"code_type": "MV"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "non_field_errors" in response_data["error"]

    def test_convert_candidate_to_employee_duplicate_email(self):
        """Test converting candidate when email already exists as employee"""
        # Create an employee with the same email first
        Employee.objects.create(
            fullname="Existing Employee",
            username="existingemp",
            email="existing@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            phone="0123456792",
            attendance_code="EMP002",
            start_date=date(2024, 1, 1),
            citizen_id="000000020029",
        )

        # Create candidate with same email
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van F",
            citizen_id="123456789015",
            email="existing@example.com",
            phone="0123456793",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        response = self.client.post(url, {"code_type": "MV"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        # Should get an error about duplicate email
        assert "email" in response_data["error"]

    def test_convert_candidate_generates_unique_attendance_code(self):
        """Test that converting multiple candidates generates unique attendance codes"""
        candidate1 = RecruitmentCandidate.objects.create(
            name="Nguyen Van G",
            citizen_id="123456789016",
            email="nguyenvang@example.com",
            phone="0123456794",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        candidate2 = RecruitmentCandidate.objects.create(
            name="Nguyen Van H",
            citizen_id="123456789017",
            email="nguyenvanh@example.com",
            phone="0123456795",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        url1 = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate1.pk})
        url2 = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate2.pk})

        response1 = self.client.post(url1, {"code_type": "MV"}, format="json")
        response2 = self.client.post(url2, {"code_type": "MV"}, format="json")

        # Get response data to check codes
        data1 = self.get_response_data(response1)
        data2 = self.get_response_data(response2)

        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_201_CREATED

        # Both should have attendance codes
        assert data1["attendance_code"] is not None
        assert data2["attendance_code"] is not None
        assert data1["attendance_code"] != data2["attendance_code"]

        # Verify employees exist in database
        employee1 = Employee.objects.get(email="nguyenvang@example.com")
        employee2 = Employee.objects.get(email="nguyenvanh@example.com")

        assert employee1.attendance_code is not None
        assert employee2.attendance_code is not None
        assert employee1.attendance_code != employee2.attendance_code

    def test_employee_field_in_candidate_response(self):
        """Test that employee field is included in candidate API response"""
        # Create a candidate
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van Test",
            citizen_id="123456789021",
            email="nguyenvantest@example.com",
            phone="0123456799",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        # Check employee is None initially
        url = reverse("hrm:recruitment-candidate-detail", kwargs={"pk": candidate.pk})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert "employee" in response_data
        assert response_data["employee"] is None

        # Convert candidate to employee
        convert_url = reverse("hrm:recruitment-candidate-to-employee", kwargs={"pk": candidate.pk})
        self.client.post(convert_url, {"code_type": "MV"}, format="json")

        # Check employee is now present
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert "employee" in response_data
        assert response_data["employee"] is not None
        assert "id" in response_data["employee"]
        assert "code" in response_data["employee"]
        assert "fullname" in response_data["employee"]
