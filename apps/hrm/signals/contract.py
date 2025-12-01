from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.constants import TEMP_CODE_PREFIX
from apps.hrm.models import Contract
from apps.hrm.utils.contract_code import generate_contract_code


@receiver(post_save, sender=Contract)
def generate_contract_code_signal(sender, instance, created, **kwargs):
    """Auto-generate code and contract number for Contract instances."""
    if created and hasattr(instance, "code") and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        new_code = generate_contract_code(instance)
        instance.code = new_code

        # Also set contract_number if not set
        if not instance.contract_number:
            instance.contract_number = new_code

        # Save both fields
        instance.save(update_fields=["code", "contract_number"])
