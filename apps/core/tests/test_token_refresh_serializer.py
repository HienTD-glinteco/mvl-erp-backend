import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


@pytest.mark.django_db
def test_token_refresh_preserves_client_device_and_tv(api_client, superuser):
    """Ensure ClientAwareTokenRefreshSerializer preserves client/device_id and sets tv to current version."""
    # Prepare user mobile token version
    superuser.mobile_token_version = 5
    superuser.save(update_fields=["mobile_token_version"])

    # Create a refresh token and add custom claims
    refresh = RefreshToken.for_user(superuser)
    refresh["client"] = "mobile"
    refresh["device_id"] = "device123"
    # an older tv value -- serializer should overwrite with current
    refresh["tv"] = 1

    url = reverse("core:token_refresh")
    response = api_client.post(url, {"refresh": str(refresh)}, format="json")

    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload and payload["data"] is not None

    data = payload["data"]
    assert "access" in data

    access_token = AccessToken(data["access"])
    assert access_token["client"] == "mobile"
    assert access_token["device_id"] == "device123"
    # tv should equal current superuser.mobile_token_version
    assert int(access_token["tv"]) == superuser.mobile_token_version
