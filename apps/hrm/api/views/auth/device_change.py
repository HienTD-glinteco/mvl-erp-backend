import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.hrm.api.serializers.auth.device_change import (
    DeviceChangeRequestSerializer,
    DeviceChangeVerifyOTPSerializer,
)

logger = logging.getLogger(__name__)


class DeviceChangeRateThrottle(AnonRateThrottle):
    scope = "device_change"
    rate = "3/minute"  # TODO: Adjust rate limit for testing purposes


class DeviceChangeRequestView(APIView):
    """API endpoint for initiating device change request.

    Validates username/password, checks if device_id is different from registered device,
    generates OTP and sends to user's email.
    """

    permission_classes = [AllowAny]
    throttle_classes = [DeviceChangeRateThrottle]
    serializer_class = DeviceChangeRequestSerializer

    @extend_schema(
        summary="Request device change",
        description="Initiate device change request with username/password. OTP will be sent to registered email.",
        responses={
            202: OpenApiResponse(
                description="OTP sent successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "success": True,
                            "data": {
                                "message": "OTP code has been sent to your email. Please verify to complete the device change request.",
                                "request_id": 1,
                                "expires_in_seconds": 300,
                            },
                            "error": None,
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Invalid credentials or device already registered",
                examples=[
                    OpenApiExample(
                        "Device already registered",
                        value={
                            "success": False,
                            "data": None,
                            "error": {
                                "non_field_errors": [
                                    "This device is already registered for your account. No need to create a device change request."
                                ]
                            },
                        },
                        status_codes=["400"],
                    )
                ],
            ),
            429: OpenApiResponse(description="Too many requests"),
        },
        tags=["9.2.11: Device Change Proposals"],
        examples=[
            OpenApiExample(
                "Request device change",
                value={
                    "username": "john.doe",
                    "password": "SecurePassword123!",
                    "device_id": "fcm_token_or_device_uuid",
                    "platform": "android",
                    "notes": "Switching to new phone",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = DeviceChangeRequestSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            logger.warning(f"Invalid device change request: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        device_request = serializer.create_request()
        response_data = {
            "message": _("OTP code has been sent to your email. Please verify to complete the device change request."),
            "request_id": device_request.id,
            "expires_in_seconds": 300,
        }
        return Response(response_data, status=status.HTTP_202_ACCEPTED)


class DeviceChangeVerifyOTPView(APIView):
    """API endpoint for verifying OTP and creating device change proposal.

    Verifies OTP code and creates a Proposal with type DEVICE_CHANGE in PENDING status.
    """

    permission_classes = [AllowAny]
    throttle_classes = [DeviceChangeRateThrottle]
    serializer_class = DeviceChangeVerifyOTPSerializer

    @extend_schema(
        summary="Verify OTP for device change",
        description="Verify OTP code and create device change proposal for admin approval",
        responses={
            201: OpenApiResponse(
                description="Proposal created successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "success": True,
                            "data": {
                                "message": "Device change request verified. Your request is pending approval from admin.",
                                "proposal_id": 9876,
                            },
                            "error": None,
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid or expired OTP"),
            410: OpenApiResponse(description="Request expired"),
            429: OpenApiResponse(description="Too many attempts"),
        },
        tags=["9.2.11: Device Change Proposals"],
        examples=[
            OpenApiExample(
                "Verify OTP",
                value={"request_id": 1, "otp": "123456"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = DeviceChangeVerifyOTPSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            logger.warning(f"Invalid OTP verification for device change: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        proposal = serializer.create_proposal()
        response_data = {
            "message": _("Device change request verified. Your request is pending approval from admin."),
            "proposal_id": proposal.id,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
