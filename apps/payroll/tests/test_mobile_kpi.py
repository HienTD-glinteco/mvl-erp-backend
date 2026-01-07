"""Tests for mobile KPI assessment views."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem, KPIAssessmentPeriod


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            data = content["data"]
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestMyKPIAssessmentViewSet(APITestMixin):
    """Test cases for MyKPIAssessmentViewSet."""

    @pytest.fixture
    def test_employee(self, superuser, branch, block, department, position):
        """Create employee linked to superuser for authentication."""
        from apps.hrm.models import Employee

        return Employee.objects.create(
            user=superuser,
            code="MV000001",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            phone="0123456789",
            personal_email="test_personal@example.com",
            attendance_code="12345",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="123456789012",
        )

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, test_employee):
        self.client = api_client
        self.employee = test_employee

    @pytest.fixture
    def kpi_period(self, db):
        """Create a KPI period."""
        from datetime import date

        return KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot={},
            finalized=False,
        )

    @pytest.fixture
    def kpi_assessment(self, test_employee, kpi_period):
        """Create a KPI assessment for the employee."""
        return EmployeeKPIAssessment.objects.create(
            employee=test_employee,
            period=kpi_period,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("85.00"),
            total_manager_score=Decimal("80.00"),
            grade_manager=None,
            plan_tasks="Complete project milestones",
            extra_tasks="Help junior team members",
            proposal="Implement new process",
            finalized=False,
        )

    @pytest.fixture
    def kpi_assessment_items(self, kpi_assessment):
        """Create assessment items."""
        item1 = EmployeeKPIItem.objects.create(
            assessment=kpi_assessment,
            criterion="Quality of Work",
            description="Work meets quality standards",
            component_total_score=Decimal("30.00"),
            employee_score=Decimal("25.00"),
            manager_score=Decimal("24.00"),
            order=1,
        )
        item2 = EmployeeKPIItem.objects.create(
            assessment=kpi_assessment,
            criterion="Timeliness",
            description="Meets deadlines consistently",
            component_total_score=Decimal("20.00"),
            employee_score=Decimal("18.00"),
            manager_score=Decimal("17.00"),
            order=2,
        )
        return [item1, item2]

    def test_list_my_kpi_assessments(self, kpi_assessment, kpi_assessment_items):
        """Test listing current user's KPI assessments."""
        url = reverse("payroll-mobile:my-kpi-assessment-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) >= 1
        assert response_data[0]["id"] == kpi_assessment.id
        assert response_data[0]["employee"]["id"] == self.employee.id

    def test_retrieve_my_kpi_assessment(self, kpi_assessment, kpi_assessment_items):
        """Test retrieving a specific KPI assessment."""
        url = reverse("payroll-mobile:my-kpi-assessment-detail", kwargs={"pk": kpi_assessment.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["id"] == kpi_assessment.id
        assert data["total_possible_score"] == "100.00"
        assert data["total_employee_score"] == "85.00"
        assert data["plan_tasks"] == "Complete project milestones"
        assert len(data["items"]) == 2

    def test_update_my_kpi_assessment(self, kpi_assessment, kpi_assessment_items):
        """Test updating self-assessment."""
        url = reverse("payroll-mobile:my-kpi-assessment-detail", kwargs={"pk": kpi_assessment.pk})
        data = {
            "plan_tasks": "Updated project milestones",
            "extra_tasks": "Additional training sessions",
            "items": [
                {"item_id": kpi_assessment_items[0].id, "score": "28.00"},
                {"item_id": kpi_assessment_items[1].id, "score": "19.00"},
            ],
        }
        response = self.client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True

        kpi_assessment.refresh_from_db()
        assert kpi_assessment.plan_tasks == "Updated project milestones"

    def test_get_current_assessment(self, kpi_assessment):
        """Test getting current unfinalized assessment."""
        url = reverse("payroll-mobile:my-kpi-assessment-current")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["id"] == kpi_assessment.id
        assert data["finalized"] is False

    def test_get_current_assessment_not_found(self, kpi_assessment):
        """Test getting current assessment when none exists."""
        kpi_assessment.finalized = True
        kpi_assessment.save()

        url = reverse("payroll-mobile:my-kpi-assessment-current")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_only_own_assessments(self, kpi_assessment, kpi_period, branch, block, department, position):
        """Test that users can only see their own assessments."""
        from apps.core.models import User
        from apps.hrm.models import Employee

        other_user = User.objects.create_user(username="other_user", email="other@test.com", password="pass123")
        other_employee = Employee.objects.create(
            user=other_user,
            code="MV000099",
            fullname="Other Employee",
            username="other_emp",
            email="other@example.com",
            personal_email="test_personal_other@example.com",
            phone="0987654321",
            attendance_code="99999",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="999999999999",
        )
        EmployeeKPIAssessment.objects.create(
            employee=other_employee,
            period=kpi_period,
            total_possible_score=Decimal("100.00"),
        )

        url = reverse("payroll-mobile:my-kpi-assessment-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["employee"]["id"] == self.employee.id

    def test_cannot_access_other_employee_assessment(self, kpi_period, branch, block, department, position):
        """Test that users cannot access other employees' assessments."""
        from apps.core.models import User
        from apps.hrm.models import Employee

        other_user = User.objects.create_user(username="other_user2", email="other2@test.com", password="pass123")
        other_employee = Employee.objects.create(
            user=other_user,
            code="MV000098",
            fullname="Other Employee 2",
            username="other_emp2",
            email="other2@example.com",
            personal_email="test_personal_other2@example.com",
            phone="0987654322",
            attendance_code="99998",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="999999999998",
        )
        other_assessment = EmployeeKPIAssessment.objects.create(
            employee=other_employee,
            period=kpi_period,
            total_possible_score=Decimal("100.00"),
        )

        url = reverse("payroll-mobile:my-kpi-assessment-detail", kwargs={"pk": other_assessment.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access assessments."""
        self.client.force_authenticate(user=None)
        url = reverse("payroll-mobile:my-kpi-assessment-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMyTeamKPIAssessmentViewSet(APITestMixin):
    """Test cases for MyTeamKPIAssessmentViewSet."""

    @pytest.fixture
    def test_employee(self, superuser, branch, block, department, position):
        """Create employee linked to superuser for authentication."""
        from apps.hrm.models import Employee

        return Employee.objects.create(
            user=superuser,
            code="MV000002",
            fullname="Test Manager",
            username="testmanager",
            email="testmanager@example.com",
            personal_email="testmanager_personal@example.com",
            phone="0123456788",
            attendance_code="12346",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="123456789013",
        )

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, test_employee):
        self.client = api_client
        self.employee = test_employee

    @pytest.fixture
    def kpi_period(self, db):
        """Create a KPI period."""
        from datetime import date

        return KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot={},
            finalized=False,
        )

    @pytest.fixture
    def team_assessments(self, test_employee, kpi_period, branch, block, department, position):
        """Create KPI assessments for team members."""
        from apps.core.models import User
        from apps.hrm.models import Employee

        user1 = User.objects.create_user(username="team_member1", email="team1@test.com", password="pass123")
        team_member1 = Employee.objects.create(
            user=user1,
            code="MV000021",
            fullname="Team Member 1",
            username="team1",
            email="team1@example.com",
            personal_email="team1_personal@example.com",
            phone="0111111111",
            attendance_code="11111",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="111111111111",
        )

        user2 = User.objects.create_user(username="team_member2", email="team2@test.com", password="pass123")
        team_member2 = Employee.objects.create(
            user=user2,
            code="MV000022",
            fullname="Team Member 2",
            username="team2",
            email="team2@example.com",
            personal_email="team2_personal@example.com",
            phone="0222222222",
            attendance_code="22222",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="222222222222",
        )

        assessment1 = EmployeeKPIAssessment.objects.create(
            employee=team_member1,
            manager=test_employee,
            period=kpi_period,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("88.00"),
            total_manager_score=Decimal("82.00"),
            grade_manager="B",
            finalized=False,
        )

        assessment2 = EmployeeKPIAssessment.objects.create(
            employee=team_member2,
            manager=test_employee,
            period=kpi_period,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("75.00"),
            total_manager_score=Decimal("70.00"),
            grade_manager="C",
            finalized=False,
        )

        return [assessment1, assessment2]

    def test_list_team_assessments(self, team_assessments):
        """Test listing team member assessments."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

    def test_retrieve_team_member_assessment(self, team_assessments):
        """Test retrieving a specific team member assessment."""
        assessment = team_assessments[0]
        url = reverse("payroll-mobile:my-team-kpi-assessment-detail", kwargs={"pk": assessment.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["id"] == assessment.id
        assert data["employee"]["id"] == assessment.employee.id

    def test_update_team_member_assessment(self, team_assessments):
        """Test updating team member assessment scores."""
        assessment = team_assessments[0]
        EmployeeKPIItem.objects.create(
            assessment=assessment,
            criterion="Quality",
            component_total_score=Decimal("50.00"),
            employee_score=Decimal("45.00"),
            order=1,
        )

        url = reverse("payroll-mobile:my-team-kpi-assessment-detail", kwargs={"pk": assessment.pk})
        data = {
            "grade": "A",
            "manager_assessment": "Excellent performance",
            "items": [
                {"item_id": assessment.items.first().id, "score": "48.00"},
            ],
        }
        response = self.client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True

        assessment.refresh_from_db()
        assert assessment.grade_manager_overridden == "A"
        assert assessment.manager_assessment == "Excellent performance"

    def test_get_current_team_assessments(self, team_assessments):
        """Test getting current unfinalized team assessments with pagination."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        # Check pagination structure
        assert "count" in data
        assert "results" in data
        assert "next" in data
        assert "previous" in data
        # Check results
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_current_action_pagination(self, kpi_period, branch, block, department, position):
        """Test pagination on current action."""
        from apps.core.models import User
        from apps.hrm.models import Employee

        # Create multiple team members
        for i in range(15):
            user = User.objects.create_user(
                username=f"team_member_{i}",
                email=f"team{i}@test.com",
                password="pass123",
            )
            employee = Employee.objects.create(
                user=user,
                code=f"MV{100 + i:06d}",  # MV000100, MV000101, etc.
                fullname=f"Team Member {i}",
                username=f"teammember{i}",
                email=f"teammember{i}@example.com",
                personal_email=f"teammember{i}_personal@example.com",
                phone=f"09{i:08d}",
                attendance_code=f"ATT{i:05d}",
                start_date="2024-01-01",
                branch=branch,
                block=block,
                department=department,
                position=position,
                citizen_id=f"CID{i:09d}",
            )
            EmployeeKPIAssessment.objects.create(
                employee=employee,
                manager=self.employee,
                period=kpi_period,
                total_possible_score=Decimal("100.00"),
                finalized=False,
            )

        # Test first page
        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url, {"page": 1, "page_size": 10})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 15
        assert len(data["results"]) == 10
        assert data["next"] is not None

        # Test second page
        response = self.client.get(url, {"page": 2, "page_size": 10})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data["results"]) == 5
        assert data["next"] is None

    def test_current_action_filter_by_employee_code(self, team_assessments):
        """Test filtering current assessments by employee code."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url, {"employee_code": "MV000021"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["results"][0]["employee"]["code"] == "MV000021"

    def test_current_action_filter_by_grade(self, team_assessments):
        """Test filtering current assessments by grade."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url, {"grade_manager": "B"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["results"][0]["grade_manager"] == "B"

    def test_current_action_search_by_employee_name(self, team_assessments):
        """Test searching current assessments by employee name."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url, {"search": "Team Member 1"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_current_action_ordering(self, team_assessments):
        """Test ordering current assessments."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url, {"ordering": "employee__code"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        codes = [r["employee"]["code"] for r in data["results"]]
        assert codes == sorted(codes)

    def test_current_action_only_latest_per_employee(self, test_employee, branch, block, department, position):
        """Test that current action returns only latest assessment per employee."""
        from datetime import date

        from apps.core.models import User
        from apps.hrm.models import Employee

        # Create a team member
        user = User.objects.create_user(username="multi_period", email="multi@test.com", password="pass123")
        employee = Employee.objects.create(
            user=user,
            code="MV000099",
            fullname="Multi Period Employee",
            username="multiperiod",
            email="multiperiod@example.com",
            personal_email="multiperiod_personal@example.com",
            phone="0999999999",
            attendance_code="99999",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="999999999999",
        )

        # Create periods and assessments
        period1 = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot={},
            finalized=False,
        )
        period2 = KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot={},
            finalized=False,
        )

        EmployeeKPIAssessment.objects.create(
            employee=employee,
            manager=test_employee,
            period=period1,
            total_possible_score=Decimal("100.00"),
            finalized=False,
        )
        EmployeeKPIAssessment.objects.create(
            employee=employee,
            manager=test_employee,
            period=period2,
            total_possible_score=Decimal("100.00"),
            finalized=False,
        )

        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        response = self.client.get(url, {"employee_code": "MV000099"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        # Should only return 1 assessment (the latest)
        assert data["count"] == 1
        # Should be from period2 (latest)
        assert data["results"][0]["period"]["month"] == "1/2026"

    def test_current_action_page_size_works(self, kpi_period, branch, block, department, position):
        """Test that page_size query parameter works correctly."""
        from apps.core.models import User
        from apps.hrm.models import Employee

        # Create 5 team members
        for i in range(5):
            user = User.objects.create_user(
                username=f"team_size_test_{i}",
                email=f"size{i}@test.com",
                password="pass123",
            )
            employee = Employee.objects.create(
                user=user,
                code=f"MV{200 + i:06d}",
                fullname=f"Page Size Test {i}",
                username=f"pagesizetest{i}",
                email=f"pagesizetest{i}@example.com",
                personal_email=f"pagesizetest{i}_personal@example.com",
                phone=f"08{i:08d}",
                attendance_code=f"PST{i:05d}",
                start_date="2024-01-01",
                branch=branch,
                block=block,
                department=department,
                position=position,
                citizen_id=f"PST{i:09d}",
            )
            EmployeeKPIAssessment.objects.create(
                employee=employee,
                manager=self.employee,
                period=kpi_period,
                total_possible_score=Decimal("100.00"),
                finalized=False,
            )

        url = reverse("payroll-mobile:my-team-kpi-assessment-current")
        
        # Test page_size=1
        response = self.client.get(url, {"page_size": 1})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data["results"]) == 1, f"Expected 1 result with page_size=1, got {len(data['results'])}"
        assert data["count"] == 5
        assert data["next"] is not None
        
        # Test page_size=2
        response = self.client.get(url, {"page_size": 2})
        data = response.json()["data"]
        assert len(data["results"]) == 2, f"Expected 2 results with page_size=2, got {len(data['results'])}"
        
        # Test page_size=10 (should return all 5)
        response = self.client.get(url, {"page_size": 10})
        data = response.json()["data"]
        assert len(data["results"]) == 5, f"Expected 5 results with page_size=10, got {len(data['results'])}"
        assert data["next"] is None

    def test_only_team_assessments(self, team_assessments, kpi_period, branch, block, department, position):
        """Test that managers can only see their team's assessments."""
        from apps.core.models import User
        from apps.hrm.models import Employee

        other_manager_user = User.objects.create_user(
            username="other_manager", email="othermanager@test.com", password="pass123"
        )
        other_manager = Employee.objects.create(
            user=other_manager_user,
            code="MV000031",
            fullname="Other Manager",
            username="othermanager",
            email="othermanager@example.com",
            personal_email="othermanager_personal@example.com",
            phone="0333333333",
            attendance_code="33333",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="333333333333",
        )

        other_team_user = User.objects.create_user(
            username="other_team_member", email="otherteam@test.com", password="pass123"
        )
        other_team_member = Employee.objects.create(
            user=other_team_user,
            code="MV000032",
            fullname="Other Team Member",
            username="otherteam",
            email="otherteam@example.com",
            personal_email="otherteam_personal@example.com",
            phone="0444444444",
            attendance_code="44444",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
            citizen_id="444444444444",
        )

        EmployeeKPIAssessment.objects.create(
            employee=other_team_member,
            manager=other_manager,
            period=kpi_period,
            total_possible_score=Decimal("100.00"),
        )

        url = reverse("payroll-mobile:my-team-kpi-assessment-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        # Verify all returned assessments have team_assessments employee IDs
        returned_employee_ids = {a["employee"]["id"] for a in response_data}
        expected_employee_ids = {a.employee.id for a in team_assessments}
        assert returned_employee_ids == expected_employee_ids

    def test_filter_by_grade(self, team_assessments):
        """Test filtering team assessments by grade."""
        url = reverse("payroll-mobile:my-team-kpi-assessment-list")
        response = self.client.get(url, {"grade_manager": "B"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["grade_manager"] == "B"

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access team assessments."""
        self.client.force_authenticate(user=None)
        url = reverse("payroll-mobile:my-team-kpi-assessment-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
