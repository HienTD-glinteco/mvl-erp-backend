"""Signal handlers for HRM app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.models import Block, Branch, Department
from libs.code_generation import generate_model_code

from .constants import TEMP_CODE_PREFIX


# TODO: combine all the signal handlers into a single generic one and use multiple decorators
@receiver(post_save, sender=Branch)
def generate_branch_code(sender, instance, created, **kwargs):
    """Auto-generate code for Branch when created.

    This signal handler generates a unique code for newly created Branch instances.
    It uses the instance ID to create a code in the format: {PREFIX}{subcode}

    Args:
        sender: The model class (Branch)
        instance: The Branch instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal

    Note:
        We use update_fields parameter and check if code starts with TEMP_
        to prevent infinite loop from the save() call inside the signal.
    """
    # Only generate code for new instances that have a temporary code
    if created and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_model_code(instance)
        # Use update_fields to prevent triggering the signal again (avoid infinite loop)
        instance.save(update_fields=["code"])


@receiver(post_save, sender=Block)
def generate_block_code(sender, instance, created, **kwargs):
    """Auto-generate code for Block when created.

    This signal handler generates a unique code for newly created Block instances.
    It uses the instance ID to create a code in the format: {PREFIX}{subcode}

    Args:
        sender: The model class (Block)
        instance: The Block instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal

    Note:
        We use update_fields parameter and check if code starts with TEMP_
        to prevent infinite loop from the save() call inside the signal.
    """
    # Only generate code for new instances that have a temporary code
    if created and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_model_code(instance)
        # Use update_fields to prevent triggering the signal again (avoid infinite loop)
        instance.save(update_fields=["code"])


@receiver(post_save, sender=Department)
def generate_department_code(sender, instance, created, **kwargs):
    """Auto-generate code for Department when created.

    This signal handler generates a unique code for newly created Department instances.
    It uses the instance ID to create a code in the format: {PREFIX}{subcode}

    Args:
        sender: The model class (Department)
        instance: The Department instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments from the signal

    Note:
        We use update_fields parameter and check if code starts with TEMP_
        to prevent infinite loop from the save() call inside the signal.
    """
    # Only generate code for new instances that have a temporary code
    if created and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_model_code(instance)
        # Use update_fields to prevent triggering the signal again (avoid infinite loop)
        instance.save(update_fields=["code"])
