"""Signal handlers for HRM app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.models import Block, Branch, Department, RecruitmentChannel
from libs.code_generation import create_auto_code_signal_handler

from .constants import TEMP_CODE_PREFIX


# Create a generic auto-code signal handler
_auto_code_handler = create_auto_code_signal_handler(TEMP_CODE_PREFIX)


# Register the generic handler for all models that need auto-code generation
@receiver(post_save, sender=Branch)
@receiver(post_save, sender=Block)
@receiver(post_save, sender=Department)
@receiver(post_save, sender=RecruitmentChannel)
def generate_model_code_on_save(sender, instance, created, **kwargs):
    """Auto-generate code for model instances when created.

    This signal handler generates a unique code for newly created instances
    of Branch, Block, Department, and RecruitmentChannel models.
    It uses the instance ID to create a code in the format: {PREFIX}{subcode}

    Args:
        sender: The model class
        instance: The model instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal

    Note:
        We use update_fields parameter and check if code starts with TEMP_
        to prevent infinite loop from the save() call inside the signal.
    """
    _auto_code_handler(sender, instance, created, **kwargs)
