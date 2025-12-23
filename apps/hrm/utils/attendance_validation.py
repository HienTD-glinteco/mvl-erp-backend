from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from apps.core.models.device import UserDevice


def validate_attendance_device(request):
    """
    Validates that the request comes from a valid mobile device using the device_id in the token.

    Args:
        request: The DRF request object.

    Raises:
        ValidationError: If device_id is missing, user device is not found, or platform is not mobile.
    """
    # 1. Extract device_id from jwt token
    if not request.auth or not hasattr(request.auth, "get"):
        # If auth is None or doesn't behave like a dict/token, we can't extract device_id.
        # This might happen if using SessionAuthentication or BasicAuthentication.
        # Assuming JWT is required as per requirements.
        raise ValidationError(_("Authentication token with device_id is required."))

    device_id = request.auth.get("device_id")

    if not device_id:
        raise ValidationError(_("Token does not contain device_id."))

    # 2. Get active user_device
    user_device = UserDevice.objects.filter(
        user=request.user,
        # client=UserDevice.Client.MOBILE,
        state=UserDevice.State.ACTIVE,
        device_id=device_id,
    ).first()

    if not user_device:
        raise ValidationError(_("User device not found."))

    # 3. Validate client
    if user_device.client != UserDevice.Client.MOBILE:
        raise ValidationError(_("Attendance is only allowed from mobile devices."))

    return user_device
