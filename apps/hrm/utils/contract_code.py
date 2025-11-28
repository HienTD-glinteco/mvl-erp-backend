"""Contract code generation utilities."""

from datetime import date

from apps.hrm.models import Contract


def generate_contract_code(instance) -> str:
    """Generate a unique code for a contract instance.

    The code format is: xx/yyyy/abc - MVL
    where:
    - xx is the sequence number (reset per year, zero-padded to 2 digits)
    - yyyy is the current year
    - abc is the contract type symbol

    Example: 01/2025/HDLD - MVL, 02/2025/HDTV - MVL, etc.

    Args:
        instance: Contract model instance that needs a code generated.

    Returns:
        Generated code string (e.g., "01/2025/HDLD - MVL")
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    current_year = date.today().year

    # Get the contract type symbol
    contract_type_symbol = instance.contract_type.symbol if instance.contract_type else "HD"

    # Count existing contracts for this year to determine sequence number
    # Use the instance's created_at year if available, otherwise current year
    existing_count = (
        Contract.objects.filter(
            created_at__year=current_year,
        )
        .exclude(pk=instance.pk)
        .count()
    )

    # Generate sequence number (1-based, reset per year)
    sequence = existing_count + 1

    # Format the sequence number with 2 digits (or more if needed)
    if sequence < 100:
        sequence_str = f"{sequence:02d}"
    else:
        sequence_str = str(sequence)

    return f"{sequence_str}/{current_year}/{contract_type_symbol} - MVL"
