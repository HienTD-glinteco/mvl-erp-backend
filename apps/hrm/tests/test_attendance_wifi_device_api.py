import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import AttendanceWifiDevice, Block, Branch

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class AttendanceWifiDeviceAPITest(TransactionTestCase, APITestMixin):
    """Test cases for AttendanceWifiDevice API endpoints."""

    def setUp(self):
        # Clear all existing data for clean tests
        AttendanceWifiDevice.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()
        Province.objects.all().delete()
        AdministrativeUnit.objects.all().delete()
        User.objects.all().delete()

        # Create superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create provinces
        self.province1 = Province.objects.create(name="Test Province 1", code="TP001")
        self.province2 = Province.objects.create(name="Test Province 2", code="TP002")

        # Create administrative units with parent provinces
        self.admin_unit1 = AdministrativeUnit.objects.create(
            name="Test Admin Unit 1",
            code="TAU001",
            parent_province=self.province1,
            level="district",
        )
        self.admin_unit2 = AdministrativeUnit.objects.create(
            name="Test Admin Unit 2",
            code="TAU002",
            parent_province=self.province2,
            level="district",
        )

        # Update provinces with administrative units
        self.province1.administrative_unit = self.admin_unit1
        self.province1.save()
        self.province2.administrative_unit = self.admin_unit2
        self.province2.save()

        # Create branches
        self.branch1 = Branch.objects.create(
            name="Ho Chi Minh Branch",
            code="CN001",
            province=self.province1,
            administrative_unit=self.admin_unit1,
        )
        self.branch2 = Branch.objects.create(
            name="Ha Noi Branch",
            code="CN002",
            province=self.province2,
            administrative_unit=self.admin_unit2,
        )

        # Create blocks
        self.block1 = Block.objects.create(
            name="Business Block 1",
            code="KH001",
            block_type="business",
            branch=self.branch1,
        )
        self.block2 = Block.objects.create(
            name="Business Block 2",
            code="KH002",
            block_type="business",
            branch=self.branch2,
        )

        # Create test WiFis
        self.wifi1 = AttendanceWifiDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=self.branch1,
            block=self.block1,
            bssid="00:11:22:33:44:55",
            state="in_use",
            notes="Main office WiFi network",
        )
        self.wifi2 = AttendanceWifiDevice.objects.create(
            name="Office WiFi Guest",
            code="WF002",
            branch=self.branch1,
            block=self.block1,
            bssid="AA:BB:CC:DD:EE:FF",
            state="in_use",
            notes="Guest WiFi network",
        )

    def test_list_wifis(self):
        """Test listing all WiFi attendance devices."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_retrieve_wifi(self):
        """Test retrieving a single attendance WiFi."""
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": self.wifi1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["code"], "WF001")
        self.assertEqual(data["name"], "Office WiFi Main")
        self.assertEqual(data["bssid"], "00:11:22:33:44:55")

    def test_create_wifi(self):
        """Test creating a new attendance WiFi with auto-generated code."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "New WiFi Network",
            "branch_id": self.branch1.id,
            "block_id": self.block1.id,
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
            "notes": "New WiFi for testing",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "New WiFi Network")
        self.assertTrue(data["code"].startswith("WF"))
        self.assertEqual(data["bssid"], "11:22:33:44:55:66")

    def test_create_wifi_without_branch_block(self):
        """Test creating WiFi without branch and block."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Standalone WiFi",
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
            "notes": "WiFi without branch/block",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "Standalone WiFi")
        self.assertIsNone(data["branch"])
        self.assertIsNone(data["block"])

    def test_create_wifi_missing_required_fields(self):
        """Test creating WiFi with missing required fields."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Incomplete WiFi",
            # Missing bssid
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_wifi_invalid_bssid_format(self):
        """Test creating WiFi with invalid BSSID format."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Invalid BSSID WiFi",
            "bssid": "invalid-bssid-format",
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_wifi_duplicate_bssid(self):
        """Test creating WiFi with duplicate BSSID."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Duplicate BSSID WiFi",
            "bssid": "00:11:22:33:44:55",  # Already used by wifi1
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_wifi_with_block_auto_sets_branch(self):
        """Test that creating WiFi with block automatically sets branch from block."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Auto Branch WiFi",
            "block_id": self.block1.id,
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "Auto Branch WiFi")
        # Branch should be auto-set from block
        self.assertEqual(data["branch"]["id"], self.block1.branch.id)
        self.assertEqual(data["block"]["id"], self.block1.id)

    def test_create_wifi_block_overrides_branch(self):
        """Test that when both block and branch provided, block's branch wins."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Override Branch WiFi",
            "branch_id": self.branch1.id,
            "block_id": self.block2.id,  # This block belongs to branch2
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        # Branch should be overridden by block's branch
        self.assertEqual(data["branch"]["id"], self.branch2.id)
        self.assertEqual(data["block"]["id"], self.block2.id)

    def test_update_wifi(self):
        """Test updating an attendance WiFi."""
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": self.wifi1.pk})
        payload = {
            "name": "Updated WiFi Name",
            "branch_id": self.branch1.id,
            "block_id": self.block1.id,
            "bssid": "00:11:22:33:44:55",
            "state": "not_in_use",
            "notes": "Updated notes",
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["name"], "Updated WiFi Name")
        self.assertEqual(data["state"], "not_in_use")
        self.assertEqual(data["notes"], "Updated notes")
        # Code should not change
        self.assertEqual(data["code"], "WF001")

    def test_partial_update_wifi(self):
        """Test partially updating an attendance WiFi."""
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": self.wifi1.pk})
        payload = {
            "state": "not_in_use",
            "notes": "Temporarily disabled",
        }
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["state"], "not_in_use")
        self.assertEqual(data["notes"], "Temporarily disabled")
        # Other fields should remain unchanged
        self.assertEqual(data["name"], "Office WiFi Main")

    def test_delete_wifi(self):
        """Test deleting an attendance WiFi."""
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": self.wifi1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify hard delete - object should not exist anymore
        with self.assertRaises(AttendanceWifiDevice.DoesNotExist):
            AttendanceWifiDevice.objects.get(pk=self.wifi1.pk)

    def test_filter_by_branch(self):
        """Test filtering WiFis by branch."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"branch": self.branch1.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)  # Both wifi1 and wifi2 belong to branch1

    def test_filter_by_block(self):
        """Test filtering WiFis by block."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"block": self.block1.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_filter_by_state(self):
        """Test filtering WiFis by state."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"state": "in_use"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_search_by_name(self):
        """Test searching WiFis by name."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"search": "Main"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Office WiFi Main")

    def test_search_by_bssid(self):
        """Test searching WiFis by BSSID."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"search": "00:11:22"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["bssid"], "00:11:22:33:44:55")

    def test_ordering_by_name(self):
        """Test ordering WiFis by name."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"ordering": "name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data[0]["name"], "Office WiFi Guest")
        self.assertEqual(data[1]["name"], "Office WiFi Main")

    def test_bssid_normalization(self):
        """Test that BSSID is normalized to uppercase with colons."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Normalized BSSID WiFi",
            "bssid": "aa-bb-cc-dd-ee-00",  # Using hyphens instead of colons
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        # Should be normalized to uppercase with colons
        self.assertEqual(data["bssid"], "AA:BB:CC:DD:EE:00")
