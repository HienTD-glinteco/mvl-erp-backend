"""Contract code generation utilities."""

from datetime import date

from apps.hrm.models import Contract
from apps.hrm.models.contract_type import ContractType


def generate_contract_code(instance) -> str:
    """Generate unique codes for a contract or appendix instance.

    For contracts (category='contract'):
    - code: System ID format HDxxxxx (e.g., HD00001)
    - contract_number: Business ID format xx/yyyy/abc - MVL (e.g., 01/2025/HDLD - MVL)

    For appendices (category='appendix'):
    - code: System ID format PLHDxxxxx (e.g., PLHD00001)
    - contract_number: Business ID format xx/yyyy/PLHD-MVL (e.g., 01/2025/PLHD-MVL)

    The contract_number is also assigned to the instance. The signal handler
    will save both fields with update_fields=['code', 'contract_number'].

    Args:
        instance: Contract model instance that needs codes generated.

    Returns:
        Generated code string for the `code` field
    """
    if not hasattr(instance, "id") or instance.id is None:
        raise ValueError("Instance must have an id to generate code")

    current_year = date.today().year

    # Determine if this is a contract or appendix based on contract_type category
    is_appendix = instance.contract_type and instance.contract_type.category == ContractType.Category.APPENDIX

    if is_appendix:
        # For appendices, generate PLHD-prefixed codes
        # Count existing appendices for this year (appendices are contracts with category='appendix')
        existing_count = (
            Contract.objects.filter(
                created_at__year=current_year,
                contract_type__category=ContractType.Category.APPENDIX,
            )
            .exclude(pk=instance.pk)
            .count()
        )
        sequence = existing_count + 1

        # Format the sequence number for contract_number with 2 digits (or more if needed)
        if sequence < 100:
            contract_number_seq_str = f"{sequence:02d}"
        else:
            contract_number_seq_str = str(sequence)

        # Generate contract_number (Business ID): xx/yyyy/PLHD-MVL
        contract_number = f"{contract_number_seq_str}/{current_year}/PLHD-MVL"

        # Generate code (System ID): PLHDxxxxx (at least 5 digits)
        if instance.id < 100000:
            code_seq_str = f"{instance.id:05d}"
        else:
            code_seq_str = str(instance.id)
        code = f"PLHD{code_seq_str}"
    else:
        # For contracts, generate HD-prefixed codes
        # Get the contract type symbol
        contract_type_symbol = instance.contract_type.symbol if instance.contract_type else "HD"

        # Count existing contracts for this year (contracts are contracts with category='contract')
        existing_count = (
            Contract.objects.filter(
                created_at__year=current_year,
                contract_type__category=ContractType.Category.CONTRACT,
            )
            .exclude(pk=instance.pk)
            .count()
        )
        sequence = existing_count + 1

        # Format the sequence number with 2 digits (or more if needed)
        if sequence < 100:
            contract_number_seq_str = f"{sequence:02d}"
        else:
            contract_number_seq_str = str(sequence)

        # Generate contract_number (Business ID): xx/yyyy/abc - MVL
        contract_number = f"{contract_number_seq_str}/{current_year}/{contract_type_symbol} - MVL"

        # Generate code (System ID): HDxxxxx (at least 5 digits)
        if instance.id < 100000:
            code_seq_str = f"{instance.id:05d}"
        else:
            code_seq_str = str(instance.id)
        code = f"HD{code_seq_str}"

    # Assign contract_number to instance - will be saved by signal handler
    instance.contract_number = contract_number

    return code
