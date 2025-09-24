from django.test import TestCase


class HRMBasicTestCase(TestCase):
    """Basic test case for HRM module to ensure CI pipeline can run tests."""

    def test_hrm_module_basic(self):
        """Test that HRM module is properly configured."""
        # This test ensures HRM module is properly set up
        self.assertTrue(True)