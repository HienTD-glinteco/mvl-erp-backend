"""Tests for Block API auto-code generation."""

import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Block, Branch

User = get_user_model()


class BlockAutoCodeGenerationAPITest(TransactionTestCase):
    """Test cases for Block API auto-code generation."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        Branch.objects.all().delete()
        Block.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.branch = Branch.objects.create(name="Chi nhánh Hà Nội", code="HN")

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

    def test_create_block_without_code_auto_generates(self):
        """Test creating a block without code field auto-generates code."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "block_type": Block.BlockType.SUPPORT,
            "branch": str(self.branch.id),
        }

        # Act
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertIn("code", response_data)
        self.assertTrue(response_data["code"].startswith("KH"))

        # Verify in database
        block = Block.objects.first()
        self.assertIsNotNone(block)
        self.assertEqual(block.code, response_data["code"])

    def test_create_block_with_code_ignores_provided_code(self):
        """Test that provided code is ignored and auto-generated code is used."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "code": "MANUAL",  # This should be ignored
            "block_type": Block.BlockType.SUPPORT,
            "branch": str(self.branch.id),
        }

        # Act
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify auto-generated code was used, not manual code
        self.assertNotEqual(response_data["code"], "MANUAL")
        self.assertTrue(response_data["code"].startswith("KH"))

    def test_auto_generated_code_format_single_digit(self):
        """Test auto-generated code format for first block (KH001)."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "block_type": Block.BlockType.SUPPORT,
            "branch": str(self.branch.id),
        }

        # Act
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code format (should be at least 3 digits)
        block = Block.objects.first()
        self.assertEqual(block.code, f"KH{block.id:03d}")

    def test_auto_generated_code_multiple_blocks(self):
        """Test auto-generated codes for multiple blocks."""
        # Arrange
        url = reverse("hrm:block-list")

        # Act - Create 3 blocks
        for i in range(3):
            block_data = {
                "name": f"Khối {i + 1}",
                "block_type": Block.BlockType.SUPPORT if i % 2 == 0 else Block.BlockType.BUSINESS,
                "branch": str(self.branch.id),
            }
            response = self.client.post(url, block_data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assert - Verify all blocks have unique auto-generated codes
        blocks = Block.objects.all().order_by("id")
        self.assertEqual(blocks.count(), 3)

        codes = [block.code for block in blocks]
        # All codes should be unique
        self.assertEqual(len(codes), len(set(codes)))
        # All codes should start with BL
        for code in codes:
            self.assertTrue(code.startswith("KH"))

    def test_code_field_is_readonly_in_response(self):
        """Test that code field is included in response but not writable."""
        # Arrange
        block_data = {
            "name": "Khối Hỗ trợ",
            "block_type": Block.BlockType.SUPPORT,
            "branch": str(self.branch.id),
        }

        # Act - Create block
        url = reverse("hrm:block-list")
        response = self.client.post(url, block_data, format="json")

        # Assert - Response includes code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertIn("code", response_data)

        # Act - Try to update code
        block = Block.objects.first()
        update_url = reverse("hrm:block-detail", kwargs={"pk": block.pk})
        update_data = {"code": "NEWCODE"}
        update_response = self.client.patch(update_url, update_data, format="json")

        # Assert - Code should not be updated
        block.refresh_from_db()
        self.assertNotEqual(block.code, "NEWCODE")
