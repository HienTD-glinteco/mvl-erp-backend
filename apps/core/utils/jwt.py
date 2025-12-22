from typing import Optional

from django.apps import apps
from django.core.cache import cache

try:
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )
except Exception:  # token_blacklist app might not be installed in some environments
    BlacklistedToken = None  # type: ignore
    OutstandingToken = None  # type: ignore


MOBILE_TOKEN_VERSION_CACHE_KEY = "mvl:mobile_token_version:{user_id}"
MOBILE_TOKEN_VERSION_CACHE_TTL_SECONDS = 300


def get_mobile_token_version(user_id: str) -> int:
    key = MOBILE_TOKEN_VERSION_CACHE_KEY.format(user_id=user_id)
    cached = cache.get(key)
    if cached is not None:
        return int(cached)

    user_model = apps.get_model("core", "User")
    version = user_model.objects.only("mobile_token_version").get(id=user_id).mobile_token_version
    cache.set(key, int(version), timeout=MOBILE_TOKEN_VERSION_CACHE_TTL_SECONDS)
    return int(version)


def set_mobile_token_version(user_id: str, version: int) -> None:
    key = MOBILE_TOKEN_VERSION_CACHE_KEY.format(user_id=user_id)
    cache.set(key, int(version), timeout=MOBILE_TOKEN_VERSION_CACHE_TTL_SECONDS)


def bump_user_mobile_token_version(user) -> int:
    user.mobile_token_version += 1
    user.save(update_fields=["mobile_token_version"])
    set_mobile_token_version(user_id=str(user.id), version=user.mobile_token_version)
    return int(user.mobile_token_version)


def revoke_user_outstanding_tokens(user, exclude_jti: Optional[str] = None) -> int:
    """
    Blacklist all existing outstanding refresh tokens for a user.

    - If exclude_jti is provided, skip that token (e.g., the one just issued).
    - Returns number of tokens blacklisted.
    """
    if OutstandingToken is None or BlacklistedToken is None:
        return 0

    if not user:
        return 0

    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        if exclude_jti and token.jti == exclude_jti:
            continue
        BlacklistedToken.objects.get_or_create(token=token)
        count += 1
    return count
