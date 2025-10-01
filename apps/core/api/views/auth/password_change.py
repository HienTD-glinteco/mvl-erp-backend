import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.core.api.serializers.auth.password_change import PasswordChangeSerializer

logger = logging.getLogger(__name__)


class PasswordChangeRateThrottle(UserRateThrottle):
    scope = "password_change"
    rate = "3/hour"


class PasswordChangeView(APIView):
    """
    API endpoint for changing password when user knows their current password.

    This is different from password reset (forgot password) flow.
    User must be authenticated and provide their current password.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeRateThrottle]
    serializer_class = PasswordChangeSerializer

    @extend_schema(
        summary="Đổi mật khẩu (khi biết mật khẩu hiện tại)",
        description="Đổi mật khẩu khi người dùng đã đăng nhập và biết mật khẩu hiện tại",
        responses={
            200: OpenApiResponse(description="Mật khẩu đã được thay đổi thành công"),
            400: OpenApiResponse(description="Thông tin không hợp lệ hoặc mật khẩu hiện tại sai"),
            401: OpenApiResponse(description="Chưa đăng nhập"),
            429: OpenApiResponse(description="Quá nhiều yêu cầu thay đổi mật khẩu"),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.save()

            logger.info(f"Password successfully changed for user {user}")
            return Response(
                {"message": "Mật khẩu đã được thay đổi thành công. Tất cả phiên đăng nhập khác đã bị đăng xuất."},
                status=status.HTTP_200_OK,
            )

        logger.warning(f"Invalid password change attempt for user {request.user}: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
