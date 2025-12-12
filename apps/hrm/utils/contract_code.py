"""Contract code generation utilities."""

from datetime import date

from django.db.utils import IntegrityError

from apps.hrm.models import Contract
from apps.hrm.models.contract_type import ContractType
from libs.retry import retry


@retry(max_attempts=5, delay=0.1, backoff=0, exceptions=(IntegrityError,))
def generate_contract_code(instance, force_save: bool = True):
    """Generate and assign unique `code` and `contract_number` for a Contract.

    This helper computes two identifiers for a `Contract` instance and assigns
    them on the instance. It supports both regular contracts and appendices:

    - Contracts (category == ContractType.Category.CONTRACT):
        - `code`: system identifier in the form `HDxxxxx` (at least 5 digits)
        - `contract_number`: business identifier in the form `xx/YYYY/<symbol> - MVL`

    - Appendices (category == ContractType.Category.APPENDIX):
        - `code`: system identifier in the form `PLHDxxxxx` (at least 5 digits)
        - `contract_number`: business identifier in the form `xx/YYYY/PLHD-MVL`

    Side effects:
    - Sets `instance.code` and `instance.contract_number`.
    - If `force_save` is True (default) the instance is saved with
        `update_fields=["code", "contract_number"]`.

    Notes:
    - The function requires `instance.id` to be set. If `id` is missing a
        `ValueError` is raised.
    - Database collisions (e.g. `IntegrityError`) may occur when saving; the
        function is commonly decorated with a retry helper to tolerate transient
        uniqueness conflicts (see the module-level `@retry` decorator).

    Args:
            instance: `Contract` instance with a non-null `id`.
            force_save: If True, persist the generated fields to the database.

    Raises:
            ValueError: if `instance.id` is None or missing.
            IntegrityError: when database constraints prevent saving (may be
                    retried by the decorator).
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

    instance.code = code
    instance.contract_number = contract_number
    if force_save:
        instance.save(update_fields=["code", "contract_number"])
