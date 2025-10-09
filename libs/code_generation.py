"""Helper functions for generating model codes."""


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
        code = generate_model_code(block)  # Returns "BL001"
    """
    if not hasattr(instance.__class__, "CODE_PREFIX"):
        raise AttributeError(f"{instance.__class__.__name__} must have a CODE_PREFIX class attribute")

    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    prefix = instance.__class__.CODE_PREFIX
    instance_id = instance.id

    # Format with at least 3 digits, but allow more if needed
    if instance_id < 1000:
        subcode = f"{instance_id:03d}"
    else:
        subcode = str(instance_id)

    return f"{prefix}{subcode}"
