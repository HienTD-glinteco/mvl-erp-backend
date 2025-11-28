"""Contract code generation utilities."""

from datetime import date

from django.db import IntegrityError, transaction


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


def generate_contract_number(instance, max_retries: int = 5) -> str:
    """Generate a unique contract number for a contract instance.

    The contract number format is: xx/yyyy/abc - MVL
    where:
    - xx is the sequence number (reset per year, zero-padded to 2 digits)
    - yyyy is the current year
    - abc is the contract type symbol

    Handles concurrency by using retry with transaction.

    Args:
        instance: Contract model instance that needs a contract number generated.
        max_retries: Maximum number of retries for handling concurrency conflicts.

    Returns:
        Generated contract number string (e.g., "01/2025/HDLD - MVL")

    Raises:
        IntegrityError: If unable to generate unique number after max_retries.
    """
    # Import here to avoid circular imports
    from apps.hrm.models import Contract

    current_year = date.today().year
    contract_type_symbol = instance.contract_type.symbol if instance.contract_type else "HD"

    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                # Get the count of contracts for this year
                # Use select_for_update to lock the rows and prevent race conditions
                year_start = date(current_year, 1, 1)
                existing_count = (
                    Contract.objects.select_for_update()
                    .filter(
                        created_at__year=current_year,
                    )
                    .exclude(pk=instance.pk if instance.pk else None)
                    .count()
                )

                # Generate sequence number (1-based, reset per year)
                sequence = existing_count + 1

                # Format the contract number
                if sequence < 100:
                    sequence_str = f"{sequence:02d}"
                else:
                    sequence_str = str(sequence)

                contract_number = f"{sequence_str}/{current_year}/{contract_type_symbol} - MVL"

                return contract_number

        except IntegrityError:
            if attempt == max_retries - 1:
                raise
            continue

    raise IntegrityError("Failed to generate unique contract number after maximum retries")
