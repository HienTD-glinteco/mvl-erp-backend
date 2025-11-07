"""Mail template constants and registry.

This module defines the template registry and action-to-template mapping.
All templates must be registered here with their metadata.
"""

from typing import Any, TypedDict


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
                "name": "fullname",
                "type": "string",
                "required": True,
                "description": "Employee's full name",
            },
            {
                "name": "start_date",
                "type": "string",
                "required": True,
                "description": "Employment start date",
            },
            {
                "name": "position",
                "type": "string",
                "required": False,
                "description": "Job position title",
            },
            {
                "name": "department",
                "type": "string",
                "required": False,
                "description": "Department name",
            },
        ],
        "sample_data": {
            "fullname": "John Doe",
            "start_date": "2025-11-01",
            "position": "Software Engineer",
            "department": "Engineering",
        },
        "variables_schema": {
            "type": "object",
            "properties": {
                "fullname": {"type": "string"},
                "start_date": {"type": "string", "format": "date"},
                "position": {"type": "string"},
                "department": {"type": "string"},
            },
            "required": ["fullname", "start_date"],
        },
    },
    {
        "slug": "interview_invite",
        "filename": "interview_invite.html",
        "title": "Interview Invitation",
        "description": "Invite candidates for job interviews",
        "purpose": "Send to candidates when scheduling interviews",
        "default_subject": "Interview Invitation - MaiVietLand",
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
        ],
        "sample_data": {
            "candidate_name": "Jane Doe",
            "position": "Product Manager",
            "interview_date": "2025-11-05",
            "interview_time": "10:00 AM",
            "location": "https://meet.example.com/interview-123",
        },
        "variables_schema": {
            "type": "object",
            "properties": {
                "candidate_name": {"type": "string"},
                "position": {"type": "string"},
                "interview_date": {"type": "string", "format": "date"},
                "interview_time": {"type": "string"},
                "location": {"type": "string"},
            },
            "required": ["candidate_name", "position", "interview_date", "interview_time"],
        },
    },
]
