# Mail Merge Templates and Bulk Send API

This feature provides a comprehensive mail merge templates system with bulk email sending capabilities.

## Features

- **Template Registry**: Templates are defined in code (`constants.py`) for version control
- **Template Management**: API endpoints to list, view, edit, and save templates
- **Template Preview**: Preview templates with sample or real data
- **Bulk Email Sending**: Send personalized emails to multiple recipients asynchronously
- **Job Tracking**: Track send jobs and per-recipient status
- **Retry Logic**: Automatic retry of failed sends with configurable attempts
- **Domain Actions**: Convenience endpoints for domain-specific email actions

## API Endpoints

### Template Management

- `GET /api/templates/` - List all templates
- `GET /api/templates/{slug}/` - Get template details
- `PUT /api/templates/{slug}/save/` - Save template content (staff only)
- `POST /api/templates/{slug}/preview/` - Preview template
- `POST /api/templates/{slug}/send/` - Send bulk emails
- `GET /api/templates/send/{job_id}/status/` - Get send job status

### Domain Actions (via TemplateActionMixin)

ViewSets can include `TemplateActionMixin` to provide domain-specific email actions:

- `POST /api/{domain}/{pk}/{action}/preview/` - Preview email for object
- `POST /api/{domain}/{pk}/{action}/send/` - Send email for object

Example: `POST /api/employees/123/send_welcome_email/send/`

## Configuration

Add to your Django settings:

```python
# Mail template directory
MAIL_TEMPLATE_DIR = "/path/to/templates/mail"

# Sending configuration
MAIL_SEND_CHUNK_SIZE = 10  # Recipients per chunk
MAIL_SEND_SLEEP_BETWEEN_CHUNKS = 1.0  # Seconds between chunks
MAIL_SEND_MAX_ATTEMPTS = 3  # Max retry attempts per recipient
```

## Usage Examples

### Using TemplateActionMixin in ViewSets

The mixin provides helper methods that you call from manually defined actions:

```python
from rest_framework.decorators import action
from apps.mailtemplates.view_mixins import TemplateActionMixin
from apps.mailtemplates.permissions import CanSendMail

class EmployeeViewSet(TemplateActionMixin, BaseModelViewSet):
    
    @action(detail=True, methods=["post"], url_path="send_welcome_email/preview")
    def send_welcome_email_preview(self, request, pk=None):
        return self.preview_template_email("welcome", request, pk)
    
    @action(detail=True, methods=["post"], url_path="send_welcome_email/send",
            permission_classes=[CanSendMail])
    def send_welcome_email_send(self, request, pk=None):
        return self.send_template_email("welcome", request, pk)
    
    @action(detail=True, methods=["post"], url_path="send_contract/preview")
    def send_contract_preview(self, request, pk=None):
        return self.preview_template_email("contract", request, pk)
    
    @action(detail=True, methods=["post"], url_path="send_contract/send",
            permission_classes=[CanSendMail])
    def send_contract_send(self, request, pk=None):
        return self.send_template_email("contract", request, pk)
    
    # Optionally override data extraction
    def get_template_action_data(self, instance, template_slug):
        data = super().get_template_action_data(instance, template_slug)
        # Add custom data extraction logic
        if template_slug == "welcome":
            data["custom_field"] = instance.custom_value
        return data
```

This provides:
- `POST /api/employees/{pk}/send_welcome_email/preview/`
- `POST /api/employees/{pk}/send_welcome_email/send/`
- `POST /api/employees/{pk}/send_contract/preview/`
- `POST /api/employees/{pk}/send_contract/send/`

The mixin provides two helper methods:
- `preview_template_email(template_slug, request, pk)` - Preview email with sample or real data
- `send_template_email(template_slug, request, pk, on_success_callback=None, callback_params=None)` - Send email to recipients with optional callback

### Using Callbacks for Post-Send Actions

You can provide a callback function to be executed after each email is successfully sent. This is useful for updating model fields or triggering other actions:

```python
from rest_framework.decorators import action
from apps.mailtemplates.view_mixins import TemplateActionMixin
from apps.mailtemplates.permissions import CanSendMail

# Define your callback function - now accepts **kwargs for additional params
def mark_welcome_email_sent(employee_instance, recipient, **kwargs):
    """Mark employee as having received welcome email."""
    notification_type = kwargs.get("notification_type", "welcome")
    source = kwargs.get("source", "unknown")
    
    employee_instance.is_sent_welcome_email = True
    employee_instance.last_notification_type = notification_type
    employee_instance.last_notification_source = source
    employee_instance.save(update_fields=[
        "is_sent_welcome_email", 
        "last_notification_type",
        "last_notification_source"
    ])

class EmployeeViewSet(TemplateActionMixin, BaseModelViewSet):
    
    @action(detail=True, methods=["post"], url_path="send_welcome_email/send",
            permission_classes=[CanSendMail])
    def send_welcome_email_send(self, request, pk=None):
        # Pass the callback function with additional parameters
        return self.send_template_email(
            "welcome", 
            request, 
            pk,
            on_success_callback=mark_welcome_email_sent,
            callback_params={
                "notification_type": "welcome",
                "source": "api",
                "campaign_id": "2025-Q1"
            }
        )
```

**Callback Signature:**
- `callback(instance, recipient, **callback_params)`
  - `instance`: The domain object (e.g., Employee instance)
  - `recipient`: The EmailSendRecipient instance that was successfully sent
  - `**callback_params`: Additional parameters passed via `callback_params` dict

**Alternative: Use string path for callback**

You can also pass a string path to the callback function:

```python
@action(detail=True, methods=["post"], url_path="send_welcome_email/send",
        permission_classes=[CanSendMail])
def send_welcome_email_send(self, request, pk=None):
    return self.send_template_email(
        "welcome", 
        request, 
        pk,
        on_success_callback="apps.hrm.callbacks.mark_welcome_email_sent",
        callback_params={"notification_type": "welcome", "source": "api"}
    )
```

**Important Notes:**
- Callbacks are executed asynchronously in the Celery worker after successful email delivery
- If the callback raises an exception, it's logged but doesn't fail the email send
- Callbacks are only executed for successfully sent emails, not for failed sends
- The callback has access to the full recipient data including `recipient.data`, `recipient.email`, etc.
- Additional parameters via `callback_params` allow you to pass context-specific data to your callback

### List Templates

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/templates/
```

### Preview Template

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"data": {"first_name": "John", "start_date": "2025-11-01"}}' \
  http://localhost:8000/api/templates/welcome/preview/
```

### Send Bulk Emails

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Welcome to our team!",
    "recipients": [
      {"email": "user1@example.com", "data": {"first_name": "John", "start_date": "2025-11-01"}},
      {"email": "user2@example.com", "data": {"first_name": "Jane", "start_date": "2025-11-02"}}
    ]
  }' \
  http://localhost:8000/api/templates/welcome/send/
```

### Check Send Job Status

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/templates/send/{job_id}/status/
```

## Adding New Templates

1. Add template metadata to `apps/mailtemplates/constants.py`:

```python
{
    "slug": "my_template",
    "filename": "my_template.html",
    "title": "My Template",
    "description": "Description of the template",
    "purpose": "When to use this template",
    "variables": [
        {
            "name": "variable_name",
            "type": "string",
            "required": True,
            "description": "Variable description"
        }
    ],
    "sample_data": {
        "variable_name": "Sample value"
    },
    "variables_schema": {
        "type": "object",
        "properties": {
            "variable_name": {"type": "string"}
        },
        "required": ["variable_name"]
    }
}
```

2. Create HTML template file in `templates/mail/my_template.html`:

```html
<!DOCTYPE html>
<html>
<body>
    <p>Hello {{ variable_name }}!</p>
</body>
</html>
```

3. (Optional) Add action mapping in `constants.py`:

```python
ACTION_TEMPLATE_MAP = {
    "send_my_email": {
        "template_slug": "my_template",
        "default_subject": "My Email Subject",
        "default_sender": None,
    }
}
```

## Permissions

- `IsTemplateEditor`: Required to save/edit templates (staff or `is_template_editor` flag)
- `CanSendMail`: Required to send emails (staff or `can_send_mail` flag)
- `CanPreviewRealData`: Required to preview with real data (staff or `can_preview_real` flag)

## Security Features

- **HTML Sanitization**: All HTML content is sanitized using `bleach`
- **Jinja2 Sandbox**: Templates are rendered in a sandboxed environment
- **Strict Undefined**: Missing template variables raise errors
- **CSS Inlining**: CSS is inlined using `premailer` for email compatibility
- **Permission Checks**: All endpoints enforce proper authorization

## Background Processing

Email sending is handled asynchronously using Celery:

1. API creates EmailSendJob and EmailSendRecipient records
2. Celery task processes recipients in chunks
3. Each recipient is retried up to MAX_ATTEMPTS on failure
4. Job status is updated in real-time

## Testing

Run tests with:

```bash
pytest apps/mailtemplates/tests/
```

## Dependencies

- `jinja2`: Template rendering
- `bleach`: HTML sanitization
- `premailer`: CSS inlining
- `jsonschema`: Data validation
- `celery`: Background task processing
