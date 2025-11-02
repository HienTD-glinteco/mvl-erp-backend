# Document Export Module

This module provides functionality to export Django model detail views as PDF or DOCX documents.

## Features

- Convert HTML templates to PDF using WeasyPrint
- Convert HTML templates to DOCX using pypandoc
- Support for direct file download or S3 link delivery
- Integration with Django Rest Framework ViewSets via mixin
- Automatic FileModel creation for tracking exported documents

## Installation

The required dependencies are already included in `pyproject.toml`:

```toml
pypandoc = "^1.13"
weasyprint = "^62.3"
```

## Usage

### 1. Create HTML Template

Create an HTML template for your document in `templates/documents/`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ object.code }}</title>
    <style>
        /* Your styles here */
    </style>
</head>
<body>
    <h1>{{ object.title }}</h1>
    <p>{{ object.description }}</p>
</body>
</html>
```

### 2. Add Mixin to ViewSet

Add the `ExportDocumentMixin` to your ViewSet and configure the template:

```python
from libs import BaseModelViewSet, ExportDocumentMixin

class MyViewSet(ExportDocumentMixin, BaseModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
    
    # Document export configuration
    document_template_name = "documents/my_template.html"
```

This automatically adds an `export-document` action to your ViewSet.

### 3. Make API Requests

Export as PDF (default):
```
GET /api/my-endpoint/{id}/export-document/
GET /api/my-endpoint/{id}/export-document/?type=pdf
```

Export as DOCX:
```
GET /api/my-endpoint/{id}/export-document/?type=docx
```

Get S3 link instead of direct download:
```
GET /api/my-endpoint/{id}/export-document/?delivery=link
```

## API Parameters

- `type`: File format (`pdf` or `docx`). Default: `pdf`
- `delivery`: Delivery mode (`direct` or `link`). Default: `direct`
  - `direct`: Returns file as HTTP attachment (206 status)
  - `link`: Uploads to S3 and returns presigned URL (200 status)

## Response Formats

### Direct Delivery (206 Partial Content)

Returns the file as an HTTP attachment:

```
Content-Type: application/pdf (or application/vnd.openxmlformats-officedocument.wordprocessingml.document)
Content-Disposition: attachment; filename="DOCUMENT_CODE.pdf"
```

### Link Delivery (200 OK)

Returns JSON with S3 information:

```json
{
  "url": "https://s3.amazonaws.com/...",
  "filename": "DOCUMENT_CODE.pdf",
  "expires_in": 3600,
  "storage_backend": "s3",
  "file_id": 123,
  "size_bytes": 1024
}
```

## Custom Context

Override the `export_detail_document` method to provide custom context:

```python
class MyViewSet(ExportDocumentMixin, BaseModelViewSet):
    document_template_name = "documents/my_template.html"
    
    def export_detail_document(self, request, pk=None):
        instance = self.get_object()
        context = {
            'object': instance,
            'filename': f'{instance.code}_custom_document',
            'extra_data': self.get_extra_data(instance)
        }
        return super().export_detail_document(request, pk, context)
```

## Utility Functions

You can also use the conversion functions directly:

```python
from libs.export_document import convert_html_to_pdf, convert_html_to_docx

# Convert to PDF
result = convert_html_to_pdf('documents/template.html', context)
pdf_content = result['content']
filename = result['filename']
content_type = result['content_type']

# Convert to DOCX
result = convert_html_to_docx('documents/template.html', context)
docx_content = result['content']
```

## Examples

### Job Description Export

```python
# apps/hrm/api/views/job_description.py
from libs import BaseModelViewSet, ExportDocumentMixin

class JobDescriptionViewSet(ExportDocumentMixin, BaseModelViewSet):
    queryset = JobDescription.objects.all()
    serializer_class = JobDescriptionSerializer
    document_template_name = "documents/job_description.html"
```

API Usage:
```bash
# Export as PDF (direct download)
GET /api/hrm/job-descriptions/1/export-document/

# Export as DOCX (S3 link)
GET /api/hrm/job-descriptions/1/export-document/?type=docx&delivery=link
```

## Error Handling

The module handles various error scenarios:

- Invalid file type → 400 Bad Request
- Invalid delivery mode → 400 Bad Request
- Object not found → 404 Not Found
- Conversion failure → 500 Internal Server Error
- S3 upload failure → 500 Internal Server Error
- Missing template → 500 Internal Server Error

## Notes

- When using `delivery=link`, a FileModel instance is created for tracking
- S3 credentials must be configured in settings for link delivery
- PDF conversion uses WeasyPrint (supports CSS for styling)
- DOCX conversion uses pypandoc (requires Pandoc to be installed on the system)
