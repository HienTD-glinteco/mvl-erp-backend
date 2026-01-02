import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import AttendanceWifiDevice, Block, Branch


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestAttendanceWifiDeviceAPI(APITestMixin):
    """Test cases for AttendanceWifiDevice API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user):
        self.client = api_client
        self.user = user

    @pytest.fixture
    def wifis(self, branch, block):
        """Create test WiFis."""
        wifi1 = AttendanceWifiDevice.objects.create(
            name="Office WiFi Main",
            code="WF001",
            branch=branch,
            block=block,
            bssid="00:11:22:33:44:55",
            state=AttendanceWifiDevice.State.IN_USE,
            notes="Main office WiFi network",
        )
        wifi2 = AttendanceWifiDevice.objects.create(
            name="Office WiFi Guest",
            code="WF002",
            branch=branch,
            block=block,
            bssid="AA:BB:CC:DD:EE:FF",
            state=AttendanceWifiDevice.State.IN_USE,
            notes="Guest WiFi network",
        )
        return wifi1, wifi2

    def test_list_wifis(self, wifis):
        """Test listing all WiFi attendance devices."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_retrieve_wifi(self, wifis):
        """Test retrieving a single attendance WiFi."""
        wifi1, _ = wifis
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": wifi1.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["code"] == "WF001"
        assert data["name"] == "Office WiFi Main"
        assert data["bssid"] == "00:11:22:33:44:55"

    def test_create_wifi(self, branch, block):
        """Test creating a new attendance WiFi with auto-generated code."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "New WiFi Network",
            "branch_id": branch.id,
            "block_id": block.id,
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
            "notes": "New WiFi for testing",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert data["name"] == "New WiFi Network"
        assert data["code"].startswith("WF")
        assert data["bssid"] == "11:22:33:44:55:66"

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

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert data["name"] == "Standalone WiFi"
        assert data["branch"] is None
        assert data["block"] is None

    def test_create_wifi_missing_required_fields(self):
        """Test creating WiFi with missing required fields."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Incomplete WiFi",
            # Missing bssid
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_wifi_invalid_bssid_format(self):
        """Test creating WiFi with invalid BSSID format."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Invalid BSSID WiFi",
            "bssid": "invalid-bssid-format",
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_wifi_duplicate_bssid(self, wifis):
        """Test creating WiFi with duplicate BSSID."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Duplicate BSSID WiFi",
            "bssid": "00:11:22:33:44:55",  # Already used by wifi1
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_wifi_with_block_auto_sets_branch(self, block):
        """Test that creating WiFi with block automatically sets branch from block."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Auto Branch WiFi",
            "block_id": block.id,
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        assert data["name"] == "Auto Branch WiFi"
        # Branch should be auto-set from block
        assert data["branch"]["id"] == block.branch.id
        assert data["block"]["id"] == block.id

    def test_create_wifi_block_overrides_branch(self, branch, admin_unit, province):
        """Test that when both block and branch provided, block's branch wins."""
        branch2 = Branch.objects.create(
            name="Ha Noi Branch",
            code="CN002",
            province=province,
            administrative_unit=admin_unit,
        )
        block2 = Block.objects.create(
            name="Business Block 2",
            code="KH002",
            block_type=Block.BlockType.BUSINESS,
            branch=branch2,
        )

        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Override Branch WiFi",
            "branch_id": branch.id,
            "block_id": block2.id,  # This block belongs to branch2
            "bssid": "11:22:33:44:55:66",
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        # Branch should be overridden by block's branch
        assert data["branch"]["id"] == branch2.id
        assert data["block"]["id"] == block2.id

    def test_update_wifi(self, wifis, branch, block):
        """Test updating an attendance WiFi."""
        wifi1, _ = wifis
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": wifi1.pk})
        payload = {
            "name": "Updated WiFi Name",
            "branch_id": branch.id,
            "block_id": block.id,
            "bssid": "00:11:22:33:44:55",
            "state": "not_in_use",
            "notes": "Updated notes",
        }
        response = self.client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["name"] == "Updated WiFi Name"
        assert data["state"] == "not_in_use"
        assert data["notes"] == "Updated notes"
        # Code should not change
        assert data["code"] == "WF001"

    def test_partial_update_wifi(self, wifis):
        """Test partially updating an attendance WiFi."""
        wifi1, _ = wifis
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": wifi1.pk})
        payload = {
            "state": "not_in_use",
            "notes": "Temporarily disabled",
        }
        response = self.client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["state"] == "not_in_use"
        assert data["notes"] == "Temporarily disabled"
        # Other fields should remain unchanged
        assert data["name"] == "Office WiFi Main"

    def test_delete_wifi(self, wifis):
        """Test deleting an attendance WiFi."""
        wifi1, _ = wifis
        url = reverse("hrm:attendance-wifi-device-detail", kwargs={"pk": wifi1.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify hard delete - object should not exist anymore
        assert not AttendanceWifiDevice.objects.filter(pk=wifi1.pk).exists()

    def test_filter_by_branch(self, wifis, branch):
        """Test filtering WiFis by branch."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"branch": branch.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2  # Both wifi1 and wifi2 belong to branch

    def test_filter_by_block(self, wifis, block):
        """Test filtering WiFis by block."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"block": block.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_filter_by_state(self, wifis):
        """Test filtering WiFis by state."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"state": "in_use"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_search_by_name(self, wifis):
        """Test searching WiFis by name."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"search": "Main"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Office WiFi Main"

    def test_search_by_bssid(self, wifis):
        """Test searching WiFis by BSSID."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"search": "00:11:22"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["bssid"] == "00:11:22:33:44:55"

    def test_ordering_by_name(self, wifis):
        """Test ordering WiFis by name."""
        url = reverse("hrm:attendance-wifi-device-list")
        response = self.client.get(url, {"ordering": "name"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        # Guest comes before Main alphabetically
        assert data[0]["name"] == "Office WiFi Guest"
        assert data[1]["name"] == "Office WiFi Main"

    def test_bssid_normalization(self):
        """Test that BSSID is normalized to uppercase with colons."""
        url = reverse("hrm:attendance-wifi-device-list")
        payload = {
            "name": "Normalized BSSID WiFi",
            "bssid": "aa-bb-cc-dd-ee-00",  # Using hyphens instead of colons
            "state": "in_use",
        }
        response = self.client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = self.get_response_data(response)
        # Should be normalized to uppercase with colons
        assert data["bssid"] == "AA:BB:CC:DD:EE:00"
