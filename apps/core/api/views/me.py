from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.constants import (
    API_ME_DESCRIPTION,
    API_ME_PERMISSIONS_DESCRIPTION,
    API_ME_PERMISSIONS_SUMMARY,
    API_ME_SUMMARY,
    QUERY_PARAM_FORMAT,
    QUERY_PARAM_INCLUDE_PERMISSION_META,
    QUERY_PARAM_INCLUDE_ROLE,
)
from apps.core.api.serializers import MePermissionsSerializer, MeSerializer
from apps.core.models import Permission


class MeView(APIView):
    """API view to retrieve the authenticated user's profile"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary=API_ME_SUMMARY,
        description=API_ME_DESCRIPTION,
        tags=["1.2: User Profile"],
        responses={
            200: MeSerializer,
            401: OpenApiExample(
                "Unauthorized",
                value={"success": False, "error": "Authentication credentials were not provided."},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Success with employee",
                description="User profile with employee information",
                value={
                    "success": True,
                    "data": {
                        "id": 123,
                        "username": "john",
                        "email": "john@example.com",
                        "phone_number": "+84901234567",
                        "first_name": "John",
                        "last_name": "Doe",
                        "full_name": "Doe John",
                        "is_active": True,
                        "is_staff": False,
                        "date_joined": "2025-01-10T12:45:00Z",
                        "role": {
                            "id": 10,
                            "code": "VT_EDITOR",
                            "name": "Editor",
                            "description": "Role with document editing rights",
                            "is_system_role": False,
                        },
                        "employee": {
                            "id": 55,
                            "code": "MV-055",
                            "fullname": "John Doe",
                            "email": "john@example.com",
                            "phone": "0901234567",
                            "department": {"id": 5, "name": "Engineering", "code": "ENG"},
                            "position": {"id": 3, "name": "Software Engineer", "code": "SE"},
                            "status": "Active",
                            "start_date": "2023-06-01",
                        },
                        "links": {"self": "/api/me", "employee": "/api/hrm/employees/55"},
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Success without employee",
                description="User profile without employee information",
                value={
                    "success": True,
                    "data": {
                        "id": 124,
                        "username": "admin",
                        "email": "admin@example.com",
                        "phone_number": None,
                        "first_name": "Admin",
                        "last_name": "User",
                        "full_name": "User Admin",
                        "is_active": True,
                        "is_staff": True,
                        "date_joined": "2024-01-01T00:00:00Z",
                        "role": {
                            "id": 1,
                            "code": "VT001",
                            "name": "System Admin",
                            "description": "Full system access",
                            "is_system_role": True,
                        },
                        "employee": None,
                        "links": {"self": "/api/me"},
                    },
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        """Get authenticated user's profile"""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Optimize query by selecting related role and employee
        user = (
            User.objects.select_related("role", "employee__department", "employee__position")
            .filter(id=request.user.id)
            .first()
        )

        serializer = MeSerializer(user, context={"request": request})
        return Response(serializer.data)


class MePermissionsView(APIView):
    """API view to retrieve the authenticated user's permissions"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary=API_ME_PERMISSIONS_SUMMARY,
        description=API_ME_PERMISSIONS_DESCRIPTION,
        tags=["1.2: User Profile"],
        parameters=[
            OpenApiParameter(
                name="include_role",
                type=bool,
                location=OpenApiParameter.QUERY,
                description=QUERY_PARAM_INCLUDE_ROLE,
                default=True,
            ),
            OpenApiParameter(
                name="include_permission_meta",
                type=bool,
                location=OpenApiParameter.QUERY,
                description=QUERY_PARAM_INCLUDE_PERMISSION_META,
                default=True,
            ),
            OpenApiParameter(
                name="format",
                type=str,
                location=OpenApiParameter.QUERY,
                description=QUERY_PARAM_FORMAT,
                enum=["flat", "grouped"],
                default="flat",
            ),
        ],
        responses={
            200: MePermissionsSerializer,
            401: OpenApiExample(
                "Unauthorized",
                value={"success": False, "error": "Authentication credentials were not provided."},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "User with role permissions",
                description="Standard user with permissions from their assigned role",
                value={
                    "success": True,
                    "data": {
                        "user_id": 123,
                        "username": "john",
                        "role": {
                            "id": 10,
                            "code": "VT_EDITOR",
                            "name": "Editor",
                            "description": "Editor role",
                            "is_system_role": False,
                        },
                        "permissions": [
                            {
                                "id": 201,
                                "code": "document.create",
                                "description": "Create documents",
                                "created_at": "2025-01-10T12:00:00Z",
                            },
                            {
                                "id": 202,
                                "code": "document.update",
                                "description": "Update documents",
                                "created_at": "2025-01-10T12:01:00Z",
                            },
                        ],
                        "meta": {"count": 2, "generated_at": "2025-11-03T04:04:48Z"},
                        "links": {"self": "/api/me/permissions"},
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "User without role",
                description="User without an assigned role has no permissions",
                value={
                    "success": True,
                    "data": {
                        "user_id": 124,
                        "username": "newuser",
                        "role": None,
                        "permissions": [],
                        "meta": {"count": 0, "generated_at": "2025-11-03T04:04:48Z"},
                        "links": {"self": "/api/me/permissions"},
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Superuser with all permissions",
                description="Superuser has access to all permissions in the system",
                value={
                    "success": True,
                    "data": {
                        "user_id": 1,
                        "username": "superadmin",
                        "role": None,
                        "permissions": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "description": "Create users",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "user.update",
                                "description": "Update users",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                        ],
                        "meta": {"count": 2, "generated_at": "2025-11-03T04:04:48Z"},
                        "links": {"self": "/api/me/permissions"},
                    },
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        """Get authenticated user's permissions"""
        user = request.user

        # Parse query parameters
        include_role = request.query_params.get("include_role", "true").lower() == "true"
        include_permission_meta = request.query_params.get("include_permission_meta", "true").lower() == "true"
        format_type = request.query_params.get("format", "flat")

        # Get permissions based on user type
        if user.is_superuser:
            # Superuser gets all permissions
            permissions_qs = Permission.objects.all().order_by("code")
        elif user.role:
            # Regular user gets permissions from their role
            permissions_qs = user.role.permissions.all().order_by("code")
        else:
            # User without role has no permissions
            permissions_qs = Permission.objects.none()

        # Build response data
        response_data = {
            "user_id": user.id,
            "username": user.username,
            "is_superuser": user.is_superuser,
            "role": None,
            "permissions": [],
            "meta": {"count": permissions_qs.count(), "generated_at": timezone.now().isoformat()},
            "links": {"self": "/api/me/permissions"},
        }

        # Include role if requested
        if include_role and user.role:
            from apps.core.api.serializers import RoleSummarySerializer

            response_data["role"] = RoleSummarySerializer(user.role).data

        # Include permissions
        if include_permission_meta:
            from apps.core.api.serializers import PermissionDetailSerializer

            response_data["permissions"] = PermissionDetailSerializer(permissions_qs, many=True).data
        else:
            # Minimal permission info without metadata
            response_data["permissions"] = [{"id": p.id, "code": p.code} for p in permissions_qs]

        return Response(response_data, status=status.HTTP_200_OK)


class MeUpdateAvatarView(APIView):
    """API view to update the authenticated user's avatar"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update my avatar",
        description=(
            "Upload and assign a new avatar to the currently logged-in user's employee profile. "
            "Requires a file token obtained from the presign endpoint. "
            "Only image files (PNG, JPEG, JPG, WEBP) are accepted. "
            "The user must have an associated employee record."
        ),
        tags=["1.2: User Profile"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "object",
                        "properties": {
                            "avatar": {
                                "type": "string",
                                "description": "File token from presign response",
                            }
                        },
                        "required": ["avatar"],
                    }
                },
                "required": ["files"],
            }
        },
        responses={
            200: MeSerializer,
            400: OpenApiExample(
                "Bad Request",
                value={"success": False, "error": "Invalid file token or file type"},
                response_only=True,
            ),
            401: OpenApiExample(
                "Unauthorized",
                value={"success": False, "error": "Authentication credentials were not provided."},
                response_only=True,
            ),
            404: OpenApiExample(
                "Not Found",
                value={"success": False, "error": "User does not have an employee record"},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Success",
                description="Avatar updated successfully",
                value={
                    "success": True,
                    "data": {
                        "id": 123,
                        "username": "john",
                        "email": "john@example.com",
                        "employee": {
                            "id": 55,
                            "code": "MV-055",
                            "fullname": "John Doe",
                            "avatar": {
                                "id": 115,
                                "purpose": "employee_avatar",
                                "file_name": "profile_picture.jpg",
                                "view_url": "https://s3.amazonaws.com/...",
                                "download_url": "https://s3.amazonaws.com/...",
                            },
                        },
                    },
                },
                response_only=True,
            ),
        ],
    )
    @transaction.atomic
    def post(self, request):
        """
        Update authenticated user's employee avatar.

        Workflow:
        1. Client obtains presigned URL: POST /api/files/presign/
           {
             "file_name": "avatar.jpg",
             "file_type": "image/jpeg",
             "purpose": "employee_avatar"
           }

        2. Client uploads file to S3 using presigned URL

        3. Client calls this endpoint with file token:
           POST /api/me/update-avatar/
           {
             "files": {
               "avatar": "file-token-from-step-1"
             }
           }

        The serializer automatically:
        - Validates the file token
        - Confirms the file upload
        - Moves file from temp to permanent storage
        - Assigns the file to employee.avatar field
        """
        from django.http import Http404

        from apps.hrm.api.serializers import EmployeeAvatarSerializer

        user = request.user

        # Check if user has an employee record
        if not hasattr(user, "employee") or user.employee is None:
            raise Http404("User does not have an employee record")

        employee = user.employee

        # Use EmployeeAvatarSerializer with the employee instance
        serializer = EmployeeAvatarSerializer(
            instance=employee,
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Refresh user to get updated employee data
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = (
            User.objects.select_related(
                "role",
                "employee__department",
                "employee__position",
                "employee__avatar",
            )
            .filter(id=request.user.id)
            .first()
        )

        # Return updated user profile with new avatar
        return Response(MeSerializer(user, context={"request": request}).data)
