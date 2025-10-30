"""Hooks for fetching real data from domain models.

This module provides a placeholder for integrators to implement
real data fetching logic for template preview and sending.
"""

from typing import Any


def fetch_real_data(template_slug: str, ref: dict[str, Any], user: Any) -> dict[str, Any]:
    """Fetch real data for template rendering.

    This is a placeholder function that integrators should implement
    to fetch data from their domain models.

    Args:
        template_slug: Template identifier
        ref: Reference object with 'type' and 'id' keys
            Example: {"type": "employee", "id": 123}
        user: User requesting the data (for permission checks)

    Returns:
        Dictionary with template variables

    Raises:
        NotImplementedError: This function must be implemented by integrators
        PermissionError: If user doesn't have permission to access the data
        ValueError: If ref is invalid or object not found

    Example implementation:
        def fetch_real_data(template_slug, ref, user):
            obj_type = ref.get("type")
            obj_id = ref.get("id")

            if obj_type == "employee":
                employee = Employee.objects.get(id=obj_id)
                return {
                    "first_name": employee.first_name,
                    "start_date": employee.start_date.isoformat(),
                    "position": employee.position.name if employee.position else "",
                    "department": employee.department.name if employee.department else "",
                }

            raise ValueError(f"Unknown object type: {obj_type}")
    """
    raise NotImplementedError(
        "fetch_real_data must be implemented by integrators. "
        "See mailtemplates/hooks.py for documentation."
    )
