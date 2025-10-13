"""Constants for API documentation."""

from drf_spectacular.utils import OpenApiParameter

# Field filtering parameter description
FIELD_FILTERING_DESCRIPTION = """
Query Parameters:
- **fields**: Comma-separated list of field names to include in the response (optional)
  - Example: `?fields=id,name,email`
  - Returns only the specified fields to optimize payload size
  - If not provided, all fields (or default_fields if defined) are returned
  - Invalid field names are silently ignored
  - Field names are case-sensitive
"""

# OpenAPI parameter for field filtering
FIELD_FILTERING_PARAMETER = OpenApiParameter(
    name="fields",
    description=(
        "Comma-separated list of field names to include in response. "
        "Example: `?fields=id,name,email`. Returns only specified fields to optimize payload size."
    ),
    required=False,
    type=str,
    location=OpenApiParameter.QUERY,
)

# Common API descriptions with field filtering
API_LIST_DESCRIPTION_WITH_FILTERING = (
    "Retrieve a list of items. Supports filtering, search, ordering, and field selection."
)

API_RETRIEVE_DESCRIPTION_WITH_FILTERING = "Retrieve detailed information about a specific item. Supports field selection to optimize payload size."
