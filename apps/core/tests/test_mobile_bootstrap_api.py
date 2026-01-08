import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import MobileAppConfig


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        content = json.loads(response.content.decode())
        return content.get("data", content)


class MobileBootstrapAPITest(TestCase, APITestMixin):
    """Tests for /api/mobile/app/bootstrap/ endpoint"""

    def setUp(self):
        self.client = APIClient()
        # Ensure cache clear before each test
        cache.delete("mobile_bootstrap_config_v1")

    def test_get_bootstrap_returns_db_config(self):
        """GET should return data from DB and be wrapped by middleware envelope."""
        # Arrange: create a custom config
        MobileAppConfig.objects.all().delete()
        MobileAppConfig.objects.create(
            ios_latest_version="1.5.0",
            ios_min_supported_version="1.3.0",
            ios_store_url="https://apps.apple.com/app/idTEST",
            android_latest_version="1.5.1",
            android_min_supported_version="1.3.1",
            android_store_url="https://play.google.com/store/apps/details?id=test",
            maintenance_enabled=True,
            maintenance_message="Scheduled maintenance",
            feature_flags='{"new_dashboard": true, "enable_chat": false}',
            links_terms_url="https://example.com/terms",
            links_privacy_url="https://example.com/privacy",
            links_support_url="https://example.com/support",
        )

        # Act
        url = reverse("mobile-core:app_bootstrap")
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["ios"]["latest_version"], "1.5.0")
        self.assertEqual(data["ios"]["min_supported_version"], "1.3.0")
        self.assertEqual(data["ios"]["store_url"], "https://apps.apple.com/app/idTEST")
        self.assertEqual(data["android"]["latest_version"], "1.5.1")
        self.assertEqual(data["android"]["min_supported_version"], "1.3.1")
        self.assertEqual(data["android"]["store_url"], "https://play.google.com/store/apps/details?id=test")
        self.assertTrue(data["maintenance"]["enabled"])
        self.assertEqual(data["maintenance"]["message"], "Scheduled maintenance")
        self.assertIn("new_dashboard", data["feature_flags"])  # parsed JSON flags
        self.assertIn("links", data)
        self.assertEqual(data["links"]["terms_url"], "https://example.com/terms")

    def test_bootstrap_uses_cache_until_invalidated(self):
        """Endpoint should use cached payload until cache is cleared."""
        # Arrange: initial config
        MobileAppConfig.objects.all().delete()
        MobileAppConfig.objects.create(
            ios_latest_version="1.0.0",
            ios_min_supported_version="1.0.0",
            android_latest_version="1.0.0",
            android_min_supported_version="1.0.0",
        )

        url = reverse("mobile-core:app_bootstrap")

        # First call populates cache
        resp1 = self.client.get(url)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        data1 = self.get_response_data(resp1)
        self.assertEqual(data1["ios"]["latest_version"], "1.0.0")

        # Update DB
        obj = MobileAppConfig.get_solo()
        obj.ios_latest_version = "1.1.0"
        obj.save(update_fields=["ios_latest_version"])  # cache still holds old version

        # Second call should still return cached old value
        resp2 = self.client.get(url)
        data2 = self.get_response_data(resp2)
        self.assertEqual(data2["ios"]["latest_version"], "1.0.0")

        # Clear cache and verify new value is returned
        cache.delete("mobile_bootstrap_config_v1")
        resp3 = self.client.get(url)
        data3 = self.get_response_data(resp3)
        self.assertEqual(data3["ios"]["latest_version"], "1.1.0")
