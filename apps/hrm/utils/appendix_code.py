"""Contract appendix code generation utilities."""

from datetime import date

from apps.hrm.models import ContractAppendix


def generate_appendix_codes(instance) -> str:
    """Generate unique codes for a contract appendix instance.

    This function generates two codes:
    1. code (Appendix number): format `x/yyyy/PLHD-MVL`
    2. appendix_code: format `PLHDxxxxx`

    The appendix_code is also assigned to the instance. The signal handler
    will save both fields with update_fields=['code', 'appendix_code'].

    Args:
        instance: ContractAppendix model instance that needs codes generated.

    Returns:
        Generated code string for the `code` field (e.g., "01/2025/PLHD-MVL")
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    current_year = date.today().year

    # Count existing appendices for this year to determine sequence number
    existing_count = (
        ContractAppendix.objects.filter(
            created_at__year=current_year,
        )
        .exclude(pk=instance.pk)
        .count()
    )

    # Generate sequence number (1-based, reset per year)
    sequence = existing_count + 1

    # Format the sequence number for code with 2 digits (or more if needed)
    if sequence < 100:
        code_sequence_str = f"{sequence:02d}"
    else:
        code_sequence_str = str(sequence)

    # Generate code (Appendix number): xx/yyyy/PLHD-MVL
    code = f"{code_sequence_str}/{current_year}/PLHD-MVL"

    # Generate appendix_code: PLHDxxxxx (at least 5 digits)
    if instance.id < 100000:
        appendix_code_sequence_str = f"{instance.id:05d}"
    else:
        appendix_code_sequence_str = str(instance.id)

    appendix_code = f"PLHD{appendix_code_sequence_str}"

    # Assign appendix_code to instance - will be saved by signal handler
    instance.appendix_code = appendix_code

    return code
