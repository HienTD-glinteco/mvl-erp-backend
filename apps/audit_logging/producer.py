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
from .utils import prepare_request_info, prepare_user_info

file_audit_logger = logging.getLogger("audit_logging")


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

        # Step 2: Check if external audit logging is disabled
        if settings.AUDIT_LOG_DISABLED:
            return

        # Step 3: Push to RabbitMQ Stream.
        asyncio.run(self._send_message_async(log_json_string))


# Singleton instance of the producer
_audit_producer = AuditStreamProducer()


def _collect_related_changes(original_object, modified_object):  # noqa: C901
    """
    Collect changes from related objects (ForeignKey, ManyToMany, reverse ForeignKey).

    Args:
        original_object: The original object state
        modified_object: The modified object state

    Returns:
        list: List of dictionaries containing related object changes, each with:
            - object_type: Type of the related object
            - object_id: ID of the related object
            - object_repr: String representation
            - changes: List of field changes
    """
    related_changes = []

    if not (hasattr(original_object, "_meta") and hasattr(modified_object, "_meta")):
        return related_changes

    try:
        # Check ManyToMany field changes
        for field in modified_object._meta.many_to_many:
            field_name = field.name
            try:
                # Get the related managers
                original_manager = getattr(original_object, field_name, None)
                modified_manager = getattr(modified_object, field_name, None)

                if original_manager is None or modified_manager is None:
                    continue

                # Get PKs from both sides
                original_pks = set(original_manager.values_list("pk", flat=True))
                modified_pks = set(modified_manager.values_list("pk", flat=True))

                # Detect additions and removals
                added_pks = modified_pks - original_pks
                removed_pks = original_pks - modified_pks

                if added_pks or removed_pks:
                    change_detail = {
                        "object_type": field.related_model._meta.model_name,
                        "relation_type": "many_to_many",
                        "field_name": field_name,
                        "changes": [],
                    }

                    if added_pks:
                        added_objs = field.related_model.objects.filter(pk__in=added_pks)
                        for obj in added_objs:
                            change_detail["changes"].append(
                                {"action": "added", "object_id": str(obj.pk), "object_repr": str(obj)}
                            )

                    if removed_pks:
                        removed_objs = field.related_model.objects.filter(pk__in=removed_pks)
                        for obj in removed_objs:
                            change_detail["changes"].append(
                                {"action": "removed", "object_id": str(obj.pk), "object_repr": str(obj)}
                            )

                    related_changes.append(change_detail)
            except Exception as e:
                logging.debug(f"Error processing M2M field {field_name}: {e}")
                continue

        # Check reverse foreign key relationships (inline objects)
        for related_object in modified_object._meta.related_objects:
            try:
                accessor_name = related_object.get_accessor_name()

                # Get related querysets
                original_related = getattr(original_object, accessor_name, None)
                modified_related = getattr(modified_object, accessor_name, None)

                if original_related is None or modified_related is None:
                    continue

                # Get all related objects
                original_related_objs = {obj.pk: obj for obj in original_related.all()}
                modified_related_objs = {obj.pk: obj for obj in modified_related.all()}

                original_pks = set(original_related_objs.keys())
                modified_pks = set(modified_related_objs.keys())

                # Detect added, removed, and modified
                added_pks = modified_pks - original_pks
                removed_pks = original_pks - modified_pks
                common_pks = original_pks & modified_pks

                changes_for_relation = []

                # Added objects
                for pk in added_pks:
                    obj = modified_related_objs[pk]
                    changes_for_relation.append({"action": "added", "object_id": str(pk), "object_repr": str(obj)})

                # Removed objects
                for pk in removed_pks:
                    obj = original_related_objs[pk]
                    changes_for_relation.append({"action": "removed", "object_id": str(pk), "object_repr": str(obj)})

                # Modified objects
                for pk in common_pks:
                    original_rel_obj = original_related_objs[pk]
                    modified_rel_obj = modified_related_objs[pk]

                    # Check for field changes in related object
                    field_changes = []
                    for field in modified_rel_obj._meta.fields:
                        field_name = field.name
                        old_value = getattr(original_rel_obj, field_name, None)
                        new_value = getattr(modified_rel_obj, field_name, None)
                        if old_value != new_value:
                            field_changes.append(
                                {
                                    "field": field.verbose_name or field_name,
                                    "old_value": str(old_value) if old_value is not None else None,
                                    "new_value": str(new_value) if new_value is not None else None,
                                }
                            )

                    if field_changes:
                        changes_for_relation.append(
                            {
                                "action": "modified",
                                "object_id": str(pk),
                                "object_repr": str(modified_rel_obj),
                                "field_changes": field_changes,
                            }
                        )

                if changes_for_relation:
                    related_changes.append(
                        {
                            "object_type": related_object.related_model._meta.model_name,
                            "relation_type": "reverse_foreign_key",
                            "field_name": accessor_name,
                            "changes": changes_for_relation,
                        }
                    )
            except Exception as e:
                logging.debug(f"Error processing reverse FK {accessor_name}: {e}")
                continue

    except Exception as e:
        logging.warning(f"Error collecting related changes: {e}")

    return related_changes


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

        # Collect related object changes
        related_changes = _collect_related_changes(original_object, modified_object)
        if related_changes:
            log_data["related_changes"] = related_changes
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
        prepare_user_info(log_data, user)

    # Extract request metadata if available
    if request:
        prepare_request_info(log_data, request)

    # Create change message describing the changes
    _prepare_change_messages(log_data, action, original_object, modified_object)

    # Add any extra kwargs provided
    log_data.update(extra_kwargs)

    # Final step
    _audit_producer.log_event(**log_data)
