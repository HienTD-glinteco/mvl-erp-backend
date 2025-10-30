from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeFilterSet
from apps.hrm.api.serializers import EmployeeSerializer
from apps.hrm.callbacks import mark_employee_onboarding_email_sent
from apps.hrm.models import Employee
from apps.mailtemplates.view_mixins import EmailTemplateActionMixin
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all employees",
        description="Retrieve a paginated list of all employees with support for filtering by code, fullname, username, email, and organizational structure",
        tags=["Employee"],
    ),
    create=extend_schema(
        summary="Create a new employee",
        description="Create a new employee in the system. A User account will be automatically created based on the employee data.",
        tags=["Employee"],
    ),
    retrieve=extend_schema(
        summary="Get employee details",
        description="Retrieve detailed information about a specific employee including their organizational structure and user account",
        tags=["Employee"],
    ),
    update=extend_schema(
        summary="Update employee",
        description="Update employee information",
        tags=["Employee"],
    ),
    partial_update=extend_schema(
        summary="Partially update employee",
        description="Partially update employee information",
        tags=["Employee"],
    ),
    destroy=extend_schema(
        summary="Delete employee",
        description="Remove an employee from the system",
        tags=["Employee"],
    ),
)
class EmployeeViewSet(EmailTemplateActionMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Employee model"""

    queryset = Employee.objects.select_related(
        "user", "branch", "block", "department", "position", "contract_type", "nationality", "avatar"
    ).all()
    serializer_class = EmployeeSerializer
    filterset_class = EmployeeFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "fullname", "username", "email", "attendance_code", "phone"]
    ordering_fields = ["code", "fullname", "start_date", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Employee Management"
    permission_prefix = "employee"

    @extend_schema(
        summary="Preview welcome email for employee",
        description="Generate a preview of the welcome/onboarding email for this employee using the welcome email template",
        tags=["Employee"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Optional data overrides for template variables",
                        "properties": {
                            "fullname": {"type": "string", "description": "Employee's full name (defaults to employee.fullname)"},
                            "start_date": {"type": "string", "format": "date", "description": "Employment start date (defaults to employee.start_date)"},
                            "position": {"type": "string", "description": "Job position (optional, defaults to employee.position.name)"},
                            "department": {"type": "string", "description": "Department name (optional, defaults to employee.department.name)"},
                        },
                    },
                },
            }
        },
        responses={
            200: {
                "description": "Email preview generated successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "data": {
                                "html": "<html>...</html>",
                                "text": "Plain text version of email",
                            },
                        }
                    }
                },
            },
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
        tags=["Employee"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "description": "Optional list of recipients. If not provided, email is sent to employee.email",
                        "items": {
                            "type": "object",
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "fullname": {"type": "string"},
                                        "start_date": {"type": "string", "format": "date"},
                                        "position": {"type": "string"},
                                        "department": {"type": "string"},
                                    },
                                },
                            },
                            "required": ["email"],
                        },
                    },
                    "subject": {
                        "type": "string",
                        "description": "Optional email subject (defaults to 'Welcome to MaiVietLand!')",
                    },
                    "data": {
                        "type": "object",
                        "description": "Optional data overrides for the default recipient (employee)",
                        "properties": {
                            "fullname": {"type": "string"},
                            "start_date": {"type": "string", "format": "date"},
                            "position": {"type": "string"},
                            "department": {"type": "string"},
                        },
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
                                "detail": "Email job created and queued",
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
