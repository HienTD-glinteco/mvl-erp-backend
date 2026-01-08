import json

from django.core.cache import cache
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.serializers import MobileAppConfigSerializer
from apps.core.models import MobileAppConfig

_CACHE_KEY = "mobile_bootstrap_config_v1"


class MobileBootstrapConfigView(APIView):
    """Provide startup configuration for the mobile app (versioning, flags, links)."""

    serializer_class = MobileAppConfigSerializer

    @extend_schema(
        summary="Get mobile bootstrap configuration",
        tags=["0.0: Mobile Startup"],
        responses={200: MobileAppConfigSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "ios": {
                            "latest_version": "1.5.0",
                            "min_supported_version": "1.3.0",
                            "store_url": "https://apps.apple.com/app/idXXXXXXXX",
                        },
                        "android": {
                            "latest_version": "1.5.0",
                            "min_supported_version": "1.3.0",
                            "store_url": "https://play.google.com/store/apps/details?id=com.company.app",
                        },
                        "maintenance": {"enabled": False, "message": ""},
                        "feature_flags": {"new_dashboard": True, "enable_chat": False},
                        "links": {
                            "terms_url": "https://example.com/terms",
                            "privacy_url": "https://example.com/privacy",
                            "support_url": "https://example.com/support",
                        },
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        cached = cache.get(_CACHE_KEY)
        if isinstance(cached, dict):
            return Response(MobileAppConfigSerializer(cached).data, status=status.HTTP_200_OK)

        obj = MobileAppConfig.get_solo()
        try:
            flags = json.loads(obj.feature_flags or "{}")
        except json.JSONDecodeError:
            flags = {}

        data = {
            "ios": {
                "latest_version": obj.ios_latest_version,
                "min_supported_version": obj.ios_min_supported_version,
                "store_url": obj.ios_store_url,
            },
            "android": {
                "latest_version": obj.android_latest_version,
                "min_supported_version": obj.android_min_supported_version,
                "store_url": obj.android_store_url,
            },
            "maintenance": {
                "enabled": obj.maintenance_enabled,
                "message": obj.maintenance_message,
            },
            "feature_flags": {k: bool(v) for k, v in dict(flags or {}).items()},
            "links": {
                "terms_url": obj.links_terms_url,
                "privacy_url": obj.links_privacy_url,
                "support_url": obj.links_support_url,
            },
        }
        cache.set(_CACHE_KEY, data)
        return Response(MobileAppConfigSerializer(data).data, status=status.HTTP_200_OK)
