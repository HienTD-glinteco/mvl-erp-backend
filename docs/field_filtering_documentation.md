# Field Filtering Auto-Documentation

This feature automatically generates OpenAPI documentation for APIs that use the `FieldFilteringSerializerMixin`.

## Overview

When a serializer uses `FieldFilteringSerializerMixin`, the API documentation will automatically include:

- A `fields` query parameter
- List of all available fields
- Default fields (if configured)
- Usage examples
- Clear instructions on how to use field filtering

## How It Works

The `FieldFilteringAutoSchema` extends drf-spectacular's `AutoSchema` class to detect when a serializer uses `FieldFilteringSerializerMixin` and automatically adds the `fields` query parameter to the API documentation.

### Implementation Details

1. **AutoSchema Extension** (`libs/spectacular/field_filtering.py`):
   - Detects serializers using `FieldFilteringSerializerMixin`
   - Extracts available fields from the serializer
   - Generates comprehensive documentation for the `fields` parameter
   - Adds examples for easy understanding

2. **Settings Configuration** (`settings/base/drf.py`):
   ```python
   REST_FRAMEWORK = {
       "DEFAULT_SCHEMA_CLASS": "libs.spectacular.field_filtering.FieldFilteringAutoSchema",
       # ... other settings
   }
   ```

## Example Output

For a serializer like this:

```python
class EmployeeSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    default_fields = ["id", "code", "fullname", "email"]
    
    class Meta:
        model = Employee
        fields = ["id", "code", "fullname", "username", "email", "phone", "branch", ...]
```

The generated documentation will include:

**Query Parameter: `fields`**

```
Comma-separated list of fields to include in the response.

Available fields: `code`, `created_at`, `email`, `fullname`, `id`, `phone`, `updated_at`, `username`

Usage: Specify field names separated by commas (e.g., ?fields=id,name,email)

Default fields (when not specified): `id`, `code`, `fullname`, `email`

If the fields parameter is not provided, only the default fields will be returned.
```

**Example:** `GET /api/employees/?fields=id,code,fullname`

## Usage in Your Code

No changes are required in your existing code! The documentation is automatically generated for any API that uses `FieldFilteringSerializerMixin`.

### Example API

```python
from libs.serializers.mixins import FieldFilteringSerializerMixin
from rest_framework import serializers

class MySerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    # Optional: define default fields
    default_fields = ["id", "name"]
    
    class Meta:
        model = MyModel
        fields = "__all__"

class MyViewSet(ModelViewSet):
    serializer_class = MySerializer
    # ... rest of the viewset
```

The OpenAPI/Swagger documentation will automatically include the `fields` parameter with complete documentation.

## Benefits

✅ **Automatic**: No manual documentation needed  
✅ **Consistent**: Same format across all APIs  
✅ **Accurate**: Always in sync with actual serializer fields  
✅ **Clear**: Includes examples and usage instructions  
✅ **Comprehensive**: Shows available fields and defaults  

## Testing

Comprehensive tests are provided in:
- `tests/libs/spectacular/test_field_filtering.py` - Unit tests
- `tests/libs/spectacular/test_field_filtering_integration.py` - Integration tests

To run tests:
```bash
poetry run pytest tests/libs/spectacular/test_field_filtering.py -v
```

## Verification

To verify the documentation is generated correctly, you can:

1. **View Swagger UI**: Visit `/docs/` endpoint (in local/develop environments)
2. **Check OpenAPI Schema**: Visit `/schema/` endpoint
3. **Run verification script**:
   ```bash
   poetry run python /tmp/verify_field_filtering_docs.py
   ```

## Technical Notes

- The `fields` parameter is only added for read operations (GET, HEAD, OPTIONS)
- Regular serializers (without the mixin) are not affected
- The extension properly handles serializers with no fields
- Default fields are clearly indicated in the documentation when present
