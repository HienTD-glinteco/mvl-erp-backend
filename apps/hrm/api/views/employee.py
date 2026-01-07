from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeDropdownFilterSet, EmployeeFilterSet
from apps.hrm.api.serializers import (
    EmployeeActiveActionSerializer,
    EmployeeAvatarSerializer,
    EmployeeChangeTypeActionSerializer,
    EmployeeDropdownSerializer,
    EmployeeExportXLSXSerializer,
    EmployeeMaternityLeaveActionSerializer,
    EmployeeReactiveActionSerializer,
    EmployeeResignedActionSerializer,
    EmployeeSerializer,
    EmployeeTransferActionSerializer,
)
from apps.hrm.callbacks import mark_employee_onboarding_email_sent
from apps.hrm.models import Employee
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.mailtemplates.serializers import TemplatePreviewResponseSerializer
from apps.mailtemplates.view_mixins import EmailTemplateActionMixin
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin
from libs.strings import generate_valid_password


@extend_schema_view(
    list=extend_schema(
        summary="List all employees",
        description="Retrieve a paginated list of all employees with support for filtering by code, fullname, username, email, and organizational structure",
        tags=["5.1: Employee"],
    ),
    create=extend_schema(
        summary="Create a new employee",
        description="Create a new employee in the system. A User account will be automatically created based on the employee data.",
        tags=["5.1: Employee"],
    ),
    retrieve=extend_schema(
        summary="Get employee details",
        description="Retrieve detailed information about a specific employee including their organizational structure and user account",
        tags=["5.1: Employee"],
    ),
    update=extend_schema(
        summary="Update employee",
        description="Update employee information",
        tags=["5.1: Employee"],
    ),
    partial_update=extend_schema(
        summary="Partially update employee",
        description="Partially update employee information",
        tags=["5.1: Employee"],
    ),
    destroy=extend_schema(
        summary="Delete employee",
        description="Remove an employee from the system",
        tags=["5.1: Employee"],
    ),
    start_import=extend_schema(
        tags=["5.1: Employee"],
    ),
    import_template=extend_schema(
        tags=["5.1: Employee"],
    ),
    export=extend_schema(
        tags=["5.1: Employee"],
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

    # Permission registration attributes
    module = _("HRM")
    submodule = _("Employee Management")
    permission_prefix = "employee"

    xlsx_template_name = "apps/hrm/fixtures/export_templates/employee_export_template.xlsx"
    PERMISSION_REGISTERED_ACTIONS = {
        "active": {
            "name_template": _("Activate employee"),
            "description_template": _("Activate employee"),
        },
        "reactive": {
            "name_template": _("Reactivate employee"),
            "description_template": _("Reactivate employee"),
        },
        "resigned": {
            "name_template": _("Resign employee"),
            "description_template": _("Resign employee"),
        },
        "maternity_leave": {
            "name_template": _("Set employee to Maternity Leave"),
            "description_template": _("Set employee to Maternity Leave"),
        },
        "transfer": {
            "name_template": _("Transfer employee"),
            "description_template": _("Transfer employee"),
        },
        "change_employee_type": {
            "name_template": _("Change employee Type"),
            "description_template": _("Change employee Type"),
        },
        "update_avatar": {
            "name_template": _("Update employee Avatar"),
            "description_template": _("Update employee Avatar"),
        },
        "welcome_email_preview": {
            "name_template": _("Preview welcome email for employee"),
            "description_template": _("Preview welcome email for employee"),
        },
        "welcome_email_send": {
            "name_template": _("Send welcome email to employee"),
            "description_template": _("Send welcome email to employee"),
        },
        "import_template": {
            "name_template": _("Download import template for {model_name}"),
            "description_template": _("Download import template for {model_name}"),
        },
        "start_import": {
            "name_template": _("Import {model_name} data"),
            "description_template": _("Import {model_name} data asynchronously"),
        },
        "dropdown": {
            "name_template": _("View employee in dropdown list"),
            "description_template": _("List employee for dropdown selection"),
        },
    }

    # Import handler path for AsyncImportProgressMixin
    import_row_handler = "apps.hrm.import_handlers.employee.import_handler"

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
        if self.action == "change_employee_type":
            return EmployeeChangeTypeActionSerializer
        if self.action == "update_avatar":
            return EmployeeAvatarSerializer
        return super().get_serializer_class()

    def get_template_action_data(self, instance: Employee, template_slug: str) -> Dict[str, Any]:
        """Get context data for employee email templates."""
        new_password_condition = self.action == "welcome_email_send"
        new_password = generate_valid_password() if new_password_condition else "********"
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
        summary="List employees for dropdown",
        description=(
            "Retrieve a non-paginated list of employees suitable for dropdowns. "
            "This action supports the same filters, search, and ordering parameters as the standard list endpoint."
        ),
        tags=["5.1: Employee"],
        responses={200: EmployeeDropdownSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Dropdown success",
                description="Matching employees returned for dropdown consumption",
                value={
                    "success": True,
                    "data": [
                        {
                            "id": 1,
                            "code": "MV00000001",
                            "fullname": "John Doe",
                            "attendance_code": "0000000000001",
                            "email": "john.doe@example.com",
                        }
                    ],
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Permission denied",
                description="User lacks permission to view dropdown data",
                value={"success": False, "data": None, "error": "permission denied"},
                response_only=True,
                status_codes=["403"],
            ),
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="dropdown",
        filterset_class=EmployeeDropdownFilterSet,
        serializer_class=EmployeeDropdownSerializer,
    )
    def dropdown(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = EmployeeDropdownSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Active an employee",
        request=EmployeeActiveActionSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1: Employee"],
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
        tags=["5.1: Employee"],
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
        tags=["5.1: Employee"],
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
        tags=["5.1: Employee"],
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
        tags=["5.1: Employee"],
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
        summary="Change employee type",
        request=EmployeeChangeTypeActionSerializer,
        responses={200: EmployeeSerializer},
        examples=[
            OpenApiExample(
                "Request example",
                value={"date": "2024-03-01", "employee_type": "INTERN", "note": "Role change"},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "fullname": "Active Employee",
                        "username": "active001",
                        "employee_type": "INTERN",
                        "branch": {"id": 1, "name": "Test Branch"},
                        "department": {"id": 1, "name": "Test Department"},
                        "position": {"id": 1, "name": "Manager"},
                        "start_date": "2019-01-01",
                        "status": "active",
                        "email": "active1@example.com",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Invalid date",
                value={"success": False, "error": {"date": ["Effective date cannot be in the future."]}},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Not found",
                value={"success": False, "error": "Not found."},
                response_only=True,
                status_codes=["404"],
            ),
        ],
        tags=["5.1: Employee"],
    )
    @action(detail=True, methods=["post"], url_path="change-employee-type")
    @transaction.atomic
    def change_employee_type(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(instance=employee, data=request.data, context={"employee": employee})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EmployeeSerializer(instance=employee).data)

    @extend_schema(
        summary="Preview welcome email for employee",
        description="Generate a preview of the welcome/onboarding email for this employee using the welcome email template",
        tags=["5.1: Employee"],
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
        parameters=[
            OpenApiParameter(
                name="use_real",
                description="Use real data instead of sample data. Default is 0. Accepted value: 0 or 1.",
                default="0",
                location=OpenApiParameter.QUERY,
                enum=["0", "1"],
            )
        ],
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
        tags=["5.1: Employee"],
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
        if not instance.personal_email:
            from apps.mailtemplates.services import TemplateValidationError

            raise TemplateValidationError("Employee does not have an email address")

        return [
            {
                "email": instance.personal_email,
                "data": self.get_template_action_data(
                    instance, template_slug=request.data.get("template_slug", "welcome")
                ),
            }
        ]

    @extend_schema(
        summary="Update employee avatar",
        description=(
            "Upload and assign a new avatar to an employee. "
            "Requires a file token obtained from the presign endpoint. "
            "Only image files (PNG, JPEG, JPG, WEBP) are accepted."
        ),
        request=EmployeeAvatarSerializer,
        responses={200: EmployeeSerializer},
        tags=["5.1: Employee"],
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

        # Get headers from serializer labels
        headers = [str(field.label) for field in serializer.child.fields.values()]
        field_names = list(serializer.child.fields.keys())

        return {
            "sheets": [
                {
                    "name": "Employees",
                    "headers": headers,
                    "field_names": field_names,
                    "data": data,
                }
            ]
        }
