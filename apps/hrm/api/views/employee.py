from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeFilterSet
from apps.hrm.api.serializers import (
    EmployeeActiveActionSerializer,
    EmployeeAvatarSerializer,
    EmployeeExportXLSXSerializer,
    EmployeeMaternityLeaveActionSerializer,
    EmployeeReactiveActionSerializer,
    EmployeeResignedActionSerializer,
    EmployeeSerializer,
    EmployeeTransferActionSerializer,
)
from apps.hrm.callbacks import mark_employee_onboarding_email_sent
from apps.hrm.models import Employee
from apps.hrm.services.employee import create_state_change_event
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.mailtemplates.serializers import TemplatePreviewResponseSerializer
from apps.mailtemplates.view_mixins import EmailTemplateActionMixin
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all employees",
        description="Retrieve a paginated list of all employees with support for filtering by code, fullname, username, email, and organizational structure",
        tags=["5.1 Employee"],
    ),
    create=extend_schema(
        summary="Create a new employee",
        description="Create a new employee in the system. A User account will be automatically created based on the employee data.",
        tags=["5.1 Employee"],
    ),
    retrieve=extend_schema(
        summary="Get employee details",
        description="Retrieve detailed information about a specific employee including their organizational structure and user account",
        tags=["5.1 Employee"],
    ),
    update=extend_schema(
        summary="Update employee",
        description="Update employee information",
        tags=["5.1 Employee"],
    ),
    partial_update=extend_schema(
        summary="Partially update employee",
        description="Partially update employee information",
        tags=["5.1 Employee"],
    ),
    destroy=extend_schema(
        summary="Delete employee",
        description="Remove an employee from the system",
        tags=["5.1 Employee"],
    ),
    start_import=extend_schema(
        tags=["5.1 Employee"],
    ),
    import_template=extend_schema(
        tags=["5.1 Employee"],
    ),
    export=extend_schema(
        tags=["5.1 Employee"],
    ),
)
class EmployeeViewSet(
    AsyncImportProgressMixin,
    ExportXLSXMixin,
    EmailTemplateActionMixin,
    AuditLoggingMixin,
    BaseModelViewSet,
):
    """ViewSet for Employee model"""

    queryset = (
        Employee.objects.select_related("user", "branch", "block", "department", "position", "nationality", "avatar")
        .prefetch_related("bank_accounts", "bank_accounts__bank")
        .all()
    )
    serializer_class = EmployeeSerializer
    filterset_class = EmployeeFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "fullname", "username", "email", "attendance_code", "phone", "citizen_id"]
    ordering_fields = ["code", "fullname", "start_date", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Employee Management"
    permission_prefix = "employee"

    # Import handler path for AsyncImportProgressMixin
    import_row_handler = "apps.hrm.import_handlers.employee.import_handler"  # type: ignore[assignment]

    def get_serializer_class(self):
        if self.action == "active":
            return EmployeeActiveActionSerializer
        if self.action == "reactive":
            return EmployeeReactiveActionSerializer
        if self.action == "resigned":
            return EmployeeResignedActionSerializer
        if self.action == "maternity_leave":
            return EmployeeMaternityLeaveActionSerializer
        if self.action == "transfer":
            return EmployeeTransferActionSerializer
        if self.action == "update_avatar":
            return EmployeeAvatarSerializer
        return super().get_serializer_class()

    def get_template_action_data(self, instance: Employee, template_slug: str) -> Dict[str, Any]:
        """Get context data for employee email templates."""
        new_password_condition = self.action == "welcome_email_send"
        new_password = (
            get_random_string(length=8)
            if new_password_condition
            else "new password will be set when the email is sent"
        )
        if new_password_condition and instance.user:
            instance.user.set_password(new_password)
            instance.user.save()

        context = {
            "employee_fullname": instance.fullname,
            "employee_email": instance.email,
            "employee_username": instance.username,
            "employee_start_date": instance.start_date.isoformat() if instance.start_date else "",
            "employee_code": instance.code,
            "employee_department_name": instance.department.name,
            "new_password": new_password,
            "logo_image_url": settings.LOGO_URL,
            "branch_contact_infos": [],
        }

        department_leader = instance.department.leader
        if department_leader:
            context["leader_fullname"] = department_leader.fullname
            context["leader_department_name"] = department_leader.department.name
            context["leader_block_name"] = department_leader.block.name
            context["leader_branch_name"] = department_leader.branch.name

        branch_contact_infos = instance.branch.contact_infos.all()
        if branch_contact_infos:
            context["branch_contact_infos"] = [
                {
                    "business_line": info.business_line,
                    "name": info.name,
                    "phone_number": info.phone_number,
                    "email": info.email,
                }
                for info in branch_contact_infos
            ]

        return context

    @extend_schema(
        summary="Active an employee",
        request=EmployeeActiveActionSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1 Employee"],
    )
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def active(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(instance=employee, data=request.data, context={"employee": employee})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EmployeeSerializer(instance=employee).data)

    @extend_schema(
        summary="Reactive an employee",
        request=EmployeeReactiveActionSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1 Employee"],
    )
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reactive(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(instance=employee, data=request.data, context={"employee": employee})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EmployeeSerializer(instance=employee).data)

    @extend_schema(
        summary="Resign an employee",
        request=EmployeeResignedActionSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1 Employee"],
    )
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def resigned(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(instance=employee, data=request.data, context={"employee": employee})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EmployeeSerializer(instance=employee).data)

    @extend_schema(
        summary="Set employee to maternity leave",
        request=EmployeeMaternityLeaveActionSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1 Employee"],
    )
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def maternity_leave(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(instance=employee, data=request.data, context={"employee": employee})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EmployeeSerializer(instance=employee).data)

    @extend_schema(
        summary="Transfer employee to new department and position",
        request=EmployeeTransferActionSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1 Employee"],
    )
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transfer(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(instance=employee, data=request.data, context={"employee": employee})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EmployeeSerializer(instance=employee).data)

    @extend_schema(
        summary="Preview welcome email for employee",
        description="Generate a preview of the welcome/onboarding email for this employee using the welcome email template",
        tags=["5.1 Employee"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Optional data overrides for template variables",
                        "properties": {
                            "fullname": {
                                "type": "string",
                                "description": "Employee's full name (defaults to employee.fullname)",
                            },
                            "start_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Employment start date (defaults to employee.start_date)",
                            },
                            "position": {
                                "type": "string",
                                "description": "Job position (optional, defaults to employee.position.name)",
                            },
                            "department": {
                                "type": "string",
                                "description": "Department name (optional, defaults to employee.department.name)",
                            },
                        },
                    },
                },
            }
        },
        responses={
            200: TemplatePreviewResponseSerializer,
            400: {
                "description": "Invalid data or template rendering error",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": "Template rendering failed: 'fullname' is undefined",
                        }
                    }
                },
            },
            404: {
                "description": "Employee not found",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": "Not found.",
                        }
                    }
                },
            },
        },
    )
    @action(detail=True, methods=["post"], url_path="welcome_email/preview")
    def welcome_email_preview(self, request, pk=None):
        """Preview welcome email for this employee."""
        return self.preview_template_email("welcome", request, pk)

    @extend_schema(
        summary="Send welcome email to employee",
        description="Send welcome/onboarding email to this employee. After successful delivery, the employee's is_onboarding_email_sent field will be set to True",
        tags=["5.1 Employee"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Optional email subject (defaults to 'Welcome to MaiVietLand!')",
                    },
                },
            }
        },
        responses={
            202: {
                "description": "Email job created and queued for sending",
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "data": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "total_recipients": 1,
                                "detail": "Email send job enqueued",
                            },
                        }
                    }
                },
            },
            400: {
                "description": "Invalid request data or template validation error",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": {"email": ["Enter a valid email address."]},
                        }
                    }
                },
            },
            404: {
                "description": "Employee not found",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": "Not found.",
                        }
                    }
                },
            },
        },
    )
    @action(detail=True, methods=["post"], url_path="welcome_email/send")
    def welcome_email_send(self, request, pk=None):
        """Send welcome email to this employee."""
        return self.send_template_email(
            "welcome",
            request,
            pk,
            on_success_callback=mark_employee_onboarding_email_sent,
        )

    def get_recipients(self, request, instance):
        """Get recipients for employee email.

        For employees, returns a single recipient using the employee's email.
        """
        if not instance.email:
            from apps.mailtemplates.services import TemplateValidationError

            raise TemplateValidationError("Employee does not have an email address")

        return [
            {
                "email": instance.email,
                "data": self.get_template_action_data(
                    instance, template_slug=request.data.get("template_slug", "welcome")
                ),
            }
        ]

    @extend_schema(
        summary="Copy employee",
        description="Create a duplicate of an existing employee with unique identifiers for code, username, email, and citizen_id",
        tags=["5.1 Employee"],
        request=None,
        responses={200: EmployeeSerializer},
    )
    @action(detail=True, methods=["post"], url_path="copy")
    def copy(self, request, pk=None):
        """Create a duplicate of an existing employee"""
        original = self.get_object()
        copied = original.copy()

        # Create work history record for the copied employee
        create_state_change_event(
            employee=copied,
            old_status=None,
            new_status=copied.status,
            effective_date=copied.start_date,
            note=_("Employee created"),
        )

        serializer = self.get_serializer(copied)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update employee avatar",
        description=(
            "Upload and assign a new avatar to an employee. "
            "Requires a file token obtained from the presign endpoint. "
            "Only image files (PNG, JPEG, JPG, WEBP) are accepted."
        ),
        request=EmployeeAvatarSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1 Employee"],
    )
    @action(detail=True, methods=["post"], url_path="update-avatar")
    @transaction.atomic
    def update_avatar(self, request, *args, **kwargs):
        """
        Update employee avatar using file upload system.

        Workflow:
        1. Client obtains presigned URL: POST /api/files/presign/
           {
             "file_name": "avatar.jpg",
             "file_type": "image/jpeg",
             "purpose": "employee_avatar"
           }

        2. Client uploads file to S3 using presigned URL

        3. Client calls this endpoint with file token:
           POST /api/hrm/employees/{id}/update-avatar/
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
        employee = self.get_object()

        # Use EmployeeAvatarSerializer with the employee instance
        serializer = EmployeeAvatarSerializer(
            instance=employee,
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated employee data with new avatar
        return Response(EmployeeSerializer(instance=employee).data)

    def get_export_data(self, request):
        """Custom export data for Employee.

        Exports employee data with the following columns:
        - No., Employee Code, Full Name, Attendance Code, Status, Start Date
        - Resignation Reason, Resignation Date (from latest work history)
        - Contract Type, Position, Branch, Block, Department
        - Phone, Personal Email, Email
        - Bank Name, Bank Account Number (from default bank account)
        - Tax Code, Emergency Contact
        - Gender, Date of Birth, Place of Birth, Marital Status
        - Ethnicity, Religion, Nationality
        - Citizen ID, ID Issued Date, ID Issued Place
        - Residential Address, Permanent Address
        - Login Username, Notes
        """
        # Optimize queryset with prefetch_related for related objects
        queryset = self.filter_queryset(self.get_queryset()).prefetch_related(
            "work_histories",
            "bank_accounts",
            "bank_accounts__bank",
        )

        # Add index to each employee for export
        employees = list(queryset)
        for index, employee in enumerate(employees, start=1):
            employee._export_index = index

        # Serialize data
        serializer = EmployeeExportXLSXSerializer(employees, many=True)
        data = serializer.data

        return {
            "sheets": [
                {
                    "name": "Employees",
                    "headers": [
                        _("No."),
                        _("Employee Code"),
                        _("Full Name"),
                        _("Attendance Code"),
                        _("Status"),
                        _("Start Date"),
                        _("Resignation Reason"),
                        _("Resignation Date"),
                        _("Contract Type"),
                        _("Position"),
                        _("Branch"),
                        _("Block"),
                        _("Department"),
                        _("Phone"),
                        _("Personal Email"),
                        _("Email"),
                        _("Bank Name"),
                        _("Bank Account Number"),
                        _("Tax Code"),
                        _("Emergency Contact"),
                        _("Gender"),
                        _("Date of Birth"),
                        _("Place of Birth"),
                        _("Marital Status"),
                        _("Ethnicity"),
                        _("Religion"),
                        _("Nationality"),
                        _("Citizen ID"),
                        _("ID Issued Date"),
                        _("ID Issued Place"),
                        _("Residential Address"),
                        _("Permanent Address"),
                        _("Login Username"),
                        _("Notes"),
                    ],
                    "field_names": EmployeeExportXLSXSerializer.Meta.fields,
                    "data": data,
                }
            ]
        }
