"""
Utility functions for exporting documents to PDF and DOCX formats.

This module provides functions to convert HTML templates to PDF or DOCX files.
The functions return file information without uploading to S3 or creating FileModel instances.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict

from django.template.loader import render_to_string
from django.utils.text import slugify

logger = logging.getLogger(__name__)


def convert_html_to_pdf(template_name: str, context: dict, filename: str) -> Dict[str, Any]:
    """
    Convert HTML template to PDF file.

    Args:
        template_name: Path to the HTML template file
        context: Context dictionary for rendering the template
        filename: Name for the output PDF file (without extension)

    Returns:
        dict: Dictionary with file information:
            - file_path (str): Path to the generated PDF file
            - file_name (str): Name of the file with extension
            - size (int): File size in bytes

    Raises:
        Exception: If PDF generation fails
    """
    from weasyprint import HTML

    try:
        # Render HTML template
        html_content = render_to_string(template_name, context)

        # Create temporary file for PDF
        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = Path(tmp_file.name)
        tmp_file.close()

        # Generate PDF from HTML
        HTML(string=html_content).write_pdf(tmp_path)

        # Prepare file information
        safe_filename = f"{slugify(filename)}.pdf"
        file_size = tmp_path.stat().st_size

        logger.info(f"Successfully created PDF: {safe_filename}")

        return {
            "file_path": str(tmp_path),
            "file_name": safe_filename,
            "size": file_size,
        }

    except Exception as e:
        logger.error(f"Failed to convert HTML to PDF: {str(e)}")
        raise


def convert_html_to_docx(template_name: str, context: dict, filename: str) -> Dict[str, Any]:
    """
    Convert HTML template to DOCX file.

    Args:
        template_name: Path to the HTML template file
        context: Context dictionary for rendering the template
        filename: Name for the output DOCX file (without extension)

    Returns:
        dict: Dictionary with file information:
            - file_path (str): Path to the generated DOCX file
            - file_name (str): Name of the file with extension
            - size (int): File size in bytes

    Raises:
        Exception: If DOCX generation fails
    """
    import pypandoc

    html_path = None
    docx_path = None

    try:
        # Render HTML template
        html_content = render_to_string(template_name, context)

        # Create temporary file for HTML
        html_tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        html_path = Path(html_tmp.name)
        html_tmp.write(html_content)
        html_tmp.close()

        # Create temporary file for DOCX
        docx_tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        docx_path = Path(docx_tmp.name)
        docx_tmp.close()

        # Convert HTML to DOCX using pypandoc
        pypandoc.convert_file(
            str(html_path),
            "docx",
            outputfile=str(docx_path),
            extra_args=["--standalone"],
        )

        # Prepare file information
        safe_filename = f"{slugify(filename)}.docx"
        file_size = docx_path.stat().st_size

        # Clean up HTML temporary file
        html_path.unlink(missing_ok=True)

        logger.info(f"Successfully created DOCX: {safe_filename}")

        return {
            "file_path": str(docx_path),
            "file_name": safe_filename,
            "size": file_size,
        }

    except Exception as e:
        # Clean up temporary files on error
        if html_path and html_path.exists():
            html_path.unlink(missing_ok=True)
        if docx_path and docx_path.exists():
            docx_path.unlink(missing_ok=True)

        logger.error(f"Failed to convert HTML to DOCX: {str(e)}")
        raise
