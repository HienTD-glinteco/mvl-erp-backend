# Translation Strings for Employee Role Management

This document lists the translation strings that need to be added to the Vietnamese `.po` files for the Employee Role Management feature.

## Location: apps/hrm/api/serializers/employee_role.py

```po
# apps/hrm/api/serializers/employee_role.py:69
msgid "List of employee IDs to update (maximum 25)"
msgstr "Danh sách ID nhân viên cần cập nhật (tối đa 25)"

# apps/hrm/api/serializers/employee_role.py:74
msgid "New role to assign to selected employees"
msgstr "Vai trò mới để gán cho nhân viên được chọn"

# apps/hrm/api/serializers/employee_role.py:80
msgid "Cannot update more than 25 employees at once."
msgstr "Không thể cập nhật quá 25 nhân viên cùng lúc."

# apps/hrm/api/serializers/employee_role.py:84
msgid "One or more employee IDs are invalid."
msgstr "Một hoặc nhiều ID nhân viên không hợp lệ."

# apps/hrm/api/serializers/employee_role.py:91
msgid "Please select at least one employee."
msgstr "Vui lòng chọn ít nhất một nhân viên."

# apps/hrm/api/serializers/employee_role.py:94
msgid "Please select a new role."
msgstr "Vui lòng chọn vai trò mới."
```

## Location: apps/hrm/api/views/employee_role.py

```po
# apps/hrm/api/views/employee_role.py:139
msgid "Chỉnh sửa thành công"
msgstr "Chỉnh sửa thành công"
```

Note: "Chỉnh sửa thành công" is already in Vietnamese, so the translation is the same.

## Instructions for updating .po files

When gettext tools are available, run:

```bash
poetry run python manage.py makemessages -l vi --no-obsolete
```

Then manually add/verify these translations in `apps/hrm/locale/vi/LC_MESSAGES/django.po`.

After updating the .po file, compile the messages:

```bash
poetry run python manage.py compilemessages
```
