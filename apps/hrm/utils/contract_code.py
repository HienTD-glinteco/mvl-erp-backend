"""Contract code generation utilities."""


def generate_contract_code(instance) -> str:
    """Generate a unique code for a contract instance.

    The code format is: HD{sequence} where sequence is zero-padded to 5 digits.
    Example: HD00001, HD00002, etc.

    Args:
        instance: Contract model instance that needs a code generated.

    Returns:
        Generated code string (e.g., "HD00001")
    """
    prefix = "HD"

    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    instance_id = instance.id

    # Format with 5 digits
    if instance_id < 100000:
        subcode = f"{instance_id:05d}"
    else:
        subcode = str(instance_id)

    return f"{prefix}{subcode}"
