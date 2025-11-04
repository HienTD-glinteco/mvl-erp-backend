"""
Decorators for automatic audit logging.

This module provides a decorator that can be applied to Django models
to automatically log create, update, and delete actions.
"""

import logging
from contextvars import ContextVar

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.utils.translation import gettext as _

from .constants import LogAction
from .middleware import get_current_request, get_current_user
from .producer import log_audit_event
from .registry import AuditLogRegistry

logger = logging.getLogger(__name__)

# Global storage for original object states (before save)
_original_objects = {}

# Context variable to track main objects being deleted
_deleting_main_objects: ContextVar[set] = ContextVar("deleting_main_objects", default=None)

# Storage for pre-delete states (for dependent models)
_pre_delete_states = {}


def _get_object_key(instance):
    """Generate a unique key for an object instance."""
    return f"{instance.__class__.__name__}_{id(instance)}"


def _mark_main_object_deleting(model_class, pk):
    """Mark a main object as being deleted."""
    ctx = _deleting_main_objects.get()
    if ctx is None:
        ctx = set()
        _deleting_main_objects.set(ctx)
    ctx.add((model_class, pk))


def _is_main_object_deleting(model_class, pk):
    """Check if a main object is being deleted."""
    ctx = _deleting_main_objects.get()
    if ctx is None:
        return False
    return (model_class, pk) in ctx


def _clear_delete_context():
    """Clear the delete context."""
    _deleting_main_objects.set(None)


def _get_target_instance(instance, audit_target):
    """
    Get the target instance for a dependent model.
    
    Args:
        instance: The dependent model instance
        audit_target: The target model class
        
    Returns:
        The target instance
        
    Raises:
        ValueError: If target instance cannot be found
    """
    for field in instance._meta.get_fields():
        if hasattr(field, "related_model") and field.related_model == audit_target:
            target_instance = getattr(instance, field.name, None)
            if target_instance is None:
                raise ValueError(
                    f"Target instance not found for {instance.__class__.__name__}.{field.name}"
                )
            return target_instance
    
    raise ValueError(
        f"No foreign key field found pointing to {audit_target.__name__} "
        f"in {instance.__class__.__name__}"
    )


def _log_dependent_save(sender, instance, created, user, request, extra_kwargs):
    """Log save action for a dependent model under its target."""
    audit_target = AuditLogRegistry.get_audit_log_target(sender)
    target_instance = _get_target_instance(instance, audit_target)
    
    extra_kwargs.update({
        "source_model": sender._meta.model_name,
        "source_pk": str(instance.pk),
        "source_repr": str(instance),
    })
    
    action_desc = _("Added") if created else _("Modified")
    log_audit_event(
        action=LogAction.CHANGE,
        original_object=target_instance,
        modified_object=target_instance,
        user=user,
        request=request,
        change_message=f"{action_desc} {sender._meta.verbose_name}: {instance}",
        **extra_kwargs,
    )


def _log_standard_save(sender, instance, created, user, request, extra_kwargs):
    """Log save action for a standard model."""
    if created:
        log_audit_event(
            action=LogAction.ADD,
            original_object=None,
            modified_object=instance,
            user=user,
            request=request,
            **extra_kwargs,
        )
    else:
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


def _log_dependent_delete(sender, instance, user, request, extra_kwargs):
    """Log delete action for a dependent model under its target."""
    audit_target = AuditLogRegistry.get_audit_log_target(sender)
    target_instance = _get_target_instance(instance, audit_target)
    
    extra_kwargs.update({
        "source_model": sender._meta.model_name,
        "source_pk": str(instance.pk),
        "source_repr": str(instance),
    })
    
    log_audit_event(
        action=LogAction.CHANGE,
        original_object=target_instance,
        modified_object=target_instance,
        user=user,
        request=request,
        change_message=f"{_('Deleted')} {sender._meta.verbose_name}: {instance}",
        **extra_kwargs,
    )


def _handle_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal handler to capture the original object state.

    This is needed to detect changes in update operations.
    """
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
    
    Handles AUDIT_LOG_TARGET for dependent models.
    """
    try:
        request = get_current_request()
        user = get_current_user()

        from .batch import get_batch_metadata

        batch_metadata = get_batch_metadata()
        extra_kwargs = batch_metadata if batch_metadata else {}

        audit_target = AuditLogRegistry.get_audit_log_target(sender)
        
        if audit_target:
            _log_dependent_save(sender, instance, created, user, request, extra_kwargs)
        else:
            _log_standard_save(sender, instance, created, user, request, extra_kwargs)

        if batch_metadata:
            from .batch import _get_batch_context

            batch_context = _get_batch_context()
            if batch_context:
                batch_context.increment_count()

    except Exception as e:
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
    
    # If this is a main object (not a dependent), mark it as being deleted
    audit_target = AuditLogRegistry.get_audit_log_target(sender)
    if not audit_target:
        _mark_main_object_deleting(sender, instance.pk)


def _handle_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal handler to log delete actions.
    
    Handles cascade deletes and AUDIT_LOG_TARGET for dependent models.
    """
    try:
        audit_target = AuditLogRegistry.get_audit_log_target(sender)
        
        # Check if this is a dependent whose main object is being deleted
        if audit_target:
            target_instance = _get_target_instance(instance, audit_target)
            # Skip logging if the main object is being deleted
            if _is_main_object_deleting(audit_target, target_instance.pk):
                key = _get_object_key(instance)
                _pre_delete_states.pop(key, None)
                return

        request = get_current_request()
        user = get_current_user()

        from .batch import get_batch_metadata

        batch_metadata = get_batch_metadata()
        extra_kwargs = batch_metadata if batch_metadata else {}

        if audit_target:
            _log_dependent_delete(sender, instance, user, request, extra_kwargs)
        else:
            log_audit_event(
                action=LogAction.DELETE,
                original_object=instance,
                modified_object=None,
                user=user,
                request=request,
                **extra_kwargs,
            )

        if batch_metadata:
            from .batch import _get_batch_context

            batch_context = _get_batch_context()
            if batch_context:
                batch_context.increment_count()

        key = _get_object_key(instance)
        _pre_delete_states.pop(key, None)
        
        # Clear delete context after top-level delete completes
        if not audit_target:
            transaction.on_commit(_clear_delete_context)

    except Exception as e:
        logger.error(f"Failed to log audit event for {sender.__name__}: {e}", exc_info=True)


def audit_logging_register(model_class):
    """
    Decorator to enable automatic audit logging for a Django model.

    Usage:
        @audit_logging_register
        class MyModel(models.Model):
            ...
        
        # For dependent models, specify AUDIT_LOG_TARGET
        @audit_logging_register
        class DependentModel(models.Model):
            AUDIT_LOG_TARGET = 'app_label.ModelName'  # or model class reference
            employee = models.ForeignKey(Employee, ...)
            ...

    This decorator registers signal handlers that automatically log
    create, update, and delete actions on the decorated model.

    The logging system captures:
    - The action performed (ADD, CHANGE, DELETE)
    - The object state (before and after for changes)
    - The user who performed the action (from request context)
    - Request metadata (IP address, user agent, session key)
    
    For dependent models with AUDIT_LOG_TARGET:
    - Changes are logged under the target model
    - Cascade deletes don't create duplicate logs
    - Source model metadata is included in logs
    """
    pre_save.connect(_handle_pre_save, sender=model_class, weak=False)
    post_save.connect(_handle_post_save, sender=model_class, weak=False)
    pre_delete.connect(_handle_pre_delete, sender=model_class, weak=False)
    post_delete.connect(_handle_post_delete, sender=model_class, weak=False)

    AuditLogRegistry.register(model_class)

    return model_class
