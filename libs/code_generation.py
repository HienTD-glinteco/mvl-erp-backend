"""Helper functions for generating model codes."""

from django.db.models.signals import post_save


def generate_model_code(instance) -> str:
    """Generate a code for a model instance based on its ID and class prefix.

    The code format is: {PREFIX}{subcode}
    where subcode is the instance ID zero-padded to at least 3 digits.

    Args:
        instance: Model instance that has a CODE_PREFIX class attribute.
                  The instance must have an id attribute.

    Returns:
        Generated code string (e.g., "BL001", "BL012", "BL444", "BL5555")

    Example:
        class Block(models.Model):
            CODE_PREFIX = "BL"
            ...

        block = Block(id=1)
        code = generate_model_code(block)  # Returns "BL000000001"
    """
    if not hasattr(instance.__class__, "CODE_PREFIX"):
        raise AttributeError(f"{instance.__class__.__name__} must have a CODE_PREFIX class attribute")

    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    prefix = instance.__class__.CODE_PREFIX
    instance_id = instance.id
    subcode = str(instance_id).zfill(9)

    return f"{prefix}{subcode}"


def create_auto_code_signal_handler(temp_code_prefix: str, custom_generate_code=None):
    """Factory function to create a generic signal handler for auto-code generation.

    This creates a reusable signal handler that can automatically generate codes
    for any model that has a CODE_PREFIX class attribute.

    Args:
        temp_code_prefix: The prefix used to identify temporary codes (e.g., "TEMP_")
        custom_generate_code: Optional custom function to generate codes.
                            If provided, this function will be used instead of generate_model_code.
                            The function should accept an instance and return a string code.

    Returns:
        A signal handler function that can be connected to post_save signal

    Example:
        from django.db.models.signals import post_save
        from django.dispatch import receiver

        # Create generic handler with default code generation
        auto_code_handler = create_auto_code_signal_handler("TEMP_")

        # Create handler with custom code generation
        def custom_code_gen(instance):
            return f"{instance.CODE_PREFIX}{instance.id:05d}"

        custom_handler = create_auto_code_signal_handler("TEMP_", custom_generate_code=custom_code_gen)

        # Register for multiple models
        @receiver(post_save, sender=Branch)
        @receiver(post_save, sender=Block)
        @receiver(post_save, sender=Department)
        def generate_code(sender, instance, created, **kwargs):
            auto_code_handler(sender, instance, created, **kwargs)
    """

    def signal_handler(sender, instance, created, **kwargs):
        """Auto-generate code for model instances when created.

        This signal handler generates a unique code for newly created instances.
        It uses the instance ID to create a code in the format: {PREFIX}{subcode}

        Args:
            sender: The model class
            instance: The model instance being saved
            created: Boolean indicating if this is a new instance
            **kwargs: Additional keyword arguments from the signal

        Note:
            We use update_fields parameter and check if code starts with temp_code_prefix
            to prevent infinite loop from the save() call inside the signal.
        """
        # Only generate code for new instances that have a temporary code
        if created and hasattr(instance, "code") and instance.code and instance.code.startswith(temp_code_prefix):
            if custom_generate_code:
                instance.code = custom_generate_code(instance)
            else:
                instance.code = generate_model_code(instance)
            # Use update_fields to prevent triggering the signal again (avoid infinite loop)
            instance.save(update_fields=["code"])

    return signal_handler


def register_auto_code_signal(*models, temp_code_prefix: str = "TEMP_", custom_generate_code=None):
    """Register auto-code generation signal for multiple models.

    This is a convenience function to register the auto-code generation signal
    for multiple models at once.

    Args:
        *models: Model classes to register the signal for
        temp_code_prefix: The prefix used to identify temporary codes (default: "TEMP_")
        custom_generate_code: Optional custom function to generate codes.
                            If provided, this function will be used instead of generate_model_code.
                            The function should accept an instance and return a string code.

    Example:
        from apps.hrm.models import Branch, Block, Department
        from libs.code_generation import register_auto_code_signal

        # Register with default code generation
        register_auto_code_signal(Branch, Block, Department)

        # Register with custom code generation
        def custom_code_gen(instance):
            return f"{instance.CODE_PREFIX}{instance.id:05d}"

        register_auto_code_signal(Branch, Block, custom_generate_code=custom_code_gen)
    """
    handler = create_auto_code_signal_handler(temp_code_prefix, custom_generate_code=custom_generate_code)

    for model in models:
        post_save.connect(handler, sender=model, weak=False)
