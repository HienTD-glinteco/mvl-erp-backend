"""Tests for Branch API auto-code generation."""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Branch


@pytest.mark.django_db
class TestBranchAutoCodeGenerationAPI:
    """Test cases for Branch API auto-code generation."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def geographic_data(self, db):
        """Create Province and AdministrativeUnit for Branch creation."""
        province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        return province, administrative_unit

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            return content["data"]
        return content

    def test_create_branch_without_code_auto_generates(self, geographic_data):
        """Test creating a branch without code field auto-generates code."""
        province, administrative_unit = geographic_data

        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
            "province_id": str(province.id),
            "administrative_unit_id": str(administrative_unit.id),
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        assert "code" in response_data
        assert response_data["code"].startswith("CN")

        # Verify in database
        branch = Branch.objects.first()
        assert branch is not None
        assert branch.code == response_data["code"]

    def test_create_branch_with_code_ignores_provided_code(self, geographic_data):
        """Test that provided code is ignored and auto-generated code is used."""
        province, administrative_unit = geographic_data

        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "code": "MANUAL",  # This should be ignored
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
            "province_id": str(province.id),
            "administrative_unit_id": str(administrative_unit.id),
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify auto-generated code was used, not manual code
        assert response_data["code"] != "MANUAL"
        assert response_data["code"].startswith("CN")

    def test_auto_generated_code_format_single_digit(self, geographic_data):
        """Test auto-generated code format for first branch (CN001)."""
        province, administrative_unit = geographic_data

        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
            "province_id": str(province.id),
            "administrative_unit_id": str(administrative_unit.id),
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED

        # Verify code format (should be at least 9 digits)
        branch = Branch.objects.first()
        assert branch.code == f"CN{branch.id:09d}"

    def test_auto_generated_code_multiple_branches(self, geographic_data):
        """Test auto-generated codes for multiple branches."""
        province, administrative_unit = geographic_data

        # Arrange
        url = reverse("hrm:branch-list")

        # Act - Create 3 branches
        for i in range(3):
            branch_data = {
                "name": f"Chi nhánh {i + 1}",
                "address": f"Địa chỉ {i + 1}",
                "province_id": str(province.id),
                "administrative_unit_id": str(administrative_unit.id),
            }
            response = self.client.post(url, branch_data, format="json")
            assert response.status_code == status.HTTP_201_CREATED

        # Assert - Verify all branches have unique auto-generated codes
        branches = Branch.objects.all().order_by("id")
        assert branches.count() == 3

        codes = [branch.code for branch in branches]
        # All codes should be unique
        assert len(codes) == len(set(codes))
        # All codes should start with CN
        for code in codes:
            assert code.startswith("CN")

    def test_code_field_is_readonly_in_response(self, geographic_data):
        """Test that code field is included in response but not writable."""
        province, administrative_unit = geographic_data

        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
            "province_id": str(province.id),
            "administrative_unit_id": str(administrative_unit.id),
        }

        # Act - Create branch
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert - Response includes code
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert "code" in response_data

        # Act - Try to update code
        branch = Branch.objects.first()
        update_url = reverse("hrm:branch-detail", kwargs={"pk": branch.pk})
        update_data = {"code": "NEWCODE"}
        self.client.patch(update_url, update_data, format="json")

        # Assert - Code should not be updated
        branch.refresh_from_db()
        assert branch.code != "NEWCODE"

    def test_branch_with_description(self, geographic_data):
        """Test creating a branch with description field."""
        province, administrative_unit = geographic_data

        # Arrange
        branch_data = {
            "name": "Chi nhánh Hà Nội",
            "address": "123 Lê Duẩn, Hà Nội",
            "description": "Branch description here",
            "province_id": str(province.id),
            "administrative_unit_id": str(administrative_unit.id),
        }

        # Act
        url = reverse("hrm:branch-list")
        response = self.client.post(url, branch_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert response_data["description"] == branch_data["description"]

        # Verify in database
        branch = Branch.objects.first()
        assert branch.description == branch_data["description"]
