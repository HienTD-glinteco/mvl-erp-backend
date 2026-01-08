from rest_framework import serializers


class StoreInfoSerializer(serializers.Serializer):
    latest_version = serializers.CharField(help_text="Latest app version available in store")
    min_supported_version = serializers.CharField(
        help_text="Minimum version that is allowed to run (force update below this)"
    )
    store_url = serializers.CharField(allow_blank=True, help_text="App store URL")


class MaintenanceSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(help_text="Whether the app is under maintenance mode")
    message = serializers.CharField(allow_blank=True, help_text="Maintenance message to display")


class LinksSerializer(serializers.Serializer):
    terms_url = serializers.CharField(allow_blank=True)
    privacy_url = serializers.CharField(allow_blank=True)
    support_url = serializers.CharField(allow_blank=True)


class MobileAppConfigSerializer(serializers.Serializer):
    ios = StoreInfoSerializer()
    android = StoreInfoSerializer()
    maintenance = MaintenanceSerializer()
    feature_flags = serializers.DictField(child=serializers.BooleanField(), required=False)
    links = LinksSerializer(required=False)
