# I18n Implementation Summary

## Overview
This document summarizes the work completed to implement internationalization (i18n) in the MaiVietLand backend application, replacing hardcoded Vietnamese strings with English equivalents wrapped in Django's gettext functions.

## Changes Made

### 1. Core Authentication Module
**Files updated:**
- `apps/core/models/user.py` - Updated all verbose_name fields to use English with `gettext_lazy`
- `apps/core/models/password_reset.py` - Updated verbose names and choice labels
- `apps/core/validators.py` - Replaced Vietnamese error messages with English equivalents using `gettext`

**Serializers updated:**
- `apps/core/api/serializers/auth/login.py`
- `apps/core/api/serializers/auth/password_change.py`
- `apps/core/api/serializers/auth/password_reset.py`
- `apps/core/api/serializers/auth/otp_verification.py`
- `apps/core/api/serializers/auth/password_reset_otp_verification.py`
- `apps/core/api/serializers/auth/password_reset_change_password.py`

All help_text, error_messages, and validation errors were translated to English and wrapped in `gettext(_)`.

**Views updated:**
- `apps/core/api/views/auth/login.py`
- `apps/core/api/views/auth/password_change.py`
- `apps/core/api/views/auth/password_reset.py`
- `apps/core/api/views/auth/password_reset_change_password.py`

All API documentation strings (summary, description) and response messages were translated.

### 2. HRM (Human Resource Management) Module
**Files updated:**
- `apps/hrm/models/organization.py` - Updated all models (Branch, Block, Department, Position, OrganizationChart) with English verbose names and choice labels
- `apps/hrm/api/serializers/organization.py` - Updated validation error messages
- `apps/hrm/management/commands/setup_default_org_data.py` - Translated all data and messages

### 3. Email Templates
**Files updated:**
- `apps/core/templates/emails/otp_email.html` - Added `{% load i18n %}` and wrapped all text in `{% trans %}` tags
- `apps/core/templates/emails/password_reset_email.html` - Same treatment as above

Changed language attribute from `lang="vi"` to `lang="en"` since the source strings are now in English.

### 4. Translation Files
**Created:**
- `locale/vi/LC_MESSAGES/django.po` - Vietnamese translation file mapping English msgid strings to Vietnamese msgstr translations

**Contains translations for:**
- User model fields
- Password validators
- Authentication serializers
- Authentication views
- Email templates
- HRM models (Branch, Block, Department, Position, OrganizationChart)
- Management command messages
- Validation errors

## Configuration

### Language Settings
The application settings remain unchanged:
- `LANGUAGE_CODE = "vi"` - Default language is Vietnamese
- `USE_I18N = True` - Internationalization is enabled

This configuration means:
1. All English `msgid` strings in the code are translated to Vietnamese at runtime
2. The application displays in Vietnamese for Vietnamese users
3. The codebase is now multilingual-ready and can support additional languages

## Not Completed

### Low Priority Items
The following files were not updated as they contain numerous API documentation strings (summary, description, tags) that are primarily for developer consumption and not user-facing:
- `apps/hrm/api/views/organization.py` - Contains ~105 API doc strings

These can be updated in the future if needed.

## Next Steps

### 1. Compile Translation Files (Required for Production)
```bash
python manage.py compilemessages
```
This creates `.mo` files from the `.po` files. The `.mo` files are binary and used by Django at runtime.

### 2. Update Pre-commit Hook
The pre-commit configuration already includes a `django-makemessages` hook, which will automatically:
- Extract new translatable strings
- Update the .po files
- Keep translations in sync

### 3. Add Additional Language Support (Future)
To add support for another language (e.g., English):
```bash
python manage.py makemessages -l en
# Edit locale/en/LC_MESSAGES/django.po
python manage.py compilemessages
```

Then add language selection capability in the application.

### 4. Testing
Test the application to ensure:
- All user-facing text displays correctly in Vietnamese
- No hardcoded Vietnamese strings remain
- Email templates render properly
- Admin interface displays correctly

### 5. Continuous Maintenance
When adding new features:
- Always use English for source strings
- Wrap user-facing strings in `gettext()` or `gettext_lazy()`
- Use `{% trans %}` in templates
- Run `makemessages` and add Vietnamese translations
- Run pre-commit hooks before committing

## Translation Function Usage Guide

### Python Code
```python
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _  # For models

# In views/serializers
message = _("User not found")

# In models
class MyModel(models.Model):
    name = models.CharField(verbose_name=_("Name"))
```

### HTML Templates
```html
{% load i18n %}
<p>{% trans "Welcome to MaiVietLand" %}</p>

<!-- With variables -->
{% blocktrans with name=user.name %}Hello {{ name }}{% endblocktrans %}
```

## Benefits Achieved

1. **Maintainability**: All user-facing strings are centralized in .po files
2. **Consistency**: Translations are managed in one place
3. **Scalability**: Easy to add new languages
4. **Best Practices**: Follows Django's internationalization framework
5. **Code Quality**: English source code is more readable for international developers

## Files Changed Summary

- **Python files**: 16 files
- **HTML files**: 2 files
- **Translation files**: 1 file created
- **Configuration**: 1 file (.gitignore)

Total: ~550 Vietnamese strings replaced with English + translations

## References

- [Django Internationalization Documentation](https://docs.djangoproject.com/en/5.1/topics/i18n/)
- [Django Translation Documentation](https://docs.djangoproject.com/en/5.1/topics/i18n/translation/)
