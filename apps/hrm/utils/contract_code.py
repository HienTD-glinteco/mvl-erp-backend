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

    # Build suffix and code prefix depending on contract vs appendix
    if is_appendix:
        suffix = f"/{current_year}/PLHD-MVL"
        code_prefix = "PLHD"
    else:
        contract_type_symbol = instance.contract_type.symbol if instance.contract_type else "HD"
        suffix = f"/{current_year}/{contract_type_symbol} - MVL"
        code_prefix = "HD"

    # Find the latest existing contract with contract_number that ends with the suffix
    latest_contract_number = (
        Contract.objects.filter(contract_number__endswith=suffix)
        .exclude(pk=instance.pk)
        .order_by("-contract_number")
        .values_list("contract_number", flat=True)
        .first()
    )

    # Extract sequence from the latest contract_number like "<seq>/<year>/..."
    if latest_contract_number:
        try:
            latest_seq_str = latest_contract_number.split("/")[0].strip()
            latest_seq = int(latest_seq_str)
        except Exception:
            latest_seq = 0
    else:
        latest_seq = 0

    new_seq = latest_seq + 1

    # Format sequence for human-facing contract_number: two digits if <100, else raw number
    contract_number_seq_str = f"{new_seq:0>2}"

    # Build contract_number using the new sequence and suffix (suffix already contains leading slash)
    contract_number = f"{contract_number_seq_str}{suffix}"

    # For system code (unique), continue using the instance id padded to at least 5 digits
    if instance.id < 100000:
        code_seq_str = f"{instance.id:05d}"
    else:
        code_seq_str = str(instance.id)
    code = f"{code_prefix}{code_seq_str}"

    instance.code = code
    instance.contract_number = contract_number
    if force_save:
        instance.save(update_fields=["code", "contract_number"])
