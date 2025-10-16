# Code Examples

This directory contains practical examples demonstrating how to use various features of the MVL Backend.

## Import Feature Examples

### [Role Import Example](role_import_example.md)
**Complete guide for adding XLSX import to an existing ViewSet**

Shows how to:
- Add import functionality to RoleViewSet with a single mixin
- Understand auto-generated import schema
- Customize import schema if needed
- Test import functionality
- Integrate with frontend (JavaScript/React)
- Handle errors and validation

**Recommended starting point for learning the import feature.**

### [Import Example Code](import_example.py)
**Python code examples for various import patterns**

Demonstrates:
- Basic import with auto schema
- Import with audit logging
- Custom import schema
- Best practices and common patterns

## Quick Reference

### Adding Import to Any ViewSet

```python
from libs import BaseModelViewSet, ImportXLSXMixin

class MyViewSet(ImportXLSXMixin, BaseModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
    module = "Module"
    submodule = "Submodule"
    permission_prefix = "mymodel"
```

### Adding Import with Audit Logging

```python
from apps.audit_logging import AuditLoggingMixin
from libs import BaseModelViewSet, ImportXLSXMixin

class MyViewSet(AuditLoggingMixin, ImportXLSXMixin, BaseModelViewSet):
    # Order matters: AuditLoggingMixin first
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
```

### Custom Import Schema

```python
class MyViewSet(ImportXLSXMixin, BaseModelViewSet):
    def get_import_schema(self, request, file):
        return {
            "fields": ["field1", "field2", "field3"],
            "required": ["field1", "field2"]
        }
```

## Related Documentation

- [XLSX Import Feature Documentation](../IMPORT_XLSX.md) - Complete feature documentation
- [Auto Permission Registration](../AUTO_PERMISSION_REGISTRATION.md) - Permission system
- [Audit Logging](../../apps/audit_logging/README.md) - Audit logging system
- [Base ViewSet](../../libs/base_viewset.py) - Base ViewSet implementation

## Contributing Examples

When adding new examples:

1. Create a new file in this directory
2. Use clear, self-contained examples
3. Include both success and error cases
4. Add frontend integration examples when applicable
5. Update this README with a link to your example
6. Follow existing code style and documentation format
