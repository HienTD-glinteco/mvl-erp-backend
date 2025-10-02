"""
Post-processing hooks for drf-spectacular schema generation.

This module contains hooks that modify the OpenAPI schema after it's generated.
"""


def wrap_with_envelope(result, generator, request, public):
    """
    Post-processing hook that wraps all application/json response schemas
    in a consistent envelope format.

    The envelope format follows the pattern:
    {
        "success": true/false,
        "message": "string",
        "data": <original_schema>,
        "meta": {
            "page": int,
            "page_size": int,
            "total": int
        }
    }

    Args:
        result: The generated OpenAPI schema dictionary
        generator: The SchemaGenerator instance
        request: The HTTP request object (if available)
        public: Boolean indicating if this is a public schema

    Returns:
        Modified OpenAPI schema with wrapped responses
    """
    if not isinstance(result, dict):
        return result

    # Get the paths section of the schema
    paths = result.get("paths", {})

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            # Skip non-operation keys like 'parameters'
            if method not in ["get", "post", "put", "patch", "delete", "head", "options", "trace"]:
                continue

            # Process responses
            responses = operation.get("responses", {})
            for status_code, response_def in responses.items():
                # Only process successful responses (2xx)
                if not status_code.startswith("2"):
                    continue

                # Get content types
                content = response_def.get("content", {})

                # Only wrap application/json responses
                if "application/json" in content:
                    json_content = content["application/json"]
                    original_schema = json_content.get("schema", {})

                    # Skip if already wrapped (check for 'success' and 'data' fields)
                    if "properties" in original_schema:
                        props = original_schema.get("properties", {})
                        if "success" in props and "data" in props:
                            continue

                    # Create the envelope schema
                    envelope_schema = {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "description": "Indicates if the request was successful"},
                            "message": {
                                "type": "string",
                                "description": "Human-readable message about the response",
                                "nullable": True,
                            },
                            "data": original_schema if original_schema else {"type": "object", "nullable": True},
                            "error": {
                                "type": "object",
                                "nullable": True,
                                "description": "Error details (only present when success is false)",
                            },
                            "meta": {
                                "type": "object",
                                "description": "Metadata about the response (e.g., pagination info)",
                                "nullable": True,
                                "properties": {
                                    "page": {"type": "integer", "description": "Current page number"},
                                    "page_size": {"type": "integer", "description": "Number of items per page"},
                                    "total": {"type": "integer", "description": "Total number of items"},
                                },
                                "additionalProperties": True,
                            },
                        },
                        "required": ["success"],
                    }

                    # Update the schema
                    json_content["schema"] = envelope_schema

    return result
