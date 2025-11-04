"""
Decorators for automatic audit logging.

This module provides a decorator that can be applied to Django models
to automatically log create, update, and delete actions.
"""

import logging
from contextvars import ContextVar

from django.db.models.signals import post_delete, post_save, pre_delete, pre_save

from .constants import LogAction
from .middleware import get_current_request, get_current_user
from .producer import log_audit_event
from .registry import AuditLogRegistry

logger = logging.getLogger(__name__)

# Global storage for original object states (before save)
_original_objects = {}

# Context variable to track cascade deletes
_cascade_delete_context: ContextVar[set] = ContextVar("cascade_delete_context", default=None)

# Storage for pre-delete states (for dependent models)
_pre_delete_states = {}


def _get_object_key(instance):
    """Generate a unique key for an object instance."""
    return f"{instance.__class__.__name__}_{id(instance)}"


def _mark_cascade_delete(model_class, pk):
    """Mark an object as being cascade deleted."""
    ctx = _cascade_delete_context.get()
    if ctx is None:
        ctx = set()
        _cascade_delete_context.set(ctx)
    ctx.add((model_class, pk))


def _is_cascade_delete(model_class, pk):
    """Check if an object is being cascade deleted."""
    ctx = _cascade_delete_context.get()
    if ctx is None:
        return False
    return (model_class, pk) in ctx


def _clear_cascade_context():
    """Clear the cascade delete context."""
    _cascade_delete_context.set(None)


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
    
    Handles audit_log_target for dependent models.
    """
    try:
        request = get_current_request()
        user = get_current_user()

        # Get batch metadata if we're in a batch context
        from .batch import get_batch_metadata

        batch_metadata = get_batch_metadata()
        extra_kwargs = batch_metadata if batch_metadata else {}

        # Check if this model has an audit_log_target
        audit_target = AuditLogRegistry.get_audit_log_target(sender)
        
        if audit_target:
            # Log under the target model instead
            # Get the target instance
            target_instance = None
            for field in instance._meta.get_fields():
                if hasattr(field, "related_model") and field.related_model == audit_target:
                    target_instance = getattr(instance, field.name, None)
                    break
            
            if target_instance:
                # Add metadata about the source
                extra_kwargs.update({
                    "source_model": sender._meta.model_name,
                    "source_pk": str(instance.pk),
                    "source_repr": str(instance),
                })
                
                # Log as a change to the target object
                action_desc = "Added" if created else "Modified"
                log_audit_event(
                    action=LogAction.CHANGE,
                    original_object=target_instance,
                    modified_object=target_instance,
                    user=user,
                    request=request,
                    change_message=f"{action_desc} {sender._meta.verbose_name}: {instance}",
                    **extra_kwargs,
                )
        else:
            # Standard save log
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


def _handle_pre_delete(sender, instance, **kwargs):
    """
    Pre-delete signal handler to capture object state before deletion.
    
    This ensures we have the complete object state even if the delete
    is rolled back by a transaction.
    """
    key = _get_object_key(instance)
    _pre_delete_states[key] = {
        "instance": instance,
        "pk": instance.pk,
    }


def _handle_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal handler to log delete actions.
    
    Handles cascade deletes and audit_log_target for dependent models.
    """
    try:
        # Check if this is a cascade delete that should be skipped
        if _is_cascade_delete(sender, instance.pk):
            # Clean up pre-delete state
            key = _get_object_key(instance)
            _pre_delete_states.pop(key, None)
            return

        request = get_current_request()
        user = get_current_user()

        # Get batch metadata if we're in a batch context
        from .batch import get_batch_metadata

        batch_metadata = get_batch_metadata()
        extra_kwargs = batch_metadata if batch_metadata else {}

        # Check if this model has an audit_log_target
        audit_target = AuditLogRegistry.get_audit_log_target(sender)
        
        if audit_target:
            # Log under the target model instead
            # Get the target instance (if it still exists)
            target_instance = None
            for field in instance._meta.get_fields():
                if hasattr(field, "related_model") and field.related_model == audit_target:
                    target_instance = getattr(instance, field.name, None)
                    break
            
            if target_instance:
                # Add metadata about the source
                extra_kwargs.update({
                    "source_model": sender._meta.model_name,
                    "source_pk": str(instance.pk),
                    "source_repr": str(instance),
                })
                
                # Log as a change to the target object
                log_audit_event(
                    action=LogAction.CHANGE,
                    original_object=target_instance,
                    modified_object=target_instance,
                    user=user,
                    request=request,
                    change_message=f"Deleted {sender._meta.verbose_name}: {instance}",
                    **extra_kwargs,
                )
            else:
                # Target was deleted, still log but as a standalone delete
                log_audit_event(
                    action=LogAction.DELETE,
                    original_object=instance,
                    modified_object=None,
                    user=user,
                    request=request,
                    **extra_kwargs,
                )
        else:
            # Standard delete log
            log_audit_event(
                action=LogAction.DELETE,
                original_object=instance,
                modified_object=None,
                user=user,
                request=request,
                **extra_kwargs,
            )
            
            # Mark dependent objects for cascade delete
            # This prevents duplicate logs when deleting the main object
            for related in instance._meta.related_objects:
                try:
                    accessor_name = related.get_accessor_name()
                    related_manager = getattr(instance, accessor_name, None)
                    if related_manager:
                        related_model = related.related_model
                        # Check if related model has audit_log_target pointing back to this model
                        target = AuditLogRegistry.get_audit_log_target(related_model)
                        if target == sender:
                            # Mark these for cascade delete
                            for rel_obj in related_manager.all():
                                _mark_cascade_delete(related_model, rel_obj.pk)
                except Exception as e:
                    logger.debug(f"Error marking cascade delete for {related}: {e}")

        # Increment batch count if in batch context
        if batch_metadata:
            from .batch import _get_batch_context

            batch_context = _get_batch_context()
            if batch_context:
                batch_context.increment_count()

        # Clean up pre-delete state
        key = _get_object_key(instance)
        _pre_delete_states.pop(key, None)
        
        # Clear cascade context after top-level delete completes
        # (This will be a no-op for cascade-deleted children)
        if not _is_cascade_delete(sender, instance.pk):
            from django.db import transaction
            transaction.on_commit(_clear_cascade_context)

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
        
        # For dependent models, specify audit_log_target
        @audit_logging
        class DependentModel(models.Model):
            audit_log_target = 'app_label.ModelName'  # or model class reference
            employee = models.ForeignKey(Employee, ...)
            ...

    This decorator registers signal handlers that automatically log
    create, update, and delete actions on the decorated model.

    The logging system captures:
    - The action performed (ADD, CHANGE, DELETE)
    - The object state (before and after for changes)
    - The user who performed the action (from request context)
    - Request metadata (IP address, user agent, session key)
    
    For dependent models with audit_log_target:
    - Changes are logged under the target model
    - Cascade deletes don't create duplicate logs
    - Source model metadata is included in logs
    """

    # Register signal handlers for the decorated model
    pre_save.connect(_handle_pre_save, sender=model_class, weak=False)
    post_save.connect(_handle_post_save, sender=model_class, weak=False)
    pre_delete.connect(_handle_pre_delete, sender=model_class, weak=False)
    post_delete.connect(_handle_post_delete, sender=model_class, weak=False)

    # Register the model in the audit log registry
    AuditLogRegistry.register(model_class)

    return model_class
