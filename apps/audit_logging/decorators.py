"""
Decorators for automatic audit logging.

This module provides a decorator that can be applied to Django models
to automatically log create, update, and delete actions.
"""

import logging

from django.db.models.signals import post_delete, post_save, pre_save

from .constants import LogAction
from .middleware import get_current_request, get_current_user
from .producer import log_audit_event
from .registry import AuditLogRegistry

logger = logging.getLogger(__name__)

# Global storage for original object states (before save)
_original_objects = {}


def _get_object_key(instance):
    """Generate a unique key for an object instance."""
    return f"{instance.__class__.__name__}_{id(instance)}"


def _handle_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal handler to capture the original object state.

    This is needed to detect changes in update operations.
    """
    # Only store the original if the object already exists in the database
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            key = _get_object_key(instance)
            _original_objects[key] = original
        except sender.DoesNotExist:
            pass


def _handle_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal handler to log create and update actions.
    """
    try:
        request = get_current_request()
        user = get_current_user()

        # Get batch metadata if we're in a batch context
        from .batch import get_batch_metadata

        batch_metadata = get_batch_metadata()
        extra_kwargs = batch_metadata if batch_metadata else {}

        if created:
            # Object was created
            log_audit_event(
                action=LogAction.ADD,
                original_object=None,
                modified_object=instance,
                user=user,
                request=request,
                **extra_kwargs,
            )
        else:
            # Object was updated
            key = _get_object_key(instance)
            original = _original_objects.pop(key, None)

            log_audit_event(
                action=LogAction.CHANGE,
                original_object=original,
                modified_object=instance,
                user=user,
                request=request,
                **extra_kwargs,
            )

        # Increment batch count if in batch context
        if batch_metadata:
            from .batch import _get_batch_context

            batch_context = _get_batch_context()
            if batch_context:
                batch_context.increment_count()

    except Exception as e:
        # Log the error but don't break the save operation
        logger.error(f"Failed to log audit event for {sender.__name__}: {e}", exc_info=True)


def _handle_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal handler to log delete actions.
    """
    try:
        request = get_current_request()
        user = get_current_user()

        # Get batch metadata if we're in a batch context
        from .batch import get_batch_metadata

        batch_metadata = get_batch_metadata()
        extra_kwargs = batch_metadata if batch_metadata else {}

        log_audit_event(
            action=LogAction.DELETE,
            original_object=instance,
            modified_object=None,
            user=user,
            request=request,
            **extra_kwargs,
        )

        # Increment batch count if in batch context
        if batch_metadata:
            from .batch import _get_batch_context

            batch_context = _get_batch_context()
            if batch_context:
                batch_context.increment_count()

    except Exception as e:
        # Log the error but don't break the delete operation
        logger.error(f"Failed to log audit event for {sender.__name__}: {e}", exc_info=True)


def audit_logging_register(model_class):
    """
    Decorator to enable automatic audit logging for a Django model.

    Usage:
        @audit_logging
        class MyModel(models.Model):
            ...

    This decorator registers signal handlers that automatically log
    create, update, and delete actions on the decorated model.

    The logging system captures:
    - The action performed (ADD, CHANGE, DELETE)
    - The object state (before and after for changes)
    - The user who performed the action (from request context)
    - Request metadata (IP address, user agent, session key)
    """

    # Register signal handlers for the decorated model
    pre_save.connect(_handle_pre_save, sender=model_class, weak=False)
    post_save.connect(_handle_post_save, sender=model_class, weak=False)
    post_delete.connect(_handle_post_delete, sender=model_class, weak=False)

    # Register the model in the audit log registry
    AuditLogRegistry.register(model_class)

    return model_class
