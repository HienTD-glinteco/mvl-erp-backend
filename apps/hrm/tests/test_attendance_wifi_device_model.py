from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import AttendanceWifiDevice, Block, Branch

User = get_user_model()


class AttendanceWifiDeviceModelTest(TestCase):
    """Test cases for AttendanceWifiDevice model."""

    def setUp(self):
        """Set up test data."""
        # Create superuser for testing
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create province first
        self.province = Province.objects.create(name="Test Province", code="TP001")

        # Create administrative unit with parent province
        self.admin_unit = AdministrativeUnit.objects.create(
            name="Test Admin Unit",
            code="TAU001",
            parent_province=self.province,
            level="district",
        )

        # Update province with administrative unit
        self.province.administrative_unit = self.admin_unit
        self.province.save()

        # Create branch
        self.branch = Branch.objects.create(
            name="Test Branch",
            code="CN001",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        # Create block
        self.block = Block.objects.create(name="Test Block", code="KH001", block_type="business", branch=self.branch)

    def test_create_wifi_with_required_fields(self):
        """Test creating a WiFi device with all required fields."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Office WiFi",
            bssid="00:11:22:33:44:55",
        )

        self.assertIsNotNone(wifi.id)
        self.assertEqual(wifi.name, "Office WiFi")
        self.assertEqual(wifi.bssid, "00:11:22:33:44:55")
        self.assertTrue(wifi.code.startswith("WF"))
        self.assertEqual(wifi.state, AttendanceWifiDevice.State.IN_USE)

    def test_code_auto_generation(self):
        """Test that code is auto-generated with WF prefix."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Auto Code WiFi",
            bssid="AA:BB:CC:DD:EE:FF",
        )

        self.assertIsNotNone(wifi.code)
        self.assertTrue(wifi.code.startswith("WF"))

    def test_code_uniqueness(self):
        """Test that codes are unique."""
        wifi1 = AttendanceWifiDevice.objects.create(
            name="WiFi 1",
            bssid="00:11:22:33:44:55",
        )
        wifi2 = AttendanceWifiDevice.objects.create(
            name="WiFi 2",
            bssid="AA:BB:CC:DD:EE:FF",
        )

        self.assertNotEqual(wifi1.code, wifi2.code)

    def test_bssid_uniqueness(self):
        """Test that BSSID must be unique."""
        AttendanceWifiDevice.objects.create(
            name="WiFi 1",
            bssid="00:11:22:33:44:55",
        )

        with self.assertRaises(Exception):  # IntegrityError wrapped in different ways
            AttendanceWifiDevice.objects.create(
                name="WiFi 2",
                bssid="00:11:22:33:44:55",  # Duplicate BSSID
            )

    def test_default_state(self):
        """Test that default state is 'in_use'."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Default State WiFi",
            bssid="00:11:22:33:44:55",
        )

        self.assertEqual(wifi.state, AttendanceWifiDevice.State.IN_USE)

    def test_wifi_with_branch(self):
        """Test creating WiFi device with branch."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Branch WiFi",
            bssid="00:11:22:33:44:55",
            branch=self.branch,
        )

        self.assertEqual(wifi.branch, self.branch)

    def test_wifi_with_branch_and_block(self):
        """Test creating WiFi device with branch and block."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Block WiFi",
            bssid="00:11:22:33:44:55",
            branch=self.branch,
            block=self.block,
        )

        self.assertEqual(wifi.branch, self.branch)
        self.assertEqual(wifi.block, self.block)

    def test_block_auto_sets_branch(self):
        """Test that when block is provided, branch is automatically set from block."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Auto Branch WiFi",
            bssid="00:11:22:33:44:55",
            block=self.block,
        )

        self.assertEqual(wifi.branch, self.block.branch)
        self.assertEqual(wifi.block, self.block)

    def test_colored_state(self):
        """Test colored state property."""
        wifi = AttendanceWifiDevice.objects.create(
            name="Colored State WiFi",
            bssid="00:11:22:33:44:55",
            state=AttendanceWifiDevice.State.IN_USE,
        )

        colored_state = wifi.colored_state
        self.assertEqual(colored_state["value"], AttendanceWifiDevice.State.IN_USE)
        self.assertEqual(colored_state["variant"], "green")

        wifi.state = AttendanceWifiDevice.State.NOT_IN_USE
        wifi.save()

        colored_state = wifi.colored_state
        self.assertEqual(colored_state["value"], AttendanceWifiDevice.State.NOT_IN_USE)
        self.assertEqual(colored_state["variant"], "red")

    def test_str_representation(self):
        """Test string representation of WiFi device."""
        wifi = AttendanceWifiDevice.objects.create(
            name="String Test WiFi",
            bssid="00:11:22:33:44:55",
        )

        expected = f"{wifi.code} - {wifi.name}"
        self.assertEqual(str(wifi), expected)
