from django.test import TestCase

from apps.hrm.models import WifiAttendanceDevice


class WifiAttendanceDeviceAutoCodeTest(TestCase):
    """Test auto-code generation for WifiAttendanceDevice model."""

    def test_code_generation_starts_with_prefix(self):
        """Test that auto-generated code starts with WF prefix."""
        wifi = WifiAttendanceDevice.objects.create(
            name="Test WiFi",
            bssid="00:11:22:33:44:55",
        )

        self.assertTrue(wifi.code.startswith("WF"))

    def test_sequential_code_generation(self):
        """Test that codes are generated sequentially."""
        wifi1 = WifiAttendanceDevice.objects.create(
            name="WiFi 1",
            bssid="00:11:22:33:44:55",
        )
        wifi2 = WifiAttendanceDevice.objects.create(
            name="WiFi 2",
            bssid="AA:BB:CC:DD:EE:FF",
        )

        # Extract numeric parts
        code1_num = int(wifi1.code.replace("WF", ""))
        code2_num = int(wifi2.code.replace("WF", ""))

        # Second code should be greater than first
        self.assertGreater(code2_num, code1_num)

    def test_code_is_unique(self):
        """Test that each WiFi gets a unique code."""
        codes = set()
        for i in range(10):
            wifi = WifiAttendanceDevice.objects.create(
                name=f"WiFi {i}",
                bssid=f"{i:02d}:11:22:33:44:55",
            )
            codes.add(wifi.code)

        # All codes should be unique
        self.assertEqual(len(codes), 10)

    def test_code_not_null(self):
        """Test that code is never null."""
        wifi = WifiAttendanceDevice.objects.create(
            name="Test WiFi",
            bssid="00:11:22:33:44:55",
        )

        self.assertIsNotNone(wifi.code)
        self.assertNotEqual(wifi.code, "")

    def test_code_readonly_after_creation(self):
        """Test that code can be manually changed if needed (not readonly)."""
        wifi = WifiAttendanceDevice.objects.create(
            name="Test WiFi",
            bssid="00:11:22:33:44:55",
        )

        original_code = wifi.code

        # Try to change the code - AutoCodeMixin allows manual code changes
        wifi.code = "CUSTOM_CODE"
        wifi.save()

        # Reload from database
        wifi.refresh_from_db()

        # Code can be changed manually (AutoCodeMixin allows this)
        self.assertEqual(wifi.code, "CUSTOM_CODE")
        self.assertNotEqual(wifi.code, original_code)
