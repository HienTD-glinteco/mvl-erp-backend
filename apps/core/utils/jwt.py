from typing import Optional

try:
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )
except Exception:  # token_blacklist app might not be installed in some environments
    BlacklistedToken = None  # type: ignore
    OutstandingToken = None  # type: ignore


def revoke_user_outstanding_tokens(user, exclude_jti: Optional[str] = None) -> int:
    """
    Blacklist all existing outstanding refresh tokens for a user.

    - If exclude_jti is provided, skip that token (e.g., the one just issued).
    - Returns number of tokens blacklisted.
    """
    if not user or not OutstandingToken or not BlacklistedToken:
        return 0

    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        if exclude_jti and token.jti == exclude_jti:
            continue
        BlacklistedToken.objects.get_or_create(token=token)
        count += 1
    return count
