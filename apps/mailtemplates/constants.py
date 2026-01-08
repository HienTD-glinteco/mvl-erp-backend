"""Mail template constants and registry.

This module defines the template registry and action-to-template mapping.
All templates must be registered here with their metadata.
"""

from typing import Any, TypedDict

from django.conf import settings
from django.utils.translation import gettext_lazy as _


class TemplateVariable(TypedDict):
    """Variable descriptor for template variables."""

    name: str
    type: str
    required: bool
    description: str


class TemplateMetadata(TypedDict):
    """Template metadata structure."""

    slug: str
    filename: str
    title: str
    description: str
    purpose: str
    default_subject: str
    variables: list[TemplateVariable]
    sample_data: dict[str, Any]
    variables_schema: dict[str, Any] | None


# Template registry - all available templates
TEMPLATE_REGISTRY: list[TemplateMetadata] = [
    {
        "slug": "welcome",
        "filename": "welcome.html",
        "title": "Welcome Email",
        "description": "Welcome new employees to the organization",
        "purpose": "Send to new employees on their first day",
        "default_subject": "Welcome to MaiVietLand!",
        "variables": [
            {
                "name": "employee_fullname",
                "type": "string",
                "required": True,
                "description": "Employee's full name",
            },
            {
                "name": "employee_email",
                "type": "string",
                "required": True,
                "description": "Employee's email address",
            },
            {
                "name": "employee_username",
                "type": "string",
                "required": True,
                "description": "Employee's username",
            },
            {
                "name": "employee_start_date",
                "type": "string",
                "required": True,
                "description": "Employee's start date",
            },
            {
                "name": "employee_code",
                "type": "string",
                "required": True,
                "description": "Employee's code",
            },
            {
                "name": "employee_department_name",
                "type": "string",
                "required": False,
                "description": "Employee's department name",
            },
            {
                "name": "new_password",
                "type": "string",
                "required": True,
                "description": "New password for the employee's account",
            },
            {
                "name": "logo_image_url",
                "type": "string",
                "required": True,
                "description": "URL of the logo image",
            },
            {
                "name": "leader_fullname",
                "type": "string",
                "required": False,
                "description": "Department leader's full name",
            },
            {
                "name": "leader_department_name",
                "type": "string",
                "required": False,
                "description": "Leader's department name",
            },
            {
                "name": "leader_block_name",
                "type": "string",
                "required": False,
                "description": "Leader's block name",
            },
            {
                "name": "leader_branch_name",
                "type": "string",
                "required": False,
                "description": "Leader's branch name",
            },
            {
                "name": "branch_contact_infos",
                "type": "list[BranchContactInfo]",
                "required": False,
                "description": "Branch contact informations",
            },
        ],
        "sample_data": {
            "employee_fullname": "John Doe",
            "employee_email": "john.doe@example.com",
            "employee_username": "john.doe",
            "employee_start_date": "2025-11-01",
            "employee_code": "MVL12345",
            "employee_department_name": "Sales",
            "new_password": "Abc12345",
            "logo_image_url": settings.LOGO_URL,
            "leader_fullname": "Jane Smith",
            "leader_department_name": "Sales",
            "leader_block_name": "North Block",
            "leader_branch_name": "Hanoi Branch",
            "branch_contact_infos": [
                {
                    "business_line": "Payroll",
                    "name": "Alice Nguyen",
                    "phone_number": "+84 123 456 789",
                    "email": "alice.nguyen@example.com",
                },
            ],
        },
        "variables_schema": {
            "type": "object",
            "properties": {
                "employee_fullname": {"type": "string"},
                "employee_email": {"type": "string", "format": "email"},
                "employee_username": {"type": "string"},
                "employee_start_date": {"type": "string", "format": "date"},
                "employee_code": {"type": "string"},
                "employee_department_name": {"type": "string"},
                "new_password": {"type": "string"},
                "logo_image_url": {"type": "string", "format": "uri"},
                "leader_fullname": {"type": "string"},
                "leader_department_name": {"type": "string"},
                "leader_block_name": {"type": "string"},
                "leader_branch_name": {"type": "string"},
                "branch_contact_infos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "business_line": {"type": "string"},
                            "name": {"type": "string"},
                            "phone_number": {"type": "string"},
                            "email": {"type": "string", "format": "email"},
                        },
                    },
                },
            },
            "required": [
                "employee_fullname",
                "employee_email",
                "employee_username",
                "employee_start_date",
                "employee_code",
                "new_password",
                "logo_image_url",
            ],
        },
    },
    {
        "slug": "interview_invite",
        "filename": "interview_invite.html",
        "title": _("Interview Invitation"),  # type: ignore
        "description": "Invite candidates for job interviews",
        "purpose": "Send to candidates when scheduling interviews",
        "default_subject": _("Interview Invitation") + " - MaiVietLand",
        "variables": [
            {
                "name": "candidate_name",
                "type": "string",
                "required": True,
                "description": "Candidate's full name",
            },
            {
                "name": "position",
                "type": "string",
                "required": True,
                "description": "Position being interviewed for",
            },
            {
                "name": "interview_date",
                "type": "string",
                "required": True,
                "description": "Date of the interview",
            },
            {
                "name": "interview_time",
                "type": "string",
                "required": True,
                "description": "Time of the interview",
            },
            {
                "name": "location",
                "type": "string",
                "required": False,
                "description": "Interview location or meeting link",
            },
            {
                "name": "logo_image_url",
                "type": "string",
                "required": False,
                "description": "URL of the logo image",
            },
            {
                "name": "contact_fullname",
                "type": "string",
                "required": False,
                "description": "Contact person's full name",
            },
            {
                "name": "contact_phone",
                "type": "string",
                "required": False,
                "description": "Contact person's phone number",
            },
            {
                "name": "contact_position",
                "type": "string",
                "required": False,
                "description": "Contact person's position",
            },
        ],
        "sample_data": {
            "candidate_name": "Jane Doe",
            "position": "Product Manager",
            "interview_date": "2025-11-05",
            "interview_time": "10:00 AM",
            "location": "https://meet.example.com/interview-123",
            "logo_image_url": settings.LOGO_URL,
            "contact_fullname": "Emily Tran",
            "contact_phone": "+84 987 654 321",
            "contact_position": "HR Manager",
        },
        "variables_schema": {
            "type": "object",
            "properties": {
                "candidate_name": {"type": "string"},
                "position": {"type": "string"},
                "interview_date": {"type": "string", "format": "date"},
                "interview_time": {"type": "string"},
                "location": {"type": "string"},
                "logo_image_url": {"type": "string", "format": "uri"},
                "contact_fullname": {"type": "string"},
                "contact_phone": {"type": "string"},
                "contact_position": {"type": "string"},
            },
            "required": ["candidate_name", "position", "interview_date", "interview_time"],
        },
    },
]
