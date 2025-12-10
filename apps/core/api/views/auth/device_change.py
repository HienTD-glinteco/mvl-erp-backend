import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.audit_logging import LogAction, log_audit_event
from apps.core.api.serializers.auth import DeviceChangeRequestSerializer, DeviceChangeVerifyOTPSerializer
from apps.core.models import DeviceChangeRequest
from apps.core.tasks import send_otp_email_task
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal

logger = logging.getLogger(__name__)


class DeviceChangeRateThrottle(AnonRateThrottle):
    scope = "device_change"
    rate = "3/hour"  # Allow 3 device change requests per hour


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
        tags=["9.2.11: Device Change Proposals - For Mobile"],
        examples=[
            OpenApiExample(
                "Request device change",
                value={
                    "username": "ng.trang",
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
        serializer = DeviceChangeRequestSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(f"Invalid device change request: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        device_id = serializer.validated_data["device_id"]
        platform = serializer.validated_data.get("platform", "")
        notes = serializer.validated_data.get("notes", "")

        # Generate OTP
        otp_code = user.generate_otp()
        otp_expires_at = timezone.now() + timedelta(seconds=300)  # 5 minutes

        # Get employee if exists
        employee = None
        try:
            employee = user.employee
        except Exception:  # nosec B110
            pass

        # Create device change request
        with transaction.atomic():
            device_request = DeviceChangeRequest.objects.create(
                user=user,
                employee=employee,
                new_device_id=device_id,
                new_platform=platform,
                notes=notes,
                otp_code=otp_code,
                otp_sent_at=timezone.now(),
                otp_expires_at=otp_expires_at,
                status=DeviceChangeRequest.Status.OTP_SENT,
            )

            # Log audit event
            log_audit_event(
                action=LogAction.ADD,
                modified_object=device_request,
                user=user,
                request=request,
                change_message=f"Device change request created for device_id: {device_id}",
            )

        # Send OTP email asynchronously
        try:
            send_otp_email_task.delay(user.id, otp_code)
            logger.info(f"OTP sent for device change request {device_request.id} for user {user.username}")
        except Exception as e:
            logger.error(f"Failed to queue OTP email for device change request: {e}")

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
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid or expired OTP"),
            410: OpenApiResponse(description="Request expired"),
            429: OpenApiResponse(description="Too many attempts"),
        },
        tags=["9.2.11: Device Change Proposals - For Mobile"],
        examples=[
            OpenApiExample(
                "Verify OTP",
                value={"request_id": 1, "otp": "123456"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = DeviceChangeVerifyOTPSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(f"Invalid OTP verification for device change: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        device_request = serializer.validated_data["device_request"]
        user = device_request.user
        employee = device_request.employee

        # Ensure user has employee mapping (required for creating Proposal)
        if not employee:
            try:
                employee = user.employee
            except Exception:
                logger.error(f"User {user.username} has no employee mapping, cannot create device change proposal")
                return Response(
                    {
                        "non_field_errors": [
                            _(
                                "Your account is not linked to an employee record. "
                                "Please contact HR to set up your employee profile before requesting device change."
                            )
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get old device_id if exists
        old_device_id = None
        if hasattr(user, "device") and user.device is not None:
            old_device_id = user.device.device_id

        # Create Proposal with type DEVICE_CHANGE
        with transaction.atomic():
            # Mark device request as verified
            device_request.mark_verified()

            # Create proposal
            proposal = Proposal.objects.create(
                proposal_type=ProposalType.DEVICE_CHANGE,
                proposal_status=ProposalStatus.PENDING,
                created_by=employee,
                device_change_new_device_id=device_request.new_device_id,
                device_change_new_platform=device_request.new_platform,
                device_change_old_device_id=old_device_id,
                device_change_contact_info=device_request.notes,
                note=device_request.notes,
            )

            # Log audit event
            log_audit_event(
                action=LogAction.ADD,
                modified_object=proposal,
                user=user,
                request=request,
                change_message=f"Device change proposal created from request {device_request.id}",
            )

            logger.info(
                f"Device change proposal {proposal.id} created for user {user.username} "
                f"with device_id: {device_request.new_device_id}"
            )

        # TODO: Send notification to admins/approvers

        response_data = {
            "message": _("Device change request verified. Your request is pending approval from admin."),
            "proposal_id": proposal.id,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
