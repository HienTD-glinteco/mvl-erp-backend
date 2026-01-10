"""
Signals for Role Data Scope cache invalidation.

These signals ensure cache consistency when:
- Role scope assignments change (RoleBranchScope, RoleBlockScope, RoleDepartmentScope)
- User's role changes
"""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import RoleBlockScope, RoleBranchScope, RoleDepartmentScope
from apps.hrm.utils.role_data_scope import invalidate_role_units_cache, invalidate_role_units_cache_for_role


@receiver([post_save, post_delete], sender=RoleBranchScope)
@receiver([post_save, post_delete], sender=RoleBlockScope)
@receiver([post_save, post_delete], sender=RoleDepartmentScope)
def invalidate_cache_on_scope_change(sender, instance, **kwargs):
    """Invalidate cache when role scope assignments change"""
    invalidate_role_units_cache_for_role(instance.role_id)


@receiver(pre_save, sender="core.User")
def invalidate_cache_on_user_role_change(sender, instance, **kwargs):
    """Invalidate cache when user's role is changed"""
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.role_id != instance.role_id:
                invalidate_role_units_cache(instance.pk)
        except sender.DoesNotExist:
            pass
