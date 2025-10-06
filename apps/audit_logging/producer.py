# audit_logging/producer.py
import asyncio
import datetime
import json
import logging
import uuid
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest
from rstream import Producer, exceptions

from .registry import AuditLogRegistry

file_audit_logger = logging.getLogger("audit_log_producer")


class AuditStreamProducer:
    """
    Manages sending messages to a RabbitMQ Stream.
    """

    async def _send_message_async(self, message_body: str):
        """
        Connects to RabbitMQ, sends a single message, and disconnects.
        """
        try:
            async with Producer(
                host=settings.RABBITMQ_STREAM_HOST,
                port=settings.RABBITMQ_STREAM_PORT,
                username=settings.RABBITMQ_STREAM_USER,
                password=settings.RABBITMQ_STREAM_PASSWORD,
                vhost=settings.RABBITMQ_STREAM_VHOST,
            ) as producer:
                try:
                    await producer.create_stream(settings.RABBITMQ_STREAM_NAME, exists_ok=True)
                except exceptions.PreconditionFailed:
                    # Stream already exists, which is fine
                    logging.debug("Stream already exists, proceeding.")

                await producer.send(settings.RABBITMQ_STREAM_NAME, message_body.encode("utf-8"))
        except Exception:
            logging.error("Failed to send audit log to RabbitMQ Stream:", exc_info=True)
            raise

    def log_event(self, **kwargs):
        """
        Formats a log event, writes it to a local file, and sends it to
        the RabbitMQ Stream.
        """
        kwargs["log_id"] = str(uuid.uuid4())
        kwargs["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log_json_string = json.dumps(kwargs)

        # Step 1: Write to local file for backup/local auditing.
        file_audit_logger.info(log_json_string)

        # Step 2: Push to RabbitMQ Stream.
        asyncio.run(self._send_message_async(log_json_string))


# Singleton instance of the producer
_audit_producer = AuditStreamProducer()


def _prepare_user_info(log_data: dict, user=None):
    log_data["user_id"] = str(user.pk) if hasattr(user, "pk") else None
    log_data["username"] = getattr(user, "username", None) or getattr(user, "email", None) or str(user)


def _prepare_request_info(log_data: dict, request):
    # Get IP address
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR")
    log_data["ip_address"] = ip_address

    # Get user agent
    log_data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")

    # Get session key if available
    if hasattr(request, "session") and request.session.session_key:
        log_data["session_key"] = request.session.session_key


def _prepare_change_messages(
    log_data: dict,
    action: str,
    original_object=None,
    modified_object=None,
):
    if action == "CHANGE" and original_object and modified_object:
        changes = []
        # Try to detect field changes if both objects are Django models
        if hasattr(original_object, "_meta") and hasattr(modified_object, "_meta"):
            for field in modified_object._meta.fields:
                field_name = field.name
                old_value = getattr(original_object, field_name, None)
                new_value = getattr(modified_object, field_name, None)
                if old_value != new_value:
                    changes.append(f"{field.verbose_name or field_name}: {old_value} -> {new_value}")
        if changes:
            log_data["change_message"] = "; ".join(changes)
        else:
            log_data["change_message"] = "Object modified"
    elif action == "ADD":
        log_data["change_message"] = "Created new object"
    elif action == "DELETE":
        log_data["change_message"] = "Deleted object"
    else:
        log_data["change_message"] = f"Action: {action}"


def log_audit_event(
    action: str,
    original_object=None,
    modified_object=None,
    user=None,
    request: Optional[HttpRequest] = None,
    **extra_kwargs,
):
    """
    Logs an audit event with standardized parameters.

    Args:
        action: The action performed (e.g., ADD, CHANGE, DELETE from LogAction enum)
        original_object: The original object state (nullable, used for CHANGE/DELETE)
        modified_object: The modified object state (nullable, used for ADD/CHANGE)
        user: The user who performed the action (nullable)
        request: The HTTP request object (nullable) for extracting metadata
        **extra_kwargs: Additional custom fields to include in the log

    This is the public interface for logging. It formats the event, writes it
    to a local log file, and pushes it to a RabbitMQ Stream.
    """
    if settings.AUDIT_LOG_DISABLED:
        return

    log_data: dict[str, Any] = {"action": action}

    # Determine which object to use for extracting metadata
    obj = modified_object or original_object

    if obj:
        model_info = AuditLogRegistry.get_model_info(obj.__class__)
        if model_info:
            log_data["object_type"] = model_info["model_name"]
        else:
            # Fallback to model name if not in registry (shouldn't happen for decorated models)
            log_data["object_type"] = obj.__class__.__name__.lower()
            logging.warning(
                f"Model {obj.__class__.__name__} not registered for audit logging. Using fallback object_type."
            )

        log_data["object_id"] = str(obj.pk) if obj.pk else None
        log_data["object_repr"] = str(obj)

    # Add user information
    if user:
        _prepare_user_info(log_data, user)

    # Extract request metadata if available
    if request:
        _prepare_request_info(log_data, request)

    # Create change message describing the changes
    _prepare_change_messages(log_data, action, original_object, modified_object)

    # Add any extra kwargs provided
    log_data.update(extra_kwargs)

    # Final step
    _audit_producer.log_event(**log_data)
