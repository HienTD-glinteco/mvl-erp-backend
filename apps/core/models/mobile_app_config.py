from django.db import models

from libs.models.fields import SafeTextField


class MobileAppConfig(models.Model):
    """Singleton model to store mobile app startup configuration."""

    ios_latest_version = models.CharField(max_length=32, default="1.0.0")
    ios_min_supported_version = models.CharField(max_length=32, default="1.0.0")
    ios_store_url = models.URLField(blank=True, default="")

    android_latest_version = models.CharField(max_length=32, default="1.0.0")
    android_min_supported_version = models.CharField(max_length=32, default="1.0.0")
    android_store_url = models.URLField(blank=True, default="")

    maintenance_enabled = models.BooleanField(default=False)
    maintenance_message = SafeTextField(blank=True, default="")

    # JSON string of feature flags, e.g. {"new_dashboard": true}
    feature_flags = SafeTextField(blank=True, default="{}")

    links_terms_url = models.URLField(blank=True, default="")
    links_privacy_url = models.URLField(blank=True, default="")
    links_support_url = models.URLField(blank=True, default="")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_mobile_app_config"

    @classmethod
    def get_solo(cls) -> "MobileAppConfig":
        obj = cls.objects.order_by("id").first()
        if obj is None:
            obj = cls.objects.create()
        return obj
