# API Schema Hooks

This directory contains post-processing hooks for drf-spectacular that modify the generated OpenAPI schema.

## Response Envelope Hook

### Overview

The `wrap_with_envelope` hook automatically wraps all `application/json` response schemas in a consistent envelope format. This ensures that the API documentation (Swagger/Redoc) accurately reflects the actual runtime behavior where responses are wrapped by the `ApiResponseWrapperMiddleware`.

### Envelope Structure

All API responses are wrapped in the following structure (matching `ApiResponseWrapperMiddleware`):

For successful responses:

```json
{
  "success": true,
  "data": "<original response data>",
  "error": null
}
```

For error responses:

```json
{
  "success": false,
  "data": null,
  "error": "<error details>"
}
```

### Configuration

The hook is registered in `settings/base/drf.py`:

```python
SPECTACULAR_SETTINGS = {
    # ... other settings ...
    "POSTPROCESSING_HOOKS": [
        "libs.schema_hooks.wrap_with_envelope",
    ],
}
```

### Behavior

The hook:
- ✅ Wraps all 2xx status code responses with `application/json` content type
- ✅ Preserves the original schema structure within the `data` field
- ✅ Handles both array (list endpoints) and object (retrieve endpoints) responses correctly
- ✅ Handles paginated responses (DRF PageNumberPagination format) correctly
- ✅ Skips non-JSON responses (e.g., file downloads, PDFs)
- ✅ Skips error responses (4xx, 5xx status codes)
- ✅ Prevents double-wrapping if a schema is already wrapped

### Response Format Guidelines

When writing `OpenApiExample` declarations in your views, ensure examples match the envelope format:

**For paginated list endpoints:**
```python
OpenApiExample(
    "List success",
    value={
        "success": True,
        "data": {
            "count": 100,
            "next": "http://api.example.org/items/?page=2",
            "previous": None,
            "results": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"},
            ]
        }
    },
    response_only=True,
)
```

**For non-paginated list endpoints:**
```python
OpenApiExample(
    "List success",
    value={
        "success": True,
        "data": [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
        ]
    },
    response_only=True,
)
```

**For single object endpoints (retrieve, create, update):**
```python
OpenApiExample(
    "Get success",
    value={
        "success": True,
        "data": {
            "id": 1,
            "name": "Item 1",
            "description": "..."
        }
    },
    response_only=True,
)
```

**For error responses:**
```python
OpenApiExample(
    "Validation error",
    value={
        "success": False,
        "error": {
            "field_name": ["Error message"]
        }
    },
    response_only=True,
    status_codes=["400"],
)
```

**Important:** Individual items in the `results` array should NOT be wrapped in the envelope. Only the top-level response uses the envelope format.

### Testing

Unit tests are located in `tests/libs/spectacular/test_schema_hooks.py` and cover:
- Basic envelope structure
- Array/list response handling
- Paginated response handling (DRF PageNumberPagination)
- Error response skipping
- Non-JSON response skipping
- Double-wrap prevention

Run tests with:
```bash
poetry run pytest tests/libs/spectacular/test_schema_hooks.py -v
```

### Schema Generation

To generate the OpenAPI schema with envelope wrapping:

```bash
poetry run python manage.py spectacular --file schema.yml
```

The generated schema will show all successful responses wrapped in the envelope format.

### Example

**Before (without hook):**
```yaml
responses:
  '200':
    content:
      application/json:
        schema:
          type: array
          items:
            $ref: '#/components/schemas/Branch'
```

**After (with hook):**
```yaml
responses:
  '200':
    content:
      application/json:
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                $ref: '#/components/schemas/Branch'
            error:
              type: object
              nullable: true
          required:
            - success
```

### Troubleshooting

If the envelope is not appearing in the generated schema:

1. Verify the hook is registered in `SPECTACULAR_SETTINGS["POSTPROCESSING_HOOKS"]`
2. Check that the endpoint returns a 2xx status code
3. Verify the response has `application/json` content type
4. Run the test suite to ensure the hook function is working correctly

### Maintenance

When adding new response envelope fields:
1. Update the `wrap_with_envelope` function in `libs/schema_hooks.py`
2. Update the tests in `tests/libs/test_schema_hooks.py`
3. Regenerate the schema to verify the changes
4. Update this documentation
