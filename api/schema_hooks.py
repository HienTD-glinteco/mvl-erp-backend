"""
Post-processing hooks for drf-spectacular schema generation.

This module contains hooks that modify the OpenAPI schema after it's generated.
"""


def wrap_with_envelope(result, generator, request, public):
    """
    Post-processing hook that wraps all application/json response schemas
    in a consistent envelope format.

    The envelope format matches the ApiResponseWrapperMiddleware:
    {
        "success": true/false,
        "data": <original_schema>,
        "error": <error_data>
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

                    # Create the envelope schema matching ApiResponseWrapperMiddleware
                    envelope_schema = {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "description": "Indicates if the request was successful"},
                            "data": original_schema if original_schema else {"type": "object", "nullable": True},
                            "error": {
                                "type": "object",
                                "nullable": True,
                                "description": "Error details (only present when success is false)",
                            },
                        },
                        "required": ["success"],
                    }

                    # Update the schema
                    json_content["schema"] = envelope_schema

    return result
