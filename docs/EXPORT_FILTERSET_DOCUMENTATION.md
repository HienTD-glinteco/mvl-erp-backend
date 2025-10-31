# Export Action FilterSet Parameters Documentation

## Overview

This document describes the automatic documentation feature for filterset parameters in the `export` action of ViewSets using `ExportXLSXMixin`.

## Feature Description

When a ViewSet:
1. Uses `ExportXLSXMixin` to provide an `/export/` endpoint
2. Has a `filterset_class` attribute defined (using django-filter)

The OpenAPI documentation for the `/export/` endpoint will automatically include:
- The existing `async` and `delivery` parameters (from ExportXLSXMixin)
- All filter parameters from the ViewSet's `filterset_class`

## How It Works

The `EnhancedAutoSchema` class in `libs/drf/spectacular/field_filtering.py` detects when:
- The current action is `export`
- The request method is `GET`
- The view has a `filterset_class` attribute

When these conditions are met, it extracts filter definitions from the FilterSet and adds them as query parameters to the OpenAPI documentation.

## Example

### ViewSet with ExportXLSXMixin and FilterSet

```python
from django_filters.rest_framework import DjangoFilterBackend
from libs.export_xlsx import ExportXLSXMixin
from libs import BaseModelViewSet

class RecruitmentCandidateFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentCandidate model"""
    
    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="exact")
    status = django_filters.MultipleChoiceFilter(choices=RecruitmentCandidate.Status.choices)
    submitted_date_from = django_filters.DateFilter(field_name="submitted_date", lookup_expr="gte")
    submitted_date_to = django_filters.DateFilter(field_name="submitted_date", lookup_expr="lte")
    
    class Meta:
        model = RecruitmentCandidate
        fields = ["name", "code", "status", "submitted_date_from", "submitted_date_to"]


class RecruitmentCandidateViewSet(ExportXLSXMixin, BaseModelViewSet):
    """ViewSet for RecruitmentCandidate model"""
    
    queryset = RecruitmentCandidate.objects.all()
    serializer_class = RecruitmentCandidateSerializer
    filterset_class = RecruitmentCandidateFilterSet  # This enables auto-documentation
    filter_backends = [DjangoFilterBackend]
```

### Generated OpenAPI Documentation

The `/export/` endpoint will include these query parameters:

**Fixed Parameters (from ExportXLSXMixin):**
- `async` (boolean, optional): Enable async export processing
- `delivery` (string, optional, enum: ["link", "direct"]): Delivery mode

**Filter Parameters (from FilterSet):**
- `name` (string, optional): Filter by name (case-insensitive partial match)
- `code` (string, optional): Filter by code
- `status` (string, optional, enum: ["CONTACTED", "INTERVIEWED_1", ...]): Filter by status
- `submitted_date_from` (string, optional): Filter by submitted_date (greater than or equal)
- `submitted_date_to` (string, optional): Filter by submitted_date (less than or equal)

## Filter Type Mapping

The feature automatically maps django-filter types to OpenAPI types:

| Django Filter Type | OpenAPI Type | Notes |
|-------------------|--------------|-------|
| `BooleanFilter` | `boolean` | True/False values |
| `NumberFilter` | `integer` | Numeric values |
| `DateFilter` | `string` | ISO 8601 date format (YYYY-MM-DD) |
| `DateTimeFilter` | `string` | ISO 8601 datetime format |
| `BaseInFilter` | `string` | Comma-separated values (e.g., "1,2,3") |
| `MultipleChoiceFilter` | `string` | Multiple values from choices |
| `ChoiceFilter` | `string` | Single value with enum constraint |
| `CharFilter` | `string` | Default type for text filters |

## Lookup Expression Documentation

Filter descriptions include human-readable explanations of lookup expressions:

| Lookup Expression | Description Format |
|------------------|-------------------|
| `exact` | "Filter by {field_name}" |
| `icontains` | "Filter by {field_name} (case-insensitive partial match)" |
| `gte` | "Filter by {field_name} (greater than or equal)" |
| `lte` | "Filter by {field_name} (less than or equal)" |
| `gt` | "Filter by {field_name} (greater than)" |
| `lt` | "Filter by {field_name} (less than)" |
| other | "Filter by {field_name} ({lookup_expr})" |

## Enum Values for Choice Filters

When a filter has choices (e.g., `ChoiceFilter`, `MultipleChoiceFilter`), the OpenAPI documentation includes enum values:

```python
status = django_filters.ChoiceFilter(choices=[
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("pending", "Pending"),
])
```

Results in OpenAPI parameter with `enum: ["active", "inactive", "pending"]`

## Implementation Details

### Key Components

1. **Detection Logic** (`_add_export_filterset_parameters`):
   - Checks if action is "export"
   - Validates filterset_class exists and is a FilterSet subclass
   - Only processes GET requests

2. **Parameter Extraction** (`_extract_filterset_parameters`):
   - Iterates through `base_filters` from the FilterSet class
   - Creates OpenApiParameter for each filter
   - Includes type, description, and enum values

3. **Helper Methods**:
   - `_build_filter_description`: Generates human-readable descriptions
   - `_get_filter_param_type`: Maps filter types to OpenAPI types
   - `_get_filter_enum_values`: Extracts enum values from choices

### Design Principles

- **Non-invasive**: Only affects OpenAPI documentation, not runtime behavior
- **Automatic**: No manual configuration required
- **Consistent**: Follows the same patterns as field filtering and ordering documentation
- **Extensible**: Can be enhanced to support more filter types

## Testing

Comprehensive tests are provided in `tests/libs/spectacular/test_export_filterset_parameters.py`:

- Filter parameter extraction for various filter types
- Description generation with lookup expressions
- Type mapping validation
- Enum value extraction for choice filters
- Action-specific behavior (only export action)
- Method-specific behavior (only GET requests)

## Usage Example

### Making API Requests

Once documented, clients can use filter parameters in export requests:

```bash
# Export all candidates
GET /api/hrm/recruitment-candidates/export/

# Export with filters
GET /api/hrm/recruitment-candidates/export/?name=john&status=CONTACTED

# Export with date range
GET /api/hrm/recruitment-candidates/export/?submitted_date_from=2025-01-01&submitted_date_to=2025-01-31

# Export with async processing
GET /api/hrm/recruitment-candidates/export/?async=true&status=HIRED

# Export with direct delivery and filters
GET /api/hrm/recruitment-candidates/export/?delivery=direct&name=smith
```

## Benefits

1. **Better Developer Experience**: Filters are clearly documented in OpenAPI/Swagger
2. **Self-Documenting**: No need to maintain separate documentation
3. **Type Safety**: Clients can validate parameters before making requests
4. **Consistency**: Same filters work for both list and export actions
5. **Discovery**: Developers can see available filters in API documentation

## Future Enhancements

Potential improvements for future iterations:

1. Support for custom filter help text from FilterSet
2. More sophisticated type inference for custom filter classes
3. Support for nested/complex filter expressions
4. Integration with filter backends beyond DjangoFilterBackend
5. Validation hints for specific filter types (e.g., date format examples)

## Troubleshooting

### Filters Not Appearing in Documentation

**Symptom**: Export endpoint doesn't show filter parameters in OpenAPI docs

**Possible Causes**:
1. `filterset_class` not set on the ViewSet
2. ViewSet doesn't use `ExportXLSXMixin`
3. Action name is not "export" (custom action names won't work)
4. FilterSet class is not a subclass of `django_filters.FilterSet`

**Solution**: Verify all conditions are met in your ViewSet definition

### Incorrect Parameter Types

**Symptom**: Filter parameters show wrong type in documentation

**Possible Cause**: Custom filter class not recognized by type mapping

**Solution**: Check `_get_filter_param_type` method and add mapping for custom filter type

### Missing Enum Values

**Symptom**: Choice filter doesn't show available values

**Possible Cause**: Choices not properly defined in FilterSet

**Solution**: Ensure choices are passed to the filter constructor:
```python
status = django_filters.ChoiceFilter(choices=MY_CHOICES)
```
