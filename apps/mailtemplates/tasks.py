"""Celery tasks for sending bulk emails."""

import importlib
import logging
import time
from typing import Any

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import EmailSendJob, EmailSendRecipient
from .services import get_template_metadata, render_and_prepare_email

logger = logging.getLogger(__name__)


def get_setting(name: str, default: Any) -> Any:
    """Get mail template setting with fallback."""
    return getattr(settings, name, default)


@shared_task(bind=True, max_retries=3)
def send_email_job_task(self, job_id: str) -> dict[str, Any]:
    """Process email send job.

    Args:
        job_id: UUID of the EmailSendJob

    Returns:
        Dictionary with job results
    """
    try:
        job = EmailSendJob.objects.get(id=job_id)
    except EmailSendJob.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return {"error": "Job not found"}

    # Update job status to running
    job.status = EmailSendJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    logger.info(f"Starting email job {job_id} with {job.total} recipients")

    # Get configuration
    chunk_size = get_setting("MAIL_SEND_CHUNK_SIZE", 10)
    sleep_between_chunks = get_setting("MAIL_SEND_SLEEP_BETWEEN_CHUNKS", 1.0)
    max_attempts = get_setting("MAIL_SEND_MAX_ATTEMPTS", 3)

    # Get template metadata
    try:
        template_meta = get_template_metadata(job.template_slug)
    except Exception as e:
        logger.error(f"Failed to load template {job.template_slug}: {e}")
        job.status = EmailSendJob.Status.FAILED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
        return {"error": str(e)}

    # Process recipients in chunks
    pending_recipients = job.recipients.filter(status=EmailSendRecipient.Status.PENDING)
    total_processed = 0

    for i in range(0, pending_recipients.count(), chunk_size):
        chunk = pending_recipients[i : i + chunk_size]

        for recipient in chunk:
            success = send_single_email(
                recipient=recipient,
                job=job,
                template_meta=template_meta,
                max_attempts=max_attempts,
            )

            if success:
                job.sent_count += 1
            else:
                job.failed_count += 1

            total_processed += 1

        # Save progress
        job.save(update_fields=["sent_count", "failed_count"])

        # Sleep between chunks to respect rate limits
        if total_processed < job.total:
            time.sleep(sleep_between_chunks)

    # Mark job as completed
    job.status = EmailSendJob.Status.COMPLETED
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "finished_at"])

    logger.info(
        f"Job {job_id} completed: {job.sent_count} sent, {job.failed_count} failed"
    )

    return {
        "job_id": job_id,
        "sent": job.sent_count,
        "failed": job.failed_count,
    }


def send_single_email(
    recipient: EmailSendRecipient,
    job: EmailSendJob,
    template_meta: dict[str, Any],
    max_attempts: int,
) -> bool:
    """Send email to a single recipient with retry logic.

    Args:
        recipient: EmailSendRecipient instance
        job: EmailSendJob instance
        template_meta: Template metadata
        max_attempts: Maximum number of send attempts

    Returns:
        True if sent successfully, False otherwise
    """
    for attempt in range(1, max_attempts + 1):
        recipient.attempts = attempt
        recipient.save(update_fields=["attempts"])

        try:
            # Render template for this recipient
            result = render_and_prepare_email(
                template_meta,
                recipient.data,
                validate=True,
            )

            # Create email message
            email = EmailMultiAlternatives(
                subject=job.subject,
                body=result["text"],
                from_email=job.sender,
                to=[recipient.email],
            )
            email.attach_alternative(result["html"], "text/html")

            # Send email
            email.send(fail_silently=False)

            # Mark as sent
            recipient.status = EmailSendRecipient.Status.SENT
            recipient.sent_at = timezone.now()
            recipient.last_error = ""
            recipient.save(update_fields=["status", "sent_at", "last_error"])

            logger.info(f"Email sent to {recipient.email} (attempt {attempt})")
            
            # Execute callback if configured
            if job.callback_data:
                execute_callback(job.callback_data, recipient)
            
            return True

        except Exception as e:
            error_msg = str(e)
            recipient.last_error = error_msg
            recipient.save(update_fields=["last_error"])

            logger.warning(
                f"Failed to send email to {recipient.email} (attempt {attempt}/{max_attempts}): {error_msg}"
            )

            # If max attempts reached, mark as failed
            if attempt >= max_attempts:
                recipient.status = EmailSendRecipient.Status.FAILED
                recipient.save(update_fields=["status"])
                logger.error(f"Email to {recipient.email} failed after {max_attempts} attempts")
                return False

            # Wait before retry (exponential backoff)
            if attempt < max_attempts:
                time.sleep(2**attempt)

    return False


def execute_callback(callback_data: dict[str, Any], recipient: EmailSendRecipient) -> None:
    """Execute callback function after successful email send.
    
    Args:
        callback_data: Dictionary containing callback information
        recipient: EmailSendRecipient instance that was successfully sent
    """
    try:
        # Get the object instance
        app_label = callback_data.get("app_label")
        model_name = callback_data.get("model_name")
        object_id = callback_data.get("object_id")
        
        if not all([app_label, model_name, object_id]):
            logger.warning("Callback data missing required fields")
            return
        
        # Get the model and instance
        model = apps.get_model(app_label, model_name)
        instance = model.objects.get(pk=object_id)
        
        # Get the callback function
        callback_fn = None
        if "path" in callback_data:
            # Import from string path like "apps.hrm.callbacks.welcome_email_sent"
            module_path, function_name = callback_data["path"].rsplit(".", 1)
            module = importlib.import_module(module_path)
            callback_fn = getattr(module, function_name)
        elif "module" in callback_data and "function" in callback_data:
            # Import from module and function name
            module = importlib.import_module(callback_data["module"])
            callback_fn = getattr(module, callback_data["function"])
        
        if callback_fn and callable(callback_fn):
            # Call the callback with instance and recipient
            callback_fn(instance, recipient)
            logger.info(f"Executed callback for {instance} after sending to {recipient.email}")
        else:
            logger.warning("Callback function not found or not callable")
            
    except Exception as e:
        # Log error but don't fail the email send
        logger.error(f"Error executing callback: {e}", exc_info=True)
