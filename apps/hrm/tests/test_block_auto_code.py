"""Tests for Block API auto-code generation."""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch


@pytest.mark.django_db
class TestBlockAutoCodeGenerationAPI:
    """Test cases for Block API auto-code generation."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def geographic_data(self, db):
        """Create Province and AdministrativeUnit for Branch."""
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

    @pytest.fixture
    def branch(self, geographic_data):
        """Create a Branch for Block tests."""
        province, administrative_unit = geographic_data
        return Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=province,
            administrative_unit=administrative_unit,
        )

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            return content["data"]
        return content

    def test_create_block_without_code_auto_generates(self, branch):
        """Test creating a block without code field auto-generates code."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(branch.id),
        }

        # Act
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        assert "code" in response_data
        assert response_data["code"].startswith("KH")

        # Verify in database
        block = Block.objects.first()
        assert block is not None
        assert block.code == response_data["code"]

    def test_create_block_with_code_ignores_provided_code(self, branch):
        """Test that provided code is ignored and auto-generated code is used."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "code": "MANUAL",  # This should be ignored
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(branch.id),
        }

        # Act
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify auto-generated code was used, not manual code
        assert response_data["code"] != "MANUAL"
        assert response_data["code"].startswith("KH")

    def test_auto_generated_code_format_single_digit(self, branch):
        """Test auto-generated code format for first block (KH001)."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(branch.id),
        }

        # Act
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED

        # Verify code format (should be at least 9 digits)
        block = Block.objects.first()
        assert block.code == f"KH{block.id:09d}"

    def test_auto_generated_code_multiple_blocks(self, branch):
        """Test auto-generated codes for multiple blocks."""
        # Arrange
        url = reverse("hrm:block-list")

        # Act - Create 3 blocks
        for i in range(3):
            block_data = {
                "name": f"Khối {i + 1}",
                "block_type": Block.BlockType.SUPPORT if i % 2 == 0 else Block.BlockType.BUSINESS,
                "branch_id": str(branch.id),
            }
            response = self.client.post(url, block_data, format="json")
            assert response.status_code == status.HTTP_201_CREATED

        # Assert - Verify all blocks have unique auto-generated codes
        blocks = Block.objects.all().order_by("id")
        assert blocks.count() == 3

        codes = [block.code for block in blocks]
        # All codes should be unique
        assert len(codes) == len(set(codes))
        # All codes should start with KH
        for code in codes:
            assert code.startswith("KH")

    def test_code_field_is_readonly_in_response(self, branch):
        """Test that code field is included in response but not writable."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "block_type": Block.BlockType.SUPPORT,
            "branch_id": str(branch.id),
        }

        # Act - Create block
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert - Response includes code
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        assert "code" in response_data

        # Act - Try to update code
        block = Block.objects.first()
        update_url = reverse("hrm:block-detail", kwargs={"pk": block.pk})
        update_data = {"code": "NEWCODE"}
        self.client.patch(update_url, update_data, format="json")

        # Assert - Code should not be updated
        block.refresh_from_db()
        assert block.code != "NEWCODE"
