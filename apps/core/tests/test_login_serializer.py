import pytest
from django.utils import timezone

from apps.core.api.serializers.auth.login import LoginSerializer, MobileDeviceConflict
from apps.core.models import User, UserDevice


@pytest.mark.django_db
class TestLoginSerializerMobile:
    @pytest.fixture
    def user(self):
        u = User.objects.create_user(username="u1", email="u1@example.com", password="pass1234")
        return u

    def test_mobile_requires_device_id(self, user):
        ser = LoginSerializer(
            data={"username": user.username, "password": "pass1234"}, context={"client": UserDevice.Client.MOBILE}
        )
        assert ser.is_valid() is False
        assert "device_id" in ser.errors

    def test_device_taken_by_other_user(self, user):
        other = User.objects.create_user(username="u2", email="u2@example.com", password="pass1234")
        UserDevice.objects.create(
            user=other,
            client=UserDevice.Client.MOBILE,
            device_id="dev123",
            platform=UserDevice.Platform.IOS,
            push_token="t",
            last_seen_at=timezone.now(),
            state=UserDevice.State.ACTIVE,
        )
        ser = LoginSerializer(
            data={
                "username": user.username,
                "password": "pass1234",
                "device_id": "dev123",
                "platform": UserDevice.Platform.IOS,
            },
            context={"client": UserDevice.Client.MOBILE},
        )
        assert ser.is_valid() is False
        assert "device_id" in ser.errors

    def test_mobile_device_conflict_when_existing_active_different_device(self, user):
        UserDevice.objects.create(
            user=user,
            client=UserDevice.Client.MOBILE,
            device_id="devA",
            platform=UserDevice.Platform.ANDROID,
            push_token="p",
            last_seen_at=timezone.now(),
            state=UserDevice.State.ACTIVE,
        )
        ser = LoginSerializer(
            data={
                "username": user.username,
                "password": "pass1234",
                "device_id": "devB",
                "platform": UserDevice.Platform.ANDROID,
            },
            context={"client": UserDevice.Client.MOBILE},
        )
        with pytest.raises(MobileDeviceConflict):
            ser.is_valid(raise_exception=True)

    def test_get_tokens_creates_device_when_none(self, user):
        ser = LoginSerializer(
            data={
                "username": user.username,
                "password": "pass1234",
                "device_id": "devX",
                "platform": UserDevice.Platform.IOS,
            },
            context={"client": UserDevice.Client.MOBILE},
        )
        assert ser.is_valid(), ser.errors
        tokens = ser.get_tokens(user, client=UserDevice.Client.MOBILE)
        assert "access" in tokens and "refresh" in tokens
        dev = UserDevice.objects.filter(user=user, client=UserDevice.Client.MOBILE, device_id="devX").first()
        assert dev is not None
        assert dev.platform == UserDevice.Platform.IOS
        assert dev.state == UserDevice.State.ACTIVE

    def test_get_tokens_updates_existing_device(self, user):
        UserDevice.objects.create(
            user=user,
            client=UserDevice.Client.MOBILE,
            device_id="devX",
            platform=UserDevice.Platform.ANDROID,
            push_token="p1",
            last_seen_at=timezone.now(),
            state=UserDevice.State.ACTIVE,
        )
        ser = LoginSerializer(
            data={
                "username": user.username,
                "password": "pass1234",
                "device_id": "devX",
                "platform": UserDevice.Platform.IOS,
                "push_token": "p2",
            },
            context={"client": UserDevice.Client.MOBILE},
        )
        assert ser.is_valid(), ser.errors
        _ = ser.get_tokens(user, client=UserDevice.Client.MOBILE)
        dev = UserDevice.objects.get(user=user, client=UserDevice.Client.MOBILE, device_id="devX")
        assert dev.platform == UserDevice.Platform.IOS
        assert dev.push_token == "p2"
        # token claims include 'client' and 'device_id'
        tokens = ser.get_tokens(user, client=UserDevice.Client.MOBILE)
        assert isinstance(tokens["access"], str)


@pytest.mark.django_db
class TestLoginSerializerWeb:
    def test_web_allows_blank_device_id_and_updates_web_device(self):
        user = User.objects.create_user(username="webu", email="webu@example.com", password="pass1234")
        ser = LoginSerializer(
            data={"username": user.username, "password": "pass1234", "device_id": ""},
            context={"client": UserDevice.Client.WEB},
        )
        assert ser.is_valid(), ser.errors
        tokens = ser.get_tokens(user, client=UserDevice.Client.WEB)
        assert "access" in tokens and "refresh" in tokens
        dev = UserDevice.objects.get(user=user, client=UserDevice.Client.WEB)
        assert dev.platform == UserDevice.Platform.WEB
        assert dev.state == UserDevice.State.ACTIVE
