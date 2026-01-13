# PR6: Audit Log Translation - Fix Plan

> **Branch name:** `fix/audit-log-translation`
> **Sprint:** Sprint 8
> **Estimated effort:** 1-2 days
> **Priority:** 🟡 Medium
> **Selected Approach:** ✅ Option 1 - Translate at API Response Level

---

## 📋 Issue Summary

| # | Task ID | Title | Status | Module |
|---|---------|-------|--------|--------|
| 1 | [86evq6gmy](./86evq6gmy-dich-noi-dung-audit-log.md) | Dịch nội dung các đối tượng trong audit log | 🔴 RE-OPEN | Audit Logging |

---

## 🔍 Issue Description

> Dịch nội dung các đối tượng trong audit log và hiển thị thêm thông tin thay đổi, rà soát đối tượng do hệ thống tạo và cập nhật

### Requirements

1. **Dịch nội dung đối tượng** - `object_type` (e.g., "Employee", "Proposal") cần hiển thị bằng tiếng Việt
2. **Dịch field names** - Các field trong `change_message` cần dịch (e.g., "phone_number" → "Số điện thoại")
3. **Hiển thị thông tin thay đổi** - Format `change_message` rõ ràng hơn
4. **Rà soát hệ thống** - Identify logs created by system (not user)

---

## 🔍 Current Architecture

### Audit Log Flow

```
Model Change → @audit_logging_register decorator → Producer → RabbitMQ → Consumer → OpenSearch
```

### Data Structure (OpenSearch)

```json
{
  "log_id": "abc123",
  "timestamp": "2025-01-13T10:00:00Z",
  "user_id": "uuid",
  "username": "admin@example.com",
  "action": "UPDATE",
  "object_type": "Employee",        // ← Need translation
  "object_id": "123",
  "object_repr": "Nguyen Van A",
  "change_message": {
    "headers": ["field", "old_value", "new_value"],
    "rows": [
      {
        "field": "phone_number",    // ← Need translation
        "old_value": "0987654321",
        "new_value": "1234567890"
      }
    ]
  }
}
```

### Registry Info

`AuditLogRegistry` already stores:
- `verbose_name` - Model's verbose name (can be translated via `gettext_lazy`)
- `verbose_name_plural` - Plural form

---

## 🔧 Solution Options

### Option 1: Translate at API Response Level (Recommended)

Add translation layer in API response serializer.

**Pros:**
- No data migration needed
- Can support multiple languages
- Quick implementation

**Cons:**
- Translation done on every request (cacheable)

### Option 2: Store Translated Values in OpenSearch

Store both English key and Vietnamese translation in OpenSearch.

**Pros:**
- Fast retrieval
- No runtime translation

**Cons:**
- Data duplication
- Harder to support multiple languages
- Need to re-index existing data

---

## 📋 Recommended: Option 1 ✅ SELECTED

### Implementation Approach

**Sử dụng `verbose_name` từ Model Meta** thay vì hardcode translation file riêng.

**Lý do:**
- Models đã có `verbose_name` định nghĩa sẵn trong `Meta` class
- Không cần maintain 2 chỗ (DRY principle)
- Tự động cập nhật khi model thay đổi
- `AuditLogRegistry` đã lưu `verbose_name` khi register

### Implementation Steps

#### 1. Create Translation Helper (Minimal)

**File:** `apps/audit_logging/translations.py`

```python
"""Translation utilities for audit log content.

Uses model verbose_name from AuditLogRegistry instead of hardcoded mappings.
"""

from django.utils.translation import gettext_lazy as _

from .registry import AuditLogRegistry

# Only need to define action translations (not model-specific)
ACTION_TRANSLATIONS = {
    "CREATE": _("Create"),
    "UPDATE": _("Update"),
    "DELETE": _("Delete"),
}


def get_object_type_display(object_type: str) -> str:
    """Get translated display name for an object type using model verbose_name.

    Looks up the model in AuditLogRegistry and returns its verbose_name.
    Falls back to humanized object_type if not found.

    Args:
        object_type: The model name (e.g., "Employee", "Proposal")

    Returns:
        Translated display name from model Meta.verbose_name
    """
    # Find model in registry by model_name
    for model_class, info in AuditLogRegistry.get_all_model_info().items():
        if info.get("model_name", "").lower() == object_type.lower():
            verbose_name = info.get("verbose_name")
            if verbose_name:
                return str(verbose_name)
            break

    # Fallback: humanize the object_type
    return object_type.replace("_", " ").title()


def get_field_display(field_name: str, object_type: str | None = None) -> str:
    """Get translated display name for a field using model field's verbose_name.

    Looks up the field in the model and returns its verbose_name.
    Falls back to humanized field_name if not found.

    Args:
        field_name: The field name (e.g., "phone_number", "status")
        object_type: Optional model name to look up field verbose_name

    Returns:
        Translated display name from field.verbose_name
    """
    if object_type:
        for model_class, info in AuditLogRegistry.get_all_model_info().items():
            if info.get("model_name", "").lower() == object_type.lower():
                try:
                    field = model_class._meta.get_field(field_name)
                    if hasattr(field, "verbose_name") and field.verbose_name:
                        return str(field.verbose_name)
                except Exception:
                    pass
                break

    # Fallback: humanize field name
    return field_name.replace("_", " ").title()


def get_action_display(action: str) -> str:
    """Get translated display name for an action."""
    if action in ACTION_TRANSLATIONS:
        return str(ACTION_TRANSLATIONS[action])
    return action.title()


def translate_change_message(change_message: dict | str | None, object_type: str | None = None) -> dict | str | None:
    """Translate field names in change_message using model field verbose_names."""
    if not change_message or not isinstance(change_message, dict):
        return change_message

    rows = change_message.get("rows", [])
    if not rows:
        return change_message

    translated_rows = []
    for row in rows:
        field_name = row.get("field", "")
        translated_rows.append({
            "field": get_field_display(field_name, object_type),
            "old_value": row.get("old_value"),
            "new_value": row.get("new_value"),
        })

    return {
        "headers": [str(_("Field")), str(_("Old value")), str(_("New value"))],
        "rows": translated_rows,
    }
```

#### 2. Update API Serializer

**File:** `apps/audit_logging/api/serializers.py`

```python
from ..translations import get_object_type_display, get_field_display, get_action_display, translate_change_message

class AuditLogSerializer(serializers.Serializer):
    # ... existing fields ...

    # Add translated fields
    object_type_display = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    change_message_display = serializers.SerializerMethodField()

    def get_object_type_display(self, obj):
        """Return translated object type using model verbose_name."""
        return get_object_type_display(obj.get("object_type", ""))

    def get_action_display(self, obj):
        """Return translated action."""
        return get_action_display(obj.get("action", ""))

    def get_change_message_display(self, obj):
        """Return change message with translated field names."""
        return translate_change_message(
            obj.get("change_message"),
            obj.get("object_type")
        )
        """Return change message with translated field names."""
        change_message = obj.get("change_message")
        if not change_message or not isinstance(change_message, dict):
            return change_message

        # Translate field names in rows
        translated_rows = []
        for row in change_message.get("rows", []):
            translated_rows.append({
                "field": translate_field_name(row.get("field", "")),
                "old_value": row.get("old_value"),
                "new_value": row.get("new_value"),
            })

        return {
            "headers": [_("Field"), _("Old Value"), _("New Value")],
            "rows": translated_rows,
        }
```

#### 3. Add System User Detection

Add field to identify if action was performed by system:

```python
class AuditLogSerializer(serializers.Serializer):
    # ... existing fields ...

    is_system_action = serializers.SerializerMethodField()

    def get_is_system_action(self, obj):
        """Check if action was performed by system (no user or system user)."""
        user_id = obj.get("user_id")
        username = obj.get("username", "")

        # System actions typically have no user or special system usernames
        if not user_id:
            return True
        if username in ["system", "celery", "scheduler"]:
            return True
        return False
```

---

## 📁 Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `apps/audit_logging/translations.py` | CREATE | Translation mappings |
| `apps/audit_logging/api/serializers.py` | MODIFY | Add translated fields |
| `apps/audit_logging/locale/vi/LC_MESSAGES/django.po` | MODIFY | Add Vietnamese translations |

---

## ✅ Test Cases

### Unit Tests

```python
@pytest.mark.django_db
class TestAuditLogTranslation:
    """Test audit log translation functionality."""

    def test_object_type_translation(self):
        """Object type should be translated to Vietnamese."""
        from apps.audit_logging.translations import translate_object_type

        assert translate_object_type("Employee") == "Nhân viên"
        assert translate_object_type("Proposal") == "Đề xuất"
        assert translate_object_type("Unknown") == "Unknown"  # Fallback

    def test_field_name_translation(self):
        """Field names should be translated."""
        from apps.audit_logging.translations import translate_field_name

        assert translate_field_name("phone_number") == "Số điện thoại"
        assert translate_field_name("fullname") == "Họ và tên"

    def test_change_message_display_translation(self, api_client):
        """API should return translated change_message."""
        # ... test API response
```

### QA Test Table

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 1 | TC-PR6-001 | object_type hiển thị tiếng Việt | - Có audit log với object_type="Employee" | 1. Mở trang Audit Log<br>2. Xem chi tiết log | Hiển thị "Nhân viên" | 🔴 Critical |
| 2 | TC-PR6-002 | Field names được dịch | - Có log UPDATE với change_message | 1. Xem chi tiết log | Field names hiển thị tiếng Việt | 🔴 Critical |
| 3 | TC-PR6-003 | Action được dịch | - Có log CREATE/UPDATE/DELETE | 1. Xem danh sách log | Action hiển thị: Tạo/Cập nhật/Xóa | 🟠 High |
| 4 | TC-PR6-004 | System actions được đánh dấu | - Có log do celery task tạo | 1. Xem log | Hiển thị icon/badge "Hệ thống" | 🟠 High |

---

## 📊 Implementation Checklist

- [ ] Create `translations.py` with mappings
- [ ] Collect all object_types from registered models
- [ ] Collect all field names from models
- [ ] Add translations to `.po` file
- [ ] Update serializers with display fields
- [ ] Add is_system_action detection
- [ ] Add unit tests
- [ ] Compile `.mo` file

### Validation Phase
- [ ] Run tests: `ENVIRONMENT=test poetry run pytest apps/audit_logging/tests/ -v`
- [ ] Pre-commit: `pre-commit run --all-files`
- [ ] Manual QA with production data

---

## 📝 Notes

1. **Collect all object types:** Need to enumerate all models with `@audit_logging_register` decorator
2. **Collect all field names:** Need to enumerate all fields from those models
3. **Performance:** Translation is lightweight, but could add caching if needed
4. **FE Consideration:** FE may need to handle new `*_display` fields

---

## 🔗 Related Files

- [86evq6gmy-dich-noi-dung-audit-log.md](./86evq6gmy-dich-noi-dung-audit-log.md)
