from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.core.utils.jwt import get_mobile_token_version, revoke_user_outstanding_tokens


class MobileTokenVersionCacheTests(TestCase):
    @patch("apps.core.utils.jwt.cache.get")
    @patch("apps.core.utils.jwt.apps.get_model")
    def test_get_mobile_token_version_cache_hit(self, mock_get_model, mock_cache_get):
        mock_cache_get.return_value = 9

        version = get_mobile_token_version(user_id="user-1")

        self.assertEqual(version, 9)
        mock_get_model.assert_not_called()

    @patch("apps.core.utils.jwt.cache.set")
    @patch("apps.core.utils.jwt.cache.get")
    @patch("apps.core.utils.jwt.apps.get_model")
    def test_get_mobile_token_version_cache_miss_sets_cache(self, mock_get_model, mock_cache_get, mock_cache_set):
        mock_cache_get.return_value = None

        mock_user_model = MagicMock()
        mock_only = MagicMock()
        mock_get = MagicMock()
        mock_get.mobile_token_version = 7
        mock_only.get.return_value = mock_get
        mock_user_model.objects.only.return_value = mock_only
        mock_get_model.return_value = mock_user_model

        version = get_mobile_token_version(user_id="user-1")

        self.assertEqual(version, 7)
        mock_cache_set.assert_called_once()


class RevokeOutstandingTokensTests(TestCase):
    @patch("apps.core.utils.jwt.BlacklistedToken")
    @patch("apps.core.utils.jwt.OutstandingToken")
    def test_revoke_user_outstanding_tokens_excludes_jti(self, mock_outstanding, mock_blacklisted):
        user = MagicMock()

        token1 = MagicMock(jti="jti-1")
        token2 = MagicMock(jti="jti-2")
        mock_outstanding.objects.filter.return_value = [token1, token2]
        mock_blacklisted.objects.get_or_create = MagicMock()

        count = revoke_user_outstanding_tokens(user, exclude_jti="jti-2")

        self.assertEqual(count, 1)
        mock_blacklisted.objects.get_or_create.assert_called_once_with(token=token1)
