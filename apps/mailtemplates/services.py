"""Core services for mail template operations.

This module provides services for:
- Loading and saving template files
- HTML sanitization
- Template rendering with Jinja2
- CSS inlining with premailer
- Data validation against JSON schemas
"""

import time
from pathlib import Path
from typing import Any

import bleach
import jsonschema
from django.conf import settings
from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment
from premailer import Premailer

from .constants import TEMPLATE_REGISTRY, TemplateMetadata


class TemplateNotFoundError(Exception):
    """Raised when a template is not found in the registry."""

    pass


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""

    pass


class TemplateValidationError(Exception):
    """Raised when template data validation fails."""

    pass


def get_template_dir() -> Path:
    """Get the mail template directory path from settings."""
    template_dir = getattr(settings, "MAIL_TEMPLATE_DIR", None)
    if not template_dir:
        raise ValueError("MAIL_TEMPLATE_DIR setting is not configured")
    return Path(template_dir)


def get_template_metadata(slug: str) -> TemplateMetadata:
    """Get template metadata by slug.

    Args:
        slug: Template slug identifier

    Returns:
        Template metadata dictionary

    Raises:
        TemplateNotFoundError: If template with the given slug is not found
    """
    for template in TEMPLATE_REGISTRY:
        if template["slug"] == slug:
            return template
    raise TemplateNotFoundError(f"Template with slug '{slug}' not found")





def get_template_file_path(filename: str) -> Path:
    """Get full path to a template file.

    Args:
        filename: Template filename

    Returns:
        Path object for the template file
    """
    template_dir = get_template_dir()
    return template_dir / filename


def load_template_content(filename: str) -> str:
    """Load template HTML content from file.

    Args:
        filename: Template filename

    Returns:
        Template HTML content

    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    file_path = get_template_file_path(filename)
    if not file_path.exists():
        raise FileNotFoundError(f"Template file '{filename}' not found at {file_path}")

    with open(file_path, encoding="utf-8") as f:
        return f.read()


def save_template_content(filename: str, content: str, create_backup: bool = True) -> None:
    """Save template HTML content to file with optional backup.

    Args:
        filename: Template filename
        content: HTML content to save
        create_backup: Whether to create a backup of existing file

    Raises:
        OSError: If file operations fail
    """
    file_path = get_template_file_path(filename)
    template_dir = get_template_dir()

    # Ensure template directory exists
    template_dir.mkdir(parents=True, exist_ok=True)

    # Create backup if file exists
    if create_backup and file_path.exists():
        timestamp = int(time.time())
        backup_path = file_path.with_suffix(f".bak.{timestamp}")
        file_path.rename(backup_path)

    # Write new content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def sanitize_html_for_storage(html: str) -> str:
    """Sanitize HTML content for safe storage.

    Removes dangerous tags and attributes while preserving email-safe HTML.
    Preserves full HTML structure including head, style tags for email templates.

    Args:
        html: Raw HTML content

    Returns:
        Sanitized HTML content
    """
    # Define allowed tags for email templates - comprehensive list for full email support
    allowed_tags = [
        # Document structure
        "html",
        "head",
        "body",
        "title",
        "meta",
        "style",
        "link",
        # Text formatting
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "cite",
        "code",
        "del",
        "div",
        "em",
        "font",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "ins",
        "mark",
        "p",
        "pre",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strike",
        "strong",
        "sub",
        "sup",
        "u",
        # Lists
        "dl",
        "dt",
        "dd",
        "li",
        "ol",
        "ul",
        # Tables
        "table",
        "caption",
        "col",
        "colgroup",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        # Media
        "img",
        # Semantic
        "article",
        "aside",
        "details",
        "figcaption",
        "figure",
        "footer",
        "header",
        "main",
        "nav",
        "section",
        "summary",
        "time",
    ]

    # Define allowed attributes - comprehensive for email styling
    allowed_attributes = {
        "*": ["class", "id", "style", "lang", "dir"],
        "a": ["href", "title", "target", "rel", "name"],
        "img": ["src", "alt", "width", "height", "style", "border", "align"],
        "table": ["border", "cellpadding", "cellspacing", "width", "align", "bgcolor", "style"],
        "td": ["colspan", "rowspan", "align", "valign", "width", "height", "bgcolor", "style"],
        "th": ["colspan", "rowspan", "align", "valign", "width", "height", "bgcolor", "style"],
        "tr": ["align", "valign", "bgcolor", "style"],
        "tbody": ["align", "valign", "style"],
        "thead": ["align", "valign", "style"],
        "tfoot": ["align", "valign", "style"],
        "meta": ["charset", "name", "content", "http-equiv"],
        "link": ["rel", "href", "type"],
        "font": ["color", "face", "size"],
        "div": ["align", "style"],
        "p": ["align", "style"],
        "span": ["style"],
        "h1": ["align", "style"],
        "h2": ["align", "style"],
        "h3": ["align", "style"],
        "h4": ["align", "style"],
        "h5": ["align", "style"],
        "h6": ["align", "style"],
    }

    # Sanitize HTML - remove only script and dangerous event handlers
    cleaned = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=False,  # Don't strip tags, just remove disallowed ones
    )

    return cleaned


def sanitize_html_for_email(html: str) -> str:
    """Sanitize rendered HTML for email sending.

    Preserves all styling and structure while removing dangerous content.

    Args:
        html: Rendered HTML content

    Returns:
        Sanitized HTML safe for email
    """
    # For email, preserve full HTML structure and styling
    # Only remove scripts and dangerous event handlers
    return sanitize_html_for_storage(html)


def render_template_content(
    template_content: str,
    data: dict[str, Any],
    strict: bool = False,
) -> str:
    """Render template content with Jinja2.

    Args:
        template_content: Jinja2 template string
        data: Template variables
        strict: Whether to use StrictUndefined (raises on missing variables)
                Default is False to allow optional variables in conditionals

    Returns:
        Rendered HTML

    Raises:
        TemplateRenderError: If rendering fails
    """
    try:
        # Create sandboxed Jinja2 environment
        # Note: StrictUndefined is disabled by default to allow {% if variable %}
        # conditionals for optional variables
        if strict:
            env = SandboxedEnvironment(undefined=StrictUndefined)
        else:
            env = SandboxedEnvironment()

        template = env.from_string(template_content)

        # Render template
        rendered = template.render(**data)
        return rendered

    except TemplateError as e:
        raise TemplateRenderError(f"Template rendering failed: {str(e)}") from e
    except Exception as e:
        raise TemplateRenderError(f"Unexpected error during rendering: {str(e)}") from e


def inline_css(html: str) -> str:
    """Inline CSS styles for better email client compatibility.

    Args:
        html: HTML content with CSS

    Returns:
        HTML with inlined CSS
    """
    try:
        premailer = Premailer(
            html,
            strip_important=False,
            keep_style_tags=True,
        )
        return premailer.transform()
    except Exception as e:
        # If inlining fails, return original HTML
        # Log the error but don't fail the entire operation
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"CSS inlining failed: {e}. Returning original HTML.")
        return html


def html_to_text(html: str) -> str:
    """Convert HTML to plain text for email text/plain part.

    Args:
        html: HTML content

    Returns:
        Plain text version
    """
    # Simple implementation - strip all HTML tags
    # In production, consider using libraries like html2text for better formatting
    import re

    # Remove script and style tags with content
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    import html as html_module

    text = html_module.unescape(text)
    # Clean up whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = text.strip()
    return text


def validate_template_data(
    data: dict[str, Any],
    template_meta: TemplateMetadata,
) -> None:
    """Validate data against template's variable requirements.

    Args:
        data: Data to validate
        template_meta: Template metadata with variables or schema

    Raises:
        TemplateValidationError: If validation fails
    """
    # If template has JSON schema, use it for validation
    if template_meta.get("variables_schema"):
        try:
            jsonschema.validate(data, template_meta["variables_schema"])
        except jsonschema.ValidationError as e:
            raise TemplateValidationError(f"Data validation failed: {e.message}") from e
    else:
        # Otherwise, check required variables
        variables = template_meta.get("variables", [])
        required_vars = [v["name"] for v in variables if v.get("required", False)]

        missing = [var for var in required_vars if var not in data]
        if missing:
            raise TemplateValidationError(f"Missing required variables: {', '.join(missing)}")


def render_and_prepare_email(
    template_meta: TemplateMetadata,
    data: dict[str, Any],
    validate: bool = True,
) -> dict[str, str]:
    """Complete template rendering pipeline.

    Validates data, loads template, renders, sanitizes, and inlines CSS.

    Args:
        template_meta: Template metadata
        data: Template variables
        validate: Whether to validate data first

    Returns:
        Dictionary with 'html' and 'text' keys

    Raises:
        TemplateValidationError: If data validation fails
        TemplateRenderError: If rendering fails
        FileNotFoundError: If template file not found
    """
    # Validate data
    if validate:
        validate_template_data(data, template_meta)

    # Load template content
    template_content = load_template_content(template_meta["filename"])

    # Render template
    rendered_html = render_template_content(template_content, data)

    # Sanitize rendered output
    sanitized_html = sanitize_html_for_email(rendered_html)

    # Inline CSS
    html_with_inlined_css = inline_css(sanitized_html)

    # Generate plain text version
    plain_text = html_to_text(html_with_inlined_css)

    return {
        "html": html_with_inlined_css,
        "text": plain_text,
    }
