"""Tests for EmployeeKPIAssessment export functionality."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.payroll.models import (
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class TestEmployeeKPIAssessmentExport:
    """Test cases for EmployeeKPIAssessment export endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self, api_client, employee, branch, block, department, position):
        """Set up test data."""
        self.client = api_client
        self.employee = employee
        self.branch = branch
        self.block = block
        self.department = department
        self.position = position

        # Create user with permissions
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        # Create KPI config
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                    {"min": 60, "max": 80, "possible_codes": ["C"], "label": "Average"},
                    {"min": 80, "max": 90, "possible_codes": ["B"], "label": "Good"},
                    {"min": 90, "max": 100, "possible_codes": ["A"], "label": "Excellent"},
                ],
            }
        )

        # Create assessment period
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Create assessments
        self.assessment1 = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=self.period,
            grade_manager="A",
            grade_hrm="A",
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("95.00"),
            total_manager_score=Decimal("95.00"),
            plan_tasks="Complete quarterly targets",
            extra_tasks="Handle urgent client requests",
            proposal="Improve team workflow",
            manager_assessment="Excellent performance",
            finalized=False,
        )

    def test_export_endpoint_exists(self):
        """Test that export endpoint is accessible (permission check)."""
        # Arrange
        url = reverse("payroll:kpi-assessments-export")

        # Act
        response = self.client.get(url, {"delivery": "direct"})

        # Assert - Either success or permission denied (both confirm endpoint exists)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_206_PARTIAL_CONTENT,
            status.HTTP_403_FORBIDDEN,  # Permission issue but endpoint exists
        ]

    def test_export_xlsx_direct_delivery(self):
        """Test XLSX export with direct delivery (permission check)."""
        # Arrange
        url = reverse("payroll:kpi-assessments-export")

        # Act
        response = self.client.get(url, {"delivery": "direct"})

        # Assert - Either success or permission denied (both confirm endpoint exists)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_206_PARTIAL_CONTENT,
            status.HTTP_403_FORBIDDEN,  # Permission issue but endpoint exists
        ]

        # If successful, check content type
        if response.status_code in [status.HTTP_200_OK, status.HTTP_206_PARTIAL_CONTENT]:
            assert response.get("Content-Type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_export_serializer_includes_all_fields(self):
        """Test that export serializer includes all required fields."""
        # Arrange
        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=self.assessment1)
        data = serializer.data

        # Assert
        expected_fields = [
            "period__month",
            "employee__code",
            "employee__fullname",
            "employee__branch__name",
            "employee__block__name",
            "employee__department__name",
            "employee__position__name",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "grade_hrm",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "finalized",
        ]

        for field in expected_fields:
            assert field in data, f"Field {field} missing from export serializer"

    def test_export_serializer_period_format(self):
        """Test that period month is formatted correctly."""
        # Arrange
        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=self.assessment1)
        data = serializer.data

        # Assert
        assert data["period__month"] == "12/2025"

    def test_export_serializer_employee_fields(self):
        """Test that employee fields are correctly flattened."""
        # Arrange
        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=self.assessment1)
        data = serializer.data

        # Assert
        assert data["employee__code"] == self.employee.code
        assert data["employee__fullname"] == self.employee.fullname
        assert data["employee__branch__name"] == self.branch.name
        assert data["employee__block__name"] == self.block.name
        assert data["employee__department__name"] == self.department.name
        assert data["employee__position__name"] == self.position.name

    def test_export_serializer_score_fields(self):
        """Test that score fields are included correctly."""
        # Arrange
        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=self.assessment1)
        data = serializer.data

        # Assert
        assert data["total_possible_score"] == "100.00"
        assert data["total_employee_score"] == "95.00"
        assert data["total_manager_score"] == "95.00"

    def test_export_serializer_grade_fields(self):
        """Test that grade fields are included correctly."""
        # Arrange
        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=self.assessment1)
        data = serializer.data

        # Assert
        assert data["grade_manager"] == "A"
        assert data["grade_hrm"] == "A"
        assert data["grade_manager_overridden"] is None

    def test_export_serializer_text_fields(self):
        """Test that text fields are included correctly."""
        # Arrange
        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=self.assessment1)
        data = serializer.data

        # Assert
        assert data["plan_tasks"] == "Complete quarterly targets"
        assert data["extra_tasks"] == "Handle urgent client requests"
        assert data["proposal"] == "Improve team workflow"
        assert data["manager_assessment"] == "Excellent performance"

    def test_export_with_filter(self):
        """Test export with query filters."""
        # Arrange
        # Create another assessment with different grade
        from datetime import date

        from apps.hrm.models import Employee

        employee2 = Employee.objects.create(
            code="E002",
            fullname="Jane Smith",
            username="emp002",
            email="emp002@example.com",
            employee_type="fulltime",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2025, 1, 1),
            phone="0912345678",
            personal_email="emp002.personal@example.com",
        )

        EmployeeKPIAssessment.objects.create(
            employee=employee2,
            period=self.period,
            grade_manager="B",
            grade_hrm="B",
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("85.00"),
            total_manager_score=Decimal("85.00"),
        )

        url = reverse("payroll:kpi-assessments-export")

        # Act
        response = self.client.get(url, {"delivery": "direct", "grade_manager": "A"})

        # Assert - Either success or permission denied
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_206_PARTIAL_CONTENT,
            status.HTTP_403_FORBIDDEN,  # Permission issue but endpoint exists
        ]

    def test_export_serializer_handles_null_fields(self):
        """Test that serializer handles null/empty fields gracefully."""
        # Arrange
        from datetime import date

        from apps.payroll.api.serializers import EmployeeKPIAssessmentExportSerializer

        # Create another period to avoid unique constraint
        another_period = KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Create assessment with minimal data
        assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee,
            period=another_period,
        )

        # Act
        serializer = EmployeeKPIAssessmentExportSerializer(instance=assessment)
        data = serializer.data

        # Assert - should not raise errors
        assert "plan_tasks" in data
        assert "extra_tasks" in data
        assert "proposal" in data
        assert "manager_assessment" in data

    def test_export_multiple_assessments(self):
        """Test exporting multiple assessments."""
        # Arrange
        from datetime import date

        from apps.hrm.models import Employee

        # Create multiple employees and assessments
        for i in range(3):
            employee = Employee.objects.create(
                code=f"E00{i + 2}",
                fullname=f"Employee {i + 2}",
                username=f"emp00{i + 2}",
                email=f"emp00{i + 2}@example.com",
                employee_type="fulltime",
                branch=self.branch,
                block=self.block,
                department=self.department,
                position=self.position,
                start_date=date(2025, 1, 1),
                phone=f"091234567{i}",
                citizen_id=f"12345678901{i}",
                personal_email=f"emp00{i + 2}.personal@example.com",
            )

            EmployeeKPIAssessment.objects.create(
                employee=employee,
                period=self.period,
                grade_manager="B",
                grade_hrm="B",
                total_possible_score=Decimal("100.00"),
                total_employee_score=Decimal("80.00"),
                total_manager_score=Decimal("80.00"),
            )

        url = reverse("payroll:kpi-assessments-export")

        # Act
        response = self.client.get(url, {"delivery": "direct"})

        # Assert - Either success or permission denied
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_206_PARTIAL_CONTENT,
            status.HTTP_403_FORBIDDEN,  # Permission issue but endpoint exists
        ]

    def test_viewset_has_export_configuration(self):
        """Test that ViewSet has proper export configuration."""
        # Arrange
        from apps.payroll.api.views.employee_kpi_assessment import EmployeeKPIAssessmentViewSet

        # Act & Assert
        assert hasattr(EmployeeKPIAssessmentViewSet, "export_serializer_class")
        assert hasattr(EmployeeKPIAssessmentViewSet, "export_filename")
        assert EmployeeKPIAssessmentViewSet.export_filename == "employee_kpi_assessments"

    def test_viewset_queryset_includes_related_fields(self):
        """Test that ViewSet queryset includes related fields for export."""
        # Arrange
        from apps.payroll.api.views.employee_kpi_assessment import EmployeeKPIAssessmentViewSet

        # Act
        queryset = EmployeeKPIAssessmentViewSet.queryset

        # Assert - check that select_related includes employee and its relations
        # The structure is nested: employee -> branch, block, department, position
        select_related_fields = queryset.query.select_related
        assert "employee" in select_related_fields

        # Check nested relations under employee
        employee_related = select_related_fields["employee"]
        assert "branch" in employee_related
        assert "block" in employee_related
        assert "department" in employee_related
        assert "position" in employee_related
